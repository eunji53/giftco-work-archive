import os
import math
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from collections import defaultdict, Counter
import re

# 설정
SAVE_PATH = "./check_tool_save_data.xlsx"

CATEGORY_COLS = [
    "브랜드", "원산지", "단위", "규격", "특징",
    "상품명", "모델명", "선택사항", "불필요"
]
ALL_OPTIONS = ["(미지정)"] + CATEGORY_COLS

CATEGORY_BG_MAP = {
    "(미지정)": None,
    "브랜드": "#1f77b4",
    "원산지": "#2ca02c",
    "단위": "#9467bd",
    "규격": "#8c564b",
    "특징": "#ff7f0e",
    "상품명": "#d62728",
    "모델명": "#17becf",
    "선택사항": "#e377c2",
    "불필요": "#7f7f7f",
}

# 파일 로드
def load_multiple_files() -> pd.DataFrame:
    paths = filedialog.askopenfilenames(
        title="상품 데이터 파일 선택 (복수 선택 가능)",
        filetypes=[
            ("Excel & CSV files", "*.xlsx *.csv"),
            ("Excel files", "*.xlsx"),
            ("CSV files", "*.csv"),
            ("All files", "*.*")
        ]
    )
    if not paths:
        raise ValueError("파일이 선택되지 않았습니다.")

    dfs = []
    for path in paths:
        if path.endswith(".xlsx"):
            df = pd.read_excel(path, dtype=str)
        else:
            df = pd.read_csv(path, dtype=str)

        df.columns = [c.strip() for c in df.columns]

        # 필수 컬럼
        required = ["상품번호", "실제 상품명", "추출단어"] + CATEGORY_COLS
        for c in required:
            if c not in df.columns:
                raise ValueError(f"[{os.path.basename(path)}] 파일에 '{c}' 컬럼이 없습니다.")

        # 비고는 있을 수도/없을 수도
        if "비고" not in df.columns:
            df["비고"] = ""

        for c in df.columns:
            df[c] = df[c].fillna("").astype(str).str.strip()

        dfs.append(df)

    out = pd.concat(dfs, ignore_index=True)

    if "비고" not in out.columns:
        out["비고"] = ""

    return out

class WordReviewTool(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("추출단어 검수 툴")
        self.geometry("800x1100")

        self.root_bg = self.cget("bg")

        try:
            self.df = load_multiple_files()
        except Exception as e:
            messagebox.showerror("로드 오류", str(e))
            self.destroy()
            return

        # 인덱스(빠른 검색용)
        self.word_to_rows = defaultdict(list)
        for i, w in self.df["추출단어"].items():
            if w:
                self.word_to_rows[w].append(i)
        
        self.all_words = list(self.word_to_rows.keys())
        
        # bigram 인덱스
        self.bigram_index = defaultdict(set)

        for w in self.all_words:
            if len(w) < 2:
                continue
            for i in range(len(w) - 1):
                bg = w[i:i+2]
                self.bigram_index[bg].add(w)
                
        self.active_filter_category = "전체"
        self.page_size = 30
        self.current_page = 1
        self.filtered_products = []

        # 현재 검색 상태
        self.current_word = ""
        self.current_products = []
        self.current_pno_to_rows = {}
        self.pno_match_type = {}
        self.row_state = {}

        self._build_ui()

        # ★
        self.current_regex = None

    # UI
    def _build_ui(self):
        # 검색창
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(top, textvariable=self.search_var, width=35)
        search_entry.pack(side="left", padx=(0, 8))
        search_entry.bind("<Return>", lambda e: self.on_search())

        ttk.Button(top, text="검색", command=self.on_search).pack(side="left")
        
        self.include_search_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="포함단어 검색", variable=self.include_search_var).pack(side="left", padx=(10, 0))
        
        # 필터창
        filter_box = ttk.LabelFrame(self, text="필터")
        filter_box.pack(fill="x", padx=10, pady=(0, 8))

        # 카테고리
        ttk.Label(filter_box, text="카테고리:").grid(row=0, column=0, padx=(10, 6), pady=6, sticky="w")
        self.filter_cat_var = tk.StringVar(value="전체")
        filter_cat_combo = ttk.Combobox(
            filter_box,
            textvariable=self.filter_cat_var,
            values=["전체"] + ALL_OPTIONS,
            state="readonly",
            width=10,
            height=11
        )
        filter_cat_combo.grid(row=0, column=1, pady=6, sticky="w")
        filter_cat_combo.bind("<MouseWheel>", lambda e: "break")

        # 검색유형
        ttk.Label(filter_box, text="검색유형:").grid(row=0, column=2, padx=(16, 6), pady=6, sticky="w")
        self.filter_match_var = tk.StringVar(value="전체")
        filter_match_combo = ttk.Combobox(
            filter_box,
            textvariable=self.filter_match_var,
            values=["전체", "완전일치", "포함단어"],
            state="readonly",
            width=10
        )
        filter_match_combo.grid(row=0, column=3, pady=6, sticky="w")
        filter_match_combo.bind("<MouseWheel>", lambda e: "break")

        ttk.Button(filter_box, text="적용", command=self.on_apply_filter).grid(row=0, column=4, padx=(16, 10), pady=6, sticky="w")

        filter_box.columnconfigure(5, weight=1)

        # 통계창
        self.stats_box = ttk.LabelFrame(self, text="검색 통계")
        self.stats_box.pack(fill="x", padx=10, pady=(0, 8))

        self.stats_summary_frame = ttk.Frame(self.stats_box)
        self.stats_summary_frame.pack(fill="x", padx=10, pady=(6, 2))

        self.stats_summary_line1 = ttk.Label(self.stats_summary_frame, text="검색 후 통계가 표시됩니다.")
        self.stats_summary_line1.pack(anchor="w")
        self.stats_summary_line2 = ttk.Label(self.stats_summary_frame, text="")

        # 카테고리별 표
        self.stats_tree = ttk.Treeview(self.stats_box, columns=("cat", "cnt", "pct"), show="headings", height=4)
        self.stats_tree.heading("cat", text="카테고리")
        self.stats_tree.heading("cnt", text="상품 수")
        self.stats_tree.heading("pct", text="비율(%)")
        self.stats_tree.column("cat", width=120, anchor="center")
        self.stats_tree.column("cnt", width=80, anchor="center")
        self.stats_tree.column("pct", width=80, anchor="center")
        self.stats_tree.pack(fill="x", padx=10, pady=(0, 8))
        
        def _on_mousewheel_tree(event):
            self.stats_tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        self.stats_tree.bind("<Enter>", lambda e: self.stats_tree.bind("<MouseWheel>", _on_mousewheel_tree))
        self.stats_tree.bind("<Leave>", lambda e: self.stats_tree.unbind("<MouseWheel>"))
        
        # 페이지네이션
        pager = ttk.Frame(self)
        pager.pack(fill="x", padx=10, pady=(0, 8))

        self.btn_prev = ttk.Button(pager, text="이전", command=self.on_prev_page, state="disabled")
        self.btn_prev.pack(side="left")

        self.page_label = ttk.Label(pager, text="0 / 0", anchor="center")
        self.page_label.pack(side="left", padx=12)

        self.btn_next = ttk.Button(pager, text="다음", command=self.on_next_page, state="disabled")
        self.btn_next.pack(side="left")

        # 결과창
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=10, pady=6)

        self.canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0, background=self.root_bg)
        self.canvas.pack(side="left", fill="both", expand=True)

        vbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        vbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=vbar.set)

        self.content = tk.Frame(self.canvas, bg=self.root_bg)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        
        def _on_mousewheel_global(event):
            widget = event.widget

            if isinstance(widget, ttk.Combobox):
                return "break"

            x, y = self.canvas.winfo_pointerxy()
            target = self.canvas.winfo_containing(x, y)

            if target and (target == self.canvas or str(target).startswith(str(self.canvas))):
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                return "break"

        def _on_content_configure(_event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        def _on_canvas_configure(event):
            self.canvas.itemconfigure(self.canvas_window, width=event.width)

        self.content.bind("<Configure>", _on_content_configure)
        self.canvas.bind("<Configure>", _on_canvas_configure)
        
        def _on_mousewheel_canvas(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"  # 이벤트 전파 차단

        def _bind_canvas_wheel(_event=None):
            self.canvas.bind("<MouseWheel>", _on_mousewheel_canvas)

        def _unbind_canvas_wheel(_event=None):
            self.canvas.unbind("<MouseWheel>")

        self.canvas.bind("<Enter>", _bind_canvas_wheel)
        self.canvas.bind("<Leave>", _unbind_canvas_wheel)
        self.content.bind("<Enter>", _bind_canvas_wheel)
        self.content.bind("<Leave>", _unbind_canvas_wheel)
        
        self.bind_all("<MouseWheel>", _on_mousewheel_global)

        # 하단부
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=10, pady=8)

        ttk.Button(bottom, text="저장", command=self.on_save).pack(side="right")

        self.info_label = ttk.Label(bottom, text="", foreground="#666")
        self.info_label.pack(side="left")
        
    # 검색
    def on_search(self):
        word = (self.search_var.get() or "").strip()
        if not word:
            messagebox.showwarning("검색", "추출단어를 입력하세요.")
            return
        
        # 정규식 여부 판단 ★
        if "$d" in word:
            pattern = word.replace("$d", r"\d+")
            try:
                self.current_regex = re.compile(pattern)
            except re.error:
                messagebox.showerror("정규식 오류", "잘못된 패턴입니다.")
                self.current_regex = None
                return
        else:
            self.current_regex = None        

        use_include = bool(self.include_search_var.get())

        # 1글자는 완전일치만
        if len(word) <= 1:
            use_include = False

        # if not use_include:
        #     matched_words = [word]
        # else:
        #     matched_words = self._find_words_containing(word)

        # 실제 검색 분기 ★
        if self.current_regex:
            matched_words = [w for w in self.all_words if self.current_regex.search(w)]
        elif use_include:
            matched_words = self._find_words_containing(word)
        else:
            matched_words = [word]

        row_idxs = []
        for w in matched_words:
            row_idxs.extend(self.word_to_rows.get(w, []))

        if not row_idxs:
            messagebox.showinfo("검색 결과", f"'{word}' 추출단어가 없습니다.")
            self._clear_results()
            return

        self.current_word = word

        # 상품번호별 그룹
        pno_to_rows = defaultdict(list)
        for ridx in row_idxs:
            pno = self.df.at[ridx, "상품번호"]
            if pno:
                pno_to_rows[pno].append(ridx)

        self.current_pno_to_rows = dict(pno_to_rows)
        
        # 상품번호별 매칭유형 기록
        self.pno_match_type.clear()
        for pno, ridxs in self.current_pno_to_rows.items():
            # if use_include:
            #     has_exact = any((self.df.at[ridx, "추출단어"] or "").strip() == word for ridx in ridxs)
            #     self.pno_match_type[pno] = "완전일치" if has_exact else "포함단어"
            # else:
            #     self.pno_match_type[pno] = "완전일치"
            
            # 정규식 모드 처리 ★
            if self.current_regex:
                has_exact = any(
                    self.current_regex.fullmatch((self.df.at[ridx, "추출단어"] or "").strip())
                    for ridx in ridxs
                )
                self.pno_match_type[pno] = "완전일치" if has_exact else "포함단어"

            elif use_include:
                has_exact = any(
                    (self.df.at[ridx, "추출단어"] or "").strip() == word
                    for ridx in ridxs
                )
                self.pno_match_type[pno] = "완전일치" if has_exact else "포함단어"

            else:
                self.pno_match_type[pno] = "완전일치"


        # 상품 리스트 생성
        products = []
        for pno, ridxs in self.current_pno_to_rows.items():
            name = self.df.at[ridxs[0], "실제 상품명"]
            products.append({"상품번호": pno, "실제 상품명": name})

        products.sort(key=lambda x: x["상품번호"])

        self.current_products = products
        self.filtered_products = self.current_products[:]
        self.current_page = 1

        # 필터 초기화
        self.active_filter_category = "전체"
        self.filter_cat_var.set("전체")
        self.filter_match_var.set("전체")

        self._render_current_page()

        # 통계
        search_mode = "완전일치 + 포함단어" if use_include else "완전일치"
        stats = self._compute_stats(self.filtered_products)
        self._render_stats(stats, word, search_mode, self.filter_cat_var.get(), self.filter_match_var.get())

        self.info_label.config(text=f"검색어: '{word}' | 결과 상품 수: {len(self.current_products)}")
        
    # 필터 적용
    def on_apply_filter(self):
        if not self.current_products:
            messagebox.showwarning("필터", "먼저 검색을 수행하세요.")
            return

        self.active_filter_category = self.filter_cat_var.get()
        match_filter = self.filter_match_var.get()

        def _pass_filters(prod):
            pno = prod["상품번호"]

            # 카테고리 필터
            if self.active_filter_category != "전체":
                ok = False
                for ridx in self.current_pno_to_rows.get(pno, []):
                    w = (self.df.at[ridx, "추출단어"] or "").strip()
                    if self.current_word in w:
                        if self._get_category_from_row(ridx) == self.active_filter_category:
                            ok = True
                            break
                if not ok:
                    return False

            # 검색유형 필터
            if match_filter in ("완전일치", "포함단어"):
                if self.pno_match_type.get(pno, "완전일치") != match_filter:
                    return False

            return True

        filtered = [p for p in self.current_products if _pass_filters(p)]

        # 통계
        stats = self._compute_stats(filtered)
        search_mode = "완전일치 + 포함단어" if self.include_search_var.get() else "완전일치"
        self._render_stats(stats, self.current_word, search_mode, self.filter_cat_var.get(), self.filter_match_var.get())

        self.filtered_products = filtered
        self.current_page = 1
        self._render_current_page()
        
    # 포함단어 검색
    # 1글자: 완전일치만(여기서는 제외)
    # 2글자: bigram 1개로 후보 조회 후 최종검증
    # 3글자 이상: bigram 교집합 후 최종검증
    def _find_words_containing(self, q: str):
        q = (q or "").strip()
        if len(q) <= 1:
            return []

        bigrams = [q[i:i+2] for i in range(len(q) - 1)]

        sets = []
        for bg in bigrams:
            s = self.bigram_index.get(bg)
            if not s:
                return []
            sets.append(s)

        candidates = set.intersection(*sets) if sets else set()

        return [w for w in candidates if q in w]

    # 결과 초기화
    def _clear_results(self):
        self.current_word = ""
        self.current_products = []
        self.current_pno_to_rows = {}
        self.active_filter_category = "전체"
        self.filter_cat_var.set("전체")

        for w in self.content.winfo_children():
            w.destroy()

        self.stats_summary_line1.config(text="검색 후 통계가 표시됩니다.")
        self.stats_summary_line2.config(text="")
        if self.stats_summary_line2.winfo_ismapped():
            self.stats_summary_line2.pack_forget()

        for item in self.stats_tree.get_children():
            self.stats_tree.delete(item)
        self.info_label.config(text="")

#     # 추후 "카테고리 자동 추천" 기능 대비
#     def _detect_existing_category(self, pno: str, word: str) -> str:
#         ridxs = self.current_pno_to_rows.get(pno, [])
#         for ridx in ridxs:
#             for c in CATEGORY_COLS:
#                 if (self.df.at[ridx, c] or "").strip() == word:
#                     return c
#         return "(미지정)"
    
    # 카테고리 판별
    def _get_category_from_row(self, ridx: int) -> str:
        if ridx in self.row_state:
            return self.row_state[ridx]

        word = (self.df.at[ridx, "추출단어"] or "").strip()
        if not word:
            return "(미지정)"

        # for c in CATEGORY_COLS:
        #     val = (self.df.at[ridx, c] or "").strip()
        #     if val == word:
        #         return c

        # return "(미지정)"

        # 정규식 모드 ★
        print("---- DEBUG ----")
        print("ridx:", ridx)
        if self.current_regex:
            # 추출단어가 현재 정규식과 매칭되면 기존 카테고리를 그대로 반환
            for c in CATEGORY_COLS:
                print(f"{c}:", repr(self.df.at[ridx, c])) # DEBUG
            
                val = (self.df.at[ridx, c] or "").strip()
                if val and self.current_regex.fullmatch(val):  # 비어있지 않으면 기존 값 반환
                    return c
            return "(미지정)"
        else:
            # 일반 검색 모드
            if word != self.current_word:
                return "(미지정)"

            for c in CATEGORY_COLS:
                val = (self.df.at[ridx, c] or "").strip()
                if val == word:
                    return c

        return "(미지정)"
    
    # 통계값 계산
    def _compute_stats(self, products_to_use):
        cat_counter = Counter()
        remark_count = 0
        total_rows = 0

        for prod in products_to_use:
            pno = prod["상품번호"]
            ridxs = self.current_pno_to_rows.get(pno, [])

            for ridx in ridxs:
                word = (self.df.at[ridx, "추출단어"] or "").strip()

                if self.filter_match_var.get() == "완전일치":
                    if word != self.current_word:
                        continue
                elif self.filter_match_var.get() == "포함단어":
                    if self.current_word not in word:
                        continue

                cat = self._get_category_from_row(ridx)
                cat_counter[cat] += 1
                total_rows += 1

                if (self.df.at[ridx, "비고"] or "").strip():
                    remark_count += 1

        unassigned = cat_counter.get("(미지정)", 0)
        unassigned_pct = round((unassigned / total_rows) * 100, 1) if total_rows else 0.0

        if total_rows:
            top_cat, top_cnt = cat_counter.most_common(1)[0]
            top_pct = round((top_cnt / total_rows) * 100, 1)
        else:
            top_cat, top_cnt, top_pct = "(미지정)", 0, 0.0

        used_cat_count = sum(1 for _, cnt in cat_counter.items() if cnt > 0)

        return {
            "total": total_rows,
            "by_category": cat_counter,
            "unassigned_cnt": unassigned,
            "unassigned_pct": unassigned_pct,
            "top_cat": top_cat,
            "top_cnt": top_cnt,
            "top_pct": top_pct,
            "used_cat_count": used_cat_count,
            "remark_cnt": remark_count,
        }

    # 통계값 렌더
    def _render_stats(self, stats: dict, word: str, search_mode: str, filter_cat: str, filter_match: str):
        line1 = f"검색어: '{word}'  |  {search_mode}  |  필터: {filter_cat}/{filter_match}"
        line2 = (
            f"총상품: {stats['total']}  | "
            f"미지정: {stats['unassigned_cnt']}({stats['unassigned_pct']}%)  | "
            f"주 카테고리: {stats['top_cat']}({stats['top_pct']}%)  | "
            f"사용 카테고리 수: {stats['used_cat_count']}  | "
            f"비고 있음: {stats['remark_cnt']}"
        )
        self.stats_summary_line1.config(text=line1)
        self.stats_summary_line2.config(text=line2)

        if not self.stats_summary_line2.winfo_ismapped():
            self.stats_summary_line2.pack(anchor="w", pady=(6, 4))

        for item in self.stats_tree.get_children():
            self.stats_tree.delete(item)

        total = stats["total"] or 1
        items = list(stats["by_category"].items())
        items.sort(key=lambda x: (x[0] != "(미지정)", -x[1], x[0]))

        for cat, cnt in items:
            pct = round((cnt / total) * 100, 1)
            self.stats_tree.insert("", "end", values=(cat, cnt, pct))
    
    # 페이지 갱신
    def _update_pager_ui(self):
        total = len(self.filtered_products)
        if total <= 0:
            self.page_label.config(text="0 / 0")
            self.btn_prev.config(state="disabled")
            self.btn_next.config(state="disabled")
            return

        total_pages = math.ceil(total / self.page_size)
        self.current_page = max(1, min(self.current_page, total_pages))

        self.page_label.config(text=f"{self.current_page} / {total_pages}")

        self.btn_prev.config(state=("normal" if self.current_page > 1 else "disabled"))
        self.btn_next.config(state=("normal" if self.current_page < total_pages else "disabled"))

    # 화면 갱신
    def _render_current_page(self):
        # 결과 영역 비우기
        for w in self.content.winfo_children():
            w.destroy()

        total = len(self.filtered_products)
        if total == 0:
            self._update_pager_ui()
            return

        start = (self.current_page - 1) * self.page_size
        end = start + self.page_size
        page_items = self.filtered_products[start:end]

        for prod in page_items:
            self._render_product_block(prod)

        # 페이지 UI 업데이트 + 스크롤 맨 위로
        self._update_pager_ui()
        self.canvas.yview_moveto(0)

    # 해당 상품 나열
    def _render_product_block(self, prod: dict):
        pno = prod["상품번호"]
        name = prod["실제 상품명"]

        # 비고
        remark = ""
        for ridx in self.current_pno_to_rows.get(pno, []):
            r = (self.df.at[ridx, "비고"] or "").strip()
            if r:
                remark = r
                break

        block = tk.Frame(self.content, bg=self.root_bg, bd=1, relief="solid")
        block.pack(fill="x", pady=6)

        inner = tk.Frame(block, bg=self.root_bg)
        inner.pack(fill="x", padx=10, pady=8)

        # 상품번호 | 상품명 레이블
        header = tk.Label(inner, text=f"{pno}  |  {name}", bg=self.root_bg, font=("맑은 고딕", 11, "bold"), anchor="w")
        header.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))

        # 기존 카테고리 확인
        match_type = self.pno_match_type.get(pno, "완전일치")
        if match_type == "완전일치":
            selected_text = "(미지정)"
            for ridx in self.current_pno_to_rows.get(pno, []):
                w = (self.df.at[ridx, "추출단어"] or "").strip()
                if w == self.current_word:
                    selected_text = self._get_category_from_row(ridx)
                    break
        else:
            selected_text = "(미지정)"
            for ridx in self.current_pno_to_rows.get(pno, []):
                w = (self.df.at[ridx, "추출단어"] or "").strip()
                if self.current_word in w:
                    selected_text = self._get_category_from_row(ridx)
                    break
                    
        cat_var = tk.StringVar(value=selected_text)

        # 카테고리 레이블
        tk.Label(inner, text="카테고리:", bg=self.root_bg, anchor="w").grid(row=1, column=0, sticky="w")

        # 콤보박스 색 강조
        bg = CATEGORY_BG_MAP.get(selected_text)
        if bg is None:
            bg = self.root_bg

        combo_wrap = tk.Frame(inner, bg=bg, padx=3, pady=3)
        combo_wrap.grid(row=1, column=1, sticky="w", padx=(6, 20))

        combo = ttk.Combobox(combo_wrap, textvariable=cat_var, values=ALL_OPTIONS, state="readonly", width=12)
        combo.pack()
        combo.bind("<MouseWheel>", lambda e: "break")

        # 비고 레이블
        tk.Label(inner, text="비고:", bg=self.root_bg, anchor="w").grid(row=1, column=2, sticky="w")

        remark_lbl = tk.Label(inner, text=remark, bg=self.root_bg, anchor="w")
        remark_lbl.grid(row=1, column=3, sticky="w", padx=(6, 0))

        # 카테고리 수정사항 반영
        def _on_combo_change(_event=None):
            v = cat_var.get()

            for ridx in self.current_pno_to_rows.get(pno, []):
                word = (self.df.at[ridx, "추출단어"] or "").strip()
                if self.current_word in word:
                    self.row_state[ridx] = v

            new_bg = CATEGORY_BG_MAP.get(v, self.root_bg)
            combo_wrap.config(bg=new_bg)

        combo.bind("<<ComboboxSelected>>", _on_combo_change)

        inner.columnconfigure(0, minsize=90)
        inner.columnconfigure(1, minsize=170)
        inner.columnconfigure(2, minsize=50)
        inner.columnconfigure(3, weight=1)
        
    # 이전
    def on_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._render_current_page()
    
    # 다음
    def on_next_page(self):
        total_pages = math.ceil(len(self.filtered_products) / self.page_size) if self.filtered_products else 0
        if self.current_page < total_pages:
            self.current_page += 1
            self._render_current_page()

    # 저장
    def on_save(self):
        if not self.current_word or not self.current_products:
            messagebox.showwarning("저장", "먼저 추출단어를 검색한 뒤 저장하세요.")
            return

        word = self.current_word

        # 검색결과 중 추출단어인 행만 처리
        target_ridxs = []
        for pno, ridxs in self.current_pno_to_rows.items():
            for ridx in ridxs:
                if (self.df.at[ridx, "추출단어"] or "").strip() == word:
                    target_ridxs.append(ridx)
        
        target_ridxs = list(set(target_ridxs))

        if not target_ridxs:
            messagebox.showinfo("저장", "저장할 대상 행이 없습니다.")
            return

        # 카테고리 반영
        for ridx in target_ridxs:
            chosen = self._get_category_from_row(ridx)
            for c in CATEGORY_COLS:
                self.df.at[ridx, c] = ""

            if chosen != "(미지정)":
                self.df.at[ridx, chosen] = word

        try:
            self.df.to_excel(SAVE_PATH, index=False)
            messagebox.showinfo("저장 완료", f"저장되었습니다.\n{os.path.abspath(SAVE_PATH)}")
        except Exception as e:
            messagebox.showerror("저장 오류", str(e))

# 실행
if __name__ == "__main__":
    app = WordReviewTool()
    app.mainloop()
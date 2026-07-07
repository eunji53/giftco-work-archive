import os
import math
import copy
import datetime
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from collections import defaultdict, Counter

# 설정
CATEGORY_COLS = [
    "브랜드", "원산지", "단위", "규격", "특징",
    "상품명", "모델명", "선택사항", "불필요"
]

ALL_OPTIONS = ["(미지정)"] + CATEGORY_COLS

CATEGORY_BG_MAP = {
    "(미지정)": "#f0f0f0",
    "브랜드": "#1f77b4",
    "원산지": "#2ca02c",
    "단위": "#9467bd",
    "규격": "#8c564b",
    "특징": "#ff7f0e",
    "상품명": "#d62728",
    "모델명": "#17becf",
    "선택사항": "#e377c2",
    "불필요": "#7f7f7f"
}

HILITE_COLOR = "#C2410C"
HILITE_THICK = 2
DEFAULT_COLOR = "#DDDDDD"
DEFAULT_THICK = 1

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

        required = ["상품번호", "실제 상품명", "추출단어"] + CATEGORY_COLS
        for c in required:
            if c not in df.columns:
                raise ValueError(f"[{os.path.basename(path)}] 파일에 '{c}' 컬럼이 없습니다.")

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
        self.geometry("1300x1000")

        self.root_bg = self.cget("bg")

        try:
            self.df = load_multiple_files()
        except Exception as e:
            messagebox.showerror("로드 오류", str(e))
            self.destroy()
            return

        if "_rid" not in self.df.columns:
            self.df["_rid"] = range(len(self.df))

        self.working_df = self.df.copy(deep=True)
        
        try:
            self._rid_seq = int(self.working_df["_rid"].astype(int).max()) + 1
        except Exception:
            self._rid_seq = len(self.working_df) + 1
        
        self._rebuild_search_indexes()
        
        self.page_size = 20 # 페이지당 상품 수
        self.current_page = 1
        self.active_filter_category = "전체"
        self.current_word = ""
        self.filtered_products = []
        self.current_products = []
        self.detail_items = []
        self.bulk_chk_vars = []
        self.bulk_row_items = []
        self.current_pno_to_rows = {}
        self.current_pno_to_all_rows = {}
        self.pno_match_type = {}
        self.search_df = None
        self.selected_pno = None
        self.selected_detail_pno = None
        self.global_undo_snapshot = None

        self._build_ui()

    # UI
    def _build_ui(self):
        main_frame = tk.Frame(self, bg=self.root_bg)
        main_frame.pack(fill="both", expand=True)

        self.left_panel = tk.Frame(main_frame, bg=self.root_bg)
        self.right_panel = tk.Frame(main_frame, bg=self.root_bg)

        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(10,5), pady=10)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(5,10), pady=10)

        main_frame.columnconfigure(0, weight=1, uniform="half")
        main_frame.columnconfigure(1, weight=1, uniform="half")
        main_frame.rowconfigure(0, weight=1)

        style = ttk.Style()

        style.layout("NoText.TCheckbutton", [
            ('Checkbutton.padding', {
                'sticky': 'nswe',
                'children': [
                    ('Checkbutton.indicator', {'side': 'left', 'sticky': ''})
                ]
            })
        ])

        # 좌측 패널
        # 검색창
        search_line = ttk.Frame(self.left_panel)
        search_line.pack(fill="x", padx=10, pady=(0, 8))

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_line, textvariable=self.search_var, width=35)
        search_entry.pack(side="left", padx=(0, 8))
        search_entry.bind("<Return>", lambda e: self.on_search())

        ttk.Button(search_line, text="검색", command=self.on_search).pack(side="left")
        
        self.include_search_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(search_line, text="포함단어 검색", variable=self.include_search_var).pack(side="left", padx=(10, 0))
        
        # 필터창
        filter_box = ttk.LabelFrame(self.left_panel, text="필터")
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

        # 추출단어 필터
        ttk.Label(filter_box, text="추출단어 필터:").grid(row=1, column=0, padx=(10, 6), pady=6, sticky="w")
        self.filter_word_var = tk.StringVar()
        filter_word_entry = ttk.Entry(filter_box, textvariable=self.filter_word_var, width=30)
        filter_word_entry.grid(row=1, column=1, columnspan=3, pady=6, sticky="we")
        filter_word_entry.bind("<Return>", lambda e: self.on_apply_filter())

        ttk.Button(
            filter_box,
            text="적용",
            command=self.on_apply_filter
        ).grid(row=0, column=4, rowspan=2, padx=(16, 10), pady=6, sticky="ns")

        filter_box.columnconfigure(5, weight=1)

        # 통계창
        self.stats_box = ttk.LabelFrame(self.left_panel, text="검색 통계")
        self.stats_box.pack(fill="x", padx=10, pady=(0, 8))

        self.stats_summary_frame = ttk.Frame(self.stats_box)
        self.stats_summary_frame.pack(fill="x", padx=10, pady=(6, 2))

        self.stats_summary_line1 = ttk.Label(self.stats_summary_frame, text="검색 후 통계가 표시됩니다.")
        self.stats_summary_line1.pack(anchor="w")
        self.stats_summary_line2 = ttk.Label(self.stats_summary_frame, text="")

        # 카테고리별 표
        self.stats_tree = ttk.Treeview(self.stats_box, columns=("cat", "cnt", "pct"), show="headings", height=4)
        self.stats_tree.heading("cat", text="카테고리")
        self.stats_tree.heading("cnt", text="추출단어 수")
        self.stats_tree.heading("pct", text="비율(%)")
        self.stats_tree.column("cat", width=40, anchor="center")
        self.stats_tree.column("cnt", width=40, anchor="center")
        self.stats_tree.column("pct", width=40, anchor="center")
        self.stats_tree.pack(fill="x", padx=10, pady=(0, 8))
        
        def _on_mousewheel_tree(event):
            self.stats_tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        self.stats_tree.bind("<Enter>", lambda e: self.stats_tree.bind("<MouseWheel>", _on_mousewheel_tree))
        self.stats_tree.bind("<Leave>", lambda e: self.stats_tree.unbind("<MouseWheel>"))

        # 일괄적용 & 상세보기 패널
        self.detail_panel = tk.Frame(
            self.left_panel,
            bg=self.root_bg,
            highlightbackground=DEFAULT_COLOR,
            highlightcolor=DEFAULT_COLOR,
            highlightthickness=DEFAULT_THICK
        )
        self.detail_panel.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        self.detail_canvas = tk.Canvas(
            self.detail_panel,
            bg=self.root_bg,
            highlightthickness=0
        )
        self.detail_canvas.grid(row=0, column=0, sticky="nsew")

        self.detail_scrollbar = ttk.Scrollbar(
            self.detail_panel,
            orient="vertical",
            command=self.detail_canvas.yview
        )
        self.detail_scrollbar.grid(row=0, column=1, sticky="ns")

        self.detail_canvas.configure(yscrollcommand=self.detail_scrollbar.set)

        # 일괄적용 & 상세보기 패널 내용 영역
        self.detail_content_frame = tk.Frame(
            self.detail_canvas,
            bg=self.root_bg
        )

        self.canvas_window = self.detail_canvas.create_window(
            (0, 0),
            window=self.detail_content_frame,
            anchor="nw"
        )

        def _on_frame_configure(event):
            self.detail_canvas.configure(scrollregion=self.detail_canvas.bbox("all"))

        self.detail_content_frame.bind("<Configure>", _on_frame_configure)

        def _on_canvas_configure(event):
            self.detail_canvas.itemconfig(self.canvas_window, width=event.width)

        self.detail_canvas.bind("<Configure>", _on_canvas_configure)
        
        def _on_mousewheel_detail(event):
            if isinstance(event.widget, ttk.Combobox):
                return "break"
            self.detail_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        def _bind_detail_wheel(_event=None):
            self.detail_canvas.bind("<MouseWheel>", _on_mousewheel_detail)

        def _unbind_detail_wheel(_event=None):
            self.detail_canvas.unbind("<MouseWheel>")

        self.detail_canvas.bind("<Enter>", _bind_detail_wheel)
        self.detail_canvas.bind("<Leave>", _unbind_detail_wheel)
        self.detail_content_frame.bind("<Enter>", _bind_detail_wheel)
        self.detail_content_frame.bind("<Leave>", _unbind_detail_wheel)

        # 일괄적용 & 상세보기 패널 기능 영역
        self.detail_action_frame = tk.Frame(self.detail_panel, bg=self.root_bg)
        self.detail_action_frame.grid(row=1, column=0, sticky="ew")
        
        self.detail_panel.columnconfigure(0, weight=1)
        self.detail_panel.rowconfigure(0, weight=1)
        self.detail_panel.rowconfigure(1, weight=0)
        
        # 우측 패널
        # 페이지네이션
        pager = ttk.Frame(self.right_panel)
        pager.pack(fill="x", padx=(0, 22), pady=(0, 8))

        self.btn_next = ttk.Button(pager, text="다음", command=self.on_next_page, state="disabled")
        self.btn_next.pack(side="right")
        
        self.page_label = ttk.Label(pager, text="0 / 0", anchor="center")
        self.page_label.pack(side="right", padx=12)

        self.btn_prev = ttk.Button(pager, text="이전", command=self.on_prev_page, state="disabled")
        self.btn_prev.pack(side="right")

        # 결과창
        container = ttk.Frame(self.right_panel)
        container.pack(fill="both", expand=True, padx=10, pady=6)

        self.canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0, background=self.root_bg)
        self.canvas.pack(side="left", fill="both", expand=True)

        vbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        vbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=vbar.set)

        self.content = tk.Frame(self.canvas, bg=self.root_bg)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")

        def _on_content_configure(_event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        def _on_canvas_configure(event):
            self.canvas.itemconfigure(self.canvas_window, width=event.width)

        self.content.bind("<Configure>", _on_content_configure)
        self.canvas.bind("<Configure>", _on_canvas_configure)
        
        def _on_mousewheel_canvas(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        def _bind_canvas_wheel(_event=None):
            self.canvas.bind("<MouseWheel>", _on_mousewheel_canvas)

        def _unbind_canvas_wheel(_event=None):
            self.canvas.unbind("<MouseWheel>")

        self.canvas.bind("<Enter>", _bind_canvas_wheel)
        self.canvas.bind("<Leave>", _unbind_canvas_wheel)
        self.content.bind("<Enter>", _bind_canvas_wheel)
        self.content.bind("<Leave>", _unbind_canvas_wheel)

        def _on_mousewheel_global(event):
            widget = event.widget

            if isinstance(widget, ttk.Combobox):
                return "break"

            try:
                x, y = self.winfo_pointerxy()
                target = self.winfo_containing(x, y)
            except Exception:
                return "break"

            if not target:
                return

            if target == self.detail_canvas or str(target).startswith(str(self.detail_canvas)):
                self.detail_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                return "break"

            if target == self.canvas or str(target).startswith(str(self.canvas)):
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                return "break"
        
        self.bind_all("<MouseWheel>", _on_mousewheel_global)

        # 하단부
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=20, pady=(0, 8))

        bottom.columnconfigure(0, weight=1, uniform="a")
        bottom.columnconfigure(1, weight=1, uniform="a")
        bottom.columnconfigure(2, weight=1, uniform="a")
        bottom.rowconfigure(0, weight=1)

        # 검색 요약
        self.info_label = ttk.Label(bottom, text="", foreground="#666")
        self.info_label.grid(row=0, column=0, sticky="w")

        btn_frame = ttk.Frame(bottom)
        btn_frame.grid(row=0, column=1, sticky="ew")

        btn_frame.columnconfigure(0, weight=1, uniform="b")
        btn_frame.columnconfigure(1, weight=1, uniform="b")

        # 일괄적용 버튼
        bulk_btn = ttk.Button(btn_frame, text="일괄적용", command=self.on_open_bulk_panel)
        bulk_btn.grid(row=0, column=0, sticky="ew", padx=20)

        # 실행취소 버튼
        undo_btn = ttk.Button(btn_frame, text="실행취소", command=self.on_global_undo)
        undo_btn.grid(row=0, column=1, sticky="ew", padx=20)

        # 저장 버튼
        save_btn = ttk.Button(bottom, text="저장", command=self.on_save)
        save_btn.grid(row=0, column=2, sticky="e", padx=(0, 12))

    # 검색
    def on_search(self):        
        word = (self.search_var.get() or "").strip()
        
        if not word:
            messagebox.showwarning("검색", "추출단어를 입력하세요.")
            return

        use_include = bool(self.include_search_var.get())

        if len(word) <= 1:
            use_include = False

        if not use_include:
            matched_words = [word]
        else:
            matched_words = self._find_words_containing(word)

        row_idxs = []
        for w in matched_words:
            row_idxs.extend(self.word_to_rows.get(w, []))

        if not row_idxs:
            messagebox.showinfo("검색 결과", f"'{word}' 추출단어가 없습니다.")
            self._clear_results()
            self._clear_detail_panel()
            return

        self.current_word = word

        matched_rows = row_idxs
        matched_pnos = set(self.working_df.loc[matched_rows, "상품번호"])

        all_rows = self.working_df.index[self.working_df["상품번호"].isin(matched_pnos)].tolist()

        tmp = self.working_df.loc[all_rows].copy()
        tmp["_widx"] = tmp.index
        self.search_df = tmp.reset_index(drop=True)

        pno_to_all_rows = defaultdict(list)
        for sridx, pno in self.search_df["상품번호"].items():
            if pno:
                pno_to_all_rows[pno].append(sridx)
        self.current_pno_to_all_rows = dict(pno_to_all_rows)

        rid_to_sridx = {}
        for sridx, rid in self.search_df["_rid"].items():
            rid_to_sridx[int(rid)] = sridx

        matched_sridxs = []
        for dfidx in matched_rows:
            rid = int(self.working_df.at[dfidx, "_rid"])
            sridx = rid_to_sridx.get(rid)
            if sridx is not None:
                matched_sridxs.append(sridx)

        pno_to_match_rows = defaultdict(list)
        for sridx in matched_sridxs:
            pno = self.search_df.at[sridx, "상품번호"]
            if pno:
                pno_to_match_rows[pno].append(sridx)

        self.current_pno_to_rows = dict(pno_to_match_rows)
        
        # 상품번호별 매칭유형 기록
        self.pno_match_type.clear()
        for pno, ridxs in self.current_pno_to_rows.items():
            if use_include:
                has_exact = any((self.search_df.at[sridx, "추출단어"] or "").strip() == word for sridx in ridxs)
                self.pno_match_type[pno] = "완전일치" if has_exact else "포함단어"
            else:
                self.pno_match_type[pno] = "완전일치"

        # 상품 리스트 생성
        products = []
        for pno, ridxs in self.current_pno_to_rows.items():
            name = self.search_df.at[ridxs[0], "실제 상품명"]
            products.append({"상품번호": pno, "실제 상품명": name})

        products.sort(key=lambda x: x["상품번호"])

        self.current_products = products
        self.filtered_products = self.current_products[:]
        self.current_page = 1

        # 필터 초기화
        self.active_filter_category = "전체"
        self.filter_cat_var.set("전체")
        self.filter_match_var.set("전체")
        self.filter_word_var.set("")

        self._render_current_page()

        self.selected_pno = None
        self.selected_detail_pno = None

        self._update_detail_area(keep_scroll=False)

        # 통계
        search_mode = "완전일치 + 포함단어" if use_include else "완전일치"
        stats = self._compute_stats(self.filtered_products)
        self._render_stats(stats, word, search_mode, self.filter_cat_var.get(), self.filter_match_var.get())

        self.info_label.config(text=f"검색어: '{word}' | 결과 상품 수: {len(self.current_products)}")

    # 포함단어 검색
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

    # 필터 적용
    def on_apply_filter(self):
        if not self.current_products:
            messagebox.showwarning("필터", "먼저 검색을 수행하세요.")
            return

        self.active_filter_category = self.filter_cat_var.get()
        match_filter = self.filter_match_var.get()
        sub_filter_word = (self.filter_word_var.get() or "").strip()

        def _pass_filters(prod):
            pno = prod["상품번호"]
            matched_rows = []

            for sridx in self.current_pno_to_rows.get(pno, []):
                w = (self.search_df.at[sridx, "추출단어"] or "").strip()
                # 검색유형 필터
                if match_filter == "완전일치":
                    if w != self.current_word:
                        continue
                elif match_filter == "포함단어":
                    if self.current_word not in w or w == self.current_word:
                        continue
                # 카테고리 필터
                if self.active_filter_category != "전체":
                    if self._get_category_from_row(sridx) != self.active_filter_category:
                        continue
                matched_rows.append(sridx)

            if not matched_rows:
                return False

            prod["_matched_rows"] = matched_rows
            
            if sub_filter_word:
                has_sub_word = False
                for sridx in self.current_pno_to_all_rows.get(pno, []):
                    if (self.search_df.at[sridx, "추출단어"] or "").strip() == sub_filter_word:
                        has_sub_word = True
                        break
                if not has_sub_word:
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
        self.selected_pno = None
        self.selected_detail_pno = None
        self._update_detail_area(keep_scroll=False)

    # 결과 초기화
    def _clear_results(self):
        self.current_word = ""
        self.current_products = []
        self.current_pno_to_rows = {}
        self.current_pno_to_all_rows = {}
        self.active_filter_category = "전체"
        self.filter_cat_var.set("전체")
        self.filter_match_var.set("전체")

        for w in self.content.winfo_children():
            w.destroy()

        self.stats_summary_line1.config(text="검색 후 통계가 표시됩니다.")
        self.stats_summary_line2.config(text="")
        if self.stats_summary_line2.winfo_ismapped():
            self.stats_summary_line2.pack_forget()

        for item in self.stats_tree.get_children():
            self.stats_tree.delete(item)
        self.info_label.config(text="")

    # 인덱스 재생성
    def _rebuild_search_indexes(self):
        if "추출단어" not in self.working_df.columns:
            self.word_to_rows = defaultdict(list)
            self.all_words = []
            self.bigram_index = defaultdict(set)
            return
        
        self.word_to_rows = defaultdict(list)

        words = self.working_df["추출단어"]
        for row_idx, w in words.items():
            if isinstance(w, str) and w:
                self.word_to_rows[w].append(row_idx)

        self.all_words = list(self.word_to_rows.keys())

        self.bigram_index = defaultdict(set)
        for w in self.all_words:
            bigrams = {w[i:i+2] for i in range(len(w) - 1)}
            for bg in bigrams:
                self.bigram_index[bg].add(w)

    # 상품번호 교체
    def _merge_search_into_working_df(self):
        if self.search_df is None:
            return
        if self.search_df.empty:
            return
        if "상품번호" not in self.search_df.columns:
            return

        pnos = set(self.search_df["상품번호"].dropna().tolist())
        if not pnos:
            return

        base = self.working_df[~self.working_df["상품번호"].isin(pnos)].copy()
        repl = self.search_df.copy(deep=True)

        self.working_df = pd.concat([base, repl], ignore_index=True)

        try:
            self._rid_seq = int(self.working_df["_rid"].astype(int).max()) + 1
        except Exception:
            self._rid_seq = len(self.working_df) + 1

        self._rebuild_search_indexes()

    # 매핑 재구성
    def _rebuild_current_mappings_from_search_df(self):
        if self.search_df is None or self.search_df.empty:
            self.current_pno_to_all_rows = {}
            self.current_pno_to_rows = {}
            return

        # pno -> sridx
        pno_to_all = defaultdict(list)
        for sridx in range(len(self.search_df)):
            pno = (self.search_df.at[sridx, "상품번호"] or "").strip()
            if pno:
                pno_to_all[pno].append(sridx)

        self.current_pno_to_all_rows = dict(pno_to_all)
        word = (self.current_word or "").strip()

        pno_to_match = defaultdict(list)
        for pno, sridxs in self.current_pno_to_all_rows.items():
            for sridx in sridxs:
                w = (self.search_df.at[sridx, "추출단어"] or "").strip()
                if not word:
                    continue
                if self.include_search_var.get():
                    if word in w:
                        pno_to_match[pno].append(sridx)
                else:
                    if w == word:
                        pno_to_match[pno].append(sridx)

        self.current_pno_to_rows = dict(pno_to_match)

    # sridx -> widx
    def _sridx_to_widx(self, sridx: int):
        try:
            return int(self.search_df.at[sridx, "_widx"])
        except Exception:
            return None

    # 전역 고유 rid 생성
    def _next_rid(self) -> int:
        rid = int(self._rid_seq)
        self._rid_seq = rid + 1
        return rid

    # working_df 변경 후 공통 갱신
    def _refresh_after_working_change(self, keep_scroll=True):
        self._rebuild_search_indexes()
        
        if self.search_df is None or self.search_df.empty:
            return

        pnos = set(self.search_df["상품번호"].dropna().astype(str).tolist())
        tmp = self.working_df[self.working_df["상품번호"].isin(pnos)].copy()
        tmp["_widx"] = tmp.index
        self.search_df = tmp.reset_index(drop=True)
        
        self._rebuild_current_mappings_from_search_df()
        self._render_current_page(keep_scroll=keep_scroll)

        if self.selected_detail_pno:
            self._render_detail_panel(self.selected_detail_pno)
        else:
            self._render_bulk_panel(keep_scroll=keep_scroll)

        stats = self._compute_stats(self.filtered_products)
        self._render_stats(stats, self.current_word, self._get_match_mode_text(),
                        self.filter_cat_var.get(), self.filter_match_var.get())

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

    # 일괄 & 상세 패널 갱신
    def _update_detail_area(self, keep_scroll: bool = False):
        if self.selected_detail_pno:
            return
        else:
            self._render_bulk_panel(keep_scroll=keep_scroll)

    # 결과창 패널 재렌더
    def _render_current_page(self, keep_scroll: bool = False):
        self.product_blocks = {}
        
        y0 = self.canvas.yview()[0]

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

        self._update_pager_ui()

        if keep_scroll:
            self.canvas.yview_moveto(y0)
        else:
            self.canvas.yview_moveto(0)

    # 결과창 패널 렌더
    def _render_product_block(self, prod: dict):
        pno = prod["상품번호"]
        name = prod["실제 상품명"]

        remark = ""
        ridxs = prod.get("_matched_rows") or self.current_pno_to_rows.get(pno, [])
        for sridx in ridxs:
            r = (self.search_df.at[sridx, "비고"] or "").strip()
            if r:
                remark = r
                break

        block = tk.Frame(
            self.content,
            bg=self.root_bg,
            highlightbackground=DEFAULT_COLOR,
            highlightcolor=DEFAULT_COLOR,
            highlightthickness=DEFAULT_THICK
        )
        block.pack(fill="x", pady=6)
        
        self.product_blocks[pno] = block
        
        if self.selected_pno == pno:
            self._apply_block_border_selected(block)
        else:
            self._apply_block_border_default(block)

        inner = tk.Frame(block, bg=self.root_bg)
        inner.pack(fill="x", padx=10, pady=8)

        # 대표 추출단어 선택
        matched_tokens = []
        exact_tokens = []

        for sridx in ridxs:
            w = (self.search_df.at[sridx, "추출단어"] or "").strip()
            if not w:
                continue

            if w == self.current_word:
                exact_tokens.append((w, sridx))
            elif self.current_word in w:
                matched_tokens.append((w, sridx))

        target_sridx = None
        matched_token = None

        if exact_tokens:
            matched_token, target_sridx = exact_tokens[0]

        elif matched_tokens:
            matched_token, target_sridx = min(matched_tokens, key=lambda x: len(x[0]))

        selected_text = self._get_category_from_row(target_sridx) if target_sridx is not None else "(미지정)"
        cat_var = tk.StringVar(value=selected_text)
        
        # 상품번호 | 상품명(추출단어 강조) 레이블
        header_font = ("맑은 고딕", 11, "bold")

        name_text = tk.Text(
            inner,
            height=1,
            borderwidth=0,
            highlightthickness=0,
            bg=self.root_bg,
            font=header_font,
            wrap="none",
            pady=3
        )

        display_text = f"{pno}  |  {name}"
        name_text.insert("1.0", display_text)

        # 단순 검색어 문자열 기반 하이라이트
        q = (self.current_word or "").strip()
        if q:
            pos = "1.0"
            while True:
                start = name_text.search(q, pos, tk.END, nocase=True)
                if not start:
                    break

                end = f"{start}+{len(q)}c"
                name_text.tag_add("highlight", start, end)
                pos = end

        # name_text.tag_config("highlight", foreground="#B00020", background="#FFEAEA")
        name_text.tag_config("highlight", foreground="#B00020", background="#FFF5CC")

        name_text.config(state="disabled")
        name_text.grid(row=0, column=0, columnspan=4, sticky="we", pady=(0, 6))

        # 추출단어 레이블
        is_changed = matched_token is None
        token_display = matched_token or "(추출단어 변경됨)"
        token_text = tk.Text(
            inner,
            height=1,
            borderwidth=0,
            highlightthickness=0,
            bg=self.root_bg,
            fg="#d9534f" if is_changed else "black",
            font=("맑은 고딕", 9, "bold"),
            wrap="none"
        )
        token_text.insert("1.0", token_display)
        token_text.config(state="disabled")        
        token_text.grid(row=1, column=0, sticky="w", padx=(10, 0))

        bg = self._get_category_bg(selected_text)
        
        combo_wrap = tk.Frame(inner, bg=bg, padx=3, pady=3)
        combo_wrap.grid(row=1, column=1, sticky="w")

        combo = ttk.Combobox(
            combo_wrap,
            textvariable=cat_var,
            values=ALL_OPTIONS,
            state="readonly",
            width=12
        )
        combo.pack()
        combo.bind("<MouseWheel>", lambda e: "break")

        remark_lbl = tk.Label(
            inner,
            text=remark,
            bg=self.root_bg,
            fg="#666",
            anchor="center"
        )
        remark_lbl.grid(row=1, column=2, sticky="we")
        
        # 상세보기 버튼
        detail_btn = ttk.Button(
            inner,
            text="상세보기",
            width=8,
            command=lambda pno=pno: self._render_detail_panel(pno)
        )
        detail_btn.grid(row=1, column=3, sticky="e", padx=(0,10))

        def _on_combo_change(_event=None):
            self._save_global_undo_snapshot()

            v = cat_var.get()
            if target_sridx is None:
                return

            widx = self._sridx_to_widx(target_sridx)
            if widx is None:
                return

            word = (self.working_df.at[widx, "추출단어"] or "").strip()

            for c in CATEGORY_COLS:
                self.working_df.at[widx, c] = ""
            if v != "(미지정)":
                self.working_df.at[widx, v] = word

            combo_wrap.config(bg=self._get_category_bg(v))

            self._refresh_after_working_change(keep_scroll=True)

        combo.bind("<<ComboboxSelected>>", _on_combo_change)

        inner.columnconfigure(0, weight=3, uniform="a")
        inner.columnconfigure(1, weight=2, uniform="a")
        inner.columnconfigure(2, weight=2, uniform="a")
        inner.columnconfigure(3, weight=1, uniform="a")

    # 일괄 패널 렌더
    def _render_bulk_panel(self, keep_scroll: bool = False):
        y0 = self.detail_canvas.yview()[0]

        for w in self.detail_content_frame.winfo_children():
            w.destroy()
        for w in self.detail_action_frame.winfo_children():
            w.destroy()

        if self.search_df is None or self.search_df.empty or not self.filtered_products:
            return

        # 현재 페이지 slice 계산
        start = (self.current_page - 1) * self.page_size
        end = start + self.page_size
        page_items = self.filtered_products[start:end]

        if not page_items:
            return
        
        # 일괄패널 리스트
        self.bulk_row_items = []
        self.bulk_chk_vars = []

        header = tk.Frame(self.detail_content_frame, bg=self.root_bg)
        header.pack(fill="x", padx=10, pady=(8, 4))

        tk.Label(header, text="", bg=self.root_bg, fg="#666", width=3).grid(row=0, column=0, sticky="w")
        tk.Label(header, text="상품번호", bg=self.root_bg, fg="#666", width=8, anchor="w").grid(row=0, column=1, sticky="w")
        tk.Label(header, text="추출단어", bg=self.root_bg, fg="#666", width=14, anchor="w").grid(row=0, column=2, sticky="w", padx=(10, 0))
        tk.Label(header, text="상품명", bg=self.root_bg, fg="#666", anchor="center").grid(row=0, column=3, sticky="ew")

        header.columnconfigure(3, weight=1)

        tk.Frame(self.detail_content_frame, bg=DEFAULT_COLOR, height=1).pack(fill="x", padx=10, pady=(0, 6))

        for prod in page_items:
            pno = (prod.get("상품번호") or "").strip()
            name = (prod.get("실제 상품명") or "").strip()

            # 대표 추출단어
            matched_token, target_sridx, is_changed = self._pick_representative_token(pno, prod)
            token_display = matched_token or "(추출단어 변경됨)"

            all_sridxs = self.current_pno_to_all_rows.get(pno, [])

            row = tk.Frame(self.detail_content_frame, bg=self.root_bg)
            row.pack(fill="x", padx=10, pady=2)

            # 체크박스
            var = tk.IntVar(value=0)
            self.bulk_chk_vars.append(var)

            chk = ttk.Checkbutton(row, style="NoText.TCheckbutton", variable=var)
            chk.grid(row=0, column=0, padx=(0, 6), sticky="w")

            # 상품번호 레이블
            tk.Label(row, text=pno, bg=self.root_bg, width=8, anchor="w").grid(row=0, column=1, sticky="w")

            # 추출단어 레이블
            tk.Label(
                row,
                text=token_display,
                bg=self.root_bg,
                fg="#d9534f" if is_changed else "black",
                width=14,
                anchor="w",
                font=("맑은 고딕", 9, "bold")
            ).grid(row=0, column=2, sticky="w")

            # 상품명 레이블
            tk.Label(
                row,
                text=name,
                bg=self.root_bg,
                anchor="w"
            ).grid(row=0, column=3, sticky="we")

            row.columnconfigure(3, weight=1)

            # 일괄적용 정보 저장
            self.bulk_row_items.append({
                "pno": pno,
                "name": name,
                "var": var,
                "all_sridxs": all_sridxs,
                "target_sridx": target_sridx
            })

        # 하단 컨트롤 영역
        self.detail_action_frame.columnconfigure(0, weight=0)
        self.detail_action_frame.columnconfigure(1, weight=1)
        self.detail_action_frame.columnconfigure(2, weight=0)

        # 좌측 버튼 영역
        left_btn_frame = tk.Frame(self.detail_action_frame, bg=self.root_bg)
        left_btn_frame.grid(row=0, column=0, sticky="w", padx=10, pady=10)

        ttk.Button(
            left_btn_frame,
            text="전체선택",
            command=self._bulk_select_all
        ).pack(side="left", padx=4)

        ttk.Button(
            left_btn_frame,
            text="전체해제",
            command=self._bulk_clear_all
        ).pack(side="left", padx=4)

        # 우측 카테고리 선택 영역
        right_frame = tk.Frame(self.detail_action_frame, bg=self.root_bg)
        right_frame.grid(row=0, column=2, sticky="e", padx=10, pady=10)

        tk.Label(
            right_frame,
            text="카테고리:",
            bg=self.root_bg
        ).pack(side="left", padx=(0, 6))

        # 현재 값 유지(이미 존재하면 그대로 사용)
        if not hasattr(self, "bulk_category_var"):
            self.bulk_category_var = tk.StringVar(value="(미지정)")

        initial_cat = self.bulk_category_var.get()
        bg = self._get_category_bg(initial_cat)

        combo_wrap = tk.Frame(right_frame, bg=bg, padx=3, pady=3)
        combo_wrap.pack(side="left")

        bulk_combo = ttk.Combobox(
            combo_wrap,
            textvariable=self.bulk_category_var,
            values=ALL_OPTIONS,
            state="readonly",
            width=12
        )
        bulk_combo.pack()

        bulk_combo.bind("<<ComboboxSelected>>", self._on_bulk_category_selected)
        bulk_combo.bind("<MouseWheel>", lambda e: "break")

        if keep_scroll:
            self.detail_canvas.yview_moveto(y0)
        else:
            self.detail_canvas.yview_moveto(0)

    # 통계값 렌더
    def _render_stats(self, stats: dict, word: str, search_mode: str, filter_cat: str, filter_match: str):
        line1 = f"검색어: '{word}'  |  {search_mode}  |  필터: {filter_cat}/{filter_match}"
        line2 = (
            f"추출단어: {stats['total']}  | "
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

    # 전체 선택
    def _bulk_select_all(self):
        for var in self.bulk_chk_vars:
            var.set(1)
    # 전체 해제
    def _bulk_clear_all(self):
        for var in self.bulk_chk_vars:
            var.set(0)

    # 카테고리 일괄 적용
    def _on_bulk_category_selected(self, event=None):
        self._save_global_undo_snapshot()

        chosen_cat = (self.bulk_category_var.get() or "").strip()
        if not chosen_cat:
            return

        selected_rows = [r for r in self.bulk_row_items if int(r["var"].get()) == 1]
        if not selected_rows:
            return

        updated = False

        for r in selected_rows:
            pno = r.get("pno")
            matched_sridxs = self.current_pno_to_rows.get(pno, [])

            for sridx in matched_sridxs:
                widx = self._sridx_to_widx(sridx)
                if widx is None:
                    continue

                word = (self.working_df.at[widx, "추출단어"] or "").strip()

                for c in CATEGORY_COLS:
                    self.working_df.at[widx, c] = ""

                if chosen_cat != "(미지정)":
                    self.working_df.at[widx, chosen_cat] = word

                updated = True

        if updated:
            self._refresh_after_working_change(keep_scroll=True)

    # 일괄 패널 열기
    def on_open_bulk_panel(self):
        if not self.filtered_products:
            messagebox.showwarning("일괄적용", "먼저 검색을 수행하세요.")
            return

        self.selected_pno = None
        self.selected_detail_pno = None

        self._render_bulk_panel(keep_scroll=False)

    # 상세 패널 렌더
    def _render_detail_panel(self, pno: str):
        self.selected_pno = pno
        self.selected_detail_pno = pno
        self.detail_items = []

        self._render_current_page(keep_scroll=True)
        self._clear_detail_panel(clear_selection=False)

        if self.search_df is None or self.search_df.empty:
            return
        if pno not in self.current_pno_to_all_rows:
            return

        # 상품 영역
        sridx0 = self.current_pno_to_all_rows[pno][0]
        name = (self.search_df.at[sridx0, "실제 상품명"] or "").strip()

        detail_header = tk.Text(
            self.detail_content_frame,
            height=1,
            borderwidth=0,
            highlightthickness=0,
            bg=self.root_bg,
            font=("맑은 고딕", 11, "bold"),
            wrap="none",
        )
        detail_header.insert("1.0", f"{pno} | {name}")
        detail_header.config(state="disabled")
        detail_header.grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(10, 10))

        column_header = tk.Frame(self.detail_content_frame, bg=self.root_bg)
        column_header.grid(row=1, column=0, columnspan=4, sticky="w", padx=20, pady=(0, 4))

        tk.Label(
            column_header,
            text="추출단어",
            fg="#666",
            bg=self.root_bg,
            font=("맑은 고딕", 9),
            width=32,
            anchor="center"
        ).grid(row=0, column=1, sticky="w")
        tk.Label(
            column_header,
            text="카테고리",
            fg="#666",
            bg=self.root_bg,
            font=("맑은 고딕", 9),
            width=20,
            anchor="center"
        ).grid(row=0, column=2, padx=(1, 0))
        tk.Label(
            column_header,
            text="비고",
            fg="#666",
            bg=self.root_bg,
            font=("맑은 고딕", 9),
            width=25,
            anchor="center"
        ).grid(row=0, column=3, padx=(1, 0))

        tk.Frame(
            self.detail_content_frame,
            bg=DEFAULT_COLOR,
            height=1
        ).grid(row=2, column=0, columnspan=4, sticky="ew", padx=20, pady=(0, 6))

        row_index = 3
        self.chk_vars = []
        
        for sridx in self.current_pno_to_all_rows[pno]:

            word = (self.search_df.at[sridx, "추출단어"] or "").strip()
            if not word:
                continue

            # 체크박스
            chk_var = tk.IntVar(value=0)
            self.chk_vars.append(chk_var)
            
            chk = ttk.Checkbutton(
                self.detail_content_frame,
                style="NoText.TCheckbutton",
                variable=chk_var,
                command=self._sync_detail_input_from_checks
            )
            chk.grid(row=row_index, column=0, padx=(20, 5), pady=6, sticky="w")

            # 추출단어 라벨
            word_text = tk.Text(
                self.detail_content_frame,
                height=1,
                width=30,
                borderwidth=0,
                highlightthickness=0,
                bg=self.root_bg,
                font=("맑은 고딕", 9, "bold"),
                wrap="none"
            )
            word_text.insert("1.0", word)
            word_text.config(state="disabled")
            word_text.grid(row=row_index, column=1, sticky="w")

            # 카테고리 콤보
            current_cat = self._get_category_from_row(sridx)
            cat_var = tk.StringVar(value=current_cat)

            bg = self._get_category_bg(current_cat)

            combo_wrap = tk.Frame(self.detail_content_frame, bg=bg, padx=3, pady=3)
            combo_wrap.grid(row=row_index, column=2, padx=(10, 0), sticky="w")

            combo = ttk.Combobox(
                combo_wrap,
                textvariable=cat_var,
                values=ALL_OPTIONS,
                state="readonly",
                width=12
            )
            combo.pack()

            rid = int(self.search_df.at[sridx, "_rid"])

            def _on_combo_change(event=None, sridx=sridx, cat_var=cat_var, wrap=combo_wrap):
                self._save_global_undo_snapshot()

                new_cat = cat_var.get()

                widx = self._sridx_to_widx(sridx)
                if widx is None:
                    return

                word = (self.working_df.at[widx, "추출단어"] or "").strip()

                for c in CATEGORY_COLS:
                    self.working_df.at[widx, c] = ""

                if new_cat != "(미지정)":
                    self.working_df.at[widx, new_cat] = word

                wrap.config(bg=self._get_category_bg(new_cat))
                self._refresh_after_working_change(keep_scroll=True)

            combo.bind("<<ComboboxSelected>>", _on_combo_change)
            combo.bind("<MouseWheel>", lambda e: "break")

            # 비고 표시
            remark = (self.search_df.at[sridx, "비고"] or "").strip()
            tk.Label(
                self.detail_content_frame,
                text=remark,
                bg=self.root_bg,
                fg="#666",
                anchor="w"
            ).grid(row=row_index, column=3, sticky="w")

            row_index += 1

            self.detail_items.append({
                "sridx": sridx,
                "rid": rid,
                "word": word,
                "chk_var": chk_var,
                "cat_var": cat_var
            })

        self.detail_content_frame.columnconfigure(0, weight=0)
        self.detail_content_frame.columnconfigure(1, weight=0)
        self.detail_content_frame.columnconfigure(2, weight=1)
        self.detail_content_frame.columnconfigure(3, weight=1)
        
        # 하단 기능 영역
        for widget in self.detail_action_frame.winfo_children():
            widget.destroy()

        self.detail_action_frame.columnconfigure(0, weight=1)

        # 입력창
        input_frame = tk.Frame(self.detail_action_frame, bg=self.root_bg)
        input_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 5))

        input_frame.columnconfigure(0, weight=1)
        input_frame.columnconfigure(1, weight=3)

        self.detail_input_var = tk.StringVar()
        detail_input_entry = ttk.Entry(input_frame, textvariable=self.detail_input_var)
        detail_input_entry.grid(row=0, column=0, sticky="ew")

        # 기능 버튼
        btn_frame = tk.Frame(self.detail_action_frame, bg=self.root_bg)
        btn_frame.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 10))

        self.detail_add_btn = ttk.Button(btn_frame, text="추가", command=self.on_detail_add)
        self.detail_add_btn.grid(row=0, column=0, padx=2)
        self.detail_edit_btn = ttk.Button(btn_frame, text="수정", command=self.on_detail_edit)
        self.detail_edit_btn.grid(row=0, column=1, padx=2)
        self.detail_split_btn = ttk.Button(btn_frame, text="분리", command=self.on_detail_split)
        self.detail_split_btn.grid(row=0, column=2, padx=2)
        self.detail_merge_btn = ttk.Button(btn_frame, text="통합", command=self.on_detail_merge)
        self.detail_merge_btn.grid(row=0, column=3, padx=2)
        self.detail_del_btn = ttk.Button(btn_frame, text="제거", command=self.on_detail_delete)
        self.detail_del_btn.grid(row=0, column=4, padx=2)

        self.detail_canvas.yview_moveto(0)

    # 상세 패널 초기화
    def _clear_detail_panel(self, clear_selection: bool = False):
        for w in self.detail_content_frame.winfo_children():
            w.destroy()
        for w in self.detail_action_frame.winfo_children():
            w.destroy()

        if clear_selection:
            self.selected_pno = None
            self.selected_detail_pno = None
            self._render_current_page(keep_scroll=True)
        
        self._update_detail_area(keep_scroll=True)

    # 상세 패널 새로고침
    def _detail_refresh(self):
        pno = self.selected_detail_pno
        if pno:
            self._render_detail_panel(pno)

    # 상세 패널 입력 반환
    def _detail_input_text(self):
        return (self.detail_input_var.get() or "").strip()

    # 상세 패널 체크 반환
    def _detail_checked_items(self):
        if not self.detail_items:
            return []
        return [it for it in self.detail_items if int(it["chk_var"].get()) == 1]

    # 상세 패널 카테고리 반환
    def _detail_get_selected_cat(self, item) -> str:
        if "cat_var" in item and item["cat_var"] is not None:
            return (item["cat_var"].get() or "").strip() or "(미지정)"
        return "(미지정)"

    # 체크박스 & 입력창 동기화
    def _sync_detail_input_from_checks(self):
        if not self.detail_items:
            return

        words = [it["word"] for it in self.detail_items if int(it["chk_var"].get()) == 1]

        if not words:
            self.detail_input_var.set("")
            return

        self.detail_input_var.set("\\".join(words))

    # 카테고리 세팅
    def _set_row_category_columns(self, sridx: int, word: str, cat: str):
        for c in CATEGORY_COLS:
            self.search_df.at[sridx, c] = ""

        if cat and cat != "(미지정)":
            self.search_df.at[sridx, cat] = word

    # 기능 버튼(추가)
    def on_detail_add(self):
        self._save_global_undo_snapshot()
        raw = self._detail_input_text()
        
        if not raw:
            messagebox.showwarning("추가", "추가할 단어를 입력하세요.")
            return

        pno = self.selected_detail_pno
        new_word = raw.replace("\\", "").strip()

        if not new_word:
            messagebox.showwarning("추가", "유효한 단어가 없습니다.")
            return

        sridxs = self.current_pno_to_all_rows.get(pno, [])
        if not sridxs:
            messagebox.showerror("추가", "현재 상품의 정보를 찾을 수 없습니다.")
            return

        base_sridx = sridxs[0]
        base_widx = self._sridx_to_widx(base_sridx)
        if base_widx is None:
            return

        template = self.working_df.loc[base_widx].copy()

        template["_rid"] = self._next_rid()
        template["추출단어"] = new_word

        for c in CATEGORY_COLS:
            template[c] = ""

        template["비고"] = "추가"

        self.working_df = pd.concat(
            [self.working_df, template.to_frame().T],
            ignore_index=True
        )

        self._refresh_after_working_change(keep_scroll=True)

    # 기능 버튼(수정)
    def on_detail_edit(self):
        self._save_global_undo_snapshot()
        checked = self._detail_checked_items()
        raw = self._detail_input_text()

        if len(checked) != 1:
            messagebox.showwarning("수정", "수정은 1개 단어만 체크해야 합니다.")
            return
        if not raw:
            messagebox.showwarning("수정", "수정할 단어를 입력하세요.")
            return

        it = checked[0]
        sridx = it["sridx"]
        
        new_word = raw.replace("\\", "").strip()

        if not new_word:
            messagebox.showwarning("수정", "유효한 단어가 없습니다.")
            return

        widx = self._sridx_to_widx(sridx)
        if widx is None:
            return

        self.working_df.at[widx, "추출단어"] = new_word

        for c in CATEGORY_COLS:
            self.working_df.at[widx, c] = ""

        cat = self._detail_get_selected_cat(it)
        if cat != "(미지정)":
            self.working_df.at[widx, cat] = new_word

        self.working_df.at[widx, "비고"] = "수정"

        self._refresh_after_working_change(keep_scroll=True)

    # 기능 버튼(분리)
    def on_detail_split(self):
        self._save_global_undo_snapshot()
        checked = self._detail_checked_items()
        raw = self._detail_input_text()

        if len(checked) != 1:
            messagebox.showwarning("분리", "분리는 1개 단어만 체크해야 합니다.")
            return
        if "\\" not in raw:
            messagebox.showwarning("분리", "분리는 '\\' 구분자가 필요합니다. 예) 사이드\\포켓")
            return

        toks = [t.strip() for t in raw.split("\\") if t.strip()]
        if not toks:
            messagebox.showwarning("분리", "분리할 단어를 입력하세요.")
            return

        it = checked[0]
        target_sridx = it["sridx"]

        target_widx = self._sridx_to_widx(target_sridx)
        if target_widx is None:
            return

        template = self.working_df.loc[target_widx].copy()

        self.working_df.drop(index=[target_widx], inplace=True)
        self.working_df.reset_index(drop=True, inplace=True)

        new_rows = []
        for tok in toks:
            r = template.copy()
            r["_rid"] = self._next_rid()
            r["추출단어"] = tok
            for c in CATEGORY_COLS:
                r[c] = ""
            r["비고"] = "분리"
            new_rows.append(r.to_frame().T)

        self.working_df = pd.concat(
            [self.working_df] + new_rows,
            ignore_index=True
        )

        self._refresh_after_working_change(keep_scroll=True)

    # 기능 버튼(통합)
    def on_detail_merge(self):
        self._save_global_undo_snapshot()
        checked = self._detail_checked_items()
        raw = self._detail_input_text()

        if len(checked) < 2:
            messagebox.showwarning("통합", "통합은 2개 이상 단어를 체크해야 합니다.")
            return
        if not raw:
            messagebox.showwarning("통합", "통합할 단어를 입력하세요.")
            return

        merge_word = raw.replace("\\", "").strip()

        if not merge_word:
            messagebox.showwarning("통합", "유효한 단어가 없습니다.")
            return

        widxs = sorted({self._sridx_to_widx(it["sridx"]) for it in checked})
        widxs = [w for w in widxs if w is not None]

        if not widxs:
            return

        template = self.working_df.loc[widxs[0]].copy()

        self.working_df.drop(index=widxs, inplace=True)
        self.working_df.reset_index(drop=True, inplace=True)

        template["_rid"] = self._next_rid()
        template["추출단어"] = merge_word
        for c in CATEGORY_COLS:
            template[c] = ""
        template["비고"] = "통합"

        self.working_df = pd.concat(
            [self.working_df, template.to_frame().T],
            ignore_index=True
        )

        self._refresh_after_working_change(keep_scroll=True)

    # 기능 버튼(제거)
    def on_detail_delete(self):
        self._save_global_undo_snapshot()
        checked = self._detail_checked_items()
        if not checked:
            messagebox.showwarning("제거", "제거할 단어를 체크하세요.")
            return

        widxs = sorted({self._sridx_to_widx(it["sridx"]) for it in checked})
        widxs = [w for w in widxs if w is not None]

        if not widxs:
            return

        self.working_df.drop(index=widxs, inplace=True)
        self.working_df.reset_index(drop=True, inplace=True)

        self._refresh_after_working_change(keep_scroll=True)

    # 실행취소용 스냅샷
    def _save_global_undo_snapshot(self):
        self.global_undo_snapshot = {
            "working_df": self.working_df.copy(deep=True),
            "current_word": self.current_word,
            "filter_cat": self.filter_cat_var.get(),
            "filter_match": self.filter_match_var.get(),
            "current_page": self.current_page,
            "selected_pno": self.selected_pno,
            "selected_detail_pno": self.selected_detail_pno
        }

    # 실행취소
    def on_global_undo(self):
        snap = self.global_undo_snapshot
        if not snap:
            messagebox.showinfo("실행취소", "되돌릴 작업이 없습니다.")
            return

        self.working_df = snap["working_df"].copy(deep=True)
        self.current_word = snap["current_word"]

        self.filter_cat_var.set(snap["filter_cat"])
        self.filter_match_var.set(snap["filter_match"])
        self.current_page = snap["current_page"]
        self.selected_pno = snap["selected_pno"]
        self.selected_detail_pno = snap["selected_detail_pno"]

        self._refresh_after_working_change(keep_scroll=True)

        self.global_undo_snapshot = None

    # 이전 페이지
    def on_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._render_current_page()
            self._update_detail_area(keep_scroll=True)
    
    # 다음 페이지
    def on_next_page(self):
        total_pages = math.ceil(len(self.filtered_products) / self.page_size) if self.filtered_products else 0
        if self.current_page < total_pages:
            self.current_page += 1
            self._render_current_page()
            self._update_detail_area(keep_scroll=True)

    # 저장
    def on_save(self):
        self.df = self.working_df.copy(deep=True)

        default_name = f"추출단어_검수결과_{datetime.datetime.now():%Y%m%d_%H%M}.xlsx"
        
        file_path = filedialog.asksaveasfilename(
            initialfile=default_name,
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")]
        )

        if not file_path:
            return

        out = self.df.drop(columns=["_rid"], errors="ignore")
        out.to_excel(file_path, index=False)
        

    # 카테고리 배경색
    def _get_category_bg(self, category):
        return CATEGORY_BG_MAP.get(category, self.root_bg)

    # 검색 방식 표시
    def _get_match_mode_text(self):
        if self.include_search_var.get():
            return "완전일치 + 포함단어"
        return "완전일치"

    # 카테고리 판별
    def _get_category_from_row(self, sridx: int) -> str:
        if self.search_df is None or self.search_df.empty:
            return "(미지정)"

        word = (self.search_df.at[sridx, "추출단어"] or "").strip()
        if not word:
            return "(미지정)"

        for c in CATEGORY_COLS:
            val = (self.search_df.at[sridx, c] or "").strip()
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

            for sridx in ridxs:
                word = (self.search_df.at[sridx, "추출단어"] or "").strip()

                if self.current_word:
                    if self.include_search_var.get():
                        if self.current_word not in word:
                            continue
                    else:
                        if word != self.current_word:
                            continue

                cat = self._get_category_from_row(sridx)
                
                if self.active_filter_category != "전체":
                    if cat != self.active_filter_category:
                        continue
                
                cat_counter[cat] += 1
                total_rows += 1

                if (self.search_df.at[sridx, "비고"] or "").strip():
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

    # 대표 추출단어 선정
    def _pick_representative_token(self, pno: str, prod: dict):
        ridxs = prod.get("_matched_rows") or self.current_pno_to_rows.get(pno, [])

        matched_tokens = []
        exact_tokens = []

        for sridx in ridxs:
            w = (self.search_df.at[sridx, "추출단어"] or "").strip()
            if not w:
                continue

            if w == self.current_word:
                exact_tokens.append((w, sridx))
            elif self.current_word and (self.current_word in w):
                matched_tokens.append((w, sridx))

        target_sridx = None
        matched_token = None

        if exact_tokens:
            matched_token, target_sridx = exact_tokens[0]
        elif matched_tokens:
            matched_token, target_sridx = min(matched_tokens, key=lambda x: len(x[0]))

        is_changed = (matched_token is None)
        return matched_token, target_sridx, is_changed

    # 테두리 기본값
    def _apply_block_border_default(self, block):
        if not block:
            return
        block.configure(
            highlightbackground=DEFAULT_COLOR,
            highlightcolor=DEFAULT_COLOR,
            highlightthickness=DEFAULT_THICK
        )

    # 테두리 하이라이트값
    def _apply_block_border_selected(self, block):
        if not block:
            return
        block.configure(
            highlightbackground=HILITE_COLOR,
            highlightcolor=HILITE_COLOR,
            highlightthickness=HILITE_THICK
        )

# 실행
if __name__ == "__main__":
    app = WordReviewTool()
    app.mainloop()
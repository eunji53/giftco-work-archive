import os
import copy
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

today_str = datetime.now().strftime("%m%d")

# 결과물 저장 경로
# SAVE_PATH = "./save_data.xlsx"
SAVE_PATH = "./save_data.csv"

# 카테고리
CATEGORY_COLS = ["브랜드", "원산지", "단위", "규격", "특징",
                 "상품명", "모델명", "선택사항", "불필요"]
ALL_OPTIONS = ["(미지정)"] + CATEGORY_COLS

# 데이터 로드
def load_products() -> pd.DataFrame:
    file_path = filedialog.askopenfilename(
        title="상품 데이터 파일 선택",
        filetypes=[
            ("Excel files", "*.xlsx"),
            ("CSV files", "*.csv")
        ]
    )

    if not file_path:
        raise ValueError("파일이 선택되지 않았습니다.")

    if file_path.endswith(".xlsx"):
        df = pd.read_excel(file_path, dtype=str)
    else:
        df = pd.read_csv(file_path, dtype=str)

    df.columns = [c.strip() for c in df.columns]
    
    required = ["상품번호", "실제 상품명", "추출단어"] + CATEGORY_COLS
    for c in required:
        if c not in df.columns:
            raise ValueError(f"로드 파일에 '{c}' 컬럼이 없습니다.")
            
    df["상품번호"] = df["상품번호"].fillna("").astype(str).str.strip()
    df["실제 상품명"] = df["실제 상품명"].fillna("").astype(str).str.strip()
    df["추출단어"] = df["추출단어"].fillna("").astype(str).str.strip()
    
    for c in CATEGORY_COLS:
        df[c] = df[c].fillna("").astype(str).str.strip()
        
    if "비고" in df.columns:
        df["비고"] = df["비고"].fillna("").astype(str).str.strip()
    else:
        df["비고"] = ""
        
    if "작업" in df.columns:
        df["작업"] = df["작업"].fillna("").astype(str).str.strip()
    else:
        df["작업"] = ""
    
    return df

# tkinter
class LabelingToolApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("상품 단어-카테고리 매칭 툴 (tkinter)")
        self.geometry("1400x900")

        # 로드
        try:
            self.df_products = load_products()
        except Exception as e:
            messagebox.showerror("로드 오류", str(e))
            self.destroy()
            return
        
        self.df_detail = self.df_products
        
        prod_df = (self.df_detail[["상품번호", "실제 상품명"]].drop_duplicates().reset_index(drop=True))
        self.products = prod_df.to_dict("records")
        if not self.products:
            raise ValueError("로드 데이터에 상품이 없습니다.")
            
        work_raw = (self.df_detail.groupby("상품번호")["작업"].first().to_dict())
        self.work_map = {str(k).strip(): (str(v).strip() if v is not None else "") for k, v in work_raw.items()}

        self.idx = 0
        cursor_idx = None
        for j, p in enumerate(self.products):
            pno = str(p.get("상품번호", "")).strip()
            if pno and self._has_cursor(pno):
                cursor_idx = j
                break

        def find_next_unworked(start_idx: int):
            for k in range(start_idx, len(self.products)):
                pno2 = str(self.products[k].get("상품번호","")).strip()
                if pno2 and (not self._is_done(pno2)):
                    return k
            return None

        if cursor_idx is not None:
            nxt = find_next_unworked(cursor_idx + 1)
            if nxt is None:
                nxt = find_next_unworked(0)
            if nxt is not None:
                self.idx = nxt
        else:
            nxt = find_next_unworked(0)
            if nxt is not None:
                self.idx = nxt
        
        # 상품번호 -> index 이동 맵
        self.no2idx = {}
        for i, p in enumerate(self.products):
            no = str(p.get("상품번호", "")).strip()
            if no and no not in self.no2idx:
                self.no2idx[no] = i

        # 상태 저장
        self.state = {}
        self.undo_snapshot = None

        # UI
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)

        self.title_label = ttk.Label(top, text="", font=("맑은 고딕", 16, "bold"), anchor="center")
        self.title_label.pack(fill="x")

        # 헤더
        header = ttk.Frame(self)
        header.pack(fill="x", padx=10)

        ttk.Label(header, text="", width=3).pack(side="left")

        ttk.Label(header, text="추출단어", font=("맑은 고딕", 11, "bold"),
                  anchor="w", width=15).pack(side="left", padx=(0, 8))

        ttk.Label(header, text="선택한 카테고리", font=("맑은 고딕", 11, "bold"),
                  anchor="center", width=14).pack(side="left", padx=(0, 10))

        ttk.Label(header, text="카테고리", font=("맑은 고딕", 11, "bold"),
                  anchor="center", width=80).pack(side="left", padx=(0,10))
        
        ttk.Label(header, text="비고", font=("맑은 고딕", 11, "bold"),
                  anchor="w").pack(side="left", fill="x", expand=True, padx=(0, 10))

        # 테이블
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=10, pady=6)

        self.canvas = tk.Canvas(container, highlightthickness=1, highlightbackground="#ddd")
        self.canvas.pack(side="left", fill="both", expand=True)

        vbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        vbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=vbar.set)

        # (옵션)
        hbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        hbar.pack(fill="x", padx=10)
        self.canvas.configure(xscrollcommand=hbar.set)

        self.table_frame = ttk.Frame(self.canvas)
        self.table_window = self.canvas.create_window((0, 0), window=self.table_frame, anchor="nw")

        def _on_frame_configure(_):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        self.table_frame.bind("<Configure>", _on_frame_configure)

        def _on_canvas_configure(event):
            self.canvas.itemconfigure(self.table_window, width=event.width)

        self.canvas.bind("<Configure>", _on_canvas_configure)

        # 하단 버튼/입력
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=8, pady=6)
        
        bottom_top = ttk.Frame(bottom)
        bottom_top.pack(fill="x", pady=(0,18))
        
        bottom_bottom = ttk.Frame(bottom)
        bottom_bottom.pack(fill="x")

        # 수정입력
        ttk.Label(bottom_top, text="수정입력 :", width=8).pack(side="left", padx=(0, 4))
        
        self.edit_var = tk.StringVar()
        self.edit_var.trace_add("write", lambda *args: self.update_button_states())
        self.edit_entry = ttk.Entry(bottom_top, textvariable=self.edit_var, width=40)
        self.edit_entry.pack(side="left", padx=(0, 6))
        
        # 분리 / 통합 / 수정 / 추가 버튼
        self.split_btn = ttk.Button(bottom_top, text="분리", command=self.on_split, state="disabled")
        self.split_btn.pack(side="left", padx=4)
        
        self.merge_btn = ttk.Button(bottom_top, text="통합", command=self.on_merge, state="disabled")
        self.merge_btn.pack(side="left", padx=4)
        
        self.edit_btn = ttk.Button(bottom_top, text="수정", command=self.on_edit, state="disabled")
        self.edit_btn.pack(side="left", padx=4)
        
        self.add_btn  = ttk.Button(bottom_top, text="추가", command=self.on_add, state="disabled")
        self.add_btn.pack(side="left", padx=(4,40))
        
        self.undo_btn = ttk.Button(bottom_top, text="실행취소", command=self.on_undo)
        self.undo_btn.pack(side="left", padx=4)

        # 상품번호로 이동
        ttk.Label(bottom_bottom, text="상품번호 :", width=8).pack(side="left", padx=(0, 4))
        
        self.goto_var = tk.StringVar()
        self.goto_entry = ttk.Entry(bottom_bottom, textvariable=self.goto_var, width=15)
        self.goto_entry.pack(side="left", padx=(0, 6))
        
        self.goto_btn = ttk.Button(bottom_bottom, text="이동", command=self.on_goto)
        self.goto_btn.pack(side="left", padx=(0,12))
        
        self.goto_entry.bind("<Return>", self.on_goto)
        
        # 이전 / 다음 버튼
        self.prev_btn = ttk.Button(bottom_bottom, text="◀ 이전", command=self.on_prev)
        self.prev_btn.pack(side="left", padx=4)
        
        self.next_btn = ttk.Button(bottom_bottom, text="다음 ▶", command=self.on_next)
        self.next_btn.pack(side="left", padx=4)

        # 저장
        self.save_btn = ttk.Button(bottom_bottom, text="저장", command=self.on_save)
        self.save_btn.pack(side="right", padx=8)

        # 작업상태
        self.status_label = ttk.Label(bottom_bottom, text="", foreground="#666")
        self.status_label.pack(side="left", padx=10)
        
        # 작업완료
        self.work_done_var = tk.BooleanVar(value=False)
        self.work_done_chk = ttk.Checkbutton(
            bottom_bottom,
            text="작업완료",
            variable=self.work_done_var,
            command=self.on_toggle_work_done
        )
        self.work_done_chk.pack(side="left", padx=(6, 0))

        # 행 위젯 핸들
        self.row_widgets = {}

        # 최초 렌더
        self.render()
        
    def _work_flags(self, pno: str) -> set:
        s = (self.work_map.get(pno, "") or "").strip()
        if not s:
            return set()
        return {x.strip() for x in s.split("|") if x.strip()}
    
    def _is_checked(self, pno: str) -> bool:
        flags = self._work_flags(pno)
        return ("CHECK" in flags) or ("DONE" in flags)

    def _is_done(self, pno: str) -> bool:
        return "DONE" in self._work_flags(pno)

    def _has_cursor(self, pno: str) -> bool:
        return "CURSOR" in self._work_flags(pno)

    def _set_check(self, pno: str, checked: bool):
        flags = self._work_flags(pno)
        if checked:
            flags.add("CHECK")
        else:
            flags.discard("CHECK")
        self.work_map[pno] = "|".join(sorted(flags))

    def apply_current_work_done(self):
        prod = self.current_product()
        pno = str(prod.get("상품번호","")).strip()
        if not pno:
            return
        self._set_check(pno, bool(self.work_done_var.get()))

    def on_toggle_work_done(self):
        self.apply_current_work_done()
        
    # 입력창 초기화
    def reset_input(self):
        self.edit_var.set("")
        self.edit_entry.configure(foreground="#000")
        
    # 실행취소용 스냅샷
    def save_undo_snapshot(self):
        self.ensure_state_for_current()
        st = self.state[self.idx]
        self.undo_snapshot = {"idx": self.idx, "tokens": copy.deepcopy(st["tokens"])}

    # 상태/유틸
    def current_product(self):
        return self.products[self.idx]
    
    # 현재 상태 확인
    def ensure_state_for_current(self):
        if self.idx in self.state:
            return

        prod = self.current_product()
        pno = prod["상품번호"]

        sub = self.df_detail[self.df_detail["상품번호"] == pno]

        tokens = []
        for _, r in sub.iterrows():
            token = r["추출단어"]

            cat = "(미지정)"
            for c in CATEGORY_COLS:
                val = r.get(c, "")
                if isinstance(val, str) and val.strip():
                    cat = c
                    break

            remark = r.get("비고", "")
            tokens.append({"token": token, "cat": cat, "remark": remark})

        self.state[self.idx] = {"tokens": tokens}

    # 선택 상태 유지
    def apply_current_ui(self):
        self.ensure_state_for_current()
        st = self.state[self.idx]
        for i, w in self.row_widgets.items():
            st["tokens"][i]["cat"] = w["cat_var"].get()
            
    # 버튼 상태 유효화
    def update_button_states(self):
        checked = self.checked_rows()   # 체크된 추출단어 index list
        n_checked = len(checked)
        raw = (self.edit_var.get() or "").strip()

        has_input = bool(raw)
        has_split_sep = ("\\" in raw)

        # 분리
        split_ok = (n_checked == 1) and has_split_sep
        self.split_btn.config(state=("normal" if split_ok else "disabled"))

        # 통합
        merge_ok = (n_checked >= 2) and has_input
        self.merge_btn.config(state=("normal" if merge_ok else "disabled"))

        # 수정
        edit_ok = (n_checked == 1) and has_input
        self.edit_btn.config(state=("normal" if edit_ok else "disabled"))

        # 추가
        add_ok = has_input
        self.add_btn.config(state=("normal" if add_ok else "disabled"))

    def checked_rows(self):
        return [i for i, w in self.row_widgets.items() if w["chk_var"].get()]
    
    # 체크상태 동기화
    def sync_edit_from_checks(self):
        self.ensure_state_for_current()
        st = self.state[self.idx]

        checked_idxs = sorted(self.checked_rows())

        if not checked_idxs:
            self.reset_input()
            return

        words = [st["tokens"][i]["token"] for i in checked_idxs]

        self.edit_entry.configure(foreground="#000")
        self.edit_var.set("\\".join(words))
        
        self.update_button_states()
        
    def find_next_unworked_idx(self, start_idx: int, step: int):
        i = start_idx
        while 0 <= i < len(self.products):
            pno = str(self.products[i].get("상품번호","")).strip()
            if pno and (not self._is_done(pno)):
                return i
            i += step
        return None
    
    # 작업상태 갱신
    def update_status_label(self):
        total = len(self.products)

        # DONE 개수
        done_idxs = []
        for i, prod in enumerate(self.products):
            pno = str(prod.get("상품번호", "")).strip()
            if self._is_done(pno):
                done_idxs.append(i)
        done_count = len(done_idxs)

        # TODO 상품 index 목록
        todo_idxs = [i for i in range(total) if i not in done_idxs]
        todo_total = len(todo_idxs)

        # 현재 상품의 TODO 순번
        if self.idx in todo_idxs:
            todo_pos = todo_idxs.index(self.idx) + 1  # 1-based
        else:
            todo_pos = 0  # 현재 상품이 DONE인 경우

        self.status_label.config(
            text=f"(TODO: {todo_pos}/{todo_total}, DONE: {done_count})"
        )

    # 렌더
    def render(self):
        self.ensure_state_for_current()

        # 테이블 초기화
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        self.row_widgets = {}

        prod = self.current_product()
        st = self.state[self.idx]

        display_name = prod.get("실제 상품명", prod.get("상품명", ""))
        self.title_label.config(text=f"상품번호: {prod.get('상품번호', '')} | 상품명: {display_name}")
        self.update_status_label()
        
        pno = str(prod.get("상품번호","")).strip()
        self.work_done_var.set(self._is_checked(pno))

        # 행 생성
        for i, row in enumerate(st["tokens"]):
            line = ttk.Frame(self.table_frame)
            line.pack(fill="x", pady=3)

            # 체크박스 + 추출단어
            chk_var = tk.BooleanVar(value=False)
            chk = ttk.Checkbutton(line, variable=chk_var, command=self.sync_edit_from_checks)
            chk.pack(side="left", padx=(4, 2))

            word_lbl = ttk.Label(line, text=row["token"], width=20, anchor="w")
            word_lbl.pack(side="left", padx=(0, 8))

            # 선택한 카테고리 라벨
            selected_lbl = ttk.Label(line, text=row["cat"], width=14, anchor="center")
            selected_lbl.pack(side="left", padx=(0, 10))

            # 카테고리 라디오버튼
            cat_var = tk.StringVar(value=row["cat"])
            cat_frame = ttk.Frame(line)
            cat_frame.pack(side="left", padx=(50,50))

            def make_cmd(lbl=selected_lbl, v=cat_var):
                return lambda: lbl.config(text=v.get())

            # (미지정)+카테고리
            for opt in ALL_OPTIONS:
                ttk.Radiobutton(
                    cat_frame, text=opt, value=opt, variable=cat_var,
                    command=make_cmd()
                ).pack(side="left", padx=3)
                
            # 비고 라벨
            remark_lbl = ttk.Label(line, text=row["remark"], width=8, anchor="center")
            remark_lbl.pack(side="left", padx=(4,10))

            self.row_widgets[i] = {
                "chk_var": chk_var,
                "cat_var": cat_var,
                "selected_lbl": selected_lbl
            }
            
        self.update_button_states()

    # 이동 (이전/다음)
    def on_prev(self):
        self.apply_current_ui()
        self.apply_current_work_done()
        self.reset_input()

        prv = self.find_next_unworked_idx(self.idx - 1, -1)
        if prv is not None:
            self.idx = prv
        self.render()

    def on_next(self):
        self.apply_current_ui()
        self.apply_current_work_done()
        self.reset_input()

        nxt = self.find_next_unworked_idx(self.idx + 1, +1)
        if nxt is not None:
            self.idx = nxt
        self.render()

    # 이동 (상품번호)
    def on_goto(self, event=None):
        target = (self.goto_var.get() or "").strip()

        if not target:
            messagebox.showwarning("이동", "상품번호를 입력하세요.")
            return

        if target not in self.no2idx:
            messagebox.showwarning("이동", f"상품번호 '{target}'를 찾을 수 없습니다.")
            return

        # 현재 작업상태 반영 후 이동
        self.apply_current_ui()
        self.apply_current_work_done()
        self.reset_input()
        self.idx = self.no2idx[target]
        self.render()
        
    # 통합
    # - 2개 이상 체크
    # - 입력 비어있으면 금지
    # - [ ] 포함(분리용 형식) 금지
    # - remark="통합"
    def on_merge(self):
        self.apply_current_ui()
        self.ensure_state_for_current()
        st = self.state[self.idx]

        checked = sorted(self.checked_rows())
        raw = (self.edit_var.get() or "").strip()

        if len(checked) < 2:
            messagebox.showwarning("통합 경고", "통합은 두 개 이상의 추출단어를 체크해야 합니다.")
            return

        new_word = raw.replace('\\', "").strip()
        if not new_word:
            messagebox.showwarning("통합 경고", "통합할 단어를 입력하세요.")
            return
        
        self.save_undo_snapshot()
        
        insert_pos = checked[0]

        for k in reversed(checked):
            del st["tokens"][k]

        st["tokens"].insert(insert_pos, {"token": new_word, "cat": "(미지정)", "remark": "통합"})
        
        self.render()
        self.reset_input()

    # 분리
    # - 체크 1개만 허용(2개 이상이면 경고)
    # - 입력에 [단어] 없으면 경고
    # - remark="분리"
    def on_split(self):
        self.apply_current_ui()
        self.ensure_state_for_current()
        st = self.state[self.idx]

        checked = sorted(self.checked_rows())
        raw = (self.edit_var.get() or "").strip()

        if len(checked) != 1:
            messagebox.showwarning("분리 경고", "분리는 하나의 추출단어만 체크해야 합니다.")
            return
        
        if "\\" not in raw:
            messagebox.showwarning("분리 경고", "분리는 '\\' 구분자가 있어야 합니다.\n예: 사이드\\포켓")
            return
        
        toks = [t.strip() for t in raw.split("\\") if t.strip()]

        if len(toks) == 0:
            messagebox.showwarning("분리 경고", "분리할 단어를 입력하고 '\\'로 구분해 입력하세요.")
            return

        self.save_undo_snapshot()
        
        base_idx = checked[0]
        del st["tokens"][base_idx]

        for i, tok in enumerate(toks):
            st["tokens"].insert(base_idx + i, {"token": tok, "cat": "(미지정)", "remark": "분리"})

        self.render()
        self.reset_input()
        
    # 수정
    # - 체크 1개만 허용
    # - remark="수정"
    def on_edit(self):
        self.apply_current_ui()
        self.ensure_state_for_current()
        st = self.state[self.idx]

        checked = sorted(self.checked_rows())
        raw = (self.edit_var.get() or "").strip()
        new_word = raw.replace("\\", "").strip()

        if len(checked) != 1:
            messagebox.showwarning("수정 경고", "수정은 하나의 추출단어만 체크해야 합니다.")
            return

        if not new_word:
            messagebox.showwarning("수정 경고", "수정할 단어를 입력하세요.")
            return

        self.save_undo_snapshot()
        
        idx = checked[0]
        
        st["tokens"][idx]["token"] = new_word
        st["tokens"][idx]["remark"] = "수정"

        self.render()
        self.reset_input()
    
    # 추가
    # - 체크 필요없음
    # - remark="추가"
    def on_add(self):
        self.apply_current_ui()
        self.ensure_state_for_current()
        st = self.state[self.idx]

        raw = (self.edit_var.get() or "").strip()
        new_word = raw.replace("\\", "").strip()

        if not new_word:
            messagebox.showwarning("추가 경고", "추가할 단어를 입력하세요.")
            return

        self.save_undo_snapshot()
        
        st["tokens"].append({"token": new_word, "cat": "(미지정)", "remark": "추가"})

        self.render()
        self.reset_input()
        
    # 실행취소
    def on_undo(self):
        if not self.undo_snapshot:
            messagebox.showinfo("작업취소", "되돌릴 작업이 없습니다.")
            return

        # 다른 상품으로 이동한 뒤 undo 누르면 혼동 방지
        if self.undo_snapshot["idx"] != self.idx:
            messagebox.showinfo("작업취소", "현재 상품에서 되돌릴 작업이 없습니다.")
            return

        self.ensure_state_for_current()
        self.state[self.idx]["tokens"] = self.undo_snapshot["tokens"]

        # Undo 1회만 허용
        self.undo_snapshot = None

        self.render()
        self.reset_input()

    # 저장
    def on_save(self):
        self.apply_current_ui()
        self.apply_current_work_done()
        
        # CHECK → DONE, 기존 CURSOR 제거
        for p in self.products:
            pno = str(p.get("상품번호","")).strip()
            flags = self._work_flags(pno)

            if "CHECK" in flags:
                flags.discard("CHECK")
                flags.add("DONE")

            flags.discard("CURSOR")
            self.work_map[pno] = "|".join(sorted(flags))

        # 현재 상품에 CURSOR 부여
        cur_pno = str(self.current_product().get("상품번호","")).strip()
        flags = self._work_flags(cur_pno)
        flags.add("CURSOR")
        self.work_map[cur_pno] = "|".join(sorted(flags))

        save_rows = []

        cur_idx = self.idx

        for i, prod in enumerate(self.products):
            self.idx = i
            self.ensure_state_for_current()
            st = self.state.get(i)
            if not st:
                continue

            for tok in st["tokens"]:
                cat = tok["cat"]
                remark = tok["remark"] or ""
                pno = str(prod["상품번호"].strip())

                row = {
                    "상품번호": prod["상품번호"],
                    "실제 상품명": prod["실제 상품명"],
                    "추출단어": tok["token"],
                    "비고": remark,
                    "작업": self.work_map.get(pno, "")
                }

                for c in CATEGORY_COLS:
                    row[c] = ""

                if cat != "(미지정)":
                    row[cat] = tok["token"]

                save_rows.append(row)

        self.idx = cur_idx

        save_df = pd.DataFrame(save_rows, columns=[
            "상품번호", "실제 상품명", "추출단어",
            *CATEGORY_COLS, "비고", "작업"
        ])

        try:
            # save_df.to_excel(SAVE_PATH, index=False)
            # save_df.to_csv(SAVE_PATH, index=False, encoding="utf-8-sig")
            cursor_idx = save_df[save_df["작업"].str.contains("CURSOR", na=False)].index.min()

            if pd.isna(cursor_idx):
                # CURSOR가 없으면 전체를 save로
                df_upper = save_df.copy()
                df_lower = pd.DataFrame(columns=save_df.columns)
            else:
                df_upper = save_df.loc[:cursor_idx-1]
                df_lower = save_df.loc[cursor_idx:]

            # 각각 저장
            df_upper.to_csv(f"save_data_{today_str}.csv", index=False, encoding="utf-8-sig")
            df_lower.to_csv(f"next_data_{today_str}.csv", index=False, encoding="utf-8-sig")
            
            messagebox.showinfo("저장 완료", "저장되었습니다.")


        except Exception as e:
            messagebox.showerror("저장 오류", str(e))

# 실행
if __name__ == "__main__":
    app = LabelingToolApp()
    app.mainloop()
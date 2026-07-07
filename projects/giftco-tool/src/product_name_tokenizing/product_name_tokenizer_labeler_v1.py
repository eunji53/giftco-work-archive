import os
import re
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# 결과물 저장 경로
SAVE_PATH = "./save_data.xlsx"
NEXT_PATH = "./next_data.xlsx"

# 카테고리
CATEGORY_COLS = ["브랜드", "원산지", "단위", "규격", "특징",
                 "상품명", "모델명", "선택사항", "불필요"]
ALL_OPTIONS = ["(미지정)"] + CATEGORY_COLS

# 단어 추출
def tokenize_product_name(name: str):
    name = "" if name is None else str(name).strip()
    if not name:
        return []

    tokens = []
    seen = set()

    i = 0
    buf = []

    def flush_buf():
        nonlocal buf
        if not buf:
            return
        chunk = "".join(buf)
        buf = []
        for t in chunk.split():
            t = t.strip()
            if t and t not in seen:
                seen.add(t)
                tokens.append(t)

    while i < len(name):
        ch = name[i]

        # 괄호 처리
        if ch in ("[", "("):
            flush_buf()
            open_ch = ch
            close_ch = "]" if ch == "[" else ")"
            depth = 1
            j = i + 1

            # 중첩 처리
            while j < len(name) and depth > 0:
                if name[j] == open_ch:
                    depth += 1
                elif name[j] == close_ch:
                    depth -= 1
                j += 1

            inner = name[i + 1:j - 1] if j - 1 > i else ""
            inner_clean = inner.replace("[", " ").replace("]", " ").replace("(", " ").replace(")", " ")
            for t in inner_clean.split():
                t = t.strip()
                if t and t not in seen:
                    seen.add(t)
                    tokens.append(t)

            i = j
            continue

        buf.append(ch)
        i += 1

    flush_buf()
    return tokens

# 분리 입력 규칙(대괄호 분리)
def parse_bracket_tokens(seq: str):
    return [m.strip() for m in re.findall(r"\[([^\]]+)\]", seq) if m.strip()]

# 데이터 로드
def load_products() -> pd.DataFrame:
    file_path = filedialog.askopenfilename(
        title="상품 데이터 파일 선택",
        filetypes=[
            ("CSV files", "*.csv"),
            ("Excel files", "*.xlsx")
        ]
    )

    if not file_path:
        raise ValueError("파일이 선택되지 않았습니다.")

    if file_path.endswith(".csv"):
        df = pd.read_csv(file_path, dtype=str)
    else:
        df = pd.read_excel(file_path, dtype=str)

    required = ["상품번호", "실제 상품명"]
    for c in required:
        if c not in df.columns:
            raise ValueError(f"로드 파일에 '{c}' 컬럼이 없습니다.")
            
    df["상품번호"] = df["상품번호"].fillna("").astype(str)
    df["실제 상품명"] = df["실제 상품명"].fillna("").astype(str)
    df = df[df["실제 상품명"].str.strip().ne("")].reset_index(drop=True)
    
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
            
        self.products = self.df_products.to_dict("records")
        if not self.products:
            raise ValueError("로드 데이터에 상품이 없습니다.")

        self.idx = 0
        
        # 상품번호 -> index 이동 맵
        self.no2idx = {}
        for i, p in enumerate(self.products):
            no = str(p.get("상품번호", "")).strip()
            if no and no not in self.no2idx:
                self.no2idx[no] = i

        # 상태 저장
        self.state = {}

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
                  anchor="w").pack(side="left", fill="x", expand=True, padx=(260, 0))

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
        bottom.pack(fill="x", padx=10, pady=8)

        # 상품번호로 이동
        ttk.Label(bottom, text="상품번호 이동:", width=12).pack(side="left", padx=(0, 4))
        
        self.goto_var = tk.StringVar()
        self.goto_entry = ttk.Entry(bottom, textvariable=self.goto_var, width=14)
        self.goto_entry.pack(side="left", padx=(0, 6))
        
        self.goto_btn = ttk.Button(bottom, text="이동", command=self.on_goto)
        self.goto_btn.pack(side="left", padx=(0,14))
        
        self.goto_entry.bind("<Return>", self.on_goto)
        
        self.prev_btn = ttk.Button(bottom, text="◀ 이전", command=self.on_prev)
        self.next_btn = ttk.Button(bottom, text="다음 ▶", command=self.on_next)
        self.split_btn = ttk.Button(bottom, text="분리", command=self.on_split)
        self.merge_btn = ttk.Button(bottom, text="통합", command=self.on_merge)

        self.prev_btn.pack(side="left", padx=4)
        self.next_btn.pack(side="left", padx=4)
        self.split_btn.pack(side="left", padx=12)
        self.merge_btn.pack(side="left", padx=4)

        # 수정입력
        self.edit_var = tk.StringVar()
        self.edit_entry = ttk.Entry(bottom, textvariable=self.edit_var, width=45)
        self.edit_entry.pack(side="left", padx=8)

        self._placeholder_text = "수정입력"
        self._set_placeholder()

        self.save_btn = ttk.Button(bottom, text="저장", command=self.on_save)
        self.save_btn.pack(side="left", padx=8)

        self.status_label = ttk.Label(bottom, text="", foreground="#666")
        self.status_label.pack(side="left", padx=10)

        # 행 위젯 핸들
        self.row_widgets = {}

        # 최초 렌더
        self.render()

    # placeholder
    def _set_placeholder(self):
        self.edit_var.set(self._placeholder_text)
        self.edit_entry.configure(foreground="#888")
        self.edit_entry.bind("<FocusIn>", self._clear_placeholder)
        self.edit_entry.bind("<FocusOut>", self._restore_placeholder)

    def _clear_placeholder(self, _):
        if self.edit_var.get() == self._placeholder_text:
            self.edit_var.set("")
            self.edit_entry.configure(foreground="#000")

    def _restore_placeholder(self, _):
        if not self.edit_var.get().strip():
            self.edit_var.set(self._placeholder_text)
            self.edit_entry.configure(foreground="#888")

    # 입력창 초기화
    def reset_input(self):
        self.edit_var.set("")
        self.edit_entry.configure(foreground="#000")
        self._restore_placeholder(None)

    # 상태/유틸
    def current_product(self):
        return self.products[self.idx]

    def ensure_state_for_current(self):
        if self.idx not in self.state:
            prod = self.current_product()
            tokens = tokenize_product_name(prod["실제 상품명"])
            self.state[self.idx] = {
                "tokens": [{"token": t, "cat": "(미지정)", "remark": ""} for t in tokens]
            }

    # 선택 상태 유지
    def apply_current_ui(self):
        self.ensure_state_for_current()
        st = self.state[self.idx]
        for i, w in self.row_widgets.items():
            st["tokens"][i]["cat"] = w["cat_var"].get()

    def checked_rows(self):
        return [i for i, w in self.row_widgets.items() if w["chk_var"].get()]

    def is_worked_state(self, st: dict) -> bool:
        any_cat = any(x["cat"] != "(미지정)" for x in st["tokens"])
        any_edit = any(x["remark"] in ("통합", "분리") for x in st["tokens"])
        return bool(any_cat or any_edit)

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
        self.status_label.config(text=f"({self.idx + 1}/{len(self.products)})")

        # 행 생성
        for i, row in enumerate(st["tokens"]):
            line = ttk.Frame(self.table_frame)
            line.pack(fill="x", pady=3)

            # 1) 체크 + 추출단어
            chk_var = tk.BooleanVar(value=False)
            chk = ttk.Checkbutton(line, variable=chk_var)
            chk.pack(side="left", padx=(4, 2))

            word_lbl = ttk.Label(line, text=row["token"], width=20, anchor="w")
            word_lbl.pack(side="left", padx=(0, 8))

            # 2) 선택한 카테고리 라벨
            selected_lbl = ttk.Label(line, text=row["cat"], width=14, anchor="center")
            selected_lbl.pack(side="left", padx=(0, 10))

            # 3) 카테고리 라디오버튼
            cat_var = tk.StringVar(value=row["cat"])
            cat_frame = ttk.Frame(line)
            cat_frame.pack(side="left", fill="x", expand=True)

            def make_cmd(lbl=selected_lbl, v=cat_var):
                return lambda: lbl.config(text=v.get())

            # (미지정)+카테고리
            for opt in ALL_OPTIONS:
                ttk.Radiobutton(
                    cat_frame, text=opt, value=opt, variable=cat_var,
                    command=make_cmd()
                ).pack(side="left", padx=3)

            self.row_widgets[i] = {
                "chk_var": chk_var,
                "cat_var": cat_var,
                "selected_lbl": selected_lbl
            }

    # 이동 (이전/다음)
    def on_prev(self):
        self.apply_current_ui()
        self.reset_input()
        if self.idx > 0:
            self.idx -= 1
        self.render()

    def on_next(self):
        self.apply_current_ui()
        self.reset_input()
        if self.idx < len(self.products) - 1:
            self.idx += 1
        self.render()

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
            messagebox.showwarning("통합 경고", "통합은 2개 이상의 추출단어를 체크해야 합니다.")
            return

        if not raw or raw == self._placeholder_text:
            messagebox.showwarning("통합 경고", "통합할 단어를 '수정입력'에 입력하세요.")
            return

        if "[" in raw or "]" in raw:
            messagebox.showwarning("통합 경고", "'[단어]' 형식은 분리용입니다.\n통합은 대괄호 없이 단어만 입력하세요.")
            return

        new_word = raw
        insert_pos = checked[0]

        # 체크된 토큰 제거(뒤에서부터)
        for k in reversed(checked):
            del st["tokens"][k]

        # 새 토큰 삽입
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

        if len(checked) == 0:
            messagebox.showwarning("분리 경고", "분리는 1개의 추출단어를 체크해야 합니다.")
            return
        if len(checked) >= 2:
            messagebox.showwarning("분리 경고", "분리는 1개만 체크해야 합니다.\n(2개 이상은 실행하지 않습니다.)")
            return
        if not raw or raw == self._placeholder_text:
            messagebox.showwarning("분리 경고", "분리할 단어를 [단어][단어] 형태로 '수정입력'에 입력하세요.")
            return

        toks = parse_bracket_tokens(raw)
        if len(toks) == 0:
            messagebox.showwarning("분리 경고", "입력에서 [단어] 형식을 찾지 못했습니다.\n예: [사이드][포켓]")
            return

        row_idx = checked[0]

        # 원본 삭제
        del st["tokens"][row_idx]

        # 분리 토큰 삽입
        for t in reversed(toks):
            st["tokens"].insert(row_idx, {"token": t, "cat": "(미지정)", "remark": "분리"})

        self.render()
        
        self.reset_input()

    # 저장
    def on_save(self):
        self.apply_current_ui()

        worked_idxs = {i for i, st in self.state.items() if self.is_worked_state(st)}

        # next_data.xlsx: 미작업 상품만
        next_rows = []
        for i, prod in enumerate(self.products):
            if i not in worked_idxs:
                next_rows.append({"상품번호": prod["상품번호"], "실제 상품명": prod["실제 상품명"]})
        next_df = pd.DataFrame(next_rows)

        # save_data.xlsx: 작업된 상품의 결과
        save_rows = []
        for i in sorted(worked_idxs):
            prod = self.products[i]
            st = self.state[i]

            for tok in st["tokens"]:
                cat = tok["cat"]
                remark = tok["remark"] or ""

                row = {
                    "상품번호": prod["상품번호"],
                    "실제 상품명": prod["실제 상품명"],
                    "추출단어": tok["token"],
                    "비고": remark
                }
                for c in CATEGORY_COLS:
                    row[c] = ""

                if cat != "(미지정)":
                    row[cat] = tok["token"]
                else:
                    # 작업된 상품에서 미지정이면 확인필요
                    row["비고"] = f"{row['비고']},확인필요".strip(",") if row["비고"] else "확인필요"

                save_rows.append(row)

        save_df = pd.DataFrame(save_rows, columns=[
            "상품번호", "실제 상품명", "추출단어",
            *CATEGORY_COLS, "비고"
        ])

        # 파일 저장
        try:
            # 현재 폴더에 저장
            next_df.to_excel(NEXT_PATH, index=False)
            save_df.to_excel(SAVE_PATH, index=False)

            messagebox.showinfo(
                "저장 완료",
                f"next_data.xlsx (미작업): {len(next_df)}건\n"
                f"save_data.xlsx (결과): {len(save_df)}행\n\n"
                f"저장 위치:\n- {os.path.abspath(NEXT_PATH)}\n- {os.path.abspath(SAVE_PATH)}"
            )
        except Exception as e:
            messagebox.showerror("저장 오류", str(e))

# 실행
if __name__ == "__main__":
    app = LabelingToolApp()
    app.mainloop()
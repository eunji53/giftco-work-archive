import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
import re

CATEGORIES = [
    "브랜드", "원산지", "단위", "규격", "특징",
    "상품명", "모델명", "선택사항", "불필요"
]

class LabelingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("상품 단어 정제 툴")

        self.df = None
        self.groups = None
        self.product_keys = []
        self.current_idx = 0

        self.radio_vars = []
        self.check_vars = []
        self.merge_word = tk.StringVar()

        self.build_ui()
        self.load_file()

    # ================= UI =================
    def build_ui(self):
        # 상단
        self.title_label = tk.Label(self.root, font=("Arial", 12, "bold"))
        self.title_label.pack(pady=5)

        # 중앙 스크롤 영역
        center = tk.Frame(self.root)
        center.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(center, takefocus=0)
        self.scrollbar = tk.Scrollbar(center, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = tk.Frame(self.canvas)

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # 하단 버튼
        bottom = tk.Frame(self.root, bd=2, relief="raised")
        bottom.pack(side="bottom", fill="x")

        tk.Label(bottom, text="분리/통합 단어").pack(side="left", padx=5)
        
        self.entry = tk.Entry(
            bottom,
            textvariable=self.merge_word,
            width=10
        )
        self.entry.pack(side="left")

        # 페이지 표시용 변수
        self.page_var = tk.StringVar()

        self.page_label = tk.Label(
            bottom,
            textvariable=self.page_var,
            font=("Arial", 10, "bold")
        )
        self.page_label.pack(side="right", padx=10)


        # 항상 포커스 유지
        self.entry.focus_force()

        # 클릭 시에도 다시 포커스
        self.entry.bind("<Button-1>", lambda e: self.entry.focus_force())

        tk.Button(bottom, text="분리", command=self.split_words).pack(side="left", padx=5)
        tk.Button(bottom, text="통합", command=self.merge_words).pack(side="left", padx=5)

        tk.Button(bottom, text="◀ 이전", command=self.prev_product).pack(side="left", padx=20)
        tk.Button(bottom, text="다음 ▶", command=self.next_product).pack(side="left")

        tk.Button(bottom, text="저장", command=self.save_file).pack(side="right", padx=20)

    def update_page_info(self):
        total = len(self.product_keys)
        current = self.current_idx + 1
        self.page_var.set(f"{current} / {total}")

    # ================= File =================
    def load_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")]
        )
        if not path:
            messagebox.showwarning("경고", "파일을 선택해주세요.")
            return

        self.df = pd.read_excel(path) if path.endswith("xlsx") else pd.read_csv(path)
        self.groups = self.df.groupby("상품번호")
        self.product_keys = list(self.groups.groups.keys())
        self.show_product()

    # ================= Display =================
    def clear_rows(self):
        for w in self.scroll_frame.winfo_children():
            w.destroy()
        self.radio_vars.clear()
        self.check_vars.clear()

    def show_product(self):
        self.clear_rows()
        key = self.product_keys[self.current_idx]
        group = self.groups.get_group(key)

        self.title_label.config(
            text=f"상품번호: {key} | 상품명: {group.iloc[0]['실제 상품명']}"
        )

        for idx, row in group.iterrows():
            frame = tk.Frame(self.scroll_frame, bd=1, relief="solid", pady=2)
            frame.pack(fill="x", padx=5, pady=2)

            chk = tk.BooleanVar()
            tk.Checkbutton(frame, variable=chk).pack(side="left")
            self.check_vars.append((idx, chk))

            tk.Label(frame, text=row["추출단어"], width=12, anchor="w").pack(side="left")

            var = tk.StringVar(value=self.get_selected_category(row))
            self.radio_vars.append((idx, var))

            for cat in CATEGORIES:
                tk.Radiobutton(frame, text=cat, variable=var, value=cat).pack(side="left")

            self.update_page_info() 

    def get_selected_category(self, row):
        for cat in CATEGORIES:
            if pd.notna(row.get(cat)) and row.get(cat) != "":
                return cat
        return ""

    # ================= Apply =================
    def apply_category_changes(self):
        for idx, var in self.radio_vars:
            for cat in CATEGORIES:
                self.df.at[idx, cat] = ""
            if var.get():
                self.df.at[idx, var.get()] = self.df.at[idx, "추출단어"]

    # ================= Navigation =================
    def prev_product(self):
        self.apply_category_changes()
        if self.current_idx > 0:
            self.current_idx -= 1
            self.show_product()

    def next_product(self):
        self.apply_category_changes()
        if self.current_idx < len(self.product_keys) - 1:
            self.current_idx += 1
            self.show_product()

    # ================= Split / Merge =================
    def split_words(self):
        raw = self.merge_word.get().strip()
        selected = [idx for idx, v in self.check_vars if v.get()]

        if not raw or not selected:
            messagebox.showwarning("경고", "단어 입력 + 행 선택 필요")
            return

        # ⭐ [] 안의 단어만 추출
        words = re.findall(r"\[([^\[\]]+)\]", raw)

        if not words:
            messagebox.showwarning("경고", "형식 오류: [asd][df] 형태로 입력하세요")
            return

        insert_idx = min(selected)
        base = self.df.loc[insert_idx].copy()

        # 선택 행 제거
        df_drop = self.df.drop(index=selected)

        # 새 행 생성
        new_rows = []
        for w in words:
            r = base.copy()
            r["추출단어"] = w
            for c in CATEGORIES:
                r[c] = ""
            r["비고"] = "분리" 
            new_rows.append(r)

        # ⭐ 원래 위치에 삽입
        top = df_drop.iloc[:insert_idx]
        bottom = df_drop.iloc[insert_idx:]

        self.df = pd.concat(
            [top, pd.DataFrame(new_rows), bottom],
            ignore_index=True
        )

        self.refresh()

    def merge_words(self):
        word = self.merge_word.get()
        selected = [idx for idx, v in self.check_vars if v.get()]

        if not word or len(selected) < 2:
            messagebox.showwarning("경고", "2개 이상 선택 + 단어 입력")
            return

        selected = sorted(selected)
        insert_idx = selected[0]   # ⭐ 유지할 위치

        base = self.df.loc[insert_idx].copy()
        base["추출단어"] = word
        for c in CATEGORIES:
            base[c] = ""
        base["비고"] = "통합"   

        # 선택된 행 제거
        self.df.drop(index=selected, inplace=True)

        # 위 / 아래 나눠서 끼워넣기
        upper = self.df.loc[self.df.index < insert_idx]
        lower = self.df.loc[self.df.index >= insert_idx]

        self.df = pd.concat(
            [upper, pd.DataFrame([base]), lower],
            ignore_index=True
        )

        self.refresh()

    def refresh(self):
        self.groups = self.df.groupby("상품번호")
        self.product_keys = list(self.groups.groups.keys())
        self.show_product()

    # ================= Save =================
    def save_file(self):
        self.apply_category_changes()

        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[
                ("Excel 파일", "*.xlsx"),
                ("CSV 파일", "*.csv")
            ]
        )

        if not path:
            return

        try:
            if path.endswith(".csv"):
                self.df.to_csv(path, index=False, encoding="utf-8-sig")
            else:
                self.df.to_excel(path, index=False)

            messagebox.showinfo("완료", "저장되었습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"저장 실패:\n{e}")


# ================= Run =================
if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1400x600")
    app = LabelingApp(root)
    root.mainloop()

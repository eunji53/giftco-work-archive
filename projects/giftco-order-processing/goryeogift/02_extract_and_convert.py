import os
import re
import pandas as pd
from PyPDF2 import PdfReader
from tqdm import tqdm

from pdf_parser import parse_items, parse_spec, parse_sender, clean_number
from config import PDF_DIR, ORDERS_XLSX

# 설정 --------------------------------------------------
OUTPUT_PATH = ORDERS_XLSX

TOTAL_RE = re.compile(r"공급가액\s*([\d,]+)\s*VAT\s*([\d,]+)\s*합계\s*([\d,]+)")
ORDER_DATE_RE = re.compile(r"발주일\s*([\d년\s월일]+)")
DUE_DATE_RE = re.compile(r"납\s*기\s*([\d월\s요일]+)")
BUYER_RE = re.compile(r"수신\s*(.+)")


# 메인 --------------------------------------------------
rows = []

for file in tqdm(os.listdir(PDF_DIR)):
    if not file.lower().endswith(".pdf"):
        continue

    fp = os.path.join(PDF_DIR, file)
    reader = PdfReader(fp)

    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""

        order_date = ORDER_DATE_RE.search(text)
        due_date = DUE_DATE_RE.search(text)
        total_match = TOTAL_RE.search(text)
        buyer_match = BUYER_RE.search(text)

        sender_company, sender_name, sender_phone, sender_mobile, sender_addr = parse_sender(text)
        items = parse_items(text)
        spec_text = parse_spec(text)

        for item in items:
            rows.append({
                "파일명": file,
                "페이지": page_num,
                "발주일": order_date.group(1) if order_date else None,
                "납기일": due_date.group(1) if due_date else None,
                "거래처": buyer_match.group(1).strip() if buyer_match else None,
                "총공급가액": clean_number(total_match.group(1)) if total_match else None,
                "총VAT": clean_number(total_match.group(2)) if total_match else None,
                "총합계": clean_number(total_match.group(3)) if total_match else None,
                "발송처 상호": sender_company,
                "발송처 성명": sender_name,
                "발송처 전화": sender_phone,
                "발송처 휴대폰": sender_mobile,
                "발송처 주소": sender_addr,
                "사양": spec_text,
                "품목코드": item["품목코드"],
                "상품명": item["상품명"],
                "수량": item["수량"],
                "단가": item["단가"],
                "공급가액": item["공급가액"],
                "부가세": item["부가세"],
                "합계": item["합계"],
            })

df = pd.DataFrame(rows)
df.to_excel(OUTPUT_PATH, index=False)
print(f"완료: {OUTPUT_PATH} 생성됨 ({len(df)}행)")

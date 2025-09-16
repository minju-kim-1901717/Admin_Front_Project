# dump_products.py
import sqlite3, json, pathlib
# 파일 맨 위 공통
from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).with_name("products.db")  # 이 파일과 같은 폴더의 DB
def get_conn(): return sqlite3.connect(DB_PATH)



DB_PATH = "products.db"   # 필요 시 절대경로로 수정
OUT_PATH = "products.json"

def to_int(val):
    if val is None: return 0
    s = str(val)
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits) if digits else 0

p = pathlib.Path(DB_PATH).resolve()
conn = sqlite3.connect(str(p))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT * FROM products ORDER BY id DESC")
rows = cur.fetchall()
print(f"rows fetched: {len(rows)}")

data = []
for r in rows:
    d = dict(r)
    category = d.get("category", "")
    brand    = d.get("brand", "")
    # product_name 대안까지 커버
    product  = d.get("product_name") or d.get("product") or d.get("name") or ""
    price    = d.get("price")
    price    = price if isinstance(price, int) else to_int(price)
    gender   = d.get("gender") or "공용"

    data.append({
        "category": category,
        "brand": brand,
        "product": product,
        "price": price,
        "gender": gender
    })

conn.close()

pathlib.Path(OUT_PATH).write_text(
    json.dumps(data, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print(f"✅ Wrote {len(data)} items to {pathlib.Path(OUT_PATH).resolve()}")

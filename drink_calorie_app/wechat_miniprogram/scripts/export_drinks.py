"""Export the website SQLite catalog into the bundled mini-program dataset."""

import json
import math
import sqlite3
from pathlib import Path


MINIPROGRAM_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = MINIPROGRAM_DIR.parent
DB_FILE = PROJECT_DIR / "data" / "drinks.db"
OUTPUT_FILE = MINIPROGRAM_DIR / "data" / "drinks.js"

BRAND_CODES = {
    "星巴克": "S",
    "瑞幸": "L",
    "喜茶": "H",
    "霸王茶姬": "B",
    "蜜雪冰城": "M",
    "Manner": "M",
    "古茗": "G",
    "库迪": "C",
}

BRAND_ALIASES = {
    **BRAND_CODES,
    "Starbucks": "S",
    "Luckin": "L",
    "Heytea": "H",
    "HEYTEA": "H",
    "CHAGEE": "B",
    "Mixue": "M",
    "Goodme": "G",
    "Cotti": "C",
}


def clean_number(value):
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def anonymize_text(value):
    text = value or ""
    for brand, code in BRAND_ALIASES.items():
        text = text.replace(brand, code)
    return text


with sqlite3.connect(DB_FILE) as connection:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT
            id, brand, name, name_cn, category, size,
            calories, sugar, fat, protein, caffeine, source_type
        FROM drinks
        WHERE calories IS NOT NULL
        ORDER BY brand, name_cn, name, size
        """
    ).fetchall()


records = []
for row in rows:
    records.append(
        {
            "key": str(row["id"]),
            "brand": BRAND_CODES.get(row["brand"], "O"),
            "name": anonymize_text(row["name"]),
            "nameCn": anonymize_text(row["name_cn"]),
            "category": row["category"] or "其他饮品",
            "size": row["size"] or "",
            "calories": clean_number(row["calories"]),
            "sugar": clean_number(row["sugar"]),
            "fat": clean_number(row["fat"]),
            "protein": clean_number(row["protein"]),
            "caffeine": clean_number(row["caffeine"]),
            "sourceType": row["source_type"] or "unknown",
        }
    )


OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
payload = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
OUTPUT_FILE.write_text(
    "// Generated from data/drinks.db. Do not edit by hand.\n"
    f"module.exports={payload}\n",
    encoding="utf-8",
)
print(f"Exported {len(records)} drinks to {OUTPUT_FILE}")

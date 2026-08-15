import sqlite3
from pathlib import Path

import pandas as pd


# ============================================================
# 1. 项目路径
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

DB_FILE = DATA_DIR / "drinks.db"

CSV_FILE = DATA_DIR / "drinks.csv"


# ============================================================
# 2. 数据库标准字段
# ============================================================

STANDARD_COLUMNS = [
    "brand",
    "name",
    "name_cn",
    "category",
    "size",
    "ounces",
    "calories",
    "sugar",
    "fat",
    "protein",
    "caffeine",
    "carbs",
    "sodium",
    "ingredients",
    "market",
    "spu_code",
    "source",
    "source_url",
    "source_type",
    "source_platform",
    "source_count",
    "calorie_min",
    "calorie_max",
    "discovery_method",
    "scraped_at",
]


NUMERIC_COLUMNS = [
    "ounces",
    "calories",
    "sugar",
    "fat",
    "protein",
    "caffeine",
    "carbs",
    "sodium",
    "source_count",
    "calorie_min",
    "calorie_max",
]


# ============================================================
# 3. 获取数据库连接
# ============================================================

def get_connection():

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(
        str(DB_FILE)
    )

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# 4. 获取已有字段
# ============================================================

def get_existing_columns(connection):

    cursor = connection.cursor()

    cursor.execute(
        """
        PRAGMA table_info(drinks)
        """
    )

    rows = cursor.fetchall()

    return {
        row[1]
        for row in rows
    }


# ============================================================
# 5. 自动升级旧数据库
# ============================================================

def upgrade_database_schema(connection):

    existing_columns = get_existing_columns(
        connection
    )

    columns_to_add = {
        "name_cn": "TEXT",
        "category": "TEXT",
        "size": "TEXT",
        "ounces": "REAL",
        "calories": "REAL",
        "sugar": "REAL",
        "fat": "REAL",
        "protein": "REAL",
        "caffeine": "REAL",
        "carbs": "REAL",
        "sodium": "REAL",
        "ingredients": "TEXT",
        "market": "TEXT",
        "spu_code": "TEXT",
        "source": "TEXT",
        "source_url": "TEXT",
        "source_type": "TEXT",
        "source_platform": "TEXT",
        "source_count": "INTEGER",
        "calorie_min": "REAL",
        "calorie_max": "REAL",
        "discovery_method": "TEXT",
        "scraped_at": "TEXT",
    }

    cursor = connection.cursor()

    for column, sql_type in columns_to_add.items():

        if column in existing_columns:
            continue

        print(
            f"🔧 添加数据库字段：{column}"
        )

        cursor.execute(
            f"""
            ALTER TABLE drinks
            ADD COLUMN {column} {sql_type}
            """
        )

    connection.commit()


# ============================================================
# 6. 初始化数据库
# ============================================================

def init_database():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS drinks (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            brand TEXT NOT NULL,

            name TEXT NOT NULL,

            name_cn TEXT,

            category TEXT,

            size TEXT,

            ounces REAL,

            calories REAL,

            sugar REAL,

            fat REAL,

            protein REAL,

            caffeine REAL,

            carbs REAL,

            sodium REAL,

            ingredients TEXT,

            market TEXT,

            spu_code TEXT,

            source TEXT,

            source_url TEXT,

            source_type TEXT,

            source_platform TEXT,

            source_count INTEGER,

            calorie_min REAL,

            calorie_max REAL,

            discovery_method TEXT,

            scraped_at TEXT
        )
        """
    )

    connection.commit()

    upgrade_database_schema(
        connection
    )

    # --------------------------------------------------------
    # 索引
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_drinks_brand
        ON drinks(brand)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_drinks_category
        ON drinks(category)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_drinks_calories
        ON drinks(calories)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_drinks_source_type
        ON drinks(source_type)
        """
    )

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_drinks_source_url
        ON drinks(source_url)
        WHERE source_url IS NOT NULL
        AND source_url != ''
        """
    )

    connection.commit()

    connection.close()


# ============================================================
# 7. 清理普通值
# ============================================================

def clean_value(value):

    if pd.isna(value):
        return None

    return str(value) if not isinstance(
        value,
        (int, float)
    ) else value


# ============================================================
# 8. 清理数字
# ============================================================

def clean_number(value):

    if pd.isna(value):
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError
    ):
        return None


# ============================================================
# 9. 标准化 DataFrame
# ============================================================

def normalize_dataframe(df):

    df = df.copy()

    # --------------------------------------------------------
    # 补齐字段
    # --------------------------------------------------------

    for column in STANDARD_COLUMNS:

        if column not in df.columns:

            df[column] = None

    # --------------------------------------------------------
    # 数值字段
    # --------------------------------------------------------

    for column in NUMERIC_COLUMNS:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # --------------------------------------------------------
    # source_type 自动判断
    # --------------------------------------------------------

    df["source_type"] = (
        df["source_type"]
        .fillna("")
        .astype(str)
    )

    for index in df.index:

        if df.at[
            index,
            "source_type"
        ]:

            continue

        source = str(
            df.at[
                index,
                "source"
            ]
        ).lower()

        if "official" in source:

            df.at[
                index,
                "source_type"
            ] = "official"

        elif (
            "third" in source
            or "第三方" in source
        ):

            df.at[
                index,
                "source_type"
            ] = "third_party"

        else:

            df.at[
                index,
                "source_type"
            ] = "unknown"

    # --------------------------------------------------------
    # source_url
    # --------------------------------------------------------

    df["source_url"] = (
        df["source_url"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # --------------------------------------------------------
    # 没有 URL 的旧测试数据生成内部唯一 key
    # --------------------------------------------------------

    missing_url_mask = (
        df["source_url"]
        ==
        ""
    )

    for index in df[
        missing_url_mask
    ].index:

        brand = str(
            df.at[index, "brand"]
        )

        name = str(
            df.at[index, "name"]
        )

        size = str(
            df.at[index, "size"]
        )

        df.at[
            index,
            "source_url"
        ] = (
            f"legacy://"
            f"{brand}/"
            f"{name}/"
            f"{size}"
        )

    return df[
        STANDARD_COLUMNS
    ]


# ============================================================
# 10. 保存饮品
#
# 这就是 luckin_thirdparty.py 要导入的 save_drinks()
# ============================================================

def save_drinks(
        drinks,
        export_csv=True,
        replace_products=False,
):

    if not drinks:

        print(
            "ℹ️ 没有新饮品数据需要保存。"
        )

        return

    init_database()

    df = pd.DataFrame(
        drinks
    )

    df = normalize_dataframe(
        df
    )

    connection = get_connection()

    cursor = connection.cursor()

    # 覆盖模式按“品牌 + 商品名”先删除旧记录，
    # 避免来源 URL 变化后保留同一商品的历史副本。
    if replace_products:

        for _, row in df.iterrows():

            brand = clean_value(
                row["brand"]
            )

            name_cn = clean_value(
                row["name_cn"]
            )

            name = clean_value(
                row["name"]
            )

            if name_cn:

                cursor.execute(
                    """
                    DELETE FROM drinks
                    WHERE brand = ?
                    AND TRIM(COALESCE(name_cn, '')) = ?
                    """,
                    (
                        brand,
                        name_cn,
                    ),
                )

            elif name:

                cursor.execute(
                    """
                    DELETE FROM drinks
                    WHERE brand = ?
                    AND TRIM(COALESCE(name, '')) = ?
                    """,
                    (
                        brand,
                        name,
                    ),
                )

    sql = """
    INSERT INTO drinks (

        brand,
        name,
        name_cn,
        category,
        size,
        ounces,
        calories,
        sugar,
        fat,
        protein,
        caffeine,
        carbs,
        sodium,
        ingredients,
        market,
        spu_code,
        source,
        source_url,
        source_type,
        source_platform,
        source_count,
        calorie_min,
        calorie_max,
        discovery_method,
        scraped_at

    )

    VALUES (

        ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?

    )

    ON CONFLICT(source_url)

    DO UPDATE SET

        brand =
            excluded.brand,

        name =
            excluded.name,

        name_cn =
            excluded.name_cn,

        category =
            excluded.category,

        size =
            excluded.size,

        ounces =
            excluded.ounces,

        calories =
            excluded.calories,

        sugar =
            excluded.sugar,

        fat =
            excluded.fat,

        protein =
            excluded.protein,

        caffeine =
            excluded.caffeine,

        carbs =
            excluded.carbs,

        sodium =
            excluded.sodium,

        ingredients =
            excluded.ingredients,

        market =
            excluded.market,

        spu_code =
            excluded.spu_code,

        source =
            excluded.source,

        source_type =
            excluded.source_type,

        source_platform =
            excluded.source_platform,

        source_count =
            excluded.source_count,

        calorie_min =
            excluded.calorie_min,

        calorie_max =
            excluded.calorie_max,

        discovery_method =
            excluded.discovery_method,

        scraped_at =
            excluded.scraped_at
    """

    for _, row in df.iterrows():

        cursor.execute(
            sql,
            (
                clean_value(
                    row["brand"]
                ),

                clean_value(
                    row["name"]
                ),

                clean_value(
                    row["name_cn"]
                ),

                clean_value(
                    row["category"]
                ),

                clean_value(
                    row["size"]
                ),

                clean_number(
                    row["ounces"]
                ),

                clean_number(
                    row["calories"]
                ),

                clean_number(
                    row["sugar"]
                ),

                clean_number(
                    row["fat"]
                ),

                clean_number(
                    row["protein"]
                ),

                clean_number(
                    row["caffeine"]
                ),

                clean_number(
                    row["carbs"]
                ),

                clean_number(
                    row["sodium"]
                ),

                clean_value(
                    row["ingredients"]
                ),

                clean_value(
                    row["market"]
                ),

                clean_value(
                    row["spu_code"]
                ),

                clean_value(
                    row["source"]
                ),

                clean_value(
                    row["source_url"]
                ),

                clean_value(
                    row["source_type"]
                ),

                clean_value(
                    row["source_platform"]
                ),

                clean_number(
                    row["source_count"]
                ),

                clean_number(
                    row["calorie_min"]
                ),

                clean_number(
                    row["calorie_max"]
                ),

                clean_value(
                    row["discovery_method"]
                ),

                clean_value(
                    row["scraped_at"]
                ),
            )
        )

    connection.commit()

    connection.close()

    print(
        f"✅ SQLite 写入完成："
        f"{len(df)} 条"
    )

    if export_csv:

        export_database_to_csv()


# ============================================================
# 11. SQLite -> CSV
# ============================================================

def export_database_to_csv():

    init_database()

    connection = get_connection()

    df = pd.read_sql_query(
        """
        SELECT

            brand,
            name,
            name_cn,
            category,
            size,
            ounces,
            calories,
            sugar,
            fat,
            protein,
            caffeine,
            carbs,
            sodium,
            ingredients,
            market,
            spu_code,
            source,
            source_url,
            source_type,
            source_platform,
            source_count,
            calorie_min,
            calorie_max,
            discovery_method,
            scraped_at

        FROM drinks

        ORDER BY
            calories DESC
        """,
        connection
    )

    connection.close()

    df.to_csv(
        str(CSV_FILE),
        index=False,
        encoding="utf-8-sig"
    )

    print(
        f"✅ CSV 已从 SQLite 更新："
        f"{CSV_FILE}"
    )


# ============================================================
# 12. CSV -> SQLite
# ============================================================

def migrate_csv_to_sqlite():

    if not CSV_FILE.exists():

        print(
            f"❌ 找不到 CSV："
            f"{CSV_FILE}"
        )

        return

    try:

        df = pd.read_csv(
            str(CSV_FILE)
        )

    except (
        pd.errors.EmptyDataError,
        pd.errors.ParserError
    ):

        print(
            "❌ drinks.csv 读取失败。"
        )

        return

    if df.empty:

        print(
            "ℹ️ drinks.csv 为空。"
        )

        return

    df = normalize_dataframe(
        df
    )

    records = (
        df
        .where(
            pd.notna(df),
            None
        )
        .to_dict(
            orient="records"
        )
    )

    save_drinks(
        records,
        export_csv=False
    )

    print(
        f"✅ CSV → SQLite 完成："
        f"{len(records)} 条"
    )


# ============================================================
# 13. 读取全部饮品
# ============================================================

def load_drinks():

    init_database()

    connection = get_connection()

    df = pd.read_sql_query(
        """
        SELECT *
        FROM drinks
        """,
        connection
    )

    connection.close()

    return df


# ============================================================
# 14. 按品牌读取
# ============================================================

def load_drinks_by_brand(
        brand
):

    init_database()

    connection = get_connection()

    df = pd.read_sql_query(
        """
        SELECT *
        FROM drinks
        WHERE brand = ?
        """,
        connection,
        params=[
            brand
        ]
    )

    connection.close()

    return df


# ============================================================
# 15. 搜索饮品
# ============================================================

def search_drinks(
        keyword
):

    init_database()

    connection = get_connection()

    pattern = (
        f"%{keyword}%"
    )

    df = pd.read_sql_query(
        """
        SELECT *

        FROM drinks

        WHERE

            name LIKE ?

            OR name_cn LIKE ?

            OR brand LIKE ?

            OR category LIKE ?

            OR ingredients LIKE ?

        ORDER BY calories DESC
        """,
        connection,
        params=[
            pattern,
            pattern,
            pattern,
            pattern,
            pattern,
        ]
    )

    connection.close()

    return df


# ============================================================
# 16. 数据库统计
# ============================================================

def get_database_stats():

    init_database()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM drinks
        """
    )

    total = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(DISTINCT brand)
        FROM drinks
        """
    )

    brands = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT AVG(calories)
        FROM drinks
        WHERE calories IS NOT NULL
        """
    )

    average_calories = (
        cursor.fetchone()[0]
    )

    connection.close()

    return {
        "total": total,
        "brands": brands,
        "average_calories":
            average_calories,
    }


# ============================================================
# 17. 直接运行 database.py
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)

    print(
        "🗄️ 饮品 SQLite 数据库"
    )

    print("=" * 60)

    init_database()

    migrate_csv_to_sqlite()

    stats = get_database_stats()

    print()
    print("=" * 60)

    print(
        "📊 数据库统计"
    )

    print("=" * 60)

    print(
        f"饮品数量："
        f"{stats['total']}"
    )

    print(
        f"品牌数量："
        f"{stats['brands']}"
    )

    if (
        stats[
            "average_calories"
        ]
        is not None
    ):

        print(
            f"平均热量："
            f"{stats['average_calories']:.1f} kcal"
        )

    print()
    print(
        f"✅ 数据库位置："
        f"{DB_FILE}"
    )

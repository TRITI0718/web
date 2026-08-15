from pathlib import Path
import sqlite3

import pandas as pd


# ============================================================
# 1. 路径
# ============================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

DATA_DIR = (
    BASE_DIR
    /
    "data"
)

PRODUCT_FILE = (
    DATA_DIR
    /
    "product_names.csv"
)

PRODUCT_BACKUP_FILE = (
    DATA_DIR
    /
    "product_names_backup.csv"
)

DB_FILE = (
    DATA_DIR
    /
    "drinks.db"
)


# ============================================================
# 2. 商品表字段
# ============================================================

PRODUCT_COLUMNS = [
    "brand",
    "name_cn",
    "name_en",
    "category",
    "enabled",
]


# ============================================================
# 3. 创建空商品表
# ============================================================

def create_empty_product_df():

    return pd.DataFrame(
        columns=PRODUCT_COLUMNS
    )


# ============================================================
# 4. 确保文件存在
# ============================================================

def ensure_product_file():

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    if not PRODUCT_FILE.exists():

        create_empty_product_df().to_csv(
            PRODUCT_FILE,
            index=False,
            encoding="utf-8-sig"
        )


# ============================================================
# 5. 读取商品表
# ============================================================

def load_products():

    ensure_product_file()

    try:

        df = pd.read_csv(
            PRODUCT_FILE
        )

    except pd.errors.EmptyDataError:

        return create_empty_product_df()


    for column in PRODUCT_COLUMNS:

        if column not in df.columns:

            if column == "enabled":

                df[column] = 1

            else:

                df[column] = ""


    df = df[
        PRODUCT_COLUMNS
    ].copy()


    for column in [
        "brand",
        "name_cn",
        "name_en",
        "category",
    ]:

        df[column] = (
            df[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )


    df["enabled"] = pd.to_numeric(
        df["enabled"],
        errors="coerce"
    ).fillna(1)

    df["enabled"] = (
        df["enabled"] != 0
    ).astype(int)


    return df


# ============================================================
# 6. 商品表清洗
# ============================================================

def clean_products(df):

    if df is None:

        return create_empty_product_df()


    df = df.copy()


    for column in PRODUCT_COLUMNS:

        if column not in df.columns:

            if column == "enabled":

                df[column] = 1

            else:

                df[column] = ""


    df = df[
        PRODUCT_COLUMNS
    ].copy()


    for column in [
        "brand",
        "name_cn",
        "name_en",
        "category",
    ]:

        df[column] = (
            df[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )


    # 删除没有品牌或名称的行
    df = df[
        (
            df["brand"] != ""
        )
        &
        (
            df["name_cn"] != ""
        )
    ].copy()


    df["enabled"] = pd.to_numeric(
        df["enabled"],
        errors="coerce"
    ).fillna(1)

    df["enabled"] = (
        df["enabled"] != 0
    ).astype(int)


    # 同品牌中文名称唯一
    df = df.drop_duplicates(
        subset=[
            "brand",
            "name_cn",
        ],
        keep="last"
    )


    df = df.sort_values(
        [
            "brand",
            "category",
            "name_cn",
        ]
    ).reset_index(
        drop=True
    )


    return df


# ============================================================
# 7. 保存商品表
# ============================================================

def save_products(df):

    df = clean_products(
        df
    )


    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    # 备份旧文件
    if PRODUCT_FILE.exists():

        try:

            old_df = pd.read_csv(
                PRODUCT_FILE
            )

            old_df.to_csv(
                PRODUCT_BACKUP_FILE,
                index=False,
                encoding="utf-8-sig"
            )

        except Exception:

            pass


    df.to_csv(
        PRODUCT_FILE,
        index=False,
        encoding="utf-8-sig"
    )


    return df


# ============================================================
# 8. 商品统计
# ============================================================

def get_product_stats(df):

    if df is None or df.empty:

        return {
            "total": 0,
            "enabled": 0,
            "disabled": 0,
            "brands": 0,
        }


    total = len(
        df
    )

    enabled = int(
        (
            df["enabled"] == 1
        ).sum()
    )


    return {
        "total":
            total,

        "enabled":
            enabled,

        "disabled":
            total - enabled,

        "brands":
            int(
                df[
                    "brand"
                ]
                .nunique()
            ),
    }


# ============================================================
# 9. 判断 drinks 表是否存在
# ============================================================

def _drinks_table_exists(
        connection
):

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        AND name='drinks'
        """
    )

    return (
        cursor.fetchone()
        is not None
    )


# ============================================================
# 10. 从数据库读取现有饮品
# ============================================================

def load_database_drinks():

    if not DB_FILE.exists():

        return pd.DataFrame()


    connection = sqlite3.connect(
        DB_FILE
    )


    try:

        if not _drinks_table_exists(
            connection
        ):

            return pd.DataFrame()


        return pd.read_sql_query(
            """
            SELECT *
            FROM drinks
            """,
            connection
        )

    finally:

        connection.close()


# ============================================================
# 11. 商品表与数据库同步
#
# 商品表为唯一真源。
#
# 删除规则：
# 1. product_names.csv 已不存在 → 删除 DB 旧记录
# 2. enabled=0 → 不删除，但排行榜会隐藏
# 3. 商品改名后旧名不存在 → 自动删除旧名
# ============================================================

def sync_database_with_products(
        products_df=None
):

    if products_df is None:

        products_df = load_products()


    products_df = clean_products(
        products_df
    )


    if not DB_FILE.exists():

        return {
            "database_exists": False,
            "before": 0,
            "after": 0,
            "removed": 0,
        }


    connection = sqlite3.connect(
        DB_FILE
    )


    try:

        if not _drinks_table_exists(
            connection
        ):

            return {
                "database_exists": True,
                "before": 0,
                "after": 0,
                "removed": 0,
            }


        db_df = pd.read_sql_query(
            """
            SELECT *
            FROM drinks
            """,
            connection
        )


        if db_df.empty:

            return {
                "database_exists": True,
                "before": 0,
                "after": 0,
                "removed": 0,
            }


        before = len(
            db_df
        )


        # ====================================================
        # product_names.csv 里的合法品牌+中文名
        # ====================================================

        allowed_pairs = set(
            zip(
                products_df[
                    "brand"
                ].astype(str),
                products_df[
                    "name_cn"
                ].astype(str),
            )
        )


        # ====================================================
        # 星巴克如果仍然不是人工商品表管理，
        # 可以保留其原有官方数据。
        #
        # 如果 product_names.csv 中已经包含星巴克，
        # 则同样由商品表管理。
        # ====================================================

        managed_brands = set(
            products_df[
                "brand"
            ]
            .astype(str)
            .unique()
        )


        keep_mask = []


        for _, row in db_df.iterrows():

            brand = str(
                row.get(
                    "brand",
                    ""
                )
            ).strip()

            name_cn = str(
                row.get(
                    "name_cn",
                    ""
                )
            ).strip()


            # ------------------------------------------------
            # 不在人工商品表管理范围的品牌保留
            # ------------------------------------------------

            if brand not in managed_brands:

                keep_mask.append(
                    True
                )

                continue


            # ------------------------------------------------
            # 人工管理品牌必须存在于商品表
            # ------------------------------------------------

            keep_mask.append(
                (
                    brand,
                    name_cn,
                )
                in
                allowed_pairs
            )


        clean_db_df = (
            db_df[
                keep_mask
            ]
            .copy()
        )


        removed = (
            before
            -
            len(
                clean_db_df
            )
        )


        # ====================================================
        # 只有真的发生变化才重写
        # ====================================================

        if removed > 0:

            cursor = connection.cursor()

            cursor.execute(
                """
                DELETE FROM drinks
                """
            )

            connection.commit()


            if "id" in clean_db_df.columns:

                clean_db_df = (
                    clean_db_df.drop(
                        columns=[
                            "id"
                        ]
                    )
                )


            if not clean_db_df.empty:

                clean_db_df.to_sql(
                    "drinks",
                    connection,
                    if_exists="append",
                    index=False
                )


            connection.commit()


        return {
            "database_exists":
                True,

            "before":
                before,

            "after":
                len(
                    clean_db_df
                ),

            "removed":
                removed,
        }


    finally:

        connection.close()


# ============================================================
# 12. 获取启用商品 key
# ============================================================

def get_enabled_product_keys(
        products_df=None
):

    if products_df is None:

        products_df = load_products()


    enabled_df = (
        products_df[
            products_df[
                "enabled"
            ]
            ==
            1
        ]
    )


    return set(
        zip(
            enabled_df[
                "brand"
            ].astype(str),
            enabled_df[
                "name_cn"
            ].astype(str),
        )
    )


# ============================================================
# 13. 商品是否启用
# ============================================================

def is_product_enabled(
        brand,
        name_cn,
        products_df=None,
):

    keys = get_enabled_product_keys(
        products_df
    )

    return (
        str(
            brand
        ).strip(),
        str(
            name_cn
        ).strip(),
    ) in keys
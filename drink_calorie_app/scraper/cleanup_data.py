import re
import sqlite3
from pathlib import Path

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

DB_FILE = (
    BASE_DIR
    /
    "data"
    /
    "drinks.db"
)


# ============================================================
# 2. 脏名称关键词
# ============================================================

DIRTY_PHRASES = [

    # 瑞幸营销文案
    "all rights reserved",
    "classic vanilla flavor",
    "smooth and velvety",
    "double enjoyment",
    "made with",
    "special selection",
    "premium vanilla",
    "flavor from madagascar",
    "brought to you",
    "indulge in",
    "consumer repurchase",
    "buttery aroma",
    "nutty fragrance",

    # 通用网站文字
    "privacy policy",
    "terms of use",
    "contact us",
    "download",
    "copyright",
    "about us",
    "brand story",

    # 页面栏目
    "our products",
    "product strength",
    "signature lattes",
]


# ============================================================
# 3. 判断名称是不是脏数据
# ============================================================

def is_dirty_name(
        name
):

    if name is None:
        return True

    name = str(
        name
    ).strip()

    if not name:
        return True


    lower = (
        name.lower()
    )


    # ========================================================
    # 营销文案
    # ========================================================

    if any(
        phrase in lower
        for phrase in DIRTY_PHRASES
    ):

        return True


    # ========================================================
    # 太长
    # ========================================================

    if len(name) > 80:

        return True


    # ========================================================
    # URL / copyright
    # ========================================================

    if re.search(
        r"https?://|www\.|©",
        name,
        re.IGNORECASE
    ):

        return True


    # ========================================================
    # 明显完整广告句
    # ========================================================

    if (
        name.endswith(
            "."
        )
        and
        len(
            name.split()
        )
        >=
        4
    ):

        return True


    # ========================================================
    # 等式式营销文案
    # ========================================================

    if "=" in name:

        return True


    return False


# ============================================================
# 4. 判断热量是否明显异常
# ============================================================

def is_bad_calorie(
        value
):

    if value is None:
        return False

    try:

        value = float(
            value
        )

    except (
        TypeError,
        ValueError
    ):

        return True


    # 整杯饮品基本范围
    if value < 0:
        return True


    if value > 800:
        return True


    return False


# ============================================================
# 5. 主清理函数
# ============================================================

def cleanup_database():

    if not DB_FILE.exists():

        print(
            f"❌ 找不到数据库：{DB_FILE}"
        )

        return


    connection = sqlite3.connect(
        str(DB_FILE)
    )


    df = pd.read_sql_query(
        """
        SELECT *
        FROM drinks
        """,
        connection
    )


    if df.empty:

        print(
            "ℹ️ 数据库为空。"
        )

        connection.close()

        return


    print()
    print("=" * 70)
    print("🧹 开始清理旧脏数据")
    print("=" * 70)

    print(
        f"清理前：{len(df)} 条"
    )


    # ========================================================
    # A. 标记脏名称
    # ========================================================

    dirty_mask = (
        df["name"]
        .apply(
            is_dirty_name
        )
    )


    # name_cn 只有在明显营销文案时删除
    if "name_cn" in df.columns:

        dirty_mask |= (
            df[
                "name_cn"
            ]
            .fillna("")
            .apply(
                lambda value:
                    (
                        bool(value)
                        and
                        is_dirty_name(
                            value
                        )
                    )
            )
        )


    # ========================================================
    # B. 热量异常
    # ========================================================

    if "calories" in df.columns:

        dirty_mask |= (
            df[
                "calories"
            ]
            .apply(
                is_bad_calorie
            )
        )


    dirty_df = (
        df[
            dirty_mask
        ]
    )


    clean_df = (
        df[
            ~dirty_mask
        ]
        .copy()
    )


    print(
        f"发现明显脏数据："
        f"{len(dirty_df)} 条"
    )


    # ========================================================
    # C. 打印准备删除的数据
    # ========================================================

    if not dirty_df.empty:

        print()
        print(
            "准备删除："
        )


        for _, row in dirty_df.iterrows():

            print(
                f"  ❌ "
                f"{row.get('brand', '')} | "
                f"{row.get('name_cn', '')} | "
                f"{row.get('name', '')} | "
                f"{row.get('calories', '')}"
            )


    # ========================================================
    # D. 同品牌同名称去重
    #
    # 保留 scraped_at 最新的一条
    # ========================================================

    clean_df[
        "_dedup_name"
    ] = (
        clean_df[
            "name_cn"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
    )


    missing_cn = (
        clean_df[
            "_dedup_name"
        ]
        ==
        ""
    )


    clean_df.loc[
        missing_cn,
        "_dedup_name"
    ] = (
        clean_df.loc[
            missing_cn,
            "name"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
    )


    if "scraped_at" in clean_df.columns:

        clean_df[
            "_scraped_time"
        ] = pd.to_datetime(
            clean_df[
                "scraped_at"
            ],
            errors="coerce"
        )


        clean_df = (
            clean_df
            .sort_values(
                "_scraped_time",
                ascending=False
            )
        )


    before_dedup = len(
        clean_df
    )


    clean_df = (
        clean_df
        .drop_duplicates(
            subset=[
                "brand",
                "_dedup_name",
            ],
            keep="first"
        )
    )


    duplicates_removed = (
        before_dedup
        -
        len(clean_df)
    )


    print(
        f"删除重复数据："
        f"{duplicates_removed} 条"
    )


    # ========================================================
    # E. 删除辅助列
    # ========================================================

    clean_df = clean_df.drop(
        columns=[
            "_dedup_name",
            "_scraped_time",
        ],
        errors="ignore"
    )


    # ========================================================
    # F. 直接重建 drinks 数据
    # ========================================================

    cursor = connection.cursor()


    cursor.execute(
        """
        DELETE FROM drinks
        """
    )


    connection.commit()


    # id 让 SQLite 重新生成
    if "id" in clean_df.columns:

        clean_df = clean_df.drop(
            columns=[
                "id"
            ]
        )


    clean_df.to_sql(
        "drinks",
        connection,
        if_exists="append",
        index=False
    )


    connection.commit()


    # ========================================================
    # G. 重置自增编号
    # ========================================================

    try:

        cursor.execute(
            """
            DELETE FROM sqlite_sequence
            WHERE name='drinks'
            """
        )

        connection.commit()

    except sqlite3.OperationalError:

        pass


    connection.close()


    print()
    print("=" * 70)

    print(
        "✅ 数据清理完成"
    )

    print("=" * 70)

    print(
        f"清理前："
        f"{len(df)}"
    )

    print(
        f"删除脏数据："
        f"{len(dirty_df)}"
    )

    print(
        f"删除重复："
        f"{duplicates_removed}"
    )

    print(
        f"剩余："
        f"{len(clean_df)}"
    )

    print(
        f"数据库："
        f"{DB_FILE}"
    )


# ============================================================
# 6. 程序入口
# ============================================================

if __name__ == "__main__":

    cleanup_database()
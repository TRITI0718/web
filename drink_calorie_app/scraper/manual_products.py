from pathlib import Path
import pandas as pd

from database.database import (
    load_drinks,
    save_drinks,
)

from scraper.base_scraper import (
    search_and_aggregate_all_sources,
    build_third_party_record,
    save_evidence_debug,
)

from utils.product_manager import (
    load_products,
    sync_database_with_products,
)


# ============================================================
# 1. 路径
# ============================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)


# ============================================================
# 2. 配置
# ============================================================

# None = 全部
ONLY_BRAND = None

# 所有查询默认覆盖刷新
FORCE_REFRESH = True


# ============================================================
# 3. 读取启用商品
# ============================================================

def load_enabled_products():

    df = load_products()


    df = df[
        df[
            "enabled"
        ]
        ==
        1
    ].copy()


    if ONLY_BRAND:

        df = df[
            df[
                "brand"
            ]
            ==
            ONLY_BRAND
        ].copy()


    return df


# ============================================================
# 4. 构造搜索词
# ============================================================

def build_queries(
        brand,
        name_cn,
        name_en="",
):

    queries = [
        f"{brand} {name_cn} 热量 kcal",
        f"{brand} {name_cn} 大卡",
        f"{brand} {name_cn} 卡路里",
        f"{brand} {name_cn} 营养",
        f"{brand} {name_cn} 减脂 热量",
        f"{brand} {name_cn} 一杯多少卡",
    ]


    english_brand_map = {
        "瑞幸":
            "Luckin Coffee",

        "喜茶":
            "HEYTEA",

        "蜜雪冰城":
            "MIXUE",

        "星巴克":
            "Starbucks",
    }


    if name_en:

        english_brand = (
            english_brand_map.get(
                brand,
                brand
            )
        )


        queries.extend(
            [
                f"{english_brand} "
                f"{name_en} calories",

                f"{english_brand} "
                f"{name_en} kcal",
            ]
        )


    return queries


# ============================================================
# 5. 判断数据库记录是否需要刷新
# ============================================================

def record_needs_refresh(
        existing_df,
        brand,
        name_cn,
        name_en="",
):
    return True


# ============================================================
# 6. 搜索单商品
# ============================================================

def collect_product(
        brand,
        name_cn,
        name_en,
        category,
):

    print()
    print("=" * 70)

    print(
        f"🥤 {brand} | {name_cn}"
    )

    print("=" * 70)


    queries = build_queries(
        brand=brand,
        name_cn=name_cn,
        name_en=name_en,
    )


    result = (
        search_and_aggregate_all_sources(

            brand=
                brand,

            name_cn=
                name_cn,

            name_en=
                name_en,

            search_queries=
                queries,

            max_results=
                10,

            delay=
                0.6,
        )
    )


    if not result:

        print(
            "⚠️ 未找到可靠热量"
        )

        return None


    print()
    print(
        f"✅ 热量："
        f"{result['estimate']} kcal"
    )

    print(
        f"   来源："
        f"{result['source_count']}"
    )

    print(
        f"   范围："
        f"{result['calorie_min']}"
        " - "
        f"{result['calorie_max']} kcal"
    )


    save_evidence_debug(
        brand=brand,
        product_name=name_cn,
        aggregation_result=result,
    )


    return build_third_party_record(

        brand=
            brand,

        name=
            name_en
            or
            name_cn,

        name_cn=
            name_cn,

        category=
            category,

        aggregation_result=
            result,

        market=
            "China",

        discovery_method=(
            "manual_product_list"
            "+social_search"
            "+public_web"
        ),
    )


# ============================================================
# 7. 主程序
# ============================================================

def main():

    print()
    print("=" * 70)

    print(
        "📋 人工商品表热量采集器"
    )

    print("=" * 70)


    # ========================================================
    # 先把数据库与商品表同步
    # ========================================================

    products_df = load_products()


    sync_result = (
        sync_database_with_products(
            products_df
        )
    )


    if sync_result[
        "removed"
    ] > 0:

        print(
            f"🧹 已自动清除 "
            f"{sync_result['removed']} 条"
            f"不再存在的旧商品数据"
        )


    products = (
        products_df[
            products_df[
                "enabled"
            ]
            ==
            1
        ]
        .copy()
    )


    if ONLY_BRAND:

        products = products[
            products[
                "brand"
            ]
            ==
            ONLY_BRAND
        ].copy()


    if products.empty:

        print(
            "ℹ️ 没有需要处理的启用商品。"
        )

        return


    print(
        f"✅ 启用商品："
        f"{len(products)}"
    )


    existing_df = (
        load_drinks()
    )


    collected = []

    skipped = 0

    failed = 0

    total = len(
        products
    )


    # ========================================================
    # 循环
    # ========================================================

    for index, row in enumerate(
        products.itertuples(
            index=False
        ),
        start=1
    ):

        brand = str(
            row.brand
        ).strip()

        name_cn = str(
            row.name_cn
        ).strip()

        name_en = str(
            row.name_en
        ).strip()

        category = str(
            row.category
        ).strip()


        print()
        print(
            f"[{index}/{total}] "
            f"{brand} | {name_cn}"
        )


        # ====================================================
        # 是否需要刷新
        # ====================================================

        if not record_needs_refresh(
            existing_df=existing_df,
            brand=brand,
            name_cn=name_cn,
            name_en=name_en,
        ):

            skipped += 1

            print("⏭️ 当前商品无需更新")

            continue


        # ====================================================
        # 抓取
        # ====================================================

        try:

            record = collect_product(
                brand=brand,
                name_cn=name_cn,
                name_en=name_en,
                category=category,
            )


            if record:

                collected.append(
                    record
                )


                # --------------------------------------------
                # 立刻加入 existing_df，
                # 防止同一次运行重复处理
                # --------------------------------------------

                new_row = pd.DataFrame(
                    [
                        record
                    ]
                )


                existing_df = pd.concat(
                    [
                        existing_df,
                        new_row,
                    ],
                    ignore_index=True
                )


            else:

                failed += 1


        except Exception as error:

            failed += 1

            print(
                f"❌ {name_cn}："
                f"{error}"
            )


    # ========================================================
    # 保存
    # ========================================================

    if collected:

        save_drinks(
            collected,
            export_csv=True,
            replace_products=True,
        )


    print()
    print("=" * 70)

    print(
        "📊 本轮完成"
    )

    print("=" * 70)

    print(
        f"启用商品："
        f"{total}"
    )

    print(
        f"新增/刷新："
        f"{len(collected)}"
    )

    print(
        f"近期跳过："
        f"{skipped}"
    )

    print(
        f"失败："
        f"{failed}"
    )


if __name__ == "__main__":

    main()

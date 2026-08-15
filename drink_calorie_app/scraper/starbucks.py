import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

from starbucks_products import discover_starbucks_products


# ============================================================
# 1. 项目路径
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

DATA_FILE = DATA_DIR / "drinks.csv"

FAILED_FILE = DATA_DIR / "starbucks_failed.csv"


# ============================================================
# 2. 爬虫配置
# ============================================================

# ------------------------------------------------------------
# None = 抓取发现的所有产品
#
# 调试时可以改成：
# MAX_PRODUCTS = 10
# ------------------------------------------------------------

MAX_PRODUCTS = None


# ------------------------------------------------------------
# 是否强制重新抓取所有饮品
#
# False：
#   最近抓过的数据直接跳过
#
# True：
#   无论是否存在，都重新抓取
# ------------------------------------------------------------

FORCE_REFRESH = False


# ------------------------------------------------------------
# 数据超过多少天以后重新抓取
#
# 例如：
# REFRESH_DAYS = 30
#
# 30 天以内的数据不会重复抓
# ------------------------------------------------------------

REFRESH_DAYS = 30


# ------------------------------------------------------------
# 单个产品失败后的最大尝试次数
# ------------------------------------------------------------

MAX_RETRIES = 3


# ------------------------------------------------------------
# 每次正常请求之间暂停
# ------------------------------------------------------------

REQUEST_DELAY = 0.8


# ------------------------------------------------------------
# 失败重试前暂停
# ------------------------------------------------------------

RETRY_DELAY = 2


# ------------------------------------------------------------
# 每成功抓多少条，就保存一次
#
# 防止运行到一半退出导致前面数据丢失
# ------------------------------------------------------------

SAVE_EVERY = 5


# ------------------------------------------------------------
# Playwright 页面设置
# ------------------------------------------------------------

PAGE_TIMEOUT = 60000

RENDER_WAIT = 2500


# ============================================================
# 3. 通用数字提取
# ============================================================

def search_number(patterns, text):

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            try:
                return float(match.group(1))

            except ValueError:
                return None

    return None


# ============================================================
# 4. 热量
# ============================================================

def extract_calories(text):

    return search_number(
        [
            r"Calories\s+(\d+(?:\.\d+)?)",
            r"Calories\s*:\s*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s+calories",
        ],
        text
    )


# ============================================================
# 5. 糖
# ============================================================

def extract_sugar(text):

    return search_number(
        [
            r"Total Sugars\s+(\d+(?:\.\d+)?)\s*g",
            r"Sugars\s+(\d+(?:\.\d+)?)\s*g",
            r"Sugar\s+(\d+(?:\.\d+)?)\s*g",
            r"(\d+(?:\.\d+)?)\s*g\s+sugar",
        ],
        text
    )


# ============================================================
# 6. 脂肪
# ============================================================

def extract_fat(text):

    return search_number(
        [
            r"Total Fat\s+(\d+(?:\.\d+)?)\s*g",
            r"Fat\s+(\d+(?:\.\d+)?)\s*g",
            r"(\d+(?:\.\d+)?)\s*g\s+fat",
        ],
        text
    )


# ============================================================
# 7. 蛋白质
# ============================================================

def extract_protein(text):

    return search_number(
        [
            r"Protein\s+(\d+(?:\.\d+)?)\s*g",
            r"(\d+(?:\.\d+)?)\s*g\s+protein",
        ],
        text
    )


# ============================================================
# 8. 咖啡因
# ============================================================

def extract_caffeine(text):

    return search_number(
        [
            r"Caffeine\s+(\d+(?:\.\d+)?)\s*mg",
            r"(\d+(?:\.\d+)?)\s*mg\s+caffeine",
        ],
        text
    )


# ============================================================
# 9. 杯型
# ============================================================

def extract_size(text):

    pattern = (
        r"\b("
        r"Short|Tall|Grande|Venti|Trenta"
        r")\s+"
        r"(\d+(?:\.\d+)?)\s*fl\s*oz"
    )

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    if not match:
        return "", None

    size_name = match.group(1).title()

    ounces = float(
        match.group(2)
    )

    size_text = (
        f"{size_name} "
        f"{ounces:g} fl oz"
    )

    return size_text, ounces


# ============================================================
# 10. 原料
# ============================================================

def extract_ingredients(text):

    patterns = [
        (
            r"Ingredients\s+(.*?)"
            r"(?:Allergens|Nutrition disclaimers|"
            r"Nutrition Disclaimer|Add to Order|$)"
        ),
        (
            r"Ingredients\s*:\s*(.*?)"
            r"(?:Allergens|$)"
        ),
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE | re.DOTALL
        )

        if not match:
            continue

        ingredients = (
            match.group(1)
            .strip()
        )

        ingredients = re.sub(
            r"\s+",
            " ",
            ingredients
        )

        # 防止错误情况下抓到整页
        if len(ingredients) > 1200:

            ingredients = (
                ingredients[:1200]
                + "..."
            )

        return ingredients

    return ""


# ============================================================
# 11. 产品名称
# ============================================================

def extract_product_name(page):

    selectors = [
        "h1",
        "[data-testid='product-name']",
    ]

    for selector in selectors:

        try:

            locator = (
                page
                .locator(selector)
                .first
            )

            if locator.count() == 0:
                continue

            name = (
                locator
                .inner_text()
                .strip()
            )

            if name:
                return name

        except Exception:
            continue

    return "Unknown Product"


# ============================================================
# 12. 自动分类
# ============================================================

def infer_category(name):

    text = str(name).lower()

    if "frappuccino" in text:
        return "星冰乐"

    if (
        "cold brew" in text
        or "nitro" in text
    ):
        return "冷萃咖啡"

    coffee_words = [
        "espresso",
        "latte",
        "macchiato",
        "mocha",
        "cappuccino",
        "americano",
        "coffee",
        "flat white",
    ]

    if any(
        word in text
        for word in coffee_words
    ):
        return "咖啡"

    if "matcha" in text:
        return "抹茶"

    if "refresher" in text:
        return "清爽饮"

    if "lemonade" in text:
        return "果饮"

    if "tea" in text:
        return "茶饮"

    return "其他饮品"


# ============================================================
# 13. 读取现有数据库
# ============================================================

def load_existing_data():

    if not DATA_FILE.exists():

        return pd.DataFrame()

    try:

        return pd.read_csv(
            str(DATA_FILE)
        )

    except (
        pd.errors.EmptyDataError,
        pd.errors.ParserError
    ):

        return pd.DataFrame()


# ============================================================
# 14. 判断一个产品是否需要重新抓取
# ============================================================

def should_skip_product(
        product_url,
        existing_df
):

    # 强制刷新模式
    if FORCE_REFRESH:
        return False

    if existing_df.empty:
        return False

    if "source_url" not in existing_df.columns:
        return False

    matched = existing_df[
        existing_df["source_url"]
        .astype(str)
        ==
        str(product_url)
    ]

    if matched.empty:
        return False

    # 如果没有抓取时间字段，
    # 说明是旧数据，重新抓一次
    if "scraped_at" not in matched.columns:
        return False

    latest_time = (
        pd.to_datetime(
            matched["scraped_at"],
            errors="coerce"
        )
        .max()
    )

    if pd.isna(latest_time):
        return False

    refresh_before = (
        datetime.now()
        -
        timedelta(
            days=REFRESH_DAYS
        )
    )

    # 最近 REFRESH_DAYS 天以内抓过
    if latest_time.to_pydatetime() >= refresh_before:

        return True

    return False


# ============================================================
# 15. 抓取一个 Nutrition 页面
# ============================================================

def scrape_product(
        page,
        product
):

    product_url = product["url"]

    print()
    print(
        f"正在访问：{product_url}"
    )

    try:

        page.goto(
            product_url,
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT
        )

    except PlaywrightTimeoutError:

        print(
            "⚠️ 页面加载超时，"
            "尝试读取已经加载的内容。"
        )

    page.wait_for_timeout(
        RENDER_WAIT
    )

    text = (
        page
        .locator("body")
        .inner_text()
    )

    name = extract_product_name(
        page
    )

    calories = extract_calories(
        text
    )

    sugar = extract_sugar(
        text
    )

    fat = extract_fat(
        text
    )

    protein = extract_protein(
        text
    )

    caffeine = extract_caffeine(
        text
    )

    size, ounces = extract_size(
        text
    )

    ingredients = extract_ingredients(
        text
    )

    category = infer_category(
        name
    )

    # 热量作为必要字段
    if calories is None:

        raise ValueError(
            f"未找到热量：{name}"
        )

    print(
        f"✅ {name}"
    )

    print(
        f"   分类：{category}"
    )

    print(
        f"   杯型：{size or '-'}"
    )

    print(
        f"   热量：{calories:g} kcal"
    )

    print(
        "   糖："
        +
        (
            f"{sugar:g} g"
            if sugar is not None
            else "-"
        )
    )

    print(
        "   脂肪："
        +
        (
            f"{fat:g} g"
            if fat is not None
            else "-"
        )
    )

    print(
        "   蛋白质："
        +
        (
            f"{protein:g} g"
            if protein is not None
            else "-"
        )
    )

    print(
        "   咖啡因："
        +
        (
            f"{caffeine:g} mg"
            if caffeine is not None
            else "-"
        )
    )

    return {

        "brand": "星巴克",

        "name": name,

        "name_cn": "",

        "category": category,

        "size": size,

        "ounces": ounces,

        "calories": calories,

        "sugar": sugar,

        "fat": fat,

        "protein": protein,

        "caffeine": caffeine,

        "ingredients": ingredients,

        "source": "Starbucks Official",

        "source_url": product_url,

        "discovery_method": product.get(
            "discovery_method",
            ""
        ),

        "scraped_at": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    }


# ============================================================
# 16. 带自动重试的抓取
# ============================================================

def scrape_with_retry(
        page,
        product
):

    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1
    ):

        try:

            if attempt > 1:

                print(
                    f"🔄 第 {attempt} 次尝试..."
                )

            result = scrape_product(
                page,
                product
            )

            return result, None

        except Exception as error:

            last_error = str(
                error
            )

            print(
                f"⚠️ 第 {attempt} 次失败："
                f"{last_error}"
            )

            if attempt < MAX_RETRIES:

                time.sleep(
                    RETRY_DELAY
                )

    return None, last_error


# ============================================================
# 17. CSV 字段标准
# ============================================================

REQUIRED_COLUMNS = [
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
    "ingredients",
    "source",
    "source_url",
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
]


# ============================================================
# 18. 合并并保存 drinks.csv
# ============================================================

def merge_and_save(
        new_results
):

    if not new_results:
        return

    old_df = load_existing_data()

    new_df = pd.DataFrame(
        new_results
    )

    if old_df.empty:

        combined_df = new_df.copy()

    else:

        combined_df = pd.concat(
            [
                old_df,
                new_df
            ],
            ignore_index=True
        )

    # 补齐字段
    for column in REQUIRED_COLUMNS:

        if column not in combined_df.columns:

            combined_df[
                column
            ] = None

    # 数字字段标准化
    for column in NUMERIC_COLUMNS:

        combined_df[
            column
        ] = pd.to_numeric(
            combined_df[column],
            errors="coerce"
        )

    # 同一个 URL 只保留最新数据
    combined_df = (
        combined_df
        .drop_duplicates(
            subset=[
                "source_url"
            ],
            keep="last"
        )
    )

    # 按热量排序
    combined_df = (
        combined_df
        .sort_values(
            by="calories",
            ascending=False,
            na_position="last"
        )
    )

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    combined_df.to_csv(
        str(DATA_FILE),
        index=False,
        encoding="utf-8-sig"
    )


# ============================================================
# 19. 保存失败日志
# ============================================================

def save_failed_log(
        failures
):

    if not failures:
        return

    failed_df = pd.DataFrame(
        failures
    )

    if FAILED_FILE.exists():

        try:

            old_failed = pd.read_csv(
                str(FAILED_FILE)
            )

            failed_df = pd.concat(
                [
                    old_failed,
                    failed_df
                ],
                ignore_index=True
            )

        except (
            pd.errors.EmptyDataError,
            pd.errors.ParserError
        ):

            pass

    failed_df.to_csv(
        str(FAILED_FILE),
        index=False,
        encoding="utf-8-sig"
    )


# ============================================================
# 20. 批量爬取
# ============================================================

def scrape_all():

    successful_results = []

    failures = []

    skipped_count = 0

    success_count = 0

    failed_count = 0


    existing_df = load_existing_data()


    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            viewport={
                "width": 1440,
                "height": 1000
            },

            locale="en-US",

            user_agent=(
                "Mozilla/5.0 "
                "(Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/151.0.0.0 "
                "Safari/537.36"
            )
        )

        page = context.new_page()


        # ====================================================
        # 产品发现
        # ====================================================

        products = (
            discover_starbucks_products(
                page
            )
        )


        if MAX_PRODUCTS is not None:

            products = products[
                :MAX_PRODUCTS
            ]


        total = len(
            products
        )


        print()
        print("=" * 60)

        print(
            f"Starbucks 共发现 {total} 个产品"
        )

        print(
            f"刷新周期：{REFRESH_DAYS} 天"
        )

        print(
            f"强制刷新：{FORCE_REFRESH}"
        )

        print("=" * 60)


        # ====================================================
        # 开始循环
        # ====================================================

        for index, product in enumerate(
            products,
            start=1
        ):

            product_url = (
                product["url"]
            )


            print()
            print("-" * 60)

            print(
                f"[{index}/{total}]"
            )


            # ------------------------------------------------
            # 判断是否需要刷新
            # ------------------------------------------------

            if should_skip_product(
                product_url,
                existing_df
            ):

                skipped_count += 1

                print(
                    "⏭️ 已有近期数据，跳过"
                )

                continue


            # ------------------------------------------------
            # 抓取 + 自动重试
            # ------------------------------------------------

            result, error = scrape_with_retry(
                page,
                product
            )


            if result is not None:

                successful_results.append(
                    result
                )

                success_count += 1


                # --------------------------------------------
                # 定期保存
                # --------------------------------------------

                if (
                    success_count
                    %
                    SAVE_EVERY
                    ==
                    0
                ):

                    merge_and_save(
                        successful_results
                    )

                    print()
                    print(
                        f"💾 已自动保存 "
                        f"{success_count} 条新数据"
                    )


            else:

                failed_count += 1

                failures.append(
                    {
                        "source_url": product_url,

                        "error": error,

                        "failed_at": (
                            datetime.now()
                            .strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                        ),
                    }
                )


            # ------------------------------------------------
            # 当前进度
            # ------------------------------------------------

            print(
                f"📊 成功 {success_count} | "
                f"跳过 {skipped_count} | "
                f"失败 {failed_count}"
            )


            time.sleep(
                REQUEST_DELAY
            )


        context.close()

        browser.close()


    # ========================================================
    # 最终保存
    # ========================================================

    merge_and_save(
        successful_results
    )

    save_failed_log(
        failures
    )


    # ========================================================
    # 返回统计
    # ========================================================

    return {

        "total": len(products),

        "success": success_count,

        "skipped": skipped_count,

        "failed": failed_count,

    }


# ============================================================
# 21. 主程序
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)

    print(
        "🥤 Starbucks 增量营养数据爬虫"
    )

    print("=" * 60)


    stats = scrape_all()


    print()
    print("=" * 60)

    print(
        "📊 本次 Starbucks 更新完成"
    )

    print("=" * 60)


    print(
        f"发现产品：{stats['total']}"
    )

    print(
        f"成功更新：{stats['success']}"
    )

    print(
        f"已有数据跳过：{stats['skipped']}"
    )

    print(
        f"失败：{stats['failed']}"
    )


    print()
    print(
        f"✅ 主数据：{DATA_FILE}"
    )


    if stats["failed"] > 0:

        print(
            f"⚠️ 失败日志：{FAILED_FILE}"
        )


    print()
    print(
        "✅ Starbucks 爬虫运行结束"
    )
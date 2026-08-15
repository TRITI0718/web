import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
# ============================================================
# 普通网页 + 中国大陆公开平台统一聚合
# ============================================================

def search_and_aggregate_all_sources(
        brand,
        name_cn,
        name_en="",
        search_queries=None,
        max_results=8,
        delay=0.8,
):

    # 延迟导入，避免循环 import
    from scraper.social_search import (
        search_social_calories,
    )

    # ========================================================
    # 1. 产品名称
    # ========================================================

    product_names = [
        name_cn
    ]

    if (
        name_en
        and
        name_en != name_cn
    ):
        product_names.append(
            name_en
        )

    # ========================================================
    # 2. 默认普通网页搜索词
    # ========================================================

    if search_queries is None:

        search_queries = [
            f"{brand} {name_cn} 热量 kcal",
            f"{brand} {name_cn} 大卡",
            f"{brand} {name_cn} 卡路里",
        ]

    # ========================================================
    # 3. 普通网页证据
    # ========================================================

    print()
    print("=" * 70)
    print("🌐 普通网页搜索")
    print("=" * 70)

    normal_evidence = (
        collect_search_evidence(
            product_names=
                product_names,

            search_queries=
                search_queries,

            max_results=
                max_results,

            delay=
                delay,
        )
    )

    print(
        f"🌐 普通网页获得 "
        f"{len(normal_evidence)} 条证据"
    )

    # ========================================================
    # 4. 中国大陆公开平台证据
    # ========================================================

    print()
    print("=" * 70)
    print("📱 中国大陆公开平台搜索")
    print("=" * 70)

    try:

        social_evidence = (
            search_social_calories(
                brand=
                    brand,

                name_cn=
                    name_cn,

                name_en=
                    name_en,

                max_results=
                    max_results,
            )
        )

    except Exception as error:

        print(
            f"⚠️ 社交平台搜索失败：{error}"
        )

        social_evidence = []

    print(
        f"📱 社交平台获得 "
        f"{len(social_evidence)} 条证据"
    )

    # ========================================================
    # 5. 合并
    # ========================================================

    combined = (
        normal_evidence
        +
        social_evidence
    )

    combined = (
        deduplicate_evidence(
            combined
        )
    )

    print()
    print(
        f"📚 合并去重后："
        f"{len(combined)} 条证据"
    )

    # ========================================================
    # 6. 没有结果
    # ========================================================

    if not combined:

        print(
            "⚠️ 没有获得任何有效热量证据。"
        )

        return None

    # ========================================================
    # 7. 统一聚合
    # ========================================================

    result = (
        aggregate_calorie_evidence(
            combined
        )
    )

    if not result:

        print(
            "⚠️ 证据存在，但聚合失败。"
        )

        return None

    # ========================================================
    # 8. 输出结果
    # ========================================================

    print()
    print("=" * 70)
    print("📊 最终聚合结果")
    print("=" * 70)

    print(
        f"热量："
        f"{result['estimate']} kcal"
    )

    print(
        f"有效来源："
        f"{result['source_count']}"
    )

    print(
        f"范围："
        f"{result['calorie_min']}"
        " - "
        f"{result['calorie_max']}"
        " kcal"
    )

    return result
# ============================================================
# 1. 项目路径
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

DEBUG_DIR = DATA_DIR / "debug"


# ============================================================
# 2. 默认网络配置
# ============================================================

DEFAULT_REQUEST_TIMEOUT = 12

DEFAULT_REQUEST_DELAY = 1.0

DEFAULT_MAX_RESULTS = 8


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151 Safari/537.36"
    )
}


# ============================================================
# 3. 不直接请求正文的平台
#
# 这些平台仍然可以利用搜索结果摘要，
# 但不主动请求正文。
# ============================================================

BLOCKED_DOMAINS = {
    "xiaohongshu.com",
    "xhslink.com",
    "douyin.com",
    "tiktok.com",
    "weibo.com",
}


# ============================================================
# 4. 平台识别
# ============================================================

def identify_platform(url):

    domain = (
        urlparse(str(url))
        .netloc
        .lower()
    )

    if (
        "xiaohongshu" in domain
        or "xhslink" in domain
    ):
        return "小红书"

    if "douyin" in domain:
        return "抖音"

    if "weibo" in domain:
        return "微博"

    if "zhihu" in domain:
        return "知乎"

    if "bilibili" in domain:
        return "哔哩哔哩"

    if "baidu" in domain:
        return "百度"

    if "sina" in domain:
        return "新浪"

    if "smzdm" in domain:
        return "什么值得买"

    if "maigoo" in domain:
        return "买购网"

    return (
        domain
        .replace(
            "www.",
            ""
        )
    )


# ============================================================
# 5. 是否允许抓正文
# ============================================================

def can_fetch_page(url):

    domain = (
        urlparse(str(url))
        .netloc
        .lower()
    )

    for blocked in BLOCKED_DOMAINS:

        if blocked in domain:
            return False

    return True


# ============================================================
# 6. 文本标准化
# ============================================================

def normalize_text(text):

    if text is None:
        return ""

    text = str(text)

    replacements = {
        "\n": " ",
        "\r": " ",
        "\t": " ",
        ",": "",
        "千卡": " kcal ",
        "大卡": " kcal ",
        "卡路里": " calories ",
        "ＫＣＡＬ": " kcal ",
        "KCAL": " kcal ",
    }

    for old, new in replacements.items():

        text = text.replace(
            old,
            new
        )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# 7. 产品名称标准化
# ============================================================

def normalize_product_name(name):

    name = normalize_text(
        name
    )

    # --------------------------------------------------------
    # 去掉价格
    # --------------------------------------------------------

    name = re.sub(
        r"\$\s*\d+(?:\.\d+)?",
        "",
        name
    )

    name = re.sub(
        r"¥\s*\d+(?:\.\d+)?",
        "",
        name
    )

    name = re.sub(
        r"￥\s*\d+(?:\.\d+)?",
        "",
        name
    )

    name = re.sub(
        r"From\s+\$.*$",
        "",
        name,
        flags=re.IGNORECASE
    )

    # --------------------------------------------------------
    # 再清理空格
    # --------------------------------------------------------

    name = re.sub(
        r"\s+",
        " ",
        name
    )

    return name.strip()


# ============================================================
# 8. 获取公开网页正文
# ============================================================

def fetch_page_text(
        url,
        timeout=DEFAULT_REQUEST_TIMEOUT
):

    if not url:
        return ""

    if not can_fetch_page(
        url
    ):
        return ""

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=timeout
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        # ----------------------------------------------------
        # 去掉噪声
        # ----------------------------------------------------

        for tag in soup(
            [
                "script",
                "style",
                "noscript",
                "svg",
            ]
        ):

            tag.decompose()

        text = soup.get_text(
            " ",
            strip=True
        )

        return normalize_text(
            text
        )

    except Exception:

        return ""


# ============================================================
# 9. 搜索网页
# ============================================================

def search_web(
        query,
        max_results=DEFAULT_MAX_RESULTS
):

    print()
    print(
        f"🔎 搜索：{query}"
    )

    results = []

    try:

        with DDGS() as ddgs:

            raw_results = ddgs.text(
                query,
                max_results=max_results
            )

            for item in raw_results:

                url = (
                    item.get(
                        "href",
                        ""
                    )
                    or
                    item.get(
                        "url",
                        ""
                    )
                )

                if not url:
                    continue

                results.append(
                    {
                        "title":
                            item.get(
                                "title",
                                ""
                            ),

                        "url":
                            url,

                        "snippet":
                            item.get(
                                "body",
                                ""
                            ),
                    }
                )

    except Exception as error:

        print(
            f"⚠️ 搜索失败：{error}"
        )

    return results


# ============================================================
# 10. kcal 候选提取
# ============================================================

def extract_calorie_candidates(text):

    text = normalize_text(
        text
    )

    if not text:
        return []

    patterns = [

        # 180 kcal
        r"(\d+(?:\.\d+)?)\s*kcal\b",

        # kcal 180
        r"\bkcal\s*[：:]?\s*(\d+(?:\.\d+)?)",

        # 热量 180
        r"热量\s*[：:]?\s*(\d+(?:\.\d+)?)",

        # 180 calories
        r"(\d+(?:\.\d+)?)\s*calories?\b",

        # calories 180
        r"calories?\s*[：:]?\s*(\d+(?:\.\d+)?)",

        # 约 180 卡
        r"约\s*(\d+(?:\.\d+)?)\s*卡\b",

        # 180 卡
        r"(\d+(?:\.\d+)?)\s*卡\b",
    ]

    values = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            re.IGNORECASE
        )

        for match in matches:

            try:

                value = float(
                    match
                )

            except (
                TypeError,
                ValueError
            ):

                continue

            # ------------------------------------------------
            # 整杯饮品的基础合理范围
            # ------------------------------------------------

            if (
                0
                <= value
                <= 1000
            ):

                values.append(
                    value
                )

    # --------------------------------------------------------
    # 去重但保持顺序
    # --------------------------------------------------------

    unique = []

    for value in values:

        if value not in unique:

            unique.append(
                value
            )

    return unique


# ============================================================
# 11. 找产品名称附近的上下文
# ============================================================

def extract_product_contexts(
        text,
        product_names,
        before_chars=80,
        after_chars=100
):

    text = normalize_text(
        text
    )

    if not text:
        return []

    if isinstance(
        product_names,
        str
    ):

        product_names = [
            product_names
        ]

    contexts = []

    lower_text = (
        text.lower()
    )

    for product_name in product_names:

        if not product_name:
            continue

        product_name = normalize_text(
            product_name
        )

        lower_product = (
            product_name.lower()
        )

        start = 0

        while True:

            index = lower_text.find(
                lower_product,
                start
            )

            if index == -1:
                break

            context_start = max(
                0,
                index - before_chars
            )

            context_end = min(
                len(text),
                index
                +
                len(product_name)
                +
                after_chars
            )

            contexts.append(
                {
                    "product_name":
                        product_name,

                    "context":
                        text[
                            context_start:
                            context_end
                        ],

                    "position":
                        index,
                }
            )

            start = (
                index
                +
                max(
                    len(product_name),
                    1
                )
            )

    return contexts


# ============================================================
# 12. 文本是否提到产品
# ============================================================

def text_mentions_product(
        text,
        product_names
):

    text = normalize_text(
        text
    ).lower()

    if not text:
        return False

    if isinstance(
        product_names,
        str
    ):

        product_names = [
            product_names
        ]

    for name in product_names:

        if not name:
            continue

        if (
            normalize_text(
                name
            ).lower()
            in text
        ):

            return True

    return False


# ============================================================
# 13. 找 kcal 与产品名称之间距离
#
# 相比单纯截取 100 字，
# 这一版会进一步计算数字距离产品名称有多远。
# ============================================================

def extract_calories_with_distance(
        context,
        product_name
):

    context = normalize_text(
        context
    )

    if not context:
        return []

    lower_context = (
        context.lower()
    )

    product_position = (
        lower_context.find(
            product_name.lower()
        )
    )

    if product_position < 0:

        product_position = (
            len(context)
            //
            2
        )

    patterns = [
        r"(\d+(?:\.\d+)?)\s*kcal\b",
        r"\bkcal\s*[：:]?\s*(\d+(?:\.\d+)?)",
        r"热量\s*[：:]?\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s*calories?\b",
        r"calories?\s*[：:]?\s*(\d+(?:\.\d+)?)",
        r"约\s*(\d+(?:\.\d+)?)\s*卡\b",
        r"(\d+(?:\.\d+)?)\s*卡\b",
    ]

    candidates = []

    for pattern in patterns:

        for match in re.finditer(
            pattern,
            context,
            re.IGNORECASE
        ):

            try:

                value = float(
                    match.group(1)
                )

            except (
                TypeError,
                ValueError
            ):

                continue

            if not (
                0
                <= value
                <= 1000
            ):
                continue

            distance = abs(
                match.start()
                -
                product_position
            )

            candidates.append(
                {
                    "calories":
                        value,

                    "distance":
                        distance,

                    "matched_text":
                        match.group(0),
                }
            )

    # --------------------------------------------------------
    # 距离近的优先
    # --------------------------------------------------------

    candidates.sort(
        key=lambda item: (
            item[
                "distance"
            ],
            item[
                "calories"
            ],
        )
    )

    return candidates


# ============================================================
# 14. 从单个搜索结果提取证据
# ============================================================

def extract_evidence_from_result(
        product_names,
        result,
        fetch_body=True
):

    if isinstance(
        product_names,
        str
    ):

        product_names = [
            product_names
        ]

    url = result.get(
        "url",
        ""
    )

    title = result.get(
        "title",
        ""
    )

    snippet = result.get(
        "snippet",
        ""
    )

    platform = identify_platform(
        url
    )

    evidence = []


    # ========================================================
    # A. 搜索结果摘要
    # ========================================================

    if text_mentions_product(
        snippet,
        product_names
    ):

        contexts = (
            extract_product_contexts(
                snippet,
                product_names
            )
        )

        for context_item in contexts:

            candidates = (
                extract_calories_with_distance(
                    context_item[
                        "context"
                    ],
                    context_item[
                        "product_name"
                    ]
                )
            )

            # ------------------------------------------------
            # 只保留离产品名称最近的候选值
            # ------------------------------------------------

            if candidates:

                nearest = candidates[0]

                evidence.append(
                    {
                        "calories":
                            nearest[
                                "calories"
                            ],

                        "distance":
                            nearest[
                                "distance"
                            ],

                        "url":
                            url,

                        "title":
                            title,

                        "platform":
                            platform,

                        "location":
                            "search_snippet",

                        "matched_name":
                            context_item[
                                "product_name"
                            ],

                        "context":
                            context_item[
                                "context"
                            ],
                    }
                )


    # ========================================================
    # B. 网页正文
    # ========================================================

    if (
        fetch_body
        and
        can_fetch_page(
            url
        )
    ):

        page_text = fetch_page_text(
            url
        )

        if text_mentions_product(
            page_text,
            product_names
        ):

            contexts = (
                extract_product_contexts(
                    page_text,
                    product_names
                )
            )

            for context_item in contexts:

                candidates = (
                    extract_calories_with_distance(
                        context_item[
                            "context"
                        ],
                        context_item[
                            "product_name"
                        ]
                    )
                )

                if not candidates:
                    continue

                nearest = (
                    candidates[0]
                )

                evidence.append(
                    {
                        "calories":
                            nearest[
                                "calories"
                            ],

                        "distance":
                            nearest[
                                "distance"
                            ],

                        "url":
                            url,

                        "title":
                            title,

                        "platform":
                            platform,

                        "location":
                            "page_context",

                        "matched_name":
                            context_item[
                                "product_name"
                            ],

                        "context":
                            context_item[
                                "context"
                            ],
                    }
                )

    return evidence


# ============================================================
# 15. 证据去重
#
# 同一 URL + 同一个 kcal，
# 不重复计算。
# ============================================================

def deduplicate_evidence(
        evidence
):

    unique = []

    seen = set()

    for item in evidence:

        key = (
            item.get(
                "url",
                ""
            ),
            item.get(
                "calories"
            )
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        unique.append(
            item
        )

    return unique


# ============================================================
# 16. 中位数
# ============================================================

def calculate_median(values):

    values = [
        float(value)
        for value in values
        if value is not None
    ]

    if not values:
        return None

    values = sorted(
        values
    )

    length = len(
        values
    )

    middle = (
        length // 2
    )

    if (
        length % 2
        ==
        1
    ):

        return values[
            middle
        ]

    return (
        values[
            middle - 1
        ]
        +
        values[
            middle
        ]
    ) / 2


# ============================================================
# 17. 每个 URL 只保留一个代表值
#
# 重点：
# 不再简单取该网页所有值的中位数。
#
# 优先选择：
# 1. 距产品名最近
# 2. 搜索摘要优先于正文
# ============================================================

def collapse_by_source(
        evidence
):

    grouped = {}

    for item in evidence:

        url = item.get(
            "url",
            ""
        )

        if not url:
            continue

        grouped.setdefault(
            url,
            []
        )

        grouped[
            url
        ].append(
            item
        )

    collapsed = []

    for url, items in grouped.items():

        def evidence_score(item):

            location_score = (
                0
                if item.get(
                    "location"
                )
                ==
                "search_snippet"
                else 1
            )

            distance = item.get(
                "distance",
                999999
            )

            return (
                distance,
                location_score,
            )

        best_item = min(
            items,
            key=evidence_score
        ).copy()

        best_item[
            "all_values_from_source"
        ] = [
            item.get(
                "calories"
            )
            for item in items
        ]

        collapsed.append(
            best_item
        )

    return collapsed


# ============================================================
# 18. IQR 异常值过滤
#
# 当来源 >= 4 时，
# 使用更稳的四分位范围过滤。
# ============================================================

def remove_outliers_iqr(
        evidence
):

    if len(evidence) < 4:
        return evidence

    values = pd.Series(
        [
            item[
                "calories"
            ]
            for item in evidence
        ],
        dtype="float64"
    )

    q1 = values.quantile(
        0.25
    )

    q3 = values.quantile(
        0.75
    )

    iqr = (
        q3
        -
        q1
    )

    # 所有值完全一样
    if iqr == 0:

        median = values.median()

        return [
            item
            for item in evidence
            if (
                median * 0.8
                <=
                item[
                    "calories"
                ]
                <=
                median * 1.2
            )
        ]

    lower = (
        q1
        -
        1.5
        *
        iqr
    )

    upper = (
        q3
        +
        1.5
        *
        iqr
    )

    filtered = [
        item
        for item in evidence
        if (
            lower
            <=
            item[
                "calories"
            ]
            <=
            upper
        )
    ]

    if len(filtered) >= 2:

        return filtered

    return evidence


# ============================================================
# 19. 中位数比例异常值过滤
#
# 当 IQR 无法处理时再做第二层。
# ============================================================

def remove_outliers_ratio(
        evidence,
        ratio=0.30
):

    if len(evidence) <= 2:
        return evidence

    values = [
        item[
            "calories"
        ]
        for item in evidence
    ]

    median = calculate_median(
        values
    )

    if median is None:
        return evidence

    if median == 0:
        return evidence

    lower = (
        median
        *
        (
            1
            -
            ratio
        )
    )

    upper = (
        median
        *
        (
            1
            +
            ratio
        )
    )

    filtered = [
        item
        for item in evidence
        if (
            lower
            <=
            item[
                "calories"
            ]
            <=
            upper
        )
    ]

    if len(filtered) >= 2:

        return filtered

    return evidence


# ============================================================
# 20. 综合异常值处理
# ============================================================

def remove_outliers(
        evidence
):

    if len(evidence) <= 2:
        return evidence

    # --------------------------------------------------------
    # 第一层 IQR
    # --------------------------------------------------------

    filtered = (
        remove_outliers_iqr(
            evidence
        )
    )

    # --------------------------------------------------------
    # 第二层 ±30%
    # --------------------------------------------------------

    filtered = (
        remove_outliers_ratio(
            filtered,
            ratio=0.30
        )
    )

    return filtered


# ============================================================
# 21. 搜索模板批量执行
# ============================================================

def collect_search_evidence(
        product_names,
        search_queries,
        max_results=DEFAULT_MAX_RESULTS,
        delay=DEFAULT_REQUEST_DELAY
):

    if isinstance(
        product_names,
        str
    ):

        product_names = [
            product_names
        ]

    evidence = []

    for query in search_queries:

        results = search_web(
            query,
            max_results=max_results
        )

        for result in results:

            result_evidence = (
                extract_evidence_from_result(
                    product_names,
                    result,
                    fetch_body=True
                )
            )

            if not result_evidence:
                continue

            evidence.extend(
                result_evidence
            )

            platform = (
                identify_platform(
                    result.get(
                        "url",
                        ""
                    )
                )
            )

            values = [
                item[
                    "calories"
                ]
                for item in result_evidence
            ]

            print(
                f"✅ {platform}: "
                f"{values}"
            )

        time.sleep(
            delay
        )

    return (
        deduplicate_evidence(
            evidence
        )
    )


# ============================================================
# 22. 最终聚合
# ============================================================

def aggregate_calorie_evidence(
        raw_evidence
):

    if not raw_evidence:

        return None

    # --------------------------------------------------------
    # 每个网页一个值
    # --------------------------------------------------------

    source_evidence = (
        collapse_by_source(
            raw_evidence
        )
    )

    if not source_evidence:

        return None

    # --------------------------------------------------------
    # 异常值
    # --------------------------------------------------------

    filtered = remove_outliers(
        source_evidence
    )

    values = [
        item[
            "calories"
        ]
        for item in filtered
    ]

    estimate = calculate_median(
        values
    )

    if estimate is None:
        return None

    return {
        "estimate":
            round(
                estimate,
                1
            ),

        "calorie_min":
            min(
                values
            ),

        "calorie_max":
            max(
                values
            ),

        "source_count":
            len(
                filtered
            ),

        "raw_evidence":
            raw_evidence,

        "source_evidence":
            source_evidence,

        "filtered_evidence":
            filtered,

        "primary_source":
            filtered[0],
    }


# ============================================================
# 23. 一步完成搜索 + 聚合
#
# 品牌爬虫最常用的入口。
# ============================================================

def search_and_aggregate_calories(
        product_names,
        search_queries,
        max_results=DEFAULT_MAX_RESULTS,
        delay=DEFAULT_REQUEST_DELAY
):

    raw_evidence = (
        collect_search_evidence(
            product_names=
                product_names,

            search_queries=
                search_queries,

            max_results=
                max_results,

            delay=
                delay
        )
    )

    if not raw_evidence:

        return None

    return (
        aggregate_calorie_evidence(
            raw_evidence
        )
    )


# ============================================================
# 24. 判断数据是否需要刷新
#
# 通用于：
# Starbucks / Luckin / Heytea / Mixue
# ============================================================

def should_refresh_record(
        existing_df,
        brand,
        names,
        refresh_days=30,
        force_refresh=False
):

    if force_refresh:

        return True

    if existing_df is None:

        return True

    if existing_df.empty:

        return True

    if isinstance(
        names,
        str
    ):

        names = [
            names
        ]

    names = [
        str(name)
        .strip()
        .lower()
        for name in names
        if name
    ]

    if not names:

        return True

    if "brand" not in existing_df.columns:

        return True

    brand_df = (
        existing_df[
            existing_df[
                "brand"
            ]
            .astype(str)
            ==
            str(brand)
        ]
    )

    if brand_df.empty:

        return True

    mask = pd.Series(
        False,
        index=brand_df.index
    )

    for column in [
        "name",
        "name_cn",
    ]:

        if column not in brand_df.columns:
            continue

        normalized_column = (
            brand_df[
                column
            ]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
        )

        for name in names:

            mask |= (
                normalized_column
                ==
                name
            )

    matched = (
        brand_df[
            mask
        ]
    )

    if matched.empty:

        return True

    if "scraped_at" not in matched.columns:

        return True

    latest = pd.to_datetime(
        matched[
            "scraped_at"
        ],
        errors="coerce"
    ).max()

    if pd.isna(
        latest
    ):

        return True

    refresh_before = (
        datetime.now()
        -
        timedelta(
            days=refresh_days
        )
    )

    # --------------------------------------------------------
    # True = 应该重新抓
    # --------------------------------------------------------

    return (
        latest.to_pydatetime()
        <
        refresh_before
    )


# ============================================================
# 25. 反向辅助函数：
# 是否应该跳过
# ============================================================

def should_skip_record(
        existing_df,
        brand,
        names,
        refresh_days=30,
        force_refresh=False
):

    return not should_refresh_record(
        existing_df=
            existing_df,

        brand=
            brand,

        names=
            names,

        refresh_days=
            refresh_days,

        force_refresh=
            force_refresh
    )


# ============================================================
# 26. 调试证据保存
# ============================================================

def save_evidence_debug(
        brand,
        product_name,
        aggregation_result
):

    if not aggregation_result:
        return None

    brand_dir = (
        DEBUG_DIR
        /
        re.sub(
            r'[\\/:*?"<>|]',
            "_",
            str(brand)
        )
    )

    brand_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    safe_product_name = re.sub(
        r'[\\/:*?"<>|]',
        "_",
        str(product_name)
    )

    file_path = (
        brand_dir
        /
        f"{safe_product_name}.txt"
    )

    lines = [
        f"BRAND: {brand}",
        f"PRODUCT: {product_name}",
        (
            "FINAL ESTIMATE: "
            f"{aggregation_result['estimate']}"
        ),
        (
            "SOURCE COUNT: "
            f"{aggregation_result['source_count']}"
        ),
        (
            "RANGE: "
            f"{aggregation_result['calorie_min']}"
            " - "
            f"{aggregation_result['calorie_max']}"
        ),
        "",
        "=" * 70,
        "RAW EVIDENCE",
        "=" * 70,
        "",
    ]

    for item in aggregation_result[
        "raw_evidence"
    ]:

        lines.append(
            (
                f"[{item.get('platform', '')}] "
                f"{item.get('calories')} kcal"
            )
        )

        lines.append(
            (
                "distance="
                f"{item.get('distance', '')}"
                " | "
                "location="
                f"{item.get('location', '')}"
            )
        )

        lines.append(
            item.get(
                "url",
                ""
            )
        )

        lines.append(
            item.get(
                "context",
                ""
            )
        )

        lines.append(
            ""
        )

    lines.extend(
        [
            "",
            "=" * 70,
            "FILTERED EVIDENCE",
            "=" * 70,
            "",
        ]
    )

    for item in aggregation_result[
        "filtered_evidence"
    ]:

        lines.append(
            (
                f"[{item.get('platform', '')}] "
                f"{item.get('calories')} kcal"
            )
        )

        lines.append(
            item.get(
                "url",
                ""
            )
        )

        lines.append(
            ""
        )

    file_path.write_text(
        "\n".join(
            lines
        ),
        encoding="utf-8"
    )

    return file_path


# ============================================================
# 27. 标准第三方数据库记录生成
#
# 品牌爬虫可以直接调用，
# 减少重复字典代码。
# ============================================================

def build_third_party_record(
        brand,
        name,
        name_cn,
        category,
        aggregation_result,
        market="China",
        ingredients="",
        size="",
        ounces=None,
        discovery_method="third_party_search"
):

    if not aggregation_result:

        return None

    primary = aggregation_result[
        "primary_source"
    ]

    return {
        "brand":
            brand,

        "name":
            name,

        "name_cn":
            name_cn,

        "category":
            category,

        "size":
            size,

        "ounces":
            ounces,

        "calories":
            aggregation_result[
                "estimate"
            ],

        "sugar":
            None,

        "fat":
            None,

        "protein":
            None,

        "caffeine":
            None,

        "carbs":
            None,

        "sodium":
            None,

        "ingredients":
            ingredients,

        "market":
            market,

        "spu_code":
            "",

        "source":
            "第三方公开网页聚合",

        "source_url":
            primary.get(
                "url",
                ""
            ),

        "source_type":
            "third_party",

        "source_platform":
            primary.get(
                "platform",
                ""
            ),

        "source_count":
            aggregation_result[
                "source_count"
            ],

        "calorie_min":
            aggregation_result[
                "calorie_min"
            ],

        "calorie_max":
            aggregation_result[
                "calorie_max"
            ],

        "discovery_method":
            discovery_method,

        "scraped_at":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
    }


# ============================================================
# 28. 测试入口
#
# 可以直接：
#
# python -m scraper.base_scraper
# ============================================================
# ============================================================
# 29. 普通网页 + 中国大陆公开平台统一聚合
# ============================================================

def search_and_aggregate_all_sources(
        brand,
        name_cn,
        name_en="",
        search_queries=None,
        max_results=8,
        delay=0.8
):

    # 延迟导入，避免循环依赖
    from scraper.social_search import (
        search_social_calories,
    )


    # ========================================================
    # 1. 普通网页证据
    # ========================================================

    product_names = [
        name_cn
    ]


    if (
        name_en
        and
        name_en != name_cn
    ):

        product_names.append(
            name_en
        )


    if search_queries is None:

        search_queries = [
            f"{brand} {name_cn} 热量 kcal",
            f"{brand} {name_cn} 大卡",
            f"{brand} {name_cn} 卡路里",
        ]


    normal_evidence = (
        collect_search_evidence(
            product_names=
                product_names,

            search_queries=
                search_queries,

            max_results=
                max_results,

            delay=
                delay,
        )
    )


    # ========================================================
    # 2. 社交平台公开搜索证据
    # ========================================================

    social_evidence = (
        search_social_calories(
            brand=brand,
            name_cn=name_cn,
            name_en=name_en,
            max_results=max_results,
        )
    )


    # ========================================================
    # 3. 合并
    # ========================================================

    combined = (
        normal_evidence
        +
        social_evidence
    )


    combined = (
        deduplicate_evidence(
            combined
        )
    )


    if not combined:

        return None


    # ========================================================
    # 4. 统一异常值过滤与聚合
    # ========================================================

    return (
        aggregate_calorie_evidence(
            combined
        )
    )
if __name__ == "__main__":

    print()
    print("=" * 70)

    print(
        "🧪 Base Scraper 搜索模块测试"
    )

    print("=" * 70)

    test_names = [
        "生椰拿铁",
        "Coconut Latte",
    ]

    test_queries = [
        "瑞幸 生椰拿铁 热量 kcal",
        "瑞幸 生椰拿铁 大卡",
        "Luckin Coconut Latte calories",
    ]

    result = (
        search_and_aggregate_calories(
            product_names=
                test_names,

            search_queries=
                test_queries,

            max_results=6,

            delay=0.5
        )
    )

    if result:

        print()
        print(
            f"✅ 聚合热量："
            f"{result['estimate']} kcal"
        )

        print(
            f"✅ 有效来源："
            f"{result['source_count']}"
        )

        print(
            f"✅ 范围："
            f"{result['calorie_min']}"
            " - "
            f"{result['calorie_max']}"
            " kcal"
        )

        debug_file = (
            save_evidence_debug(
                brand="瑞幸",
                product_name="生椰拿铁",
                aggregation_result=result
            )
        )

        print(
            f"✅ 调试文件："
            f"{debug_file}"
        )

    else:

        print(
            "⚠️ 测试没有得到有效结果。"
        )
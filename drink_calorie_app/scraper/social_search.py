import re
import time
from urllib.parse import urlparse

from ddgs import DDGS

from scraper.base_scraper import (
    normalize_text,
    extract_product_contexts,
    extract_calories_with_distance,
)


# ============================================================
# 1. 中国大陆公开内容来源
# ============================================================

SOCIAL_DOMAINS = {

    "小红书": [
        "xiaohongshu.com",
        "xhslink.com",
    ],

    "抖音": [
        "douyin.com",
    ],

    "微博": [
        "weibo.com",
    ],

    "知乎": [
        "zhihu.com",
    ],

    "哔哩哔哩": [
        "bilibili.com",
    ],

    "什么值得买": [
        "smzdm.com",
    ],

    "新浪": [
        "sina.cn",
        "sina.com.cn",
    ],
}


# ============================================================
# 2. 基础配置
# ============================================================

MAX_RESULTS_PER_QUERY = 10

SEARCH_DELAY = 0.7


# ============================================================
# 3. 平台识别
# ============================================================

def get_platform(url):

    domain = (
        urlparse(
            str(url)
        )
        .netloc
        .lower()
    )

    for platform, domains in SOCIAL_DOMAINS.items():

        if any(
            item in domain
            for item in domains
        ):

            return platform

    return domain.replace(
        "www.",
        ""
    )


# ============================================================
# 4. 搜索单个 query
# ============================================================

def search_query(
        query,
        max_results=MAX_RESULTS_PER_QUERY
):

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

                        "platform":
                            get_platform(
                                url
                            ),
                    }
                )

    except Exception as error:

        print(
            f"⚠️ 搜索失败：{error}"
        )

    return results


# ============================================================
# 5. 构造大陆社交媒体搜索词
# ============================================================

def build_social_queries(
        brand,
        name_cn,
        name_en=""
):

    queries = []


    # ========================================================
    # 中文通用搜索
    # ========================================================

    base_queries = [

        f"{brand} {name_cn} 热量 kcal",

        f"{brand} {name_cn} 热量 大卡",

        f"{brand} {name_cn} 卡路里",

        f"{brand} {name_cn} 减脂 热量",

        f"{brand} {name_cn} 不另外加糖 热量",
    ]


    # ========================================================
    # 各平台 site 搜索
    # ========================================================

    domains = [
        "xiaohongshu.com",
        "douyin.com",
        "weibo.com",
        "zhihu.com",
        "bilibili.com",
        "smzdm.com",
    ]


    for domain in domains:

        queries.append(
            f"site:{domain} "
            f"{brand} {name_cn} 热量"
        )

        queries.append(
            f"site:{domain} "
            f"{brand} {name_cn} kcal"
        )


    queries.extend(
        base_queries
    )


    # ========================================================
    # 英文名补充
    # ========================================================

    if (
        name_en
        and
        name_en != name_cn
    ):

        queries.append(
            f"{brand} "
            f"{name_en} calories"
        )


    # ========================================================
    # 去重
    # ========================================================

    return list(
        dict.fromkeys(
            queries
        )
    )


# ============================================================
# 6. 判断摘要是否和产品相关
# ============================================================

def contains_product_name(
        text,
        names
):

    text = normalize_text(
        text
    ).lower()

    for name in names:

        if not name:
            continue

        name = normalize_text(
            name
        ).lower()

        if name in text:

            return True

    return False


# ============================================================
# 7. 从搜索摘要中提取最接近商品名的热量
# ============================================================

def extract_social_evidence(
        result,
        product_names
):

    title = normalize_text(
        result.get(
            "title",
            ""
        )
    )

    snippet = normalize_text(
        result.get(
            "snippet",
            ""
        )
    )

    url = result.get(
        "url",
        ""
    )

    platform = result.get(
        "platform",
        ""
    )


    # 标题 + 摘要一起判断
    combined = (
        f"{title} {snippet}"
    )


    if not contains_product_name(
        combined,
        product_names
    ):

        return []


    evidence = []


    for product_name in product_names:

        if not product_name:
            continue


        contexts = (
            extract_product_contexts(
                combined,
                product_name,
                before_chars=80,
                after_chars=120
            )
        )


        for context_item in contexts:

            context = context_item[
                "context"
            ]


            candidates = (
                extract_calories_with_distance(
                    context,
                    product_name
                )
            )


            if not candidates:
                continue


            # 只取最近的热量
            best = candidates[
                0
            ]


            value = best[
                "calories"
            ]


            # ------------------------------------------------
            # 基础合理范围
            # ------------------------------------------------

            if not (
                0
                <= value
                <= 800
            ):

                continue


            evidence.append(
                {
                    "calories":
                        value,

                    "distance":
                        best[
                            "distance"
                        ],

                    "url":
                        url,

                    "title":
                        title,

                    "platform":
                        platform,

                    "location":
                        "social_search_snippet",

                    "matched_name":
                        product_name,

                    "context":
                        context,
                }
            )


    return evidence


# ============================================================
# 8. 社交媒体公开搜索
# ============================================================

def search_social_calories(
        brand,
        name_cn,
        name_en="",
        max_results=MAX_RESULTS_PER_QUERY
):

    product_names = [
        name_cn,
    ]


    if (
        name_en
        and
        name_en != name_cn
    ):

        product_names.append(
            name_en
        )


    queries = build_social_queries(
        brand=brand,
        name_cn=name_cn,
        name_en=name_en
    )


    all_evidence = []

    seen_results = set()


    print()
    print(
        "📱 开始搜索中国大陆公开平台"
    )


    for query in queries:

        print(
            f"   🔎 {query}"
        )


        results = search_query(
            query,
            max_results=max_results
        )


        for result in results:

            url = result[
                "url"
            ]


            # 同 URL 不重复分析
            key = url

            if key in seen_results:
                continue


            seen_results.add(
                key
            )


            evidence = (
                extract_social_evidence(
                    result,
                    product_names
                )
            )


            if not evidence:
                continue


            all_evidence.extend(
                evidence
            )


            values = [
                item[
                    "calories"
                ]
                for item
                in evidence
            ]


            print(
                f"      ✅ "
                f"{result['platform']}: "
                f"{values}"
            )


        time.sleep(
            SEARCH_DELAY
        )


    # ========================================================
    # URL + kcal 去重
    # ========================================================

    unique = []

    seen = set()


    for item in all_evidence:

        key = (
            item[
                "url"
            ],
            item[
                "calories"
            ]
        )


        if key in seen:
            continue


        seen.add(
            key
        )

        unique.append(
            item
        )


    print()
    print(
        f"📱 社交平台共获得 "
        f"{len(unique)} 条候选证据"
    )


    return unique
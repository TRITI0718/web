import re
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page


# ============================================================
# 1. 基础配置
# ============================================================

BASE_URL = "https://www.starbucks.com"


# Starbucks 饮品分类页面
CATEGORY_URLS = [
    "https://www.starbucks.com/menu/drinks/hot-coffee",
    "https://www.starbucks.com/menu/drinks/cold-coffee",
    "https://www.starbucks.com/menu/drinks/matcha",
    "https://www.starbucks.com/menu/drinks/hot-tea",
    "https://www.starbucks.com/menu/drinks/cold-tea",
    "https://www.starbucks.com/menu/drinks/refreshers",
    "https://www.starbucks.com/menu/drinks/frappuccino-blended-beverage",
    "https://www.starbucks.com/menu/drinks/hot-chocolate-lemonade-more",
]


# ============================================================
# 2. 官方产品种子链接
#
# 作用：
# 如果 Starbucks 改网页结构导致自动发现失败，
# 至少仍然有一批真实官方产品可以继续爬。
# ============================================================

SEED_PRODUCT_URLS = [

    # ---------- Coffee ----------

    "https://www.starbucks.com/menu/product/407/hot/nutrition",
    "https://www.starbucks.com/menu/product/407/iced/nutrition",

    "https://www.starbucks.com/menu/product/408/hot/nutrition",

    "https://www.starbucks.com/menu/product/413/hot/nutrition",

    "https://www.starbucks.com/menu/product/2122164/hot/nutrition",


    # ---------- Frappuccino ----------

    "https://www.starbucks.com/menu/product/483/iced/nutrition",

    "https://www.starbucks.com/menu/product/424/iced/nutrition",

    "https://www.starbucks.com/menu/product/426/iced/nutrition",


    # ---------- Refreshers ----------

    "https://www.starbucks.com/menu/product/2121342/iced/nutrition",

    "https://www.starbucks.com/menu/product/2122725/iced/nutrition",

    "https://www.starbucks.com/menu/product/40475/iced/nutrition",

    "https://www.starbucks.com/menu/product/40494/iced/nutrition",


    # ---------- Tea ----------

    "https://www.starbucks.com/menu/product/457/iced/nutrition",

    "https://www.starbucks.com/menu/product/459/iced/nutrition",

    "https://www.starbucks.com/menu/product/461/iced/nutrition",

    "https://www.starbucks.com/menu/product/2122274/hot/nutrition",


    # ---------- Matcha ----------

    "https://www.starbucks.com/menu/product/468/iced/nutrition",


    # ---------- Protein drinks ----------

    "https://www.starbucks.com/menu/product/28576/hot/nutrition",

    "https://www.starbucks.com/menu/product/28498/iced/nutrition",

    "https://www.starbucks.com/menu/product/34819/hot/nutrition",
]


# ============================================================
# 3. 判断是否是饮品 URL
# ============================================================

def is_product_url(url):
    """
    只接受 Starbucks 产品 hot / iced 页面。

    排除：
    /single
    等食品页面。
    """

    if not url:
        return False

    url = str(url)

    if "/menu/product/" not in url:
        return False

    if "/hot" not in url and "/iced" not in url:
        return False

    return True


# ============================================================
# 4. URL 标准化
# ============================================================

def normalize_product_url(url):
    """
    将：

    /menu/product/407/hot

    转换为：

    https://www.starbucks.com/menu/product/407/hot/nutrition
    """

    full_url = urljoin(
        BASE_URL,
        str(url)
    )

    parsed = urlparse(
        full_url
    )

    clean_url = (
        f"{parsed.scheme}://"
        f"{parsed.netloc}"
        f"{parsed.path}"
    )

    clean_url = clean_url.rstrip("/")


    if clean_url.endswith(
        "/nutrition"
    ):
        return clean_url


    return (
        clean_url
        + "/nutrition"
    )


# ============================================================
# 5. 从文本中寻找产品路径
# ============================================================

def extract_product_urls_from_text(text):
    """
    不管文本来自 HTML、JSON 还是 JavaScript，
    都尝试寻找：

    /menu/product/123/hot
    /menu/product/123/iced
    """

    urls = set()

    if not text:
        return urls


    matches = re.findall(
        r"/menu/product/\d+/(?:hot|iced)"
        r"(?:/nutrition)?",
        text,
        re.IGNORECASE
    )


    for match in matches:

        urls.add(
            normalize_product_url(
                match
            )
        )


    return urls


# ============================================================
# 6. 从普通 HTML 链接中发现
# ============================================================

def discover_from_links(page: Page):
    """
    扫描页面里的普通 <a href="">
    """

    discovered = set()

    try:

        hrefs = page.locator(
            "a"
        ).evaluate_all(
            """
            elements =>
                elements.map(
                    element => element.href || ""
                )
            """
        )


        for href in hrefs:

            if is_product_url(
                href
            ):

                discovered.add(
                    normalize_product_url(
                        href
                    )
                )


    except Exception as error:

        print(
            f"⚠️ 扫描页面链接失败：{error}"
        )


    return discovered


# ============================================================
# 7. 扫描 HTML 源码
# ============================================================

def discover_from_html(page: Page):

    discovered = set()

    try:

        html = page.content()

        discovered.update(
            extract_product_urls_from_text(
                html
            )
        )

    except Exception as error:

        print(
            f"⚠️ 扫描 HTML 失败：{error}"
        )


    return discovered


# ============================================================
# 8. 访问一个分类页面
# ============================================================

def discover_from_category(
        page: Page,
        category_url: str
):
    """
    打开分类页，例如：

    /menu/drinks/refreshers

    然后扫描产品 URL。
    """

    discovered = set()


    print()
    print(
        f"正在扫描分类：{category_url}"
    )


    try:

        page.goto(
            category_url,
            wait_until="domcontentloaded",
            timeout=60000
        )


        page.wait_for_timeout(
            3000
        )


        # 多滚几次，触发潜在懒加载
        for _ in range(6):

            page.mouse.wheel(
                0,
                1800
            )

            page.wait_for_timeout(
                400
            )


        discovered.update(
            discover_from_links(
                page
            )
        )


        discovered.update(
            discover_from_html(
                page
            )
        )


        print(
            f"   找到 {len(discovered)} 个链接"
        )


    except Exception as error:

        print(
            f"⚠️ 分类页面读取失败：{error}"
        )


    return discovered


# ============================================================
# 9. 总产品发现函数
# ============================================================

def discover_starbucks_products(
        page: Page
):
    """
    最终返回：

    [
        {
            "url": "...",
            "discovery_method": "auto"
        },
        ...
    ]
    """

    print()
    print("=" * 55)
    print("🔎 Starbucks 产品发现器")
    print("=" * 55)


    discovered = set()


    # ========================================================
    # A. 自动读取分类页面
    # ========================================================

    for category_url in CATEGORY_URLS:

        urls = discover_from_category(
            page,
            category_url
        )

        discovered.update(
            urls
        )


    auto_count = len(
        discovered
    )


    print()
    print(
        f"✅ 自动发现：{auto_count} 个产品"
    )


    # ========================================================
    # B. 官方种子链接兜底
    # ========================================================

    seeds = {
        normalize_product_url(url)
        for url in SEED_PRODUCT_URLS
    }


    before_seed = len(
        discovered
    )


    discovered.update(
        seeds
    )


    added_seed_count = (
        len(discovered)
        - before_seed
    )


    print(
        f"✅ 种子链接补充：{added_seed_count} 个"
    )


    print(
        f"✅ 最终可用产品：{len(discovered)} 个"
    )


    # ========================================================
    # C. 整理
    # ========================================================

    products = []


    for url in sorted(
        discovered
    ):

        products.append(
            {
                "url": url,

                "discovery_method": (
                    "auto"
                    if url not in seeds
                    else "seed"
                )
            }
        )


    return products


# ============================================================
# 10. 单独运行该文件时用于测试
# ============================================================

if __name__ == "__main__":

    print(
        "这个文件负责 Starbucks 产品发现。"
    )

    print(
        "请运行："
    )

    print(
        "python scraper/starbucks.py"
    )
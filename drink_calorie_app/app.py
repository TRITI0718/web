import html
from pathlib import Path

import pandas as pd
import streamlit as st

from database.database import load_drinks
from scraper import manual_products

from utils.color import get_calorie_color

from utils.product_manager import (
    load_products,
    save_products,
    get_product_stats,
    sync_database_with_products,
    get_enabled_product_keys,
)


# ============================================================
# 1. 页面配置
# ============================================================

st.set_page_config(
    page_title="DRINK CALORIE",
    page_icon=":material/local_cafe:",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# 2. 项目路径
# ============================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
)

CSS_FILE = (
    BASE_DIR
    / "assets"
    / "style.css"
)


# ============================================================
# 3. 加载独立 CSS
# ============================================================

if CSS_FILE.exists():

    st.markdown(
        f"""
        <style>
        {CSS_FILE.read_text(encoding="utf-8")}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# 4. 页面导航
# ============================================================

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand-icon">茶</div>
            <div>
                <strong>饮品轻卡</strong>
                <span>喝得明白，也喝得轻松</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    page = st.radio(
        "功能",
        [
            "🥤 营养排行榜",
            "📝 商品管理",
        ],
    )
    st.caption("数据仅供日常饮食参考")


# ============================================================
# 5. 分类配置
# ============================================================

CATEGORY_OPTIONS = [
    "拿铁",
    "美式咖啡",
    "咖啡",
    "奶茶",
    "果茶",
    "果饮",
    "茶饮",
    "纯茶",
    "抹茶",
    "奶昔",
    "冰淇淋",
    "星冰乐",
    "冰沙",
    "其他饮品",
]


CATEGORY_DISPLAY_MAP = {

    "能力茶":
        "茶饮",

    "咖啡":
        "咖啡",

    "拿铁":
        "拿铁",

    "美式咖啡":
        "美式咖啡",

    "星冰乐":
        "星冰乐",

    "抹茶":
        "抹茶",

    "奶茶":
        "奶茶",

    "纯茶":
        "纯茶",

    "果茶":
        "果茶",

    "茶饮":
        "茶饮",

    "果饮":
        "果饮",

    "冰淇淋":
        "冰淇淋",

    "奶昔":
        "奶昔",

    "冰沙":
        "冰沙",

    "其他饮品":
        "其他饮品",
}


BRAND_OPTIONS = [
    "瑞幸",
    "喜茶",
    "蜜雪冰城",
    "星巴克",
]


# ============================================================
# 6. 通用工具函数
# ============================================================

def safe_text(value):

    if pd.isna(
        value
    ):

        return ""

    return html.escape(
        str(
            value
        )
    )


# ------------------------------------------------------------
# 商品显示名
# ------------------------------------------------------------

def get_display_name(row):

    name_cn = str(
        row.get(
            "name_cn",
            ""
        )
    ).strip()

    name = str(
        row.get(
            "name",
            ""
        )
    ).strip()


    # 人工中文名最高优先级
    if (
        name_cn
        and
        name_cn.lower()
        not in {
            "nan",
            "none",
        }
    ):

        return name_cn


    if (
        name
        and
        name.lower()
        not in {
            "nan",
            "none",
        }
    ):

        return name


    return "未命名饮品"


# ------------------------------------------------------------
# 分类显示
# ------------------------------------------------------------

def get_display_category(row):

    category = str(
        row.get(
            "category",
            ""
        )
    ).strip()


    if not category:

        return "其他饮品"


    return CATEGORY_DISPLAY_MAP.get(
        category,
        category,
    )


# ------------------------------------------------------------
# 数值格式
# ------------------------------------------------------------

def format_value(
        row,
        column,
        unit,
):

    value = row.get(
        column
    )


    if pd.isna(
        value
    ):

        return "暂无"


    try:

        value = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        return "暂无"


    return (
        f"{value:g}"
        f"{unit}"
    )


# ------------------------------------------------------------
# 来源标签
# ------------------------------------------------------------

def get_source_badge(
        source_type
):

    source_type = (
        str(
            source_type
        )
        .strip()
        .lower()
    )


    if source_type == "official":

        return (
            '<span class="source-badge source-official">'
            '官方数据'
            '</span>'
        )


    if source_type == "third_party":

        return (
            '<span class="source-badge source-third">'
            '第三方聚合'
            '</span>'
        )


    return (
        '<span class="source-badge source-other">'
        '来源未分类'
        '</span>'
    )


# ============================================================
# 7. 商品管理页
# ============================================================

if page == "📝 商品管理":

    st.markdown(
        """
        <div class="page-hero page-hero-manage">
            <span class="eyebrow">饮品数据库</span>
            <h1>商品管理</h1>
            <p>集中维护品牌、品类与启用状态，让排行榜始终清晰可靠。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


    st.markdown(
        """
        <div class="manage-note">
        商品表是当前中国大陆商品名称的唯一管理入口。
        新增、改名、删除、启用或停用商品后，
        保存时会自动同步数据库。
        </div>
        """,
        unsafe_allow_html=True,
    )


    # ========================================================
    # 7.1 热量更新成功提示
    # ========================================================

    if st.session_state.pop(
        "calorie_update_success",
        False,
    ):

        st.success(
            "✅ 最新热量已经写入数据库。"
            "切换到“营养排行榜”即可查看最新结果。"
        )


    # ========================================================
    # 7.2 读取商品表
    # ========================================================

    products_df = load_products()


    stats = get_product_stats(
        products_df
    )


    # ========================================================
    # 7.3 顶部统计
    # ========================================================

    stat1, stat2, stat3, stat4 = st.columns(
        4
    )


    with stat1:

        st.metric(
            "商品总数",
            stats[
                "total"
            ],
        )


    with stat2:

        st.metric(
            "已启用",
            stats[
                "enabled"
            ],
        )


    with stat3:

        st.metric(
            "已停用",
            stats[
                "disabled"
            ],
        )


    with stat4:

        st.metric(
            "品牌数量",
            stats[
                "brands"
            ],
        )


    st.divider()


    # ========================================================
    # 7.4 新增商品
    # ========================================================

    st.subheader(
        "➕ 新增商品"
    )


    with st.form(
        "add_product_form",
        clear_on_submit=True,
    ):

        add_col1, add_col2 = st.columns(
            2
        )


        with add_col1:

            new_brand = st.selectbox(
                "品牌",
                BRAND_OPTIONS,
                key="new_brand",
            )


            new_name_cn = st.text_input(
                "中国大陆商品名 *",
                placeholder="例如：生椰拿铁",
            )


            new_category = st.selectbox(
                "类别",
                CATEGORY_OPTIONS,
                key="new_category",
            )


        with add_col2:

            new_name_en = st.text_input(
                "英文名（可选）",
                placeholder="例如：Coconut Latte",
            )


            new_enabled = st.checkbox(
                "立即启用",
                value=True,
            )


        submitted = st.form_submit_button(
            "添加商品",
            type="primary",
            width="stretch",
        )


        if submitted:

            new_name_cn = (
                new_name_cn
                .strip()
            )

            new_name_en = (
                new_name_en
                .strip()
            )


            if not new_name_cn:

                st.error(
                    "商品中文名不能为空。"
                )


            else:

                duplicate = (
                    (
                        products_df[
                            "brand"
                        ]
                        .fillna("")
                        .astype(str)
                        .str.strip()
                        ==
                        new_brand
                    )
                    &
                    (
                        products_df[
                            "name_cn"
                        ]
                        .fillna("")
                        .astype(str)
                        .str.strip()
                        ==
                        new_name_cn
                    )
                ).any()


                if duplicate:

                    st.warning(
                        "这个品牌已经存在同名商品。"
                    )


                else:

                    new_row = pd.DataFrame(
                        [
                            {
                                "brand":
                                    new_brand,

                                "name_cn":
                                    new_name_cn,

                                "name_en":
                                    new_name_en,

                                "category":
                                    new_category,

                                "enabled":
                                    (
                                        1
                                        if new_enabled
                                        else 0
                                    ),
                            }
                        ]
                    )


                    new_products_df = pd.concat(
                        [
                            products_df,
                            new_row,
                        ],
                        ignore_index=True,
                    )


                    cleaned_df = save_products(
                        new_products_df
                    )


                    sync_result = (
                        sync_database_with_products(
                            cleaned_df
                        )
                    )


                    st.cache_data.clear()


                    message = (
                        f"✅ 已添加："
                        f"{new_brand} · "
                        f"{new_name_cn}"
                    )


                    removed = (
                        sync_result.get(
                            "removed",
                            0,
                        )
                    )


                    if removed > 0:

                        message += (
                            f"；同时清除了 "
                            f"{removed} 条旧数据库记录"
                        )


                    st.success(
                        message
                    )


                    st.rerun()


    st.divider()


    # ========================================================
    # 7.5 编辑商品
    # ========================================================

    st.subheader(
        "✏️ 编辑商品"
    )


    management_brand = st.selectbox(
        "筛选品牌",
        [
            "全部",
            *BRAND_OPTIONS,
        ],
        key="management_brand",
    )


    if management_brand == "全部":

        editor_source_df = (
            products_df.copy()
        )

    else:

        editor_source_df = (
            products_df[
                products_df[
                    "brand"
                ]
                ==
                management_brand
            ]
            .copy()
        )


    editor_df = (
        editor_source_df.copy()
    )


    if not editor_df.empty:

        editor_df[
            "enabled"
        ] = (
            editor_df[
                "enabled"
            ]
            .fillna(1)
            .astype(int)
            .astype(bool)
        )


    st.caption(
        "可以直接修改表格。删除一整行即删除商品；"
        "取消“启用”后不会继续爬取，并会从排行榜隐藏。"
    )


    edited_df = st.data_editor(

        editor_df,

        width="stretch",

        hide_index=True,

        num_rows="dynamic",

        column_config={

            "brand":
                st.column_config.SelectboxColumn(
                    "品牌",
                    options=BRAND_OPTIONS,
                    required=True,
                ),

            "name_cn":
                st.column_config.TextColumn(
                    "中国大陆商品名",
                    required=True,
                ),

            "name_en":
                st.column_config.TextColumn(
                    "英文名",
                ),

            "category":
                st.column_config.SelectboxColumn(
                    "类别",
                    options=CATEGORY_OPTIONS,
                ),

            "enabled":
                st.column_config.CheckboxColumn(
                    "启用",
                    help=(
                        "启用后 manual_products.py "
                        "才会处理该商品。"
                    ),
                ),
        },

        key="product_editor",
    )


    save_col1, save_col2 = st.columns(
        [
            1,
            3,
        ]
    )


    with save_col1:

        if st.button(
            "💾 保存修改",
            type="primary",
            width="stretch",
        ):

            edited_df = (
                edited_df.copy()
            )


            if not edited_df.empty:

                edited_df[
                    "enabled"
                ] = (
                    edited_df[
                        "enabled"
                    ]
                    .fillna(False)
                    .astype(bool)
                    .astype(int)
                )


            # =================================================
            # 编辑全部品牌
            # =================================================

            if management_brand == "全部":

                final_df = (
                    edited_df.copy()
                )


            # =================================================
            # 只编辑一个品牌
            # =================================================

            else:

                other_df = (
                    products_df[
                        products_df[
                            "brand"
                        ]
                        !=
                        management_brand
                    ]
                    .copy()
                )


                final_df = pd.concat(
                    [
                        other_df,
                        edited_df,
                    ],
                    ignore_index=True,
                )


            cleaned_df = save_products(
                final_df
            )


            sync_result = (
                sync_database_with_products(
                    cleaned_df
                )
            )


            st.cache_data.clear()


            removed = (
                sync_result.get(
                    "removed",
                    0,
                )
            )


            message = (
                f"✅ 已保存 "
                f"{len(cleaned_df)} 款商品"
            )


            if removed > 0:

                message += (
                    f"，并自动清除了 "
                    f"{removed} 条旧数据库记录"
                )


            st.success(
                message
            )


            st.rerun()


    with save_col2:

        st.caption(
            "保存前会自动备份上一版商品表到 "
            "`data/product_names_backup.csv`。"
        )


    st.divider()


    # ========================================================
    # 7.6 商品分布
    # ========================================================

    st.subheader(
        "📊 商品分布"
    )


    if products_df.empty:

        st.info(
            "目前没有商品。"
        )


    else:

        brand_stats = (
            products_df
            .groupby(
                "brand"
            )
            .agg(
                商品数量=(
                    "name_cn",
                    "count"
                ),

                已启用=(
                    "enabled",
                    "sum"
                ),
            )
            .reset_index()
        )


        brand_stats[
            "已停用"
        ] = (
            brand_stats[
                "商品数量"
            ]
            -
            brand_stats[
                "已启用"
            ]
        )


        st.dataframe(
            brand_stats,
            width="stretch",
            hide_index=True,
        )


    st.divider()


    # ========================================================
    # 7.7 热量更新
    # ========================================================

    st.subheader(
        "🕷️ 更新热量数据"
    )


    st.caption(
        "每次运行都会重新查询所选范围，"
        "并彻底覆盖对应商品的旧数据。"
    )


    run_brand = st.selectbox(
        "运行范围",
        [
            "全部品牌",
            *BRAND_OPTIONS,
        ],
        key="run_brand",
    )


    # ========================================================
    # 7.8 直接执行爬虫
    # ========================================================

    if st.button(
        "🚀 开始更新热量",
        type="primary",
        width="stretch",
    ):

        # ----------------------------------------------------
        # 重新读取最新商品表
        # ----------------------------------------------------

        latest_products = (
            load_products()
        )


        # ----------------------------------------------------
        # 先同步数据库
        # ----------------------------------------------------

        sync_result = (
            sync_database_with_products(
                latest_products
            )
        )


        removed = (
            sync_result.get(
                "removed",
                0,
            )
        )


        if removed > 0:

            st.info(
                f"🧹 已清除 "
                f"{removed} 条"
                f"不再存在的旧商品记录。"
            )


        # ----------------------------------------------------
        # 设置品牌
        # ----------------------------------------------------

        if run_brand == "全部品牌":

            manual_products.ONLY_BRAND = None

        else:

            manual_products.ONLY_BRAND = (
                run_brand
            )


        # ----------------------------------------------------
        # 每次查询都强制刷新
        # ----------------------------------------------------

        manual_products.FORCE_REFRESH = True


        # ----------------------------------------------------
        # 执行
        # ----------------------------------------------------

        try:

            with st.spinner(
                "正在搜索公开网页和公开社交平台，"
                "并聚合热量数据..."
            ):

                manual_products.main()


            # ------------------------------------------------
            # 清缓存
            # ------------------------------------------------

            st.cache_data.clear()


            # ------------------------------------------------
            # 再读取数据库验证
            # ------------------------------------------------

            verify_df = (
                load_drinks()
            )


            if (
                run_brand
                !=
                "全部品牌"
                and
                not verify_df.empty
                and
                "brand"
                in verify_df.columns
            ):

                brand_count = len(
                    verify_df[
                        verify_df[
                            "brand"
                        ]
                        .fillna("")
                        .astype(str)
                        .str.strip()
                        ==
                        run_brand
                    ]
                )


                st.success(
                    f"✅ 热量更新完成。"
                    f"数据库目前有 "
                    f"{brand_count} 条 "
                    f"{run_brand} 数据。"
                )


            else:

                st.success(
                    f"✅ 热量更新完成。"
                    f"数据库目前共有 "
                    f"{len(verify_df)} 条饮品数据。"
                )


            st.session_state[
                "calorie_update_success"
            ] = True


            st.rerun()


        except Exception as error:

            st.error(
                f"❌ 热量更新失败：{error}"
            )


            st.exception(
                error
            )


    st.stop()


# ============================================================
# 8. 排行榜：读取数据库
#
# 调试阶段不使用 st.cache_data，
# 确保每次 rerun 都直接读取 SQLite。
# ============================================================

def load_data():

    df = load_drinks()


    if (
        df is None
        or
        df.empty
    ):

        return pd.DataFrame()


    df = df.copy()


    # ========================================================
    # 数值字段
    # ========================================================

    numeric_columns = [
        "calories",
        "sugar",
        "fat",
        "protein",
        "caffeine",
        "carbs",
        "sodium",
        "ounces",
        "source_count",
        "calorie_min",
        "calorie_max",
    ]


    for column in numeric_columns:

        if column in df.columns:

            df[
                column
            ] = pd.to_numeric(
                df[
                    column
                ],
                errors="coerce",
            )


    # ========================================================
    # 文本字段
    # ========================================================

    text_columns = [
        "brand",
        "name",
        "name_cn",
        "category",
        "size",
        "ingredients",
        "source",
        "source_url",
        "source_type",
        "source_platform",
        "market",
        "scraped_at",
    ]


    for column in text_columns:

        if column not in df.columns:

            df[
                column
            ] = ""


        df[
            column
        ] = (
            df[
                column
            ]
            .fillna("")
            .astype(str)
            .str.strip()
        )


    return df


# ============================================================
# 9. 加载排行榜数据
# ============================================================

df = load_data()


# ============================================================
# 10. product_names.csv 控制排行榜显示
#
# 商品身份统一：
#
#     brand + name_cn
# ============================================================

products_for_display = (
    load_products()
)


enabled_keys = (
    get_enabled_product_keys(
        products_for_display
    )
)


managed_brands = set(
    products_for_display[
        "brand"
    ]
    .fillna("")
    .astype(str)
    .str.strip()
    .unique()
)


def should_show_row(row):

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


    # --------------------------------------------------------
    # 没由人工商品表管理的品牌继续显示
    # --------------------------------------------------------

    if brand not in managed_brands:

        return True


    # --------------------------------------------------------
    # 人工管理品牌严格按照 brand + name_cn
    # --------------------------------------------------------

    return (
        brand,
        name_cn,
    ) in enabled_keys


if not df.empty:

    display_mask = (
        df.apply(
            should_show_row,
            axis=1,
        )
    )


    df = (
        df[
            display_mask
        ]
        .copy()
    )


# ============================================================
# 11. 没有数据
# ============================================================

if df.empty:

    st.title(
        "DRINK CALORIE"
    )


    st.warning(
        "当前没有可显示的饮品数据。"
        "请进入“商品管理”新增商品并更新热量。"
    )


    st.stop()


# ============================================================
# 12. 营养指标
# ============================================================

METRICS = {

    "🔥 热量": {
        "column":
            "calories",

        "unit":
            "千卡",
    },

    "🍬 糖": {
        "column":
            "sugar",

        "unit":
            "克",
    },

    "🥛 脂肪": {
        "column":
            "fat",

        "unit":
            "克",
    },

    "💪 蛋白质": {
        "column":
            "protein",

        "unit":
            "克",
    },

    "☕ 咖啡因": {
        "column":
            "caffeine",

        "unit":
            "毫克",
    },
}


# ============================================================
# 13. 页面标题
# ============================================================

st.markdown(
    """
    <div class="page-hero page-hero-brand">
        <h1>DRINK CALORIE</h1>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 14. 首页数据范围
# ============================================================

official_heytea_mask = (
    df["brand"].eq("喜茶")
    & df["source_type"].str.lower().eq("official")
)

official_heytea_count = int(
    official_heytea_mask.sum()
)


if official_heytea_count:

    data_scope = st.segmented_control(
        "首页数据范围",
        [
            "喜茶官方数据",
            "全部饮品",
        ],
        default="喜茶官方数据",
        label_visibility="collapsed",
        width="stretch",
    )


    if data_scope == "喜茶官方数据":

        display_df = (
            df[
                official_heytea_mask
            ]
            .copy()
        )


        st.caption(
            f"已载入 {official_heytea_count} 款喜茶官方热量数据"
        )


    else:

        display_df = df.copy()


else:

    display_df = df.copy()


# ============================================================
# 15. 搜索框
# ============================================================

keyword = st.text_input(
    "🔎 搜索饮品",
    placeholder=(
        "例如：生椰、拿铁、抹茶、葡萄、美式..."
    ),
)


# ============================================================
# 15. 第一排筛选
# ============================================================

filter_col1, filter_col2, filter_col3 = st.columns(
    3
)


# ------------------------------------------------------------
# 品牌
# ------------------------------------------------------------

with filter_col1:

    brands = [
        "全部"
    ]


    brands += sorted(
        [
            item
            for item
            in display_df[
                "brand"
            ]
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
            .tolist()
            if item
        ]
    )


    selected_brand = st.selectbox(
        "品牌",
        brands,
    )


# ------------------------------------------------------------
# 类别
# ------------------------------------------------------------

with filter_col2:

    raw_categories = (
        display_df[
            "category"
        ]
        .dropna()
        .astype(str)
        .str.strip()
        .tolist()
    )


    display_categories = sorted(
        set(
            CATEGORY_DISPLAY_MAP.get(
                category,
                category,
            )
            for category
            in raw_categories
            if category
        )
    )


    selected_category = st.selectbox(
        "类别",
        [
            "全部",
            *display_categories,
        ],
    )


# ------------------------------------------------------------
# 指标
# ------------------------------------------------------------

with filter_col3:

    selected_metric = st.selectbox(
        "指标营养",
        list(
            METRICS.keys()
        ),
    )


# ============================================================
# 16. 第二排筛选
# ============================================================

filter_col4, filter_col5, filter_col6 = st.columns(
    3
)


# ------------------------------------------------------------
# 杯型
# ------------------------------------------------------------

with filter_col4:

    valid_sizes = (
        display_df[
            "size"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
    )


    valid_sizes = sorted(
        [
            item
            for item
            in valid_sizes.unique().tolist()
            if item
        ]
    )


    selected_size = st.selectbox(
        "杯型",
        [
            "全部",
            *valid_sizes,
        ],
    )


# ------------------------------------------------------------
# 数据来源
# ------------------------------------------------------------

with filter_col5:

    source_filter = st.selectbox(
        "数据来源",
        [
            "全部",
            "官方数据",
            "第三方数据",
        ],
    )


# ------------------------------------------------------------
# 排序
# ------------------------------------------------------------

with filter_col6:

    sort_order = st.selectbox(
        "排序方式",
        [
            "由高到低",
            "由低到高",
        ],
    )


# ============================================================
# 17. 热量区间
# ============================================================

st.markdown(
    "### 热量区间"
)


calorie_filter = st.segmented_control(
    "热量区间",
    [
        "全部",
        "0–100千卡",
        "100–200千卡",
        "200–300千卡",
        "300千卡以上",
    ],
    label_visibility="collapsed",
    width="stretch",
)


# ============================================================
# 18. 当前指标
# ============================================================

metric_column = (
    METRICS[
        selected_metric
    ][
        "column"
    ]
)


metric_unit = (
    METRICS[
        selected_metric
    ][
        "unit"
    ]
)


# ============================================================
# 19. 开始筛选
# ============================================================

filtered_df = (
    display_df.copy()
)


# ------------------------------------------------------------
# 品牌
# ------------------------------------------------------------

if selected_brand != "全部":

    filtered_df = (
        filtered_df[
            filtered_df[
                "brand"
            ]
            ==
            selected_brand
        ]
    )


# ------------------------------------------------------------
# 分类
# ------------------------------------------------------------

if selected_category != "全部":

    category_mask = (
        filtered_df[
            "category"
        ]
        .astype(str)
        .apply(
            lambda value:
                CATEGORY_DISPLAY_MAP.get(
                    value,
                    value,
                )
                ==
                selected_category
        )
    )


    filtered_df = (
        filtered_df[
            category_mask
        ]
    )


# ------------------------------------------------------------
# 杯型
# ------------------------------------------------------------

if selected_size != "全部":

    filtered_df = (
        filtered_df[
            filtered_df[
                "size"
            ]
            ==
            selected_size
        ]
    )


# ------------------------------------------------------------
# 数据来源
# ------------------------------------------------------------

if source_filter == "官方数据":

    filtered_df = (
        filtered_df[
            filtered_df[
                "source_type"
            ]
            ==
            "official"
        ]
    )


elif source_filter == "第三方数据":

    filtered_df = (
        filtered_df[
            filtered_df[
                "source_type"
            ]
            ==
            "third_party"
        ]
    )


# ------------------------------------------------------------
# 搜索
# ------------------------------------------------------------

if keyword:

    keyword = (
        keyword
        .strip()
    )


    search_mask = pd.Series(
        False,
        index=filtered_df.index,
    )


    for column in [
        "name",
        "name_cn",
        "brand",
        "category",
        "ingredients",
    ]:

        if column not in filtered_df.columns:

            continue


        search_mask |= (
            filtered_df[
                column
            ]
            .fillna("")
            .astype(str)
            .str.contains(
                keyword,
                case=False,
                na=False,
            )
        )


    display_names = (
        filtered_df.apply(
            get_display_name,
            axis=1,
        )
    )


    search_mask |= (
        display_names
        .astype(str)
        .str.contains(
            keyword,
            case=False,
            na=False,
        )
    )


    filtered_df = (
        filtered_df[
            search_mask
        ]
    )


# ------------------------------------------------------------
# 热量区间
# ------------------------------------------------------------

if calorie_filter == "0–100千卡":

    filtered_df = (
        filtered_df[
            filtered_df[
                "calories"
            ]
            .between(
                0,
                100,
                inclusive="both",
            )
        ]
    )


elif calorie_filter == "100–200千卡":

    filtered_df = (
        filtered_df[
            (
                filtered_df[
                    "calories"
                ]
                >
                100
            )
            &
            (
                filtered_df[
                    "calories"
                ]
                <=
                200
            )
        ]
    )


elif calorie_filter == "200–300千卡":

    filtered_df = (
        filtered_df[
            (
                filtered_df[
                    "calories"
                ]
                >
                200
            )
            &
            (
                filtered_df[
                    "calories"
                ]
                <=
                300
            )
        ]
    )


elif calorie_filter == "300千卡以上":

    filtered_df = (
        filtered_df[
            filtered_df[
                "calories"
            ]
            >
            300
        ]
    )


# ============================================================
# 20. 当前指标必须有值
# ============================================================

if metric_column not in filtered_df.columns:

    st.error(
        f"数据库缺少字段：{metric_column}"
    )

    st.stop()


filtered_df = (
    filtered_df.dropna(
        subset=[
            metric_column
        ]
    )
)


# ============================================================
# 21. 排序
# ============================================================

ascending = (
    sort_order
    ==
    "由低到高"
)


filtered_df = (
    filtered_df.sort_values(
        metric_column,
        ascending=ascending,
    )
)


# ============================================================
# 22. 顶部统计
# ============================================================

st.divider()


stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(
    4
)


with stat_col1:

    st.metric(
        "饮品数量",
        len(
            filtered_df
        ),
    )


with stat_col2:

    if filtered_df.empty:

        st.metric(
            "平均值",
            "-",
        )

    else:

        average_value = (
            filtered_df[
                metric_column
            ]
            .mean()
        )


        st.metric(
            "平均值",
            (
                f"{average_value:.1f}"
                f"{metric_unit}"
            ),
        )


with stat_col3:

    if filtered_df.empty:

        st.metric(
            "最高值",
            "-",
        )

    else:

        highest_value = (
            filtered_df[
                metric_column
            ]
            .max()
        )


        st.metric(
            "最高值",
            (
                f"{highest_value:g}"
                f"{metric_unit}"
            ),
        )


with stat_col4:

    st.metric(
        "品牌数量",
        (
            filtered_df[
                "brand"
            ]
            .nunique()
            if not filtered_df.empty
            else 0
        ),
    )


st.divider()


# ============================================================
# 23. 没有结果
# ============================================================

if filtered_df.empty:

    st.warning(
        "当前筛选条件下没有可显示的饮品。"
    )

    st.stop()


# ============================================================
# 24. 最大值
# ============================================================

max_metric_value = (
    filtered_df[
        metric_column
    ]
    .max(
        skipna=True
    )
)


if pd.isna(
    max_metric_value
):

    max_metric_value = 0


# ============================================================
# 25. 卡片列表
# ============================================================

for rank, (_, row) in enumerate(
    filtered_df.iterrows(),
    start=1,
):

    # ========================================================
    # 当前指标
    # ========================================================

    value = float(
        row[
            metric_column
        ]
    )


    # ========================================================
    # 颜色
    # ========================================================

    color = get_calorie_color(
        value,
        max_metric_value,
    )


    # ========================================================
    # 横条长度
    # ========================================================

    if max_metric_value > 0:

        width = (
            value
            /
            max_metric_value
            *
            100
        )

    else:

        width = 0


    display_width = max(
        width,
        1.5,
    )


    # ========================================================
    # 商品名
    # ========================================================

    display_name = safe_text(
        get_display_name(
            row
        )
    )


    brand = safe_text(
        row.get(
            "brand",
            ""
        )
    )


    category = safe_text(
        get_display_category(
            row
        )
    )


    size = safe_text(
        row.get(
            "size",
            ""
        )
    )


    meta_parts = [
        brand,
        category,
    ]


    if size:

        meta_parts.append(
            size
        )


    meta_text = (
        " · ".join(
            [
                item
                for item
                in meta_parts
                if item
            ]
        )
    )


    # ========================================================
    # 营养信息
    # ========================================================

    calories_text = format_value(
        row,
        "calories",
        "千卡",
    )


    sugar_text = format_value(
        row,
        "sugar",
        "克",
    )


    fat_text = format_value(
        row,
        "fat",
        "克",
    )


    protein_text = format_value(
        row,
        "protein",
        "克",
    )


    caffeine_text = format_value(
        row,
        "caffeine",
        "毫克",
    )


    # ========================================================
    # 来源信息
    # ========================================================

    source_type = (
        str(
            row.get(
                "source_type",
                ""
            )
        )
        .strip()
        .lower()
    )


    source_platform = safe_text(
        row.get(
            "source_platform",
            ""
        )
    )


    source_count = row.get(
        "source_count"
    )


    calorie_min = row.get(
        "calorie_min"
    )


    calorie_max = row.get(
        "calorie_max"
    )


    source_badge = get_source_badge(
        source_type
    )


    # ========================================================
    # 第三方热量显示 ≈
    # ========================================================

    approximate_prefix = ""


    if (
        source_type
        ==
        "third_party"
        and
        metric_column
        ==
        "calories"
    ):

        approximate_prefix = "≈"


    current_metric_text = (
        f"{approximate_prefix}"
        f"{value:g}"
        f"{metric_unit}"
    )


    # ========================================================
    # 原料
    # ========================================================

    ingredients = safe_text(
        row.get(
            "ingredients",
            ""
        )
    )


    if len(
        ingredients
    ) > 180:

        ingredients = (
            ingredients[
                :180
            ]
            +
            "..."
        )


    ingredients_html = ""


    if ingredients:

        ingredients_html = f"""
        <div class="ingredients">
            {ingredients}
        </div>
        """


    # ========================================================
    # 来源说明
    # ========================================================

    source_html = ""


    if source_type == "official":

        source_html = """
        <div class="source-info">
            数据来源：官方营养信息
        </div>
        """


    elif source_type == "third_party":

        pieces = [
            "数据来源：第三方公开网页聚合"
        ]


        if pd.notna(
            source_count
        ):

            try:

                pieces.append(
                    f"{int(source_count)} 个来源"
                )

            except (
                TypeError,
                ValueError,
            ):

                pass


        if source_platform:

            pieces.append(
                source_platform
            )


        source_line = (
            " · ".join(
                pieces
            )
        )


        range_html = ""


        if (
            pd.notna(
                calorie_min
            )
            and
            pd.notna(
                calorie_max
            )
        ):

            try:

                range_html = (
                    "<br>"
                    "热量范围："
                    f"{float(calorie_min):g}"
                    "–"
                    f"{float(calorie_max):g}"
                    "千卡"
                )

            except (
                TypeError,
                ValueError,
            ):

                range_html = ""


        source_html = f"""
        <div class="source-info">
            {source_line}
            {range_html}
        </div>
        """


    # ========================================================
    # HTML 卡片
    # ========================================================

    card_html = f"""
    <div class="drink-card">

        <div class="drink-header">

            <div class="drink-left">

                <div class="drink-rank">
                    #{rank}
                </div>

                <div>

                    <div class="drink-name">
                        {display_name}
                    </div>

                    <div class="drink-meta">
                        {meta_text}
                    </div>

                    {source_badge}

                </div>

            </div>


            <div
                class="metric-big"
                style="color:{color};"
            >
                {current_metric_text}
            </div>

        </div>


        <div class="nutrition-row">

            <div class="nutrition-chip">
                🔥 {calories_text}
            </div>

            <div class="nutrition-chip">
                🍬 {sugar_text}
            </div>

            <div class="nutrition-chip">
                🥛 {fat_text}
            </div>

            <div class="nutrition-chip">
                💪 {protein_text}
            </div>

            <div class="nutrition-chip">
                ☕ {caffeine_text}
            </div>

        </div>


        <div class="bar-background">

            <div style="
                width:{display_width}%;
                height:100%;
                background:{color};
                border-radius:999px;
            ">
            </div>

        </div>


        {ingredients_html}

        {source_html}

    </div>
    """


    st.html(
        card_html
    )

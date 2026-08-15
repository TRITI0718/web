# 饮品营养排行榜

基于 Streamlit 的饮品营养信息查询与商品管理网站，支持品牌、类别、杯型、数据来源、热量区间和营养指标筛选。

## 本地运行

```bash
cd drink_calorie_app
python -m pip install -r requirements.txt
streamlit run app.py
```

默认访问地址为 `http://localhost:8501`。

## 数据更新

网站的“商品管理”页面可以维护商品列表并运行热量更新。每次查询都会重新抓取所选范围，并按品牌和商品名彻底覆盖旧记录。公开网页抓取结果会写入 `data/drinks.db`，同时导出至 `data/drinks.csv`。

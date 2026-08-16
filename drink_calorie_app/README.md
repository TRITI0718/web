# DRINK CALORIE

基于 Streamlit 的饮品营养信息查询网站，支持搜索，以及按品牌、类别、杯型、数据来源、热量区间和营养指标筛选。卡片底部颜色与热量数值线性对应，并配有适合收藏夹和浏览器标签页的网站图标。

## 本地运行

```bash
cd drink_calorie_app
python -m pip install -r requirements.txt
streamlit run app.py
```

默认访问地址为 `http://localhost:8501`。

## 数据更新

网站数据保存在 `data/drinks.db`，并同步导出到 `data/drinks.csv`。当前网页只提供公开查询展示，不显示商品管理入口。

## 微信小程序

原生微信小程序工程位于 `wechat_miniprogram/`，内置当前饮品数据，不依赖外部接口。导入微信开发者工具前，需要将 `wechat_miniprogram/project.config.json` 中的 `touristappid` 替换为你自己的小程序 AppID。

更新网站数据库后，可重新生成小程序数据：

```bash
python wechat_miniprogram/scripts/export_drinks.py
```

更完整的导入、预览和发布说明见 `wechat_miniprogram/README.md`。

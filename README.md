# Fund Valuation Dashboard

基金估值、当日收益测算与持仓分析的可视化 Dashboard（MVP）。

## 功能亮点

- 基金查询：按代码/名称搜索基金，展示单位净值、估值、当日涨跌幅。
- 我的持仓：录入多只基金，自动计算单只与组合收益。
- KPI 看板：总成本、市值、今日预估收益、累计收益率。
- 图表分析：净值/估值趋势、持仓收益分布。
- 自动结论：输出“今日贡献最大/拖累最大/波动等级/风险提示”。
- 中英文切换：主要页面文案支持中文与 English。

## 本地运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

打开本地地址：`http://localhost:8501`

## 目录结构

```text
.
├── app.py                 # Streamlit 主应用
├── data/
│   └── mock_data.py       # 示例/Mock 数据与趋势生成
├── utils/
│   └── analysis.py        # 持仓指标计算与自动结论
└── requirements.txt
```

## 后续接入真实数据源建议

1. 在 `data/mock_data.py` 中新增 `providers/` 层，统一封装第三方基金 API。
2. 用实时接口替换 `get_fund_snapshots()` 与 `get_mock_trend()`。
3. 为接口增加缓存（`st.cache_data`）与失败降级逻辑。
4. 加入历史回测与仓位变化导入（CSV/Excel）。


# Fund Valuation Dashboard

基金估值、当日收益测算与持仓分析的可视化 Dashboard（MVP）。

## 功能亮点

- 基金查询：按代码/名称搜索基金，展示单位净值、估值、当日涨跌幅。
- 我的持仓：录入多只基金，自动计算单只与组合收益。
- KPI 看板：总成本、市值、今日预估收益、累计收益率。
- 图表分析：净值/估值趋势、持仓收益分布。
- 自动结论：输出“今日贡献最大/拖累最大/波动等级/风险提示”。
- 中英文切换：主要页面文案支持中文与 English。

---

## 运行环境（推荐）

- **Python 3.11（推荐并默认）**
- pip 最新版本
- macOS / Linux / WSL 均可

项目根目录提供了 `.python-version`（`3.11`），方便 pyenv / asdf 等工具自动切换版本。

---

## 依赖策略

- `requirements.txt`：日常开发主依赖（保留一定弹性范围）。
- `requirements-lock.txt`：稳定锁定依赖（CI、复现环境、部署建议优先使用）。

如需最高可复现性，请使用 `requirements-lock.txt`。

---

## 一键初始化与启动（推荐）

### 1) 初始化环境

```bash
./scripts/setup.sh
```

该脚本会自动完成：
- 检查 Python 版本（必须 >= 3.11）
- 创建 `.venv`
- 安装依赖
- 执行启动前自检

> 如你的 Python 3.11 命令不是 `python3.11`，可这样执行：
>
> ```bash
> PYTHON_BIN=python3 ./scripts/setup.sh
> ```

### 2) 启动应用

```bash
./scripts/run.sh
```

该脚本会自动：
- 激活虚拟环境
- 运行启动前自检
- 执行 `streamlit run app.py`

启动后访问：`http://localhost:8501`

---

## 手动运行方式（兼容旧习惯）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/preflight.py
streamlit run app.py
```

### 切换数据源 Provider

默认使用本地 mock provider。若要切到 AKShare 真实开放式基金日净值快照：

```bash
export FUND_DATA_PROVIDER=akshare_live
streamlit run app.py
```

说明：
- `akshare_live` 使用 `ak.fund_name_em()` 作为基金主数据；
- 使用 `ak.fund_open_fund_daily_em()` 作为开放式基金日净值快照；
- 趋势图第一阶段仍可回退到 mock trend（用于保持交互和图表稳定性）。

### 首次切换 `akshare_live` 的本地验证步骤

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FUND_DATA_PROVIDER=akshare_live
python scripts/smoke_akshare_provider.py
streamlit run app.py
```

验证要点：
- `smoke_akshare_provider.py` 正常输出 provider 信息且进程退出码为 0；
- 若 AKShare 可用，应看到 `provider=AKShareFundProvider` 与 `snapshots_rows=...`；
- 可通过 `provider_note=...` 查看最近一次 AKShare 快照实际返回列（便于字段兼容调试）；
- 若 AKShare 不可用（网络/字段变更/依赖问题），脚本会打印 `akshare_error=...`，并验证 mock fallback 可用；
- 页面端同样会显示“数据源加载失败，已回退到本地 mock 数据。原因：...”的友好提示。

---

## 启动前自检说明

自检脚本：`scripts/preflight.py`

检查项：
1. Python 版本（>=3.11）
2. 关键依赖是否已安装（streamlit / pandas / numpy / plotly / altair）

若不满足要求，会输出清晰报错并退出，避免“启动后才发现缺包/版本不对”。

---

## CI（基础稳定性保障）

已添加 GitHub Actions：`.github/workflows/ci.yml`

CI 会自动执行：
1. Python 3.11 环境创建
2. 安装 `requirements-lock.txt`
3. 运行 `scripts/preflight.py`
4. 运行 `python -m compileall ...` 语法检查

目标：确保 fresh install 不会因为明显依赖或语法问题立刻失败。

---

## 部署准备（Streamlit Community Cloud）

### 已提供配置

- `.streamlit/config.toml`
  - `headless=true`
  - 默认端口 `8501`
  - 关闭 `gatherUsageStats`

### 部署步骤建议

1. 推送仓库到 GitHub。
2. 在 Streamlit Community Cloud 选择该仓库和分支。
3. Main file path 填写：`app.py`。
4. 依赖文件默认识别 `requirements.txt`（若要完全锁定，可将其替换为 lock 版本内容，或在部署流程使用 lock 文件）。

### Secrets / API Keys 管理建议（为接入真实基金数据源准备）

后续接入真实数据源时，不要把密钥写入代码仓库：

- 本地开发：
  - 使用 `.streamlit/secrets.toml`（加入 `.gitignore`）
- 云端部署：
  - 在 Streamlit Cloud 的 App Settings -> Secrets 中配置

代码中建议这样读取：

```python
api_key = st.secrets["FUND_API_KEY"]
```

---

## 目录结构

```text
.
├── .github/workflows/ci.yml      # 基础 CI
├── .streamlit/config.toml         # Streamlit 运行配置
├── .python-version                # Python 版本约束
├── app.py                         # Streamlit 主应用
├── data/
│   └── mock_data.py               # 示例/Mock 数据与趋势生成
├── scripts/
│   ├── setup.sh                   # 一键初始化
│   ├── run.sh                     # 一键启动
│   └── preflight.py               # 启动前环境自检
├── utils/
│   └── analysis.py                # 持仓指标计算与自动结论
├── requirements.txt               # 主依赖（范围）
└── requirements-lock.txt          # 锁定依赖（稳定复现）
```

---

## 后续接入真实数据源建议

1. 在 `data/mock_data.py` 中新增 `providers/` 层，统一封装第三方基金 API。
2. 用实时接口替换 `get_fund_snapshots()` 与 `get_mock_trend()`。
3. 为接口增加缓存（`st.cache_data`）与失败降级逻辑。
4. 加入历史回测与仓位变化导入（CSV/Excel）。

# 养基智析 · Fund Valuation Dashboard

一个面向真实投资场景的基金分析 Dashboard：支持 **真实历史趋势**、**AKShare Live 估值**、**多账户分析**、**Simple/Pro 双模式持仓**，并对 Streamlit 公网部署做了完整准备。

---

## 功能亮点

- 基金查询：按代码/名称/分类搜索，展示净值、估值、估值语义与快照时间。
- 持仓管理：支持多账户、新增/删除账户、双模式录入（simple / pro）。
- KPI 看板：总成本、当前市值、今日预估收益、累计收益率。
- 图表分析：净值/估值趋势、持仓收益分布、账户收益率对比。
- 自动分析：自动生成收益贡献、风险波动等提示。
- 数据语义清晰：区分 `official_estimate / approx_from_change / nav_snapshot`。

---

## 运行环境

- **Python 3.11**（推荐并默认）
- pip 最新版本
- macOS / Linux / WSL 均可

项目根目录已提供：
- `.python-version`：`3.11`
- `.streamlit/config.toml`：默认 `headless`、端口、基础 theme 配置

---

## 依赖策略

- `requirements.txt`：开发与 Streamlit Cloud 默认安装依赖。
- `requirements-lock.txt`：锁定版本，适合 CI/高可复现环境。

> Streamlit Community Cloud 默认读取 `requirements.txt`。若你希望最强复现性，可将 lock 内容同步到 `requirements.txt` 后再部署。

---

## 本地启动（推荐）

### 1) 一键初始化

```bash
./scripts/setup.sh
```

### 2) 一键启动

```bash
./scripts/run.sh
```

启动后访问：`http://localhost:8501`

---

## 手动启动方式

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/preflight.py
streamlit run app.py
```

---

## 数据源切换（AKShare Live）

默认 provider：本地 mock。
切换到 AKShare Live：

```bash
export FUND_DATA_PROVIDER=akshare_live
streamlit run app.py
```

说明：
- 优先使用官方估值字段。
- 缺失时回退 `nav * (1 + day_change_pct)` 近似估值。
- 再缺失时回退 `nav_snapshot`。
- 页面会展示估值语义，便于用户理解当前值类型。

---

## 上线前可用性检查（建议必跑）

```bash
python scripts/preflight.py
python scripts/smoke_akshare_provider.py
```

检查目标：
- fresh install 下依赖、Python 版本、关键包齐全。
- AKShare 可用时正常返回 live 数据。
- AKShare 不可用时 fallback 仍可运行。

---

## Streamlit Community Cloud 部署指南

### 1) 部署前准备

确保以下文件在仓库根目录：
- `app.py`（入口）
- `requirements.txt`（依赖）
- `.python-version`（Python 版本说明）
- `.streamlit/config.toml`（运行配置）

### 2) Cloud 控制台配置

在 Streamlit Community Cloud 新建应用时填写：
- **Repository**：你的 GitHub 仓库
- **Branch**：建议 `main`
- **Main file path**：`app.py`
- **Python version**：`3.11`（与 `.python-version` 一致）

### 3) 环境变量与 Secrets

#### 可放环境变量（非敏感）
- `FUND_DATA_PROVIDER=akshare_live`

#### 必须放 Secrets（敏感）
- 未来可能接入的 API Key / Token / Secret
- 统一放到 Streamlit Cloud 的 **App Settings → Secrets**，不要写入 Git 仓库

本地调试可使用 `.streamlit/secrets.toml`（并确保加入 `.gitignore`）。

读取方式示例：

```python
api_key = st.secrets["FUND_API_KEY"]
```

### 4) 常见部署注意事项

- 依赖安装失败：优先检查 `requirements.txt` 与 Python 版本是否匹配。
- 启动失败：先本地跑 `python scripts/preflight.py`。
- AKShare 网络波动：页面已有 fallback，不会直接崩溃。

---

## 产品说明与风险提示（公网展示建议）

- 本项目是基金分析 Dashboard，不是交易系统。
- 今日估值属于盘中/快照估算，和最终确认净值可能存在偏差。
- 页面分析结论仅用于研究与展示，不构成投资建议。

---

## 目录结构

```text
.
├── .streamlit/config.toml
├── .python-version
├── app.py
├── data/providers/
├── scripts/
│   ├── setup.sh
│   ├── run.sh
│   ├── preflight.py
│   └── smoke_akshare_provider.py
├── utils/analysis.py
├── requirements.txt
└── requirements-lock.txt
```

# 天眼 SkyEye — 项目完整文档

> 全球财经洞察平台：市场概览 + 深度分析 + 新闻舆情 + AI 预测
> 地址: `http://localhost:8888`
> 启动: `cd ~/workspace/financial-dashboard && .venv/bin/python server.py`

---

## 一、技术架构

```
┌───────────────────────────────────────────────────────────┐
│              Frontend (React 18 + TypeScript + Vite)       │
│  D3.js (K线图) + Canvas (新闻粒子) + CSS Grid (布局)      │
│  build → static/ (346KB JS + 48KB CSS, gzip ~120KB)       │
├───────────────────────────────────────────────────────────┤
│              Backend (FastAPI + Python 3.11)                │
│  uvicorn → port 8888, GZip middleware                      │
│  11个 Router, 44个 API 端点                                 │
├───────────────────────────────────────────────────────────┤
│              Data Layer                                     │
│  SQLite (skyeye.db) + yfinance + Polygon API + RSS Feeds   │
│  Pipeline: Layer 0/1/2 新闻分析 + OHLC 对齐                │
│  AI: mimo2.5pro via OpenAI-compatible API                  │
├───────────────────────────────────────────────────────────┤
│              Cron (Hermes Agent)                            │
│  financial-news-fetch: 每7分钟抓取+对齐                     │
└───────────────────────────────────────────────────────────┘
```

---

## 二、目录结构

```
~/workspace/financial-dashboard/
├── server.py                  # FastAPI 主应用入口
├── database.py                # SQLite schema (13张表) + 连接
├── config.py                  # 环境变量加载 (含 ~/.hermes/.env)
├── polygon_client.py          # Polygon API 客户端 (指数退避重试)
├── ai_analyzer.py             # AI 分析模块 (mimo2.5pro, 可替换)
├── .env                       # API keys
├── requirements.txt           # Python 依赖
├── requirements-ml.txt        # 可选 LSTM/PyTorch 依赖
├── start.sh                   # 启动脚本
├── skyeye.db                  # SQLite 数据库
├── routers/
│   ├── market.py              # 市场概览、板块分析、K线
│   ├── stocks.py              # Ticker CRUD、OHLC
│   ├── news.py                # 新闻查询、粒子、分类
│   ├── analysis.py            # 深度分析、Story、区间分析
│   ├── predict.py             # 预测、forecast、相似日
│   ├── geopolitical.py        # RSS聚合、地缘风险、情绪
│   ├── events.py              # 事件/IPO/私人AI公司
│   ├── opportunity.py         # 风口雷达聚合 API
│   ├── paper.py               # 双币种模拟交易账本
│   └── market_sectors.py      # 多市场板块热力图
├── pipeline/
│   ├── alignment.py           # 新闻-OHLC 日期对齐 + 收益率
│   ├── layer0.py              # 规则过滤 (免费)
│   ├── layer1.py              # SkyEye 批量舆情标注 (mimo/本地兜底)
│   ├── layer2.py              # 按需深度分析
│   └── similarity.py          # 相似文章查找
├── ml/
│   ├── model.py               # ML 预测模型
│   ├── features.py            # 特征工程
│   ├── features_v2.py         # 市场情绪/蜡烛图/文本特征增强
│   ├── backtest.py            # 扩展窗口交叉验证回测
│   ├── train.py               # 训练 CLI: python -m ml.train
│   ├── lstm_model.py          # 可选 LSTM 序列模型
│   ├── similar.py             # 相似日查找
│   ├── catalyst.py            # 近期舆情/事件催化雷达
│   ├── opportunity.py         # 风口评分、主题聚合和 paper action 建议
│   ├── paper_performance.py   # paper allocation 历史表现、基准和贡献
│   └── inference.py           # 推理 + forecast
├── static/                    # 前端 build 输出
└── frontend/
    ├── package.json           # react, d3, axios, vite, typescript
    ├── vite.config.ts         # proxy /api → localhost:8888
    └── src/
        ├── main.tsx
        ├── App.tsx            # 主应用 (路由+状态)
        ├── App.css            # 全局样式 (48KB, 暗黑主题)
        ├── api.ts             # API 封装 (去重+5s缓存)
        ├── types.ts           # TypeScript 类型
        └── components/
            ├── Header.tsx              # 顶栏 (搜索/时钟/GitHub)
            ├── MarketOverview.tsx       # 全球市场卡片
            ├── SectorHeatmap.tsx        # 美股板块热力图+龙头股
            ├── MarketSectorHeatmap.tsx  # 多市场板块热力图
            ├── SectorAnalysisPanel.tsx  # 板块深度分析弹窗
            ├── CandlestickChart.tsx     # D3 K线图+Canvas粒子
            ├── NewsFeed.tsx             # 全球新闻舆情
            ├── NewsPanel.tsx            # K线右侧新闻
            ├── NewsCategoryPanel.tsx    # 新闻分类标签
            ├── PredictionPanel.tsx      # AI预测面板
            ├── SimilarDaysPanel.tsx     # 相似历史日
            ├── RangeAnalysisPanel.tsx   # 区间分析
            ├── RangeNewsPanel.tsx       # 区间新闻
            ├── RangeQueryPopup.tsx      # 区间选择弹窗
            ├── StoryPanel.tsx           # AI Story (PPT风格)
            ├── GeopoliticalGauge.tsx    # 地缘风险仪表盘
            ├── SentimentTrend.tsx       # 舆情趋势图
            ├── TrendingTopics.tsx       # 热门话题
            ├── EventTracker.tsx         # 事件/IPO追踪
            ├── OpportunityRadarPanel.tsx # 风口雷达 + 双币种模拟交易入口
            ├── CatalystRadarPanel.tsx   # 近期舆情/事件催化雷达
            ├── PaperPerformancePanel.tsx# paper 组合历史表现校验
            └── StockSelector.tsx        # 股票选择器
```

---

## 三、数据库 Schema (SQLite: skyeye.db)

```sql
-- 追踪的股票/指数/加密
CREATE TABLE tickers (
    symbol TEXT PRIMARY KEY, name TEXT, sector TEXT,
    last_ohlc_fetch TEXT, last_news_fetch TEXT
);

-- K线数据 (5,010 条)
CREATE TABLE ohlc (
    symbol TEXT NOT NULL, date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume REAL, vwap REAL, transactions INTEGER,
    PRIMARY KEY (symbol, date)
);

-- 原始新闻 (804 条)
CREATE TABLE news_raw (
    id TEXT PRIMARY KEY, title TEXT, description TEXT,
    publisher TEXT, author TEXT, published_utc TEXT,
    article_url TEXT, amp_url TEXT, tickers_json TEXT, insights_json TEXT
);

-- 新闻-股票关联 (3,615 条)
CREATE TABLE news_ticker (
    news_id TEXT NOT NULL, symbol TEXT NOT NULL,
    PRIMARY KEY (news_id, symbol)
);

-- 新闻-OHLC 对齐 (1,533 条)
CREATE TABLE news_aligned (
    news_id TEXT NOT NULL, symbol TEXT NOT NULL, trade_date TEXT NOT NULL,
    published_utc TEXT, ret_t0 REAL, ret_t1 REAL, ret_t3 REAL, ret_t5 REAL, ret_t10 REAL,
    PRIMARY KEY (news_id, symbol)
);
CREATE INDEX idx_news_aligned_symbol_date ON news_aligned(symbol, trade_date);

-- Layer 0 规则过滤
CREATE TABLE layer0_results (
    news_id TEXT NOT NULL, symbol TEXT NOT NULL, passed INTEGER NOT NULL, reason TEXT,
    PRIMARY KEY (news_id, symbol)
);

-- Layer 1 AI 分析
CREATE TABLE layer1_results (
    news_id TEXT NOT NULL, symbol TEXT NOT NULL,
    relevance TEXT, key_discussion TEXT, chinese_summary TEXT,
    sentiment TEXT, discussion TEXT, reason_growth TEXT, reason_decrease TEXT,
    PRIMARY KEY (news_id, symbol)
);

-- Layer 2 深度分析
CREATE TABLE layer2_results (
    news_id TEXT NOT NULL, symbol TEXT NOT NULL,
    discussion TEXT, growth_reasons TEXT, decrease_reasons TEXT, created_at TEXT,
    PRIMARY KEY (news_id, symbol)
);

-- Batch API jobs
CREATE TABLE batch_jobs (
    batch_id TEXT PRIMARY KEY, symbol TEXT, status TEXT,
    total INTEGER, completed INTEGER DEFAULT 0, created_at TEXT, finished_at TEXT
);

CREATE TABLE batch_request_map (
    batch_id TEXT NOT NULL, custom_id TEXT NOT NULL,
    symbol TEXT NOT NULL, article_ids TEXT NOT NULL,
    PRIMARY KEY (batch_id, custom_id)
);

-- 双币种模拟交易账本
CREATE TABLE paper_books (
    id TEXT PRIMARY KEY, label TEXT NOT NULL, currency TEXT NOT NULL,
    initial_cash REAL NOT NULL, created_at TEXT, updated_at TEXT
);

CREATE TABLE paper_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL,
    quantity REAL NOT NULL, price REAL NOT NULL, notional REAL NOT NULL,
    reason TEXT, radar_alert_id TEXT, trade_date TEXT, created_at TEXT,
    FOREIGN KEY(book_id) REFERENCES paper_books(id)
);
CREATE INDEX idx_paper_orders_book_symbol ON paper_orders(book_id, symbol);

CREATE TABLE paper_positions (
    book_id TEXT NOT NULL, symbol TEXT NOT NULL, shares REAL NOT NULL,
    avg_cost REAL, realized_pnl REAL DEFAULT 0, updated_at TEXT,
    PRIMARY KEY (book_id, symbol),
    FOREIGN KEY(book_id) REFERENCES paper_books(id)
);
```

**数据统计**:
- 24 个追踪 ticker (NVDA/AAPL/MSFT/TSLA/META/AMZN/GOOGL/AMD/AVGO/PLTR + 港股 + 加密 + 大宗)
- NVDA: 355 条对齐新闻, MSFT: 171, AMZN: 147, GOOGL: 145, AAPL: 143

---

## 四、API 端点 (44个)

### 市场数据
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/market-overview` | 全球市场概览 (所有指数+加密+大宗) |
| GET | `/api/market/{key}` | 单市场详情 (us/hk/cn/jp/eu) |
| GET | `/api/market-status` | 市场开盘/收盘状态 |
| GET | `/api/kline/{symbol}?period=` | K线 (yfinance: 1d/5d/1mo/3mo/1y/5y) |
| GET | `/api/sectors` | 美股板块列表 (含龙头股实时价格) |
| GET | `/api/sector/{key}` | 板块深度分析 (outlook/驱动/风险/股票) |
| GET | `/api/market-sectors/{market}` | 多市场板块 (hk/cn/jp/eu) |

### 股票
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stocks` | 追踪列表 |
| POST | `/api/stocks` | 添加 ticker + 后台拉取数据 |
| GET | `/api/stocks/{symbol}/ohlc` | OHLC 数据 (数据库) |
| GET | `/api/stocks/search?q=` | 搜索 |
| GET | `/api/search/{query}` | 搜索 (本地+Polygon+yfinance) |
| GET | `/api/company/{symbol}` | 公司详情 |

### 新闻
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/news?sentiment=&category=&limit=` | 全球 RSS 新闻 |
| GET | `/api/news/{symbol}` | 股票新闻 (数据库) |
| GET | `/api/news/{symbol}?date=` | 指定日期新闻 |
| GET | `/api/news/{symbol}/particles` | K线图新闻粒子 |
| GET | `/api/news/{symbol}/categories` | 新闻分类统计 |
| GET | `/api/news/{symbol}/range?start=&end=` | 区间新闻 |
| GET | `/api/news/{symbol}/timeline` | 新闻时间线 |
| GET | `/api/news/symbol/{symbol}` | 任意 symbol 新闻 (Google News RSS) |

### 分析
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/analysis/deep` | AI 深度分析单篇新闻 |
| POST | `/api/analysis/story` | AI Story 生成 |
| POST | `/api/analysis/range-local` | 区间分析 (本地数据) |
| POST | `/api/analysis/similar` | 相似文章查找 |

### 预测
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/predict/{symbol}` | 方向预测 (ML → mimo2.5pro fallback) |
| GET | `/api/predict/{symbol}/forecast?window=` | 7天/30天 forecast |
| GET | `/api/predict/{symbol}/similar-days?date=` | 相似历史日 |
| GET | `/api/predict/{symbol}/backtest` | 回测结果 |
| GET | `/api/predict/{symbol}/quant` | 量化模型/回测/依赖/质量状态 |
| GET | `/api/predict/{symbol}/risk-brief` | 单票风险简报、波动、回撤、ATR 与信号闸门 |
| GET | `/api/predict/decision-board` | 核心股票池研究排序、舆情、风险和闸门汇总 |
| GET | `/api/predict/strategy-monitor` | 量化模型/回测 readiness 总览、UNIFIED fallback 与策略护栏 |
| GET | `/api/predict/catalyst-radar?lookback_days=` | 近期舆情/事件催化雷达：新闻量、舆情偏向、即时价格反应和待标注缺口 |
| GET | `/api/predict/portfolio-plan?capital=` | 组合研究计划、live/paper 权重、仓位风险上限 |
| POST | `/api/predict/{symbol}/train?horizon=t1&backtest=true` | 后台训练可用树模型并可生成回测 |
| POST | `/api/predict/{symbol}/analyze-news?limit=100&engine=auto` | 后台运行 Layer 1 舆情标注 |

### 组合
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/portfolio` | 实际持仓监控、浮盈亏、权重、ATR 风险和信号闸门 |
| GET | `/api/portfolio/action-center` | 行动中心，汇总持仓、数据、风险、信号闸门和研究事项 |
| GET | `/api/portfolio/investment-brief?capital=` | 投资晨报式总览，聚合策略、组合、行动、复盘和研究队列 |
| GET | `/api/portfolio/paper-performance?capital=&window_days=` | 当前 paper allocation 的 5/20/60 日表现、等权基准、主动收益、回撤和贡献 |
| GET | `/api/portfolio/rebalance?capital=` | 实际持仓与 live/paper 组合计划的再平衡差异表 |
| GET | `/api/portfolio/trades` | 交易日志、复盘状态、标记盈亏和信号闸门上下文 |
| GET | `/api/portfolio/trade-review` | 交易复盘聚合、setup playbook、优先复盘清单 |
| POST | `/api/portfolio/trades` | 新增交易日志 |
| PUT | `/api/portfolio/trades/{id}` | 更新交易日志与复盘 |
| DELETE | `/api/portfolio/trades/{id}` | 删除交易日志 |
| PUT | `/api/portfolio/positions/{symbol}` | 新增/更新持仓数量、成本和投资备注 |
| DELETE | `/api/portfolio/positions/{symbol}` | 删除持仓 |

### 风口与模拟交易
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/opportunity-radar?market=&lookback_days=&mode=` | 风口雷达，聚合新闻、事件、产业链、催化和 trade setup，输出 strong/watch alerts |
| GET | `/api/paper/books` | 双币种模拟账本：HKD 1,000,000 与 USD 40,000，账本不互相折算 |
| POST | `/api/paper/orders` | 从风口提醒写入模拟成交，按最新可用 close price 成交 |
| GET | `/api/paper/performance?book=&window_days=` | 单一 paper book 的持仓、权益曲线、波动与回撤 |

### 其他
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/geopolitical` | 地缘政治风险 (8维度评分) |
| GET | `/api/sentiment-trend` | 7天情绪趋势 |
| GET | `/api/trending` | 热门话题 |
| GET | `/api/events` | 事件/IPO + 私人AI公司 |
| GET | `/api/events/private-ai-news` | 私人AI公司实时新闻 |
| GET | `/api/health` | 健康检查 |

---

## 五、数据源

| 来源 | 用途 | 限制 |
|------|------|------|
| **yfinance** | 实时行情、K线、搜索 | 免费, 首次调用慢 (~15s), NaN需处理 |
| **Polygon API** | 公司新闻、OHLC、搜索 | 免费 5 req/min, 港股不支持 |
| **Google News RSS** | 任意 symbol 新闻 | 免费, 无限制 |
| **10个 RSS 源** | BBC/CNBC/NYT/Yahoo/36氪/InfoQ/CoinTelegraph/SeekingAlpha | 免费 |
| **mimo2.5pro** | AI 分析/预测/Story | 通过 Hermes API (OPENAI_API_KEY) |

---

## 六、关键设计决策

### 前端
- **双视图模式**: Overview (市场概览) ↔ Deep Analysis (K线深度分析)
- **风口雷达入口**: Overview 顶部聚合主题机会、证据抽屉、相关产业链公司和模拟交易按钮，不另起独立首页。
- **港股搜索别名**: `00100.HK / 0100.HK / MiniMax / 稀宇科技` 会映射到同一 tracking 标的；港交所五位代码对接免费行情源四位代码。
- **K线图**: D3.js SVG 蜡烛图 + Canvas 新闻粒子叠加
- **时间周期**: 1分/15分/日/周/月/5年, 每个周期用不同的 yfinance interval
- **新闻粒子**: 每个对齐的新闻渲染为彩色圆点 (绿=利好, 红=利空, 青=中性)
- **请求去重**: api.ts 中 5s TTL 缓存 + inflight 去重
- **ErrorBoundary**: 防止 React 崩溃白屏
- **性能**: React.memo, requestAnimationFrame, GZip

### 后端
- **并发获取**: ThreadPoolExecutor 8线程并行调 yfinance
- **缓存**: 市场数据 120s TTL, 新闻 300s TTL
- **新闻对齐**: RSS 新闻通过关键词匹配关联到股票, 再对齐到 OHLC 日期
- **AI fallback**: ML模型 → mimo2.5pro → 趋势启发式
- **Layer 1 舆情标注**: `python -m pipeline.layer1 NVDA --limit 100 --engine auto` 批量写入 `layer1_results`; 优先 mimo/OpenAI-compatible, 无 key 或失败时用 Polygon insights + 本地文本规则兜底
- **统一量化模型**: `POST /api/predict/UNIFIED/train?horizon=t1&backtest=true` 训练跨股票模型；单票模型缺失时 `ml.model.predict()` 会 fallback 到 `UNIFIED_{horizon}`。
- **量化训练**: `python -m ml.train --symbol NVDA --backtest` 训练树模型并生成回测；优先 XGBoost, 缺失时自动使用 scikit-learn RandomForest；LSTM 需先安装 `requirements-ml.txt`
- **市场状态特征**: `ml/features.py` 现在加入核心股票池等权市场收益、波动、宽度、相对强弱、beta proxy 和全市场舆情动量，避免模型只看单票局部信息
- **模型质量护栏**: `/api/predict/{symbol}/quant` 和方向预测会返回 `quality/model_quality`, 对 holdout lift 与 CV lift 做分级；CV 未跑赢基准时标记 `Overfit Risk` 或 `Below Baseline`, `trade_ready=false`
- **策略回测护栏**: 扩展窗口回测会输出 long/cash 与 long/short 的策略收益、基准收益、超额收益、Sharpe、最大回撤和交易次数；质量状态会同时检查分类 edge 与策略 edge
- **决策工作台**: `/api/predict/decision-board` 汇总核心股票池的近 30 天舆情、趋势、波动、回撤、数据健康和 T1/T5 信号闸门，只把未通过风控的标为研究或观察状态。
- **策略监控**: `/api/predict/strategy-monitor` 读取已有模型和回测产物，汇总模型质量、严格策略超额收益、driver group 边际、UNIFIED fallback 和数据健康，明确哪些 horizon 仍不能进入 live sizing。
- **Catalyst Radar**: `/api/predict/catalyst-radar` 聚合近期新闻量、Layer 1 舆情、当日价格反应、短期趋势和标注缺口，给出最需要阅读的事件驱动股票与下一步动作。
- **组合计划护栏**: `/api/predict/portfolio-plan` 在决策工作台之上生成 live/paper 两套权重；未通过信号闸门时 live allocation 保持 0，只输出研究观察权重。
- **实际持仓监控**: `/api/portfolio` 持久化实际持仓，按最新价格计算市值、浮盈亏、权重、估算止损风险，并和单票信号闸门联动。
- **行动中心**: `/api/portfolio/action-center` 把持仓、研究排序、数据质量、波动、信号闸门和组合计划合成为优先级事项，减少人工巡检成本。
- **投资晨报**: `/api/portfolio/investment-brief` 聚合 Action Center、Strategy Monitor、Decision Board、Portfolio Plan 和 Trade Review，输出当前操作模式、优先事项、研究队列、paper allocation 与风险提示。
- **Paper Performance**: `/api/portfolio/paper-performance` 用当前 paper allocation 对最近 OHLC 历史做静态组合表现校验，对比等权研究基准，输出主动收益、波动、最大回撤和单票贡献。
- **再平衡监控**: `/api/portfolio/rebalance` 对比实际持仓与 live/paper 组合计划，标记 off-gate、research-watch、add/trim candidate 等状态。
- **交易日志复盘**: `/api/portfolio/trades` 持久化买卖记录、交易逻辑和复盘结论，并自动补上标记盈亏、当前价格和信号闸门上下文。
- **交易复盘聚合**: `/api/portfolio/trade-review` 将日志聚合为复盘率、标记盈亏、闸门违规、setup playbook 和优先复盘任务，帮助把交易结果反馈到研究流程。
- **Opportunity Radar**: `/api/opportunity-radar` 复用新闻、事件/IPO、产业链、Catalyst Radar 和 Trade Setup，按来源质量、事件新鲜度、舆情强度、价格反应、产业链相关性加权，并扣除拥挤度和风险项。
- **双币种模拟账本**: `/api/paper/*` 持久化 HKD/USD 两个 paper book；港股只能进入 HKD 账本，美股只能进入 USD 账本，指数、加密和大宗只允许观察；数据库 OHLC 缺失时用 yfinance 最新日线兜底 paper fill。
- **新闻影响解释**: 个股新闻 API 返回中文分类、可能影响、T+反应和“下一步看什么”；产品发布/新模型发布被单独归类，避免只看泛泛舆情。
- **量化工具折叠**: Overview 默认只露出局势雷达、行动和催化；Decision Board、Trade Setup、Strategy Monitor、Portfolio/Performance/Review 收进 Quant Tools。
- **舆情特征兜底**: Layer 1 AI 标签缺失时, 特征工程会解析 Polygon insights；再缺失时用基础关键词推断正/负/中性, 避免量化模型退化成纯技术指标
- **yfinance NaN**: 所有 OHLC 字段检查 NaN, volume 默认 0

### 数据库
- **新闻-OHLC 对齐**: 每条新闻映射到最近的交易日, 计算 T+0/1/3/5/10 收益率
- **Layer 0/1/2 Pipeline**: Layer 0 规则过滤 → Layer 1 批量AI分类 → Layer 2 按需深度分析
- **关键词匹配**: RSS 新闻通过公司名/ticker 关键词关联到股票
- **模拟交易隔离**: paper books/orders/positions 独立于真实 portfolio/trade journal，避免研究单和真实持仓混在一起。

---

## 七、已知问题与 TODO

### 高优先级
1. **新闻粒子不显示** — 数据库有 355 个粒子 (NVDA), API 返回正确, 但 Canvas 渲染坐标可能偏移。需调试 D3 x/y scale 与 Canvas px/py 坐标的对齐。
2. **Generate Story 质量** — AI 输出可能不够结构化, 需优化 prompt。
3. **Layer 2 输出质量** — 已统一到 SkyEye/mimo 配置, 后续需要继续优化结构化 prompt 和缓存评估。

### 中优先级
4. **港股/A股搜索** — Polygon 免费版不支持, yfinance fallback 有限。
5. **Hang Seng Tech 显示 0.00** — yfinance 对 ^HSTECH 返回异常。
6. **区间选择分析 (Range Analysis)** — D3 brush 交互 + 后端分析需联调。

### 低优先级
7. **图表水平滚动/缩放** — 已有 +/- 按钮, 但拖拽平移未实现。
8. **多市场板块热力图** — 后端 API 已创建, 但 yfinance 获取港股/A股数据较慢。
9. **实时新闻粒子联动** — 需要新闻粒子在 K 线图上实时显示。

---

## 八、环境配置

```bash
# .env
POLYGON_API_KEY=<your_polygon_key>
ANTHROPIC_API_KEY=<optional>

# ~/.hermes/.env (自动加载)
OPENAI_API_KEY=<hermes_api_key>  # 用于 ai_analyzer.py

# Python 依赖
pip install fastapi uvicorn yfinance feedparser requests pydantic numpy pandas scikit-learn

# 启动
cd ~/workspace/financial-dashboard
.venv/bin/python server.py
# 或
./start.sh

# 前端开发
cd frontend
npm install
npm run dev          # 开发服务器 (port 3000, proxy → 8888)
npm run build        # 生产构建 → dist/
```

---

## 九、Cron 任务

| 任务 | 频率 | 功能 |
|------|------|------|
| `financial-news-fetch` | 每 7 分钟 | RSS + Polygon 新闻抓取 + 对齐 |
| `morning-news` | 每天 8:00 | 港股早间新闻 |
| `ipo-scoring-v2` | 工作日 9:00 | IPO 评分 |
| `market-monitor` | 工作日 9:30/13:30/15:30 | 市场波动监控 |

---

## 十、前端组件清单 (34个)

| 组件 | 功能 | 数据源 |
|------|------|--------|
| Header | 搜索/时钟/GitHub/返回 | - |
| MarketOverview | 全球市场卡片网格 | /api/market-overview |
| SectorHeatmap | 美股板块+龙头股 | /api/sectors |
| MarketSectorHeatmap | 多市场板块 | /api/market-sectors/{m} |
| SectorAnalysisPanel | 板块深度分析弹窗 | /api/sector/{key} |
| CandlestickChart | D3 K线+Canvas粒子+缩放 | /api/stocks/{s}/ohlc + /api/kline/{s} + /api/news/{s}/particles |
| NewsFeed | 全球新闻+情绪+地缘筛选 | /api/news + /api/geopolitical |
| NewsPanel | K线右侧新闻 | /api/news/{s}?date= |
| NewsCategoryPanel | 新闻分类标签 | /api/news/{s}/categories |
| OpportunityRadarPanel | 风口雷达、证据抽屉、相关产业链和双币种模拟下单入口 | /api/opportunity-radar + /api/paper/* |
| InvestmentBriefPanel | 投资晨报式总览、操作模式和优先事项 | /api/portfolio/investment-brief |
| ActionCenterPanel | 投资行动中心与优先级事项 | /api/portfolio/action-center |
| DecisionBoardPanel | 核心股票池研究排序工作台 | /api/predict/decision-board |
| CatalystRadarPanel | 近期舆情/事件催化雷达、价格反应和下一步动作 | /api/predict/catalyst-radar |
| StrategyMonitorPanel | 量化策略 readiness 与模型护栏总览 | /api/predict/strategy-monitor |
| PortfolioPlanPanel | 组合研究计划与仓位护栏 | /api/predict/portfolio-plan |
| PaperPerformancePanel | paper allocation 历史表现、等权基准和贡献拆分 | /api/portfolio/paper-performance |
| HoldingsMonitorPanel | 实际持仓监控、浮盈亏和风险闸门 | /api/portfolio |
| RebalanceMonitorPanel | 实际持仓 vs live/paper 计划差异 | /api/portfolio/rebalance |
| TradeJournalPanel | 交易日志、复盘和标记盈亏 | /api/portfolio/trades |
| TradeReviewPanel | 交易复盘聚合与 setup playbook | /api/portfolio/trade-review |
| PredictionPanel | AI预测 7天/30天 | /api/predict/{s}/forecast |
| RiskBriefPanel | 单票风险简报与信号闸门 | /api/predict/{s}/risk-brief |
| QuantLabPanel | 舆情标注、量化训练、依赖、回测质量 | /api/predict/{s}/quant |
| SimilarDaysPanel | 相似历史日 | /api/predict/{s}/similar-days |
| RangeAnalysisPanel | 区间分析 | /api/analysis/range-local |
| RangeNewsPanel | 区间新闻 | /api/news/{s}/range |
| RangeQueryPopup | 区间选择弹窗 | - |
| StoryPanel | AI Story (PPT风格) | /api/analysis/story |
| GeopoliticalGauge | 地缘风险仪表盘 | /api/geopolitical |
| SentimentTrend | 舆情趋势图 | /api/sentiment-trend |
| TrendingTopics | 热门话题 | /api/trending |
| EventTracker | 事件/IPO/私人AI公司/产业链主题 | /api/events |
| StockSelector | 股票选择器+搜索 | /api/stocks + /api/search |

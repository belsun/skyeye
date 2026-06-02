# SkyEye

SkyEye is a personal market-intelligence dashboard for learning-driven investing. It combines news, event monitoring, IPO watchlists, supply-chain mapping, technical signals, and paper trading into one research workflow.

The project is designed for a beginner investor who wants to understand market narratives before placing real trades. SkyEye does not place live orders and does not provide financial advice.

## Highlights

- Opportunity Radar: turns news, events, IPOs, catalyst data, and trade setups into research alerts.
- Dual-currency paper books: HKD paper book for Hong Kong equities and USD paper book for US equities.
- News-to-price workflow: aligns news dates with OHLC data, K-line views, sentiment, and follow-up watch points.
- Beginner-friendly research panels: risk brief, support/stop/target references, portfolio planning, and quant-learning modules.
- Hong Kong and US focus: HK IPO/new economy watch, AI applications, AI compute/HBM, robotics, crypto infrastructure, and macro liquidity.

## Tech Stack

- Backend: FastAPI, SQLite, yfinance, Polygon-compatible news ingestion.
- Frontend: React, TypeScript, Vite, D3.
- ML/research layer: scikit-learn-style feature engineering, catalyst scoring, trade setup analysis, and paper-performance tracking.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-ml.txt

cd frontend
npm install
npm run build
cd ..

cp .env.example .env
python server.py
```

Open `http://localhost:8888`.

## Environment

Create `.env` from `.env.example`.

```bash
POLYGON_API_KEY=
OPENAI_API_KEY=
AI_API_KEY=
AI_API_BASE=https://api.openai.com/v1
DATABASE_PATH=skyeye.db
```

API keys are optional for basic local UI exploration. Some news and AI-analysis features require external providers.

## Core APIs

- `GET /api/opportunity-radar?market=all|hk|us&lookback_days=10&mode=balanced`
- `GET /api/paper/books`
- `POST /api/paper/orders`
- `GET /api/paper/performance?book=hkd|usd&window_days=20`
- `GET /api/events`
- `GET /api/news/{symbol}`
- `GET /api/kline/{symbol}`

## Safety Notes

- This repository excludes local `.env`, SQLite databases, model artifacts, caches, and generated build assets.
- Paper trading is simulation only.
- Support, stop, and target values are research references, not live trading instructions.
- HKD and USD paper books are intentionally not FX-converted.

## Why This Project

SkyEye explores how Codex can help a solo builder turn scattered market ideas into a working product loop:

1. Detect a market narrative or event.
2. Connect it to affected symbols and upstream/downstream industries.
3. Show evidence and risks.
4. Place a simulated trade in the correct currency book.
5. Review performance and improve the thesis.

## License

MIT


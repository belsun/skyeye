# SkyEye

**A news-to-price market intelligence tracker for learning-driven investors.**

SkyEye turns scattered market information into one research loop: spot a theme,
open the symbol, read the evidence, inspect the K-line reaction, simulate a
trade, and review what happened afterward.

It is designed for Hong Kong and U.S. market learning, especially where company
news, macro shocks, policy signals, IPOs, supply-chain narratives, crypto flows,
and commodities all collide with price.

> Research and paper trading only. SkyEye does not place live orders and does
> not provide financial advice.

## Product Preview

![News explains the K-line](docs/media/real-showcase-01-news-kline.png)

![Opportunity radar and market intelligence](docs/media/real-showcase-02-radar-dashboard.png)

![Company context before price action](docs/media/real-showcase-03-company-to-macro.png)

## What Makes SkyEye Different

- **News-to-K-line context**: company news, sentiment, event categories, price
  reaction, support/resistance notes, and AI analysis live next to the chart.
- **Opportunity Radar**: filters news, events, IPOs, catalysts, market themes,
  and trade setups into strong signals and watch signals.
- **Company and instrument profiles**: equities get company background,
  official links, filings, financials, and recent news; indices, crypto, and
  commodities get tracker-style quote context instead of fake company profiles.
- **Dual-currency paper trading**: HK equities route to an HKD paper book and
  U.S. equities route to a USD paper book, with no forced FX conversion.
- **Macro-from-micro workflow**: individual company decisions, supply chains,
  policy shifts, and sentiment clusters roll up into broader market themes.
- **Built for learning**: bilingual UI modes, learning/pro modes, and a quant
  lab are included so the product can grow with the investor.

## Core Workflows

1. **Scan the market**
   Open the overview dashboard to see market status, global news, risk themes,
   hot topics, IPOs, and Opportunity Radar alerts.

2. **Open a symbol**
   Search for a company, index, crypto pair, or commodity future. SkyEye shows
   the right kind of profile for that instrument before the chart.

3. **Connect news to price**
   Inspect candlesticks, news particles, category filters, event timelines, and
   external impact panels to understand why a move may have happened.

4. **Simulate before acting**
   Convert a research alert into a paper order, then review position exposure
   and book performance separately for HKD and USD.

## Bilingual And Future Multilingual Support

SkyEye currently supports Chinese and English UI modes, including a bilingual
mode for investors who are still learning market terminology. Source names,
tickers, official filings, and original article titles remain in their native
form when that is the clearest representation.

Future versions are planned to add more language packs so the same market
tracker can serve international users without losing local-market nuance.

## Release Media

### 15-Second Launch Videos

- [Opportunity Radar](docs/media/01-opportunity-radar.mp4)
- [Company Profile](docs/media/02-company-profile.mp4)
- [Paper Trading](docs/media/03-paper-trading.mp4)

### Product Images

All showcase images are generated from real SkyEye UI screenshots and then
composed into product-introduction graphics for GitHub, demos, and application
materials.

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

## Safety And Privacy

- Local `.env`, SQLite databases, model artifacts, caches, and generated build
  assets are excluded from the public repository.
- Paper trading is simulation only.
- HKD and USD books are intentionally not FX-converted.
- News storage is designed around metadata, summaries, links, timestamps, and
  analysis indexes, not full article archives.

## Iteration Log

SkyEye keeps a human-readable [CHANGELOG](CHANGELOG.md). Bug fixes, UI polish,
and product capability upgrades should be logged there before publishing.

"""
AI Analysis module - uses mimo2.5pro via OpenAI-compatible API.
Replace the model/provider below to use a different LLM.
"""

import os, json, time
import requests

# Load config first to populate env vars from .env files
try:
    import config  # noqa: F401 - triggers _load_env()
except ImportError:
    pass

# ============================================================
# CONFIGURATION - Change these to switch models/providers
# ============================================================
# Priority: AI_API_BASE > AUXILIARY_VISION_BASE_URL > OPENAI_API_BASE > fallback
API_BASE = os.environ.get("AI_API_BASE",
    os.environ.get("AUXILIARY_VISION_BASE_URL",
    os.environ.get("OPENAI_API_BASE", "https://api.nousresearch.com/v1")))
API_KEY = os.environ.get("AI_API_KEY", os.environ.get("CUSTOM_API_KEY",
    os.environ.get("OPENAI_API_KEY", "")))
MODEL = os.environ.get("AI_MODEL", "mimo-v2.5-pro")
# ============================================================


def _chat(system: str, user: str, max_tokens: int = 2048) -> str:
    """Generic chat completion call. Returns text response."""
    if not API_KEY:
        return ""
    try:
        resp = requests.post(
            f"{API_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=60,
        )
        if resp.status_code == 200:
            return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            return f"API error {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return f"Error: {e}"


def analyze_article_impact(title: str, description: str, symbol: str) -> dict:
    """Deep analysis of a single news article's impact on a stock."""
    system = "You are a senior financial analyst. Provide deep analysis. Return JSON only."
    user = f"""Analyze this news article's impact on {symbol} stock:

TITLE: {title}
DESCRIPTION: {description or 'N/A'}

Return JSON:
{{"discussion": "200-300 word analysis of impact on {symbol}",
  "growth_reasons": "Bullish factors (bullet points)",
  "decrease_reasons": "Bearish risk factors (bullet points)"}}"""

    text = _chat(system, user, max_tokens=1024)
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except json.JSONDecodeError:
        pass
    return {"discussion": text[:500], "growth_reasons": "", "decrease_reasons": ""}


def generate_trend_story(symbol: str, csv_content: str) -> str:
    """Generate an AI narrative about a stock's price journey."""
    system = "You are a financial storyteller. Write vivid investment narratives in HTML format."
    user = f"""Below is {symbol}'s OHLC data and related news. Generate a compelling investment story.

Data (last 50000 chars):
```
{csv_content[-50000:]}
```

Requirements:
1. Tell the complete journey from start to end, highlighting key turning points
2. Analyze underlying business and economic factors with news events
3. Start with a brief 1-2 sentence summary
4. Output in HTML: <h3>, <p>, <strong> tags
5. ~500-1000 words, vivid narrative language"""

    return _chat(system, user, max_tokens=4096)


def analyze_price_range(symbol: str, start_date: str, end_date: str, 
                        price_summary: str, news_context: str, question: str = "") -> dict:
    """Analyze what drove price movement in a date range."""
    system = "You are a senior financial analyst. Return JSON only."
    q_part = f"User's specific question: {question}\n\n" if question else ""
    user = f"""Analyze {symbol}'s price movement from {start_date} to {end_date}.

Price data: {price_summary}

Related news:
{news_context or 'No related news'}

{q_part}Return JSON:
{{"summary": "Brief 1-2 sentence overview",
  "key_events": ["Event 1", "Event 2"],
  "bullish_factors": ["Factor 1"],
  "bearish_factors": ["Factor 1"],
  "trend_analysis": "100-150 word trend analysis"}}"""

    text = _chat(system, user, max_tokens=2048)
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except json.JSONDecodeError:
        pass
    return {
        "summary": text[:200],
        "key_events": [],
        "bullish_factors": [],
        "bearish_factors": [],
        "trend_analysis": text,
    }


def predict_direction(symbol: str, context: str) -> dict:
    """Predict stock direction based on recent data."""
    system = "You are a quantitative analyst. Return JSON only."
    user = f"""Predict {symbol}'s short-term direction based on:

{context}

Return JSON:
{{"direction": "up" or "down",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation",
  "top_drivers": [{{"name": "factor", "impact": "positive/negative"}}]}}"""

    text = _chat(system, user, max_tokens=512)
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except json.JSONDecodeError:
        pass
    return {"direction": "up", "confidence": 0.5, "reasoning": text[:200], "top_drivers": []}

#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate 2>/dev/null || true
pip install -q -r requirements.txt 2>/dev/null
echo "🚀 天眼 SkyEye v5 starting on http://localhost:8888"
python server.py

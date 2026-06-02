import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

def _load_env():
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    # Also try Hermes global .env for API keys (AI_API_KEY, OPENAI_API_KEY, etc.)
    hermes_env = Path.home() / ".hermes" / ".env"
    if hermes_env.exists():
        for line in hermes_env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                # Only load API-related keys from Hermes config
                if any(tag in k.upper() for tag in ("API_KEY", "API_BASE")):
                    os.environ.setdefault(k, v.strip())

_load_env()

POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DATABASE_PATH = os.environ.get("DATABASE_PATH", str(PROJECT_ROOT / "skyeye.db"))

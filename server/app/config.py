"""All tunables come from environment variables so the same image runs locally and on AMD cloud."""
import os
from pathlib import Path


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _b(name: str, default: bool) -> bool:
    return os.getenv(name, "1" if default else "0").lower() in ("1", "true", "yes", "on")


ROOT = Path(__file__).resolve().parents[2]

DB_PATH = os.getenv("FIRELINE_DB", str(ROOT / "server" / "fireline.db"))
WEB_DIST = Path(os.getenv("FIRELINE_WEB_DIST", str(ROOT / "web" / "dist")))

# Simulated satellite link (Iridium short burst data sized).
SAT_MAX_BYTES = int(_f("SAT_MAX_BYTES", 340))
SAT_DELAY_MIN = _f("SAT_DELAY_MIN", 5)
SAT_DELAY_MAX = _f("SAT_DELAY_MAX", 20)
SAT_DROP_RATE = _f("SAT_DROP_RATE", 0.0)

# Ground logic.
OFFLINE_AFTER_S = _f("OFFLINE_AFTER_S", 120)
INCIDENT_THRESHOLD = _f("INCIDENT_THRESHOLD", 0.5)
INCIDENT_WINDOW_S = _f("INCIDENT_WINDOW_S", 600)
SNAPSHOT_MAX_AGE_S = _f("SNAPSHOT_MAX_AGE_S", 120)
DEMO_MODE = _b("DEMO_MODE", False)

# Gemma, served by vLLM (or anything OpenAI-compatible) on the AMD GPU droplet.
GEMMA_BASE_URL = os.getenv("GEMMA_BASE_URL", "").rstrip("/")  # e.g. http://localhost:8001/v1
GEMMA_MODEL = os.getenv("GEMMA_MODEL", "google/gemma-3-27b-it")
GEMMA_API_KEY = os.getenv("GEMMA_API_KEY", "EMPTY")
GEMMA_VISION = _b("GEMMA_VISION", True)
GEMMA_TIMEOUT_S = _f("GEMMA_TIMEOUT_S", 30)

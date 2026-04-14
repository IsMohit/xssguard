"""
backend/utils/logger.py
Logs malicious XSS attempts to a JSONL file.
"""
import json
import logging
import os
from datetime import datetime, timezone
from config.settings import Config

logger = logging.getLogger(__name__)

def log_malicious_attempt(ip: str, input_text: str, result: dict, project_id: str = None):
    """Append a malicious detection event to the JSONL log file."""
    os.makedirs(Config.LOG_DIR, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip_address": ip,
        "project_id": project_id,
        "input_preview": input_text[:200],
        "confidence": result.get("confidence"),
        "risk_level": result.get("risk_level"),
        "model_used": result.get("model_used"),
    }
    try:
        with open(Config.MALICIOUS_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.error("Failed to write malicious log: %s", e)


def get_recent_logs(limit: int = 50) -> list:
    """Read the most recent N entries from the JSONL log."""
    path = Config.MALICIOUS_LOG_FILE
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        entries = [json.loads(l) for l in lines if l.strip()]
        return list(reversed(entries))[:limit]
    except Exception as e:
        logger.error("Failed to read logs: %s", e)
        return []

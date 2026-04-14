"""
config/settings.py
Central config. Reads from .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-in-production")
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    ENV = os.getenv("FLASK_ENV", "development")

    FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_PATH", "config/firebase_service_account.json"
    )
    FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")

    FIREBASE_CLIENT_CONFIG = {
        "apiKey": os.getenv("FIREBASE_API_KEY", ""),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", ""),
        "projectId": os.getenv("FIREBASE_PROJECT_ID", ""),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET", ""),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID", ""),
        "appId": os.getenv("FIREBASE_APP_ID", ""),
    }

    MODEL_PATH = os.getenv("MODEL_PATH", "ml_model/xss_cnn_lstm_model.h5")
    TOKENIZER_PATH = os.getenv("TOKENIZER_PATH", "ml_model/tokenizer.pkl")
    MAX_INPUT_LENGTH = int(os.getenv("MAX_INPUT_LENGTH", 10000))
    RATE_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", 1000))

    LOG_DIR = "logs"
    MALICIOUS_LOG_FILE = "logs/malicious_attempts.jsonl"
    APP_LOG_FILE = "logs/app.log"


def get_config():
    """Return the Config class."""
    return Config

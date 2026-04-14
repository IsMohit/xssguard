"""
backend/firebase_init.py
Initializes Firebase Admin SDK once at app startup.
"""
import os
import logging
import firebase_admin
from firebase_admin import credentials

logger = logging.getLogger(__name__)

def init_firebase(app):
    """
    Initialize Firebase Admin SDK.
    Uses service account JSON from the path set in .env.
    """
    if firebase_admin._apps:
        # Already initialized (e.g., during testing)
        return

    sa_path = app.config.get("FIREBASE_SERVICE_ACCOUNT_PATH")

    if not sa_path or not os.path.exists(sa_path):
        logger.warning(
            "Firebase service account not found at '%s'. "
            "Running WITHOUT Firebase — auth will fail. "
            "See README.md → Firebase Setup.", sa_path
        )
        app.config["FIREBASE_ENABLED"] = False
        return

    try:
        cred = credentials.Certificate(sa_path)
        firebase_admin.initialize_app(cred)
        app.config["FIREBASE_ENABLED"] = True
        logger.info("Firebase Admin SDK initialized successfully.")
    except Exception as e:
        logger.error("Firebase init failed: %s", e)
        app.config["FIREBASE_ENABLED"] = False

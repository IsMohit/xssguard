"""
backend/middleware/auth_middleware.py
Verifies Firebase ID tokens sent in the Authorization header.
Usage:
    from backend.middleware.auth_middleware import require_auth
    @app.route("/api/protected")
    @require_auth
    def protected(uid):
        ...
"""
import logging
from functools import wraps
from flask import request, jsonify, current_app

logger = logging.getLogger(__name__)

def require_auth(f):
    """Decorator: verifies Bearer token, injects uid into the route."""
    @wraps(f)
    def decorated(*args, **kwargs):
        logger.info("[AUTH-MIDDLEWARE] Checking authorization...")
        
        if not current_app.config.get("FIREBASE_ENABLED"):
            # Firebase not configured — reject all protected requests
            logger.error("[AUTH-MIDDLEWARE] Firebase not enabled!")
            return jsonify({
                "error": "Authentication service unavailable",
                "hint": "Configure Firebase in .env and config/firebase_service_account.json"
            }), 503

        auth_header = request.headers.get("Authorization", "")
        logger.info("[AUTH-MIDDLEWARE] Authorization header present: %s", bool(auth_header))
        
        if not auth_header.startswith("Bearer "):
            logger.error("[AUTH-MIDDLEWARE] Invalid Authorization header format")
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        id_token = auth_header.split("Bearer ")[1].strip()
        logger.info("[AUTH-MIDDLEWARE] Extracted token (first 20 chars): %s...", id_token[:20])

        try:
            from firebase_admin import auth as firebase_auth
            logger.info("[AUTH-MIDDLEWARE] Verifying token with Firebase Admin SDK...")
            decoded = firebase_auth.verify_id_token(id_token)
            uid = decoded["uid"]
            logger.info("[AUTH-MIDDLEWARE] Token verified successfully! uid=%s", uid)
        except Exception as e:
            logger.warning("[AUTH-MIDDLEWARE] Token verification FAILED: %s (type: %s)", str(e), type(e).__name__)
            return jsonify({"error": "Invalid or expired token", "details": str(e)}), 401

        logger.info("[AUTH-MIDDLEWARE] Authorization success, calling route handler...")
        return f(uid, *args, **kwargs)
    return decorated


def require_api_key(f):
    """
    Decorator: verifies X-API-Key header against Firestore.
    Used for protecting the /api/xss/check endpoint (SDK calls).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get("X-API-Key", "")
        if not api_key:
            return jsonify({"error": "Missing X-API-Key header"}), 401

        if not current_app.config.get("FIREBASE_ENABLED"):
            # Dev mode: skip key validation if Firebase not set up
            return f(*args, **kwargs)

        try:
            import hashlib
            from firebase_admin import firestore
            from google.cloud.firestore_v1.base_query import FieldFilter
            db = firestore.client()
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            docs = (
                db.collection("api_keys")
                .where(filter=FieldFilter("key_hash", "==", key_hash))
                .where(filter=FieldFilter("is_active", "==", True))
                .limit(1)
                .get()
            )
            if not docs:
                return jsonify({"error": "Invalid API key"}), 401
            # Update last_used
            docs[0].reference.update({"last_used_at": firestore.SERVER_TIMESTAMP})
        except Exception as e:
            logger.error("API key validation error: %s", e)
            return jsonify({"error": "Key validation failed"}), 500

        return f(*args, **kwargs)
    return decorated

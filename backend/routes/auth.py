"""
backend/routes/auth.py
Auth helper endpoints.
Real sign-in/sign-up is done client-side via Firebase JS SDK.
These endpoints handle server-side tasks: syncing user to Firestore,
verifying tokens, and returning user profile data.
"""
import logging
from flask import Blueprint, request, jsonify, current_app
from backend.middleware.auth_middleware import require_auth

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/sync-user", methods=["POST"])
@require_auth
def sync_user(uid):
    """
    Called after Firebase sign-up to create the user document in Firestore.
    Frontend sends: { displayName, email }
    """
    logger.info("[SYNC-USER] Starting... uid=%s", uid)
    
    if not current_app.config.get("FIREBASE_ENABLED"):
        logger.error("[SYNC-USER] ERROR: Firebase not enabled")
        return jsonify({"error": "Firebase not configured"}), 503

    data = request.get_json(silent=True) or {}
    display_name = data.get("displayName", "")
    email = data.get("email", "")
    
    logger.info("[SYNC-USER] Request data: displayName=%s, email=%s", display_name, email)

    try:
        from firebase_admin import firestore
        logger.info("[SYNC-USER] Importing firestore...")
        
        db = firestore.client()
        logger.info("[SYNC-USER] Got firestore client")
        
        user_ref = db.collection("users").document(uid)
        logger.info("[SYNC-USER] Got user document reference")
        
        doc = user_ref.get()
        logger.info("[SYNC-USER] Checked if user exists: exists=%s", doc.exists)

        if not doc.exists:
            logger.info("[SYNC-USER] Creating new user document...")
            user_ref.set({
                "uid": uid,
                "displayName": display_name,
                "email": email,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "plan": "free",
                "totalScans": 0,
            })
            logger.info("[SYNC-USER] SUCCESS: New user synced to Firestore: %s", uid)
            return jsonify({"status": "created", "uid": uid}), 201
        else:
            logger.info("[SYNC-USER] User already exists: %s", uid)
            return jsonify({"status": "exists", "uid": uid}), 200

    except Exception as e:
        logger.error("[SYNC-USER] EXCEPTION: %s (type: %s)", str(e), type(e).__name__, exc_info=True)
        return jsonify({"error": "Failed to sync user", "details": str(e)}), 500


@auth_bp.route("/me", methods=["GET"])
@require_auth
def get_me(uid):
    """Returns the current user's Firestore profile."""
    try:
        from firebase_admin import firestore
        db = firestore.client()
        doc = db.collection("users").document(uid).get()
        if not doc.exists:
            return jsonify({"error": "User not found"}), 404
        return jsonify(doc.to_dict()), 200
    except Exception as e:
        logger.error("get_me error: %s", e)
        return jsonify({"error": "Failed to fetch profile"}), 500


@auth_bp.route("/me", methods=["PATCH"])
@require_auth
def update_me(uid):
    """Update display name."""
    data = request.get_json(silent=True) or {}
    display_name = data.get("displayName", "").strip()
    if not display_name:
        return jsonify({"error": "displayName is required"}), 400
    try:
        from firebase_admin import auth as firebase_auth
        from firebase_admin import firestore
        db = firestore.client()
        db.collection("users").document(uid).update({"displayName": display_name})
        firebase_auth.update_user(uid, display_name=display_name)
        return jsonify({"status": "updated", "displayName": display_name}), 200
    except Exception as e:
        logger.error("update_me error: %s", e)
        return jsonify({"error": "Update failed"}), 500

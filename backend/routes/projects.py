"""
backend/routes/projects.py
CRUD for projects and API key management.
All routes require a valid Firebase ID token.
"""
import secrets
import hashlib
import logging
from flask import Blueprint, request, jsonify, current_app
from backend.middleware.auth_middleware import require_auth

logger = logging.getLogger(__name__)
projects_bp = Blueprint("projects", __name__)


def _db():
    from firebase_admin import firestore
    return firestore.client()


def _gen_api_key():
    """Generate a sk-XXXXX API key (32 random bytes)."""
    return "sk-" + secrets.token_urlsafe(32)


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _sort_firestore_docs(items, field_name):
    """Sort dict-like Firestore payloads by timestamp-ish field descending."""
    def _key(item):
        value = item.get(field_name)
        if value is None:
            return 0
        if hasattr(value, "timestamp"):
            try:
                return value.timestamp()
            except Exception:
                return 0
        if isinstance(value, dict) and "_seconds" in value:
            return value.get("_seconds", 0)
        if isinstance(value, (int, float)):
            return value
        return 0

    return sorted(items, key=_key, reverse=True)


# ── List all projects ────────────────────────────────────────
@projects_bp.route("/", methods=["GET"])
@require_auth
def list_projects(uid):
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        db = _db()
        docs = db.collection("projects").where(filter=FieldFilter("uid", "==", uid)).get()
        projects = []
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            d.pop("uid", None)          # Don't expose uid
            d.pop("key_hash", None)     # Never expose hash
            # Only return key prefix for display
            d["key_prefix"] = d.get("key_prefix", "sk-...")
            projects.append(d)
        projects = _sort_firestore_docs(projects, "createdAt")
        return jsonify({"projects": projects}), 200
    except Exception as e:
        logger.error("list_projects error: %s", e)
        return jsonify({"error": "Failed to fetch projects"}), 500


# ── Create project ───────────────────────────────────────────
@projects_bp.route("/", methods=["POST"])
@require_auth
def create_project(uid):
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()

    if not name:
        return jsonify({"error": "Project name is required"}), 400
    if len(name) > 80:
        return jsonify({"error": "Project name too long (max 80 chars)"}), 400

    raw_key = _gen_api_key()
    key_hash = _hash_key(raw_key)
    key_prefix = raw_key[:10]  # e.g. "sk-AbCd12"

    try:
        from firebase_admin import firestore
        db = _db()
        project_ref = db.collection("projects").document()
        project_ref.set({
            "uid": uid,
            "name": name,
            "description": description,
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "totalScans": 0,
            "maliciousDetected": 0,
            "is_active": True,
        })
        # Also store in api_keys collection for fast lookup
        db.collection("api_keys").document(project_ref.id).set({
            "project_id": project_ref.id,
            "uid": uid,
            "key_hash": key_hash,
            "is_active": True,
            "last_used_at": None,
        })
        logger.info("Project created: %s by uid %s", project_ref.id, uid)
        # Return the raw key ONCE — never stored in plaintext
        return jsonify({
            "status": "created",
            "project": {
                "id": project_ref.id,
                "name": name,
                "description": description,
                "key_prefix": key_prefix,
            },
            "api_key": raw_key,   # Show once to user
            "warning": "Copy this key now. It will never be shown again.",
        }), 201

    except Exception as e:
        logger.error("create_project error: %s", e)
        return jsonify({"error": "Failed to create project"}), 500


# ── Get single project ───────────────────────────────────────
@projects_bp.route("/<project_id>", methods=["GET"])
@require_auth
def get_project(uid, project_id):
    try:
        db = _db()
        doc = db.collection("projects").document(project_id).get()
        if not doc.exists:
            return jsonify({"error": "Project not found"}), 404
        d = doc.to_dict()
        if d.get("uid") != uid:
            return jsonify({"error": "Forbidden"}), 403
        d["id"] = doc.id
        d.pop("uid", None)
        d.pop("key_hash", None)
        return jsonify(d), 200
    except Exception as e:
        logger.error("get_project error: %s", e)
        return jsonify({"error": "Failed to fetch project"}), 500


# ── Delete project ───────────────────────────────────────────
@projects_bp.route("/<project_id>", methods=["DELETE"])
@require_auth
def delete_project(uid, project_id):
    try:
        from firebase_admin import firestore
        db = _db()
        doc = db.collection("projects").document(project_id).get()
        if not doc.exists:
            return jsonify({"error": "Project not found"}), 404
        if doc.to_dict().get("uid") != uid:
            return jsonify({"error": "Forbidden"}), 403

        # Deactivate the API key
        db.collection("api_keys").document(project_id).update({"is_active": False})
        # Delete project document
        db.collection("projects").document(project_id).delete()
        logger.info("Project deleted: %s by uid %s", project_id, uid)
        return jsonify({"status": "deleted"}), 200
    except Exception as e:
        logger.error("delete_project error: %s", e)
        return jsonify({"error": "Failed to delete project"}), 500


# ── Rotate API key ───────────────────────────────────────────
@projects_bp.route("/<project_id>/rotate-key", methods=["POST"])
@require_auth
def rotate_key(uid, project_id):
    try:
        from firebase_admin import firestore
        db = _db()
        doc = db.collection("projects").document(project_id).get()
        if not doc.exists:
            return jsonify({"error": "Project not found"}), 404
        if doc.to_dict().get("uid") != uid:
            return jsonify({"error": "Forbidden"}), 403

        raw_key = _gen_api_key()
        key_hash = _hash_key(raw_key)
        key_prefix = raw_key[:10]

        db.collection("projects").document(project_id).update({
            "key_hash": key_hash,
            "key_prefix": key_prefix,
        })
        db.collection("api_keys").document(project_id).update({
            "key_hash": key_hash,
            "is_active": True,
            "last_used_at": None,
        })
        logger.info("API key rotated for project %s", project_id)
        return jsonify({
            "status": "rotated",
            "api_key": raw_key,
            "warning": "Copy this key now. It will never be shown again.",
        }), 200
    except Exception as e:
        logger.error("rotate_key error: %s", e)
        return jsonify({"error": "Failed to rotate key"}), 500


# ── Get project scan logs ────────────────────────────────────
@projects_bp.route("/<project_id>/logs", methods=["GET"])
@require_auth
def get_project_logs(uid, project_id):
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        db = _db()
        doc = db.collection("projects").document(project_id).get()
        if not doc.exists:
            return jsonify({"error": "Project not found"}), 404
        if doc.to_dict().get("uid") != uid:
            return jsonify({"error": "Forbidden"}), 403

        limit = min(int(request.args.get("limit", 50)), 200)
        logs = db.collection("scan_logs") \
            .where(filter=FieldFilter("project_id", "==", project_id)) \
            .get()

        log_items = _sort_firestore_docs(
            [{"id": l.id, **l.to_dict()} for l in logs],
            "timestamp",
        )[:limit]

        return jsonify({
            "logs": log_items
        }), 200
    except Exception as e:
        logger.error("get_project_logs error: %s", e)
        return jsonify({"error": "Failed to fetch logs"}), 500

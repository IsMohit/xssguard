"""
backend/routes/xss.py
XSS detection endpoints called by the SDK / direct API consumers.
Requires X-API-Key header for detection endpoints.
"""
import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app
from backend.middleware.auth_middleware import require_api_key
from backend.utils.xss_detector import detect_xss, detect_xss_batch
from backend.utils.logger import log_malicious_attempt

logger = logging.getLogger(__name__)
xss_bp = Blueprint("xss", __name__)


def _get_model():
    return current_app.config.get("ML_MODEL"), current_app.config.get("ML_TOKENIZER")


def _json_error(message, status=400, **extra):
    payload = {"error": message}
    payload.update(extra)
    return jsonify(payload), status


def _log_scan_to_firestore(project_id, result, input_text):
    """Write scan event to Firestore scan_logs collection."""
    try:
        if not current_app.config.get("FIREBASE_ENABLED"):
            return

        from firebase_admin import firestore

        db = firestore.client()
        db.collection("scan_logs").add({
            "project_id": project_id,
            "input_preview": str(input_text)[:200],
            "prediction": result["prediction"],
            "confidence": result["confidence"],
            "risk_level": result.get("risk_level", "low"),
            "timestamp": firestore.SERVER_TIMESTAMP,
        })

        update = {"totalScans": firestore.Increment(1)}
        if result.get("is_malicious"):
            update["maliciousDetected"] = firestore.Increment(1)
        db.collection("projects").document(project_id).update(update)

        key_doc = db.collection("api_keys").document(project_id).get()
        if key_doc.exists:
            uid = key_doc.to_dict().get("uid")
            if uid:
                db.collection("users").document(uid).update({
                    "totalScans": firestore.Increment(1)
                })
    except Exception as e:
        logger.warning("Firestore scan log write failed: %s", e)


def _get_project_id_from_key(api_key):
    """Resolve project_id from api key hash."""
    try:
        import hashlib
        from firebase_admin import firestore
        from google.cloud.firestore_v1.base_query import FieldFilter

        db = firestore.client()
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        docs = (
            db.collection("api_keys")
            .where(filter=FieldFilter("key_hash", "==", key_hash))
            .limit(1)
            .get()
        )
        if docs:
            return docs[0].to_dict().get("project_id")
    except Exception as e:
        logger.warning("Could not resolve project_id from API key: %s", e)
    return None


@xss_bp.route("/check", methods=["POST"])
@require_api_key
def check():
    data = request.get_json(silent=True) or {}
    user_input = data.get("input", "")

    if isinstance(user_input, list):
        return _json_error(
            "Field 'input' must be a string. Use /api/xss/batch-check with an 'inputs' array for batch scans.",
            400,
        )
    if not isinstance(user_input, str):
        return _json_error("Field 'input' must be a string", 400)

    if not user_input or not user_input.strip():
        return jsonify({
            "prediction": "safe",
            "message": "Empty input",
            "sanitized": "",
            "confidence": 100.0,
            "probabilities": {"safe": 100.0, "malicious": 0.0},
            "model_used": "CNN-LSTM",
            "original_length": len(user_input),
            "sanitized_length": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 200

    max_len = current_app.config.get("MAX_INPUT_LENGTH", 10000)
    if len(user_input) > max_len:
        return _json_error(f"Input exceeds maximum length of {max_len} characters", 400)

    model, tokenizer = _get_model()
    if not model or not tokenizer:
        return _json_error(
            "ML model not loaded",
            503,
            hint="Verify the TensorFlow/Keras environment and the files in ml_model/.",
        )

    result = detect_xss(user_input, model, tokenizer)
    result["timestamp"] = datetime.now(timezone.utc).isoformat()

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if result.get("is_malicious"):
        api_key = request.headers.get("X-API-Key", "")
        project_id = _get_project_id_from_key(api_key)
        log_malicious_attempt(client_ip, user_input, result, project_id=project_id)
    else:
        api_key = request.headers.get("X-API-Key", "")
        project_id = _get_project_id_from_key(api_key)

    if project_id:
        _log_scan_to_firestore(project_id, result, user_input)

    return jsonify(result), 200


@xss_bp.route("/batch-check", methods=["POST"])
@require_api_key
def batch_check():
    data = request.get_json(silent=True) or {}
    inputs = data.get("inputs", [])

    if not inputs or not isinstance(inputs, list):
        return _json_error("Field 'inputs' must be a non-empty list", 400)
    if len(inputs) > 100:
        return _json_error("Maximum 100 inputs per batch request", 400)
    if any(not isinstance(item, str) for item in inputs):
        return _json_error("Every item in 'inputs' must be a string", 400)
    if any(not item.strip() for item in inputs):
        return _json_error("Input items cannot be empty", 400)

    model, tokenizer = _get_model()
    if not model or not tokenizer:
        return _json_error(
            "ML model not loaded",
            503,
            hint="Verify the TensorFlow/Keras environment and the files in ml_model/.",
        )

    results = detect_xss_batch(inputs, model, tokenizer)
    malicious_count = sum(1 for r in results if r.get("prediction") == "malicious")

    return jsonify({
        "total": len(inputs),
        "malicious_detected": malicious_count,
        "safe_detected": len(inputs) - malicious_count,
        "model_used": "CNN-LSTM",
        "results": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200


@xss_bp.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy" if current_app.config.get("ML_ENABLED") else "degraded",
        "model_type": "CNN-LSTM",
        "ml_model_loaded": current_app.config.get("ML_ENABLED", False),
        "firebase_enabled": current_app.config.get("FIREBASE_ENABLED", False),
        "max_sequence_length": current_app.config.get("ML_MAX_SEQUENCE_LENGTH", 300),
        "vocabulary_size": current_app.config.get("ML_VOCAB_SIZE"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200


@xss_bp.route("/model-info", methods=["GET"])
def model_info():
    model, _ = _get_model()
    if not model:
        return jsonify({"error": "Model not loaded"}), 503

    try:
        params = int(model.count_params())
    except Exception:
        params = None

    return jsonify({
        "model_type": "CNN-LSTM Hybrid",
        "architecture": "Embedding -> CNN -> MaxPool -> BiLSTM -> Dense",
        "total_parameters": params,
        "max_sequence_length": current_app.config.get("ML_MAX_SEQUENCE_LENGTH", 300),
        "vocabulary_size": current_app.config.get("ML_VOCAB_SIZE"),
        "tokenization": "Character-level",
        "advantages": [
            "Better pattern recognition",
            "Captures sequential dependencies",
            "Handles obfuscated payloads",
            "Lower false positive rate",
        ],
    }), 200


@xss_bp.route("/stats", methods=["GET"])
def stats():
    from backend.utils.logger import get_recent_logs

    logs = get_recent_logs(100)
    high_conf = [l for l in logs if (l.get("confidence") or 0) >= 90]
    return jsonify({
        "model_type": "CNN-LSTM",
        "total_logged_attempts": len(logs),
        "high_confidence_attempts": len(high_conf),
        "recent": logs[:10],
    }), 200

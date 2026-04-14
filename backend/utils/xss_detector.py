"""
backend/utils/xss_detector.py
Core XSS detection and sanitization logic.
Uses the loaded CNN-LSTM model from app.config.
"""
import re
import html
import logging
import bleach

logger = logging.getLogger(__name__)

DEFAULT_MAX_LENGTH = 300
ALLOWED_TAGS = ["p", "br", "strong", "em", "u", "a", "ul", "ol", "li"]
ALLOWED_ATTRS = {"a": ["href", "title"]}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def preprocess_text(text: str) -> str:
    """Decode HTML entities, lowercase, and normalize whitespace."""
    text = str(text)
    text = html.unescape(text)
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def sanitize_input(text: str) -> str:
    """Remove dangerous HTML using a Bleach whitelist."""
    return bleach.clean(
        str(text),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )


def detect_xss(text: str, model, tokenizer) -> dict:
    """
    Run the CNN-LSTM model on one input and return the richer original API schema.
    """
    try:
        from flask import current_app

        pad_sequences = current_app.config.get("ML_PAD_SEQUENCES")
        max_length = current_app.config.get("ML_MAX_SEQUENCE_LENGTH", DEFAULT_MAX_LENGTH)
        if pad_sequences is None:
            raise RuntimeError("pad_sequences is not available")

        cleaned = preprocess_text(text)
        sequence = tokenizer.texts_to_sequences([cleaned])
        padded = pad_sequences(sequence, maxlen=max_length, padding="post", truncating="post")
        prediction_proba = float(model.predict(padded, verbose=0)[0][0])

        is_malicious = prediction_proba >= 0.5
        confidence = prediction_proba * 100 if is_malicious else (1 - prediction_proba) * 100
        sanitized = sanitize_input(text)
        sanitization_effective = True

        if is_malicious and sanitized.strip():
            sanitized_seq = tokenizer.texts_to_sequences([preprocess_text(sanitized)])
            sanitized_padded = pad_sequences(
                sanitized_seq,
                maxlen=max_length,
                padding="post",
                truncating="post",
            )
            sanitized_score = float(model.predict(sanitized_padded, verbose=0)[0][0])
            if sanitized_score >= 0.5:
                sanitized = ""
                sanitization_effective = False

        result = {
            "prediction": "malicious" if is_malicious else "safe",
            "is_malicious": is_malicious,
            "confidence": round(confidence, 2),
            "sanitized": sanitized,
            "probabilities": {
                "safe": round((1 - prediction_proba) * 100, 2),
                "malicious": round(prediction_proba * 100, 2),
            },
            "model_used": "CNN-LSTM",
            "original_length": len(str(text)),
            "sanitized_length": len(sanitized),
            "risk_level": "high" if confidence > 90 else "medium" if is_malicious else "low",
            "sanitization_effective": sanitization_effective,
        }

        if is_malicious:
            result["warning"] = "Potential XSS attack detected by CNN-LSTM model!"
            result["recommendation"] = "Input has been sanitized. Do not trust this input."
            if not sanitization_effective:
                result["sanitization_warning"] = (
                    "Could not sanitize input safely - still contains malicious patterns"
                )
                result["action_required"] = "Input must be completely rejected"
                result["sanitized"] = ""
                result["sanitized_length"] = 0

        return result
    except Exception as e:
        logger.error("XSS detection error: %s", e)
        safe_text = sanitize_input(text)
        return {
            "prediction": "unknown",
            "is_malicious": False,
            "confidence": 0.0,
            "sanitized": safe_text,
            "probabilities": {"safe": 0.0, "malicious": 0.0},
            "model_used": "CNN-LSTM",
            "original_length": len(str(text)),
            "sanitized_length": len(safe_text),
            "risk_level": "unknown",
            "sanitization_effective": False,
            "error": str(e),
        }


def detect_xss_batch(inputs: list, model, tokenizer) -> list:
    """Batch prediction for up to 100 inputs."""
    try:
        from flask import current_app

        pad_sequences = current_app.config.get("ML_PAD_SEQUENCES")
        max_length = current_app.config.get("ML_MAX_SEQUENCE_LENGTH", DEFAULT_MAX_LENGTH)
        if pad_sequences is None:
            raise RuntimeError("pad_sequences is not available")

        cleaned = [preprocess_text(t) for t in inputs]
        sequences = tokenizer.texts_to_sequences(cleaned)
        padded = pad_sequences(sequences, maxlen=max_length, padding="post", truncating="post")
        scores = model.predict(padded, verbose=0).flatten()

        results = []
        for idx, (user_input, score) in enumerate(zip(inputs, scores)):
            score = float(score)
            is_malicious = score >= 0.5
            confidence = score * 100 if is_malicious else (1 - score) * 100
            sanitized = sanitize_input(user_input)

            results.append({
                "index": idx,
                "prediction": "malicious" if is_malicious else "safe",
                "is_malicious": is_malicious,
                "confidence": round(confidence, 2),
                "sanitized": sanitized,
                "probabilities": {
                    "safe": round((1 - score) * 100, 2),
                    "malicious": round(score * 100, 2),
                },
                "risk_level": "high" if confidence > 90 else "medium" if is_malicious else "low",
            })
        return results
    except Exception as e:
        logger.error("Batch detection error: %s", e)
        return [{"index": i, "error": str(e)} for i in range(len(inputs))]

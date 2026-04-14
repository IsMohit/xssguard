"""
backend/ml_loader.py
Loads the CNN-LSTM model and tokenizer once at startup.
Attaches them to app.config so all routes can access them.
"""
import os
import pickle
import logging
import sys
import types

logger = logging.getLogger(__name__)


def _load_keras_runtime():
    """
    Import a usable Keras runtime from the local environment.
    Returns the keras module and pad_sequences helper.
    """
    try:
        from tensorflow import keras
        from tensorflow.keras.preprocessing.sequence import pad_sequences
        return keras, pad_sequences
    except Exception as tf_err:
        logger.warning("tensorflow.keras import failed: %s", tf_err)

    try:
        import keras
        from keras.preprocessing.sequence import pad_sequences
        return keras, pad_sequences
    except Exception as keras_err:
        raise RuntimeError(
            "Could not import a usable Keras runtime. "
            f"tensorflow.keras failed and standalone keras failed: {keras_err}"
        ) from keras_err


def _install_keras_pickle_compat():
    """
    Old tokenizer pickles may reference keras.src.legacy.preprocessing.*.
    Map those modules to the current Keras preprocessing modules before unpickling.
    """
    import keras.src.preprocessing.sequence as sequence_mod
    import keras.src.preprocessing.text as text_mod

    legacy_pkg = types.ModuleType("keras.src.legacy")
    legacy_preprocessing_pkg = types.ModuleType("keras.src.legacy.preprocessing")
    legacy_preprocessing_pkg.text = text_mod
    legacy_preprocessing_pkg.sequence = sequence_mod

    sys.modules.setdefault("keras.src.legacy", legacy_pkg)
    sys.modules.setdefault("keras.src.legacy.preprocessing", legacy_preprocessing_pkg)
    sys.modules["keras.src.legacy.preprocessing.text"] = text_mod
    sys.modules["keras.src.legacy.preprocessing.sequence"] = sequence_mod


def _build_model_fallback(keras, max_length, vocab_size):
    """
    Rebuild the original CNN-LSTM architecture explicitly.
    This is used when H5 deserialization fails on newer Keras versions.
    """
    from tensorflow.keras import layers, regularizers

    inputs = keras.Input(shape=(max_length,), name="input")
    x = layers.Embedding(vocab_size, 256, name="embedding")(inputs)
    x = layers.SpatialDropout1D(0.2, name="spatial_dropout1d")(x)

    conv3 = layers.Conv1D(128, 3, padding="same", activation="relu", name="conv1d")(x)
    conv3 = layers.BatchNormalization(name="batch_normalization")(conv3)
    conv3 = layers.MaxPooling1D(2, name="max_pooling1d")(conv3)

    conv5 = layers.Conv1D(128, 5, padding="same", activation="relu", name="conv1d_1")(x)
    conv5 = layers.BatchNormalization(name="batch_normalization_1")(conv5)
    conv5 = layers.MaxPooling1D(2, name="max_pooling1d_1")(conv5)

    conv7 = layers.Conv1D(128, 7, padding="same", activation="relu", name="conv1d_2")(x)
    conv7 = layers.BatchNormalization(name="batch_normalization_2")(conv7)
    conv7 = layers.MaxPooling1D(2, name="max_pooling1d_2")(conv7)

    x = layers.Concatenate(name="concatenate")([conv3, conv5, conv7])
    x = layers.Dropout(0.3, name="dropout")(x)
    x = layers.Conv1D(256, 3, padding="same", activation="relu", name="conv1d_3")(x)
    x = layers.BatchNormalization(name="batch_normalization_3")(x)
    x = layers.MaxPooling1D(2, name="max_pooling1d_3")(x)
    x = layers.Dropout(0.3, name="dropout_1")(x)

    x = layers.Bidirectional(
        layers.LSTM(128, return_sequences=True, name="forward_lstm"),
        backward_layer=layers.LSTM(128, return_sequences=True, go_backwards=True, name="backward_lstm"),
        name="bidirectional",
    )(x)
    x = layers.BatchNormalization(name="batch_normalization_4")(x)

    x = layers.Bidirectional(
        layers.LSTM(64, return_sequences=False, name="forward_lstm_1"),
        backward_layer=layers.LSTM(64, return_sequences=False, go_backwards=True, name="backward_lstm_1"),
        name="bidirectional_1",
    )(x)
    x = layers.BatchNormalization(name="batch_normalization_5")(x)
    x = layers.Dropout(0.4, name="dropout_2")(x)

    x = layers.Dense(
        256,
        activation="relu",
        kernel_regularizer=regularizers.l2(0.01),
        name="dense",
    )(x)
    x = layers.BatchNormalization(name="batch_normalization_6")(x)
    x = layers.Dropout(0.5, name="dropout_3")(x)
    x = layers.Dense(128, activation="relu", name="dense_1")(x)
    x = layers.BatchNormalization(name="batch_normalization_7")(x)
    x = layers.Dropout(0.4, name="dropout_4")(x)
    x = layers.Dense(64, activation="relu", name="dense_2")(x)
    x = layers.Dropout(0.3, name="dropout_5")(x)
    outputs = layers.Dense(1, activation="sigmoid", name="output")(x)

    return keras.Model(inputs=inputs, outputs=outputs, name="XSS_CNN_LSTM")


def init_ml_model(app):
    print("[ML_LOADER] Starting ML model initialization...", flush=True)
    model_path = app.config.get("MODEL_PATH", "ml_model/xss_cnn_lstm_model.h5")
    tokenizer_path = app.config.get("TOKENIZER_PATH", "ml_model/tokenizer.pkl")

    model_ok = os.path.exists(model_path)
    tokenizer_ok = os.path.exists(tokenizer_path)

    if not model_ok or not tokenizer_ok:
        logger.warning(
            "ML model files not found (%s, %s). "
            "XSS detection will be unavailable until model files are present.",
            model_path,
            tokenizer_path,
        )
        app.config["ML_ENABLED"] = False
        app.config["ML_MODEL"] = None
        app.config["ML_TOKENIZER"] = None
        app.config["ML_PAD_SEQUENCES"] = None
        app.config["ML_MAX_SEQUENCE_LENGTH"] = 300
        app.config["ML_VOCAB_SIZE"] = None
        return

    try:
        print("[ML_LOADER] Importing Keras/TensorFlow runtime...", flush=True)
        keras, pad_sequences = _load_keras_runtime()

        print("[ML_LOADER] Loading tokenizer from", tokenizer_path, flush=True)
        _install_keras_pickle_compat()
        with open(tokenizer_path, "rb") as f:
            tokenizer_data = pickle.load(f)

        if isinstance(tokenizer_data, dict):
            tokenizer = tokenizer_data.get("tokenizer")
            max_length = tokenizer_data.get("max_length", 300)
            vocab_size = tokenizer_data.get("vocab_size")
        else:
            tokenizer = tokenizer_data
            max_length = 300
            vocab_size = getattr(tokenizer, "num_words", None)

        if tokenizer is None:
            raise ValueError("Tokenizer payload is missing the tokenizer object")

        max_length = int(max_length or 300)
        vocab_size = int(vocab_size or getattr(tokenizer, "num_words", 5000) or 5000)

        print("[ML_LOADER] Loading model from", model_path, flush=True)
        try:
            model = keras.models.load_model(model_path)
        except Exception as load_err:
            logger.warning("Standard model load failed, using architecture fallback: %s", load_err)
            model = _build_model_fallback(keras, max_length, vocab_size)
            model.load_weights(model_path)

        app.config["ML_ENABLED"] = True
        app.config["ML_MODEL"] = model
        app.config["ML_TOKENIZER"] = tokenizer
        app.config["ML_PAD_SEQUENCES"] = pad_sequences
        app.config["ML_MAX_SEQUENCE_LENGTH"] = max_length
        app.config["ML_VOCAB_SIZE"] = vocab_size
        logger.info(
            "CNN-LSTM model loaded successfully from %s (max_length=%s, vocab_size=%s)",
            model_path,
            app.config["ML_MAX_SEQUENCE_LENGTH"],
            vocab_size,
        )
    except Exception as e:
        logger.error("ML model load failed: %s", e)
        app.config["ML_ENABLED"] = False
        app.config["ML_MODEL"] = None
        app.config["ML_TOKENIZER"] = None
        app.config["ML_PAD_SEQUENCES"] = None
        app.config["ML_MAX_SEQUENCE_LENGTH"] = 300
        app.config["ML_VOCAB_SIZE"] = None

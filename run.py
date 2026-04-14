"""
XSSGuard — Entry Point
Run this file to start the Flask server.
"""
import os
import sys

# Suppress TensorFlow verbose logging for faster startup
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

print("[STARTUP] Importing backend.app...", flush=True)
from backend.app import create_app

print("[STARTUP] Creating app instance...", flush=True)
app = create_app()

print("[STARTUP] App created. Starting server...", flush=True)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

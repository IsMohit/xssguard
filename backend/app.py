"""
backend/app.py
Flask application factory.
"""
import os
import logging
from flask import Flask, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from config.settings import Config
from backend.firebase_init import init_firebase
from backend.ml_loader import init_ml_model

def create_app():
    app = Flask(
        __name__,
        template_folder="../frontend/templates",
        static_folder="../frontend/static",
        static_url_path="/static",
    )
    app.config.from_object(Config)

    # CORS — allow all in dev; tighten in production
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Logging
    os.makedirs(Config.LOG_DIR, exist_ok=True)
    logging.basicConfig(
        filename=Config.APP_LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app.logger.setLevel(logging.INFO)

    # Firebase Admin SDK
    print("[APP] Initializing Firebase...", flush=True)
    init_firebase(app)
    print("[APP] Firebase initialized.", flush=True)

    # ML Model
    print("[APP] Initializing ML model...", flush=True)
    init_ml_model(app)
    print("[APP] ML model initialized.", flush=True)

    # Register blueprints
    from backend.routes.pages import pages_bp
    from backend.routes.auth import auth_bp
    from backend.routes.xss import xss_bp
    from backend.routes.projects import projects_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(xss_bp, url_prefix="/api/xss")
    app.register_blueprint(projects_bp, url_prefix="/api/projects")

    @app.errorhandler(HTTPException)
    def handle_http_exception(err):
        if not str(getattr(err, "path", "")).startswith("/api/"):
            return err
        return {
            "error": err.name,
            "message": err.description,
            "status": err.code,
        }, err.code

    @app.errorhandler(Exception)
    def handle_api_exception(err):
        if not request.path.startswith("/api/"):
            app.logger.exception("Unhandled page exception on %s", request.path)
            return {
                "error": "Internal Server Error",
                "message": "An unexpected error occurred",
                "status": 500,
            }, 500

        app.logger.exception("Unhandled API exception on %s", request.path)
        return {
            "error": "Internal Server Error",
            "message": str(err) if app.debug else "An unexpected error occurred",
            "status": 500,
        }, 500

    return app

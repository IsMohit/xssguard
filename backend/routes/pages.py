"""
backend/routes/pages.py
Serves all HTML pages (Flask renders Jinja2 templates).
Injects Firebase client config into every page so the frontend JS
can initialise the Firebase SDK without hardcoding keys.
"""
from flask import Blueprint, render_template, current_app

pages_bp = Blueprint("pages", __name__)


def _firebase_cfg():
    """Return client config dict (safe to expose to browser)."""
    return current_app.config.get("FIREBASE_CLIENT_CONFIG", {})


@pages_bp.route("/")
def landing():
    return render_template("landing.html", firebase=_firebase_cfg())


@pages_bp.route("/favicon.ico")
def favicon():
    return "", 204


@pages_bp.route("/signin")
def signin():
    return render_template("signin.html", firebase=_firebase_cfg())


@pages_bp.route("/signup")
def signup():
    return render_template("signup.html", firebase=_firebase_cfg())


@pages_bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", firebase=_firebase_cfg())


@pages_bp.route("/project/<project_id>")
def project_detail(project_id):
    return render_template("project.html", firebase=_firebase_cfg(), project_id=project_id)

"""Opaque PostgreSQL sessions, cookie authentication and CSRF protection."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import current_app, g, jsonify, request

COOKIE_NAME = "hikeup_session"


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def current_user_id():
    return getattr(g, "auth_session", {}).get("user", {}).get("id")


def login_required(view):
    @wraps(view)
    def protected(*args, **kwargs):
        if current_user_id() is None:
            return jsonify(success=False, message="Wymagane logowanie."), 401
        return view(*args, **kwargs)
    return protected


def initialize_auth(app):
    @app.before_request
    def authenticate_request():
        if request.method == "OPTIONS":
            return None
        g.auth_session = {}
        if request.is_json and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if not isinstance(request.get_json(silent=True), dict):
                return jsonify(success=False, message="Wymagany obiekt JSON."), 400
        token = request.cookies.get(COOKIE_NAME)
        if token and len(token) == 43:
            from database import find_auth_session
            g.auth_session = find_auth_session(token_hash(token)) or {}
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("Origin")
            if origin and origin not in current_app.config["FRONTEND_ORIGINS"]:
                return jsonify(success=False, message="Niedozwolone pochodzenie żądania."), 403
            if not request.is_json:
                return jsonify(success=False, message="Wymagany format application/json."), 415
            if g.auth_session and not secrets.compare_digest(
                request.headers.get("X-CSRF-Token", ""), g.auth_session["csrf_token"]
            ):
                return jsonify(success=False, message="Nieprawidłowy token CSRF."), 403

    @app.after_request
    def prevent_auth_caching(response):
        if request.path.startswith(("/api/auth", "/api/profile", "/api/favorites", "/api/login", "/api/logout")):
            response.headers["Cache-Control"] = "no-store"
        return response


def revoke_session():
    token = request.cookies.get(COOKIE_NAME)
    if token:
        from database import delete_auth_session
        delete_auth_session(token_hash(token))


def establish_session(user):
    from database import store_auth_session
    revoke_session()
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    lifetime = current_app.config["AUTH_SESSION_HOURS"]
    store_auth_session(token_hash(token), user["id"], csrf,
                       datetime.now(timezone.utc) + timedelta(hours=lifetime))
    response = jsonify(success=True, user=user, csrf_token=csrf)
    response.set_cookie(COOKIE_NAME, token, httponly=True,
                        secure=current_app.config["SESSION_COOKIE_SECURE"],
                        samesite=current_app.config["SESSION_COOKIE_SAMESITE"],
                        max_age=lifetime * 3600, path="/")
    return response

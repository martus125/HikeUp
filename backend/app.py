import os

from flask import Flask
from flask_cors import CORS

from database import init_database
from routes.auth_routes import auth_bp
from routes.favorite_routes import favorites_bp
from routes.map_routes import map_bp
from routes.profile_routes import profile_bp


def create_app():
    app = Flask(__name__)
    
    from auth import initialize_auth
    origins = [value.strip() for value in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if value.strip()]
    if not origins or "*" in origins:
        raise ValueError("FRONTEND_ORIGINS must contain explicit frontend origins")
    app.config.update(
        FRONTEND_ORIGINS=origins,
        AUTH_SESSION_HOURS=int(os.getenv("AUTH_SESSION_HOURS", "24")),
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true",
        SESSION_COOKIE_SAMESITE=os.getenv("SESSION_COOKIE_SAMESITE", "Lax"),
    )
    if app.config["SESSION_COOKIE_SAMESITE"] not in {"Lax", "Strict", "None"}:
        raise ValueError("Invalid SESSION_COOKIE_SAMESITE")
    if app.config["SESSION_COOKIE_SAMESITE"] == "None" and not app.config["SESSION_COOKIE_SECURE"]:
        raise ValueError("SameSite=None requires Secure cookies")
    CORS(app, origins=origins, supports_credentials=True,
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         allow_headers=["Content-Type", "X-CSRF-Token"])
    initialize_auth(app)

    from validation import ValidationError

    @app.errorhandler(ValidationError)
    def invalid_input(error):
        from flask import jsonify
        return jsonify(success=False, message=str(error)), 400

    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    @app.errorhandler(413)
    def request_too_large(error):
        from flask import jsonify
        return jsonify(success=False, message="Przesłane dane są zbyt duże."), 413

    init_database()

    app.register_blueprint(auth_bp)
    app.register_blueprint(favorites_bp)
    app.register_blueprint(map_bp)
    app.register_blueprint(profile_bp)

    @app.route("/")
    def home():
        return "Backend HikeUp działa."

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

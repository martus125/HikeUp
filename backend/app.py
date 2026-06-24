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
    CORS(app)

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
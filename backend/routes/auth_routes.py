'''logowanie i rejestracja uzytkownika'''
from flask import Blueprint, jsonify, request, g
from auth import COOKIE_NAME, establish_session, login_required, revoke_session

from database import create_user, verify_user
from validation import text, email_address, password_value

auth_bp = Blueprint("auth", __name__, url_prefix="/api")


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    name = text(data.get("name"), "Imię")
    email = email_address(data.get("email"))
    password = password_value(data.get("password"), registration=True)

    result = create_user(name, email, password)
    if not result["success"]:
        return jsonify(result), 400

    return jsonify({"success": True, "message": "Konto zostało utworzone. Możesz się zalogować."})


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = email_address(data.get("email"))
    password = password_value(data.get("password"))

    result = verify_user(email, password)
    if not result["success"]:
        return jsonify(result), 401

    return establish_session(result["user"])


@auth_bp.route("/auth/me", methods=["GET"])
@login_required
def me():
    return jsonify(success=True, **g.auth_session)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    revoke_session()
    response = jsonify(success=True)
    response.delete_cookie(COOKIE_NAME, path="/")
    return response

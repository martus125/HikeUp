'''logowanie i rejestracja uzytkownika'''
from flask import Blueprint, jsonify, request

from database import create_user, verify_user

auth_bp = Blueprint("auth", __name__, url_prefix="/api")


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({"success": False, "message": "Uzupełnij wszystkie pola formularza."}), 400

    if len(password) < 6:
        return jsonify({"success": False, "message": "Hasło powinno mieć co najmniej 6 znaków."}), 400

    result = create_user(name, email, password)
    if not result["success"]:
        return jsonify(result), 400

    return jsonify({"success": True, "message": "Konto zostało utworzone. Możesz się zalogować."})


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"success": False, "message": "Podaj email i hasło."}), 400

    result = verify_user(email, password)
    if not result["success"]:
        return jsonify(result), 401

    return jsonify({"success": True, "message": "Zalogowano pomyślnie.", "user": result["user"]})

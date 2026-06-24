from flask import Blueprint, request, jsonify
from database import get_user_profile, update_user_profile

profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/profile/<int:user_id>", methods=["GET"])
def profile_get(user_id):
    profile = get_user_profile(user_id)
    return jsonify(profile)


@profile_bp.route("/profile/<int:user_id>", methods=["PUT"])
def profile_update(user_id):
    data = request.get_json() or {}

    height_cm = data.get("height_cm")
    experience_level = data.get("experience_level")
    route_preference = data.get("route_preference")

    result = update_user_profile(
        user_id,
        height_cm,
        experience_level,
        route_preference,
    )

    status_code = 200 if result.get("success") else 500
    return jsonify(result), status_code

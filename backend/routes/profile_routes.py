from auth import current_user_id, login_required
from flask import Blueprint, request, jsonify
from database import get_user_profile, update_user_profile
from validation import profile_data

profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/api/profile", methods=["GET"])
@login_required
def profile_get():
    user_id = current_user_id()
    profile = get_user_profile(user_id)
    return jsonify(profile)


@profile_bp.route("/api/profile", methods=["PUT"])
@login_required
def profile_update():
    user_id = current_user_id()
    data = request.get_json() or {}

    age_years, experience_level, route_preference, prefer_shelters = profile_data(data)

    result = update_user_profile(
        user_id,
        age_years,
        experience_level,
        route_preference,
        prefer_shelters,
    )

    status_code = 200 if result.get("success") else 500
    return jsonify(result), status_code

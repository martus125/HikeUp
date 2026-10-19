"""Authentication flow with an isolated session repository; no production DB."""
import importlib
from datetime import datetime, timezone
from unittest.mock import patch

import pytest


@pytest.fixture
def auth_app():
    import database
    with patch.object(database, "init_database"):
        module = importlib.import_module("app")
        app = module.create_app()
    app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False,
                      FRONTEND_ORIGINS=["http://localhost:5173"])
    sessions = {}
    user = {"id": 7, "name": "Tester", "email": "test@example.com", "experience_level": "beginner"}

    def store(key, uid, csrf, expires):
        sessions[key] = {"user": {**user, "id": uid}, "csrf_token": csrf, "expires": expires}

    def find(key):
        record = sessions.get(key)
        if record and record["expires"] > datetime.now(timezone.utc):
            return {"user": record["user"], "csrf_token": record["csrf_token"]}
        return None

    with patch.object(database, "store_auth_session", side_effect=store), \
         patch.object(database, "find_auth_session", side_effect=find), \
         patch.object(database, "delete_auth_session", side_effect=lambda key: sessions.pop(key, None)), \
         patch("routes.auth_routes.verify_user", return_value={"success": True, "user": user}):
        yield app, sessions


def sign_in(client):
    response = client.post("/api/login", json={"email": "test@example.com", "password": "password"})
    assert response.status_code == 200
    return response.get_json()["csrf_token"]


def test_session_cookie_restore_rotation_and_logout(auth_app):
    app, sessions = auth_app
    client = app.test_client()
    csrf = sign_in(client)
    cookie = client.get_cookie("hikeup_session")
    assert cookie.http_only
    assert cookie.value not in sessions  # DB only stores a hash.
    assert client.get("/api/auth/me").get_json()["user"]["id"] == 7
    assert client.get("/api/auth/me").headers["Cache-Control"] == "no-store"
    assert client.post("/api/logout", json={}).status_code == 403
    response = client.post("/api/login", json={"email": "a", "password": "b"}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert client.get_cookie("hikeup_session").value != cookie.value
    assert len(sessions) == 1
    csrf = response.get_json()["csrf_token"]
    assert client.post("/api/logout", json={}, headers={"X-CSRF-Token": csrf}).status_code == 200
    assert not sessions
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("path,method", [("/api/profile", "get"), ("/api/profile", "put"),
                                         ("/api/favorites", "get"), ("/api/favorites", "post")])
def test_guest_cannot_access_account(auth_app, path, method):
    client = auth_app[0].test_client()
    assert getattr(client, method)(path, json={"user_id": 99}).status_code == 401


def test_profile_and_favorites_always_use_session_owner(auth_app):
    client = auth_app[0].test_client()
    csrf = sign_in(client)
    headers = {"X-CSRF-Token": csrf}
    with patch("routes.profile_routes.get_user_profile", return_value={"user_id": 7}) as get_profile, \
         patch("routes.profile_routes.update_user_profile", return_value={"success": True}) as update, \
         patch("routes.favorite_routes.add_favorite_route", return_value={"success": True}) as add, \
         patch("routes.favorite_routes.get_favorite_routes", return_value={"success": True, "favorites": []}) as favorites:
        assert client.get("/api/profile?user_id=99").status_code == 200
        get_profile.assert_called_once_with(7)
        assert client.put("/api/profile", json={"user_id": 99}, headers=headers).status_code == 200
        assert update.call_args.args[0] == 7
        assert client.post("/api/favorites", json={"user_id": 99, "route_name": "Test"}, headers=headers).status_code == 201
        assert add.call_args.kwargs["user_id"] == 7
        assert client.get("/api/favorites?user_id=99").status_code == 200
        favorites.assert_called_once_with(7)
    assert client.get("/profile/99").status_code == 404
    assert client.get("/api/favorites/99").status_code == 404


def test_csrf_origin_and_content_type(auth_app):
    client = auth_app[0].test_client()
    assert client.post("/api/login", data={"email": "x"}).status_code == 415
    assert client.post("/api/login", json=[], headers={"Origin": "http://localhost:5173"}).status_code == 400
    assert client.post("/api/login", json={}, headers={"Origin": "https://evil.example"}).status_code == 403
    csrf = sign_in(client)
    assert client.put("/api/profile", json={}, headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert client.post("/api/logout", json={}, headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example"}).status_code == 403
    preflight = client.options("/api/profile", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "PUT"})
    assert preflight.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert preflight.headers["Access-Control-Allow-Credentials"] == "true"


def test_expired_and_forged_session(auth_app):
    from datetime import timedelta
    client = auth_app[0].test_client()
    sign_in(client)
    for record in auth_app[1].values():
        record["expires"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert client.get("/api/auth/me").status_code == 401
    client.set_cookie("hikeup_session", "x" * 43)
    assert client.get("/api/auth/me").status_code == 401


def test_failed_login_does_not_create_session(auth_app):
    client = auth_app[0].test_client()
    with patch("routes.auth_routes.verify_user", return_value={"success": False, "message": "Invalid"}):
        assert client.post("/api/login", json={"email": "x", "password": "x"}).status_code == 401
    assert not auth_app[1]


def test_route_ignores_forged_user_id(auth_app):
    from services.routing_context import build_routing_context
    client = auth_app[0].test_client()
    nodes = [{"id": "A", "lat": 49.0, "lng": 19.0, "elevation": 100},
             {"id": "B", "lat": 49.01, "lng": 19.01, "elevation": 110}]
    points = [{**node, "type": "peak", "name": node["id"], "nearest_routing_node_id": node["id"]} for node in nodes]
    edges = [{"from": "A", "to": "B", "distance_km": 2, "difficulty": 1,
              "elevation_gain_m": 10, "elevation_loss_m": 0, "slope_percent": 1}]
    context = build_routing_context(nodes, edges, points)
    import database
    with patch("routes.map_routes.load_routing_context", return_value=context), \
         patch.object(database, "get_user_profile", return_value={"experience_level": "expert"}) as profile:
        response = client.post("/api/route", json={"start": "A", "end": "B", "user_id": 99})
        assert response.status_code == 200
        profile.assert_not_called()
        custom = next(r for r in response.get_json()["routes"] if r["algorithm"] == "custom_hikeup")
        assert custom["recommendation_status"] == "unpersonalized"
        csrf = sign_in(client)
        response = client.post("/api/route", json={"start": "A", "end": "B", "user_id": 99}, headers={"X-CSRF-Token": csrf})
        assert response.status_code == 200
        profile.assert_called_once_with(7)


def test_logout_revokes_cookie_copied_to_another_client(auth_app):
    app, _ = auth_app
    owner = app.test_client()
    csrf = sign_in(owner)
    copied = app.test_client()
    copied.set_cookie("hikeup_session", owner.get_cookie("hikeup_session").value)
    assert copied.get("/api/auth/me").status_code == 200
    owner.post("/api/logout", json={}, headers={"X-CSRF-Token": csrf})
    assert copied.get("/api/auth/me").status_code == 401

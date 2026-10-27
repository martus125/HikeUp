"""HTTP validation and account isolation against an in-memory repository."""
from copy import deepcopy
from unittest.mock import patch, MagicMock

import pytest

from test_auth import auth_app, sign_in
from services.routing_context import build_routing_context


@pytest.fixture
def small_context():
    nodes = [dict(id=key, lat=49 + index * .001, lng=19, elevation=100)
             for index, key in enumerate(("A", "B", "C"))]
    edges = [dict(**{"from": "A", "to": "B"}, distance_km=.2,
                  difficulty=1, elevation_gain_m=0, elevation_loss_m=0)]
    return build_routing_context(nodes, edges, nodes)


def favorite():
    return dict(route_name="A → B", start_point_name="A", end_point_name="B",
                distance_km=.2, time_min=2.4, elevation_gain_m=0,
                criterion="distance", path=dict(start_id="A", end_id="B", node_ids=["A", "B"]))


@pytest.mark.parametrize("field,value", [
    ("age_years", -1), ("age_years", 0), ("age_years", 121),
    ("age_years", True), ("age_years", 20.5), ("age_years", "25"),
    ("age_years", []), ("experience_level", "wizard"),
    ("experience_level", []), ("route_preference", {}),
    ("route_preference", "unknown"), ("prefer_shelters", "false"),
    ("prefer_shelters", 1), ("prefer_shelters", None),
])
def test_invalid_profile_never_reaches_database(auth_app, field, value):
    client = auth_app[0].test_client()
    csrf = sign_in(client)
    with patch("routes.profile_routes.update_user_profile") as save:
        response = client.put("/api/profile", json={field: value}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 400
    assert response.json["success"] is False
    assert response.json["message"]
    save.assert_not_called()


@pytest.mark.parametrize("age", [None, "", 1, 25, 120])
def test_valid_profile_is_normalized(auth_app, age):
    client = auth_app[0].test_client()
    csrf = sign_in(client)
    with patch("routes.profile_routes.update_user_profile", return_value={"success": True}) as save:
        response = client.put("/api/profile", json=dict(age_years=age, experience_level="expert",
            route_preference="najkrótsza", prefer_shelters=True), headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    save.assert_called_once_with(7, None if age == "" else age, "expert", "najkrótsza", True)


@pytest.mark.parametrize("payload", [
    {}, {"start": [], "end": "B"}, {"start": {}, "end": "B"},
    {"start": True, "end": "B"}, {"start": "A", "end": ["B"]},
    {"start": "A", "end": "A"}, {"start": "A", "end": "B", "criterion": []},
    {"start": "A", "end": "B", "criterion": {}},
    {"start": "A", "end": "B", "criterion": False},
    {"start": "A", "end": "B", "criterion": "unknown"},
    {"example_id": []}, {"example_id": "unknown"},
])
def test_invalid_route_is_400_before_loading_map(auth_app, payload):
    with patch("routes.map_routes.load_routing_context") as load:
        response = auth_app[0].test_client().post("/api/route", json=payload)
    assert response.status_code == 400
    load.assert_not_called()


def test_unknown_points_and_disconnected_route(auth_app, small_context):
    client = auth_app[0].test_client()
    with patch("routes.map_routes.load_routing_context", return_value=small_context):
        for end in ("unknown", "C"):
            response = client.post("/api/route", json=dict(start="A", end=end, criterion="distance"))
            assert response.status_code == 404
            assert response.json["success"] is False


@pytest.mark.parametrize("field,value", [
    ("route_name", " "), ("route_name", "x" * 256), ("route_name", []),
    ("start_point_name", None), ("distance_km", -1), ("distance_km", True),
    ("distance_km", "1"), ("distance_km", float("inf")),
    ("distance_km", 10 ** 400), ("distance_km", float("nan")),
    ("time_min", None), ("time_min", -1), ("elevation_gain_m", -1),
    ("criterion", []), ("criterion", "unknown"), ("path", "A,B"),
    ("path", dict(start_id="A", end_id="B", node_ids=["A"])),
    ("path", dict(start_id="A", end_id="B", node_ids=["A", {}])),
])
def test_invalid_favorite_never_reaches_database(auth_app, field, value):
    client = auth_app[0].test_client()
    csrf = sign_in(client)
    data = favorite()
    data[field] = value
    with patch("routes.favorite_routes.add_favorite_route") as save:
        response = client.post("/api/favorites", json=data, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 400
    save.assert_not_called()


def test_favorites_validate_graph_and_persist_for_session_owner(auth_app, small_context):
    client = auth_app[0].test_client()
    csrf = sign_in(client)
    headers = {"X-CSRF-Token": csrf}
    with patch("routes.favorite_routes.load_routing_context", return_value=small_context), \
         patch("routes.favorite_routes.add_favorite_route", return_value={"success": True, "favorite_id": 12}) as save:
        data = favorite()
        data["user_id"] = 999
        assert client.post("/api/favorites", json=data, headers=headers).status_code == 201
        assert save.call_args.kwargs["user_id"] == 7
        for path in [dict(start_id="unknown", end_id="B", node_ids=["A", "B"]),
                     dict(start_id="A", end_id="B", node_ids=["A", "unknown", "B"]),
                     dict(start_id="A", end_id="B", node_ids=["B", "A"]),
                     dict(start_id="A", end_id="C", node_ids=["A", "C"])]:
            bad = deepcopy(data)
            bad["path"] = path
            assert client.post("/api/favorites", json=bad, headers=headers).status_code == 400
        assert save.call_count == 1


@pytest.mark.parametrize("path", ["/api/login", "/api/register"])
@pytest.mark.parametrize("email", [None, [], "wrong", "a@b", "a b@example.com", "a@@example.com", "x" * 256])
def test_invalid_email_rejected(auth_app, path, email):
    with patch("routes.auth_routes.verify_user") as verify, patch("routes.auth_routes.create_user") as create:
        response = auth_app[0].test_client().post(path, json=dict(name="Tester", email=email, password="password"))
    assert response.status_code == 400
    verify.assert_not_called()
    create.assert_not_called()


def test_registration_normalizes_email_without_changing_password(auth_app):
    with patch("routes.auth_routes.create_user", return_value={"success": True}) as create:
        response = auth_app[0].test_client().post("/api/register", json=dict(
            name=" Tester ", email=" TEST@Example.com ", password=" password "))
    assert response.status_code == 200
    create.assert_called_once_with("Tester", "test@example.com", " password ")


@pytest.mark.parametrize("password", [None, [], "", "short", "x" * 1025])
def test_registration_rejects_invalid_password(auth_app, password):
    with patch("routes.auth_routes.create_user") as create:
        response = auth_app[0].test_client().post("/api/register", json=dict(
            name="Tester", email="test@example.com", password=password))
    assert response.status_code == 400
    create.assert_not_called()


def test_delete_uses_owner_and_hides_foreign_favorite(auth_app):
    client = auth_app[0].test_client()
    assert client.delete("/api/favorites/12", json={}).status_code == 401
    csrf = sign_in(client)
    with patch("routes.favorite_routes.delete_favorite_route", return_value=False) as delete:
        response = client.delete("/api/favorites/12?user_id=999", json={"user_id": 999}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 404
    delete.assert_called_once_with(7, 12)


def test_database_delete_filters_by_both_owner_and_id():
    import database
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.rowcount = 0
    with patch.object(database, "get_connection", return_value=connection):
        assert database.delete_favorite_route(7, 12) is False
    sql, params = cursor.execute.call_args.args
    assert "WHERE id = %s AND user_id = %s" in sql
    assert params == (12, 7)


def test_malformed_json_is_readable_400(auth_app):
    response = auth_app[0].test_client().post("/api/login", data='{', content_type="application/json")
    assert response.status_code == 400
    assert response.json["message"]


def test_oversized_body_returns_json(auth_app):
    app = auth_app[0]
    app.config["MAX_CONTENT_LENGTH"] = 100
    response = app.test_client().post("/api/register", json=dict(name="x" * 101))
    assert response.status_code == 413
    assert response.json["success"] is False

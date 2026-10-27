"""Validation at the HTTP boundary, before database writes or graph lookups."""
import math
import re

from algorithms.weights import validate_criterion
from models.experience_config import EXPERIENCE_LIMITS, ROUTE_PREFERENCE_CRITERIA


class ValidationError(ValueError):
    pass


def text(value, field, maximum=255):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field}: wymagany niepusty tekst (maks. {maximum} znaków).")
    return value.strip()


def email_address(value):
    value = text(value, "Email").lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValidationError("Podaj poprawny adres email.")
    return value


def password_value(value, registration=False):
    if not isinstance(value, str) or not value.strip() or len(value) > 1024:
        raise ValidationError("Hasło: wymagany tekst o długości do 1024 znaków.")
    if registration and len(value) < 6:
        raise ValidationError("Hasło powinno mieć co najmniej 6 znaków.")
    return value


def profile_data(data):
    age = data.get("age_years")
    if age == "" or age is None:
        age = None
    elif type(age) is not int or not 1 <= age <= 120:
        raise ValidationError("Wiek musi być liczbą całkowitą od 1 do 120.")
    level = data.get("experience_level")
    preference = data.get("route_preference")
    if level is None:
        level = ""
    if preference is None:
        preference = ""
    if not isinstance(level, str) or (level and level not in EXPERIENCE_LIMITS):
        raise ValidationError("Nieprawidłowy poziom doświadczenia.")
    if not isinstance(preference, str) or (preference and preference not in ROUTE_PREFERENCE_CRITERIA):
        raise ValidationError("Nieprawidłowa preferencja trasy.")
    shelters = data.get("prefer_shelters", False)
    if type(shelters) is not bool:
        raise ValidationError("Preferencja schronisk musi mieć wartość true lub false.")
    return age, level, preference, shelters


def route_input(data):
    """Examples are resolved separately; identity always comes from the session."""
    if "example_id" in data:
        text(data["example_id"], "Identyfikator przykładu")
        return
    start = text(data.get("start"), "Punkt początkowy")
    end = text(data.get("end"), "Punkt końcowy")
    if start == end:
        raise ValidationError("Punkt początkowy i końcowy nie mogą być takie same.")
    if "criterion" in data and data["criterion"] is not None:
        validate_criterion(data["criterion"])


def favorite_data(data):
    result = {key: text(data.get(key), label) for key, label in (
        ("route_name", "Nazwa trasy"), ("start_point_name", "Nazwa startu"),
        ("end_point_name", "Nazwa celu"))}
    for key in ("distance_km", "time_min", "elevation_gain_m"):
        value = data.get(key)
        if (type(value) not in (int, float) or not 0 <= value <= 1_000_000
                or not math.isfinite(value)):
            raise ValidationError(f"{key}: wymagana nieujemna liczba do 1000000.")
        result[key] = value
    try:
        result["criterion"] = validate_criterion(data.get("criterion"))
    except ValueError as error:
        raise ValidationError(str(error)) from error
    path = data.get("path")
    if not isinstance(path, dict):
        raise ValidationError("Ścieżka musi być obiektem zawierającym start_id, end_id i node_ids.")
    start = text(path.get("start_id"), "Identyfikator startu")
    end = text(path.get("end_id"), "Identyfikator celu")
    if start == end:
        raise ValidationError("Start i cel muszą być różne.")
    ids = path.get("node_ids")
    if not isinstance(ids, list) or not 2 <= len(ids) <= 200_000:
        raise ValidationError("Ścieżka musi zawierać od 2 do 200000 identyfikatorów węzłów.")
    ids = [text(node, "Identyfikator węzła") for node in ids]
    result["path"] = {"start_id": start, "end_id": end, "node_ids": ids}
    return result


def saved_path_exists(path, context):
    from services.map_service import resolve_routing_node

    start = context.points_by_id.get(path["start_id"])
    end = context.points_by_id.get(path["end_id"])
    ids = path["node_ids"]
    if start is None or end is None or any(node not in context.node_ids for node in ids):
        raise ValidationError("Ścieżka zawiera nieistniejące punkty lub węzły.")
    if (resolve_routing_node(start, context.nodes, context.node_ids) != ids[0]
            or resolve_routing_node(end, context.nodes, context.node_ids) != ids[-1]):
        raise ValidationError("Końce ścieżki nie odpowiadają wybranym punktom.")
    if any(not any(item["node"] == end for item in context.graph.get(start, []))
           for start, end in zip(ids, ids[1:])):
        raise ValidationError("Ścieżka zawiera niepołączone węzły.")

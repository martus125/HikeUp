"""Funkcje kosztu używane podczas wyznaczania tras."""

import math

DEFAULT_FLAT_SPEED_KMH = 5.0
DEFAULT_ASCENT_RATE_M_PER_HOUR = 600.0
MAX_TRAIL_DIFFICULTY = 6.0
MAX_REASONABLE_SLOPE_PERCENT = 100.0
MIN_EDGE_DISTANCE_KM = 1e-9
VALID_CRITERIA = frozenset({"time", "distance", "elevation", "difficulty"})


def as_number(value, default=0.0):
    """Bezpiecznie zamienia wartość z danych mapy na liczbę."""
    try:
        if value is None:
            return default

        if isinstance(value, str) and value.strip().lower() in {
            "",
            "unknown",
            "none",
            "null",
        }:
            return default

        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def validate_criterion(criterion):
    """Zwraca kryterium albo zgłasza czytelny błąd dla nieznanej wartości."""
    if criterion not in VALID_CRITERIA:
        supported = ", ".join(sorted(VALID_CRITERIA))
        raise ValueError(
            f"Nieznane kryterium trasy: {criterion!r}. "
            f"Obsługiwane wartości: {supported}."
        )

    return criterion


def calculate_slope_percent(elevation_difference_m, distance_km):
    """Liczy bezwzględne średnie nachylenie i chroni przed zerowym dystansem."""
    distance = as_number(distance_km, None)
    elevation_difference = as_number(elevation_difference_m, None)

    if (
        distance is None
        or elevation_difference is None
        or distance <= MIN_EDGE_DISTANCE_KM
    ):
        return None

    return abs(elevation_difference) / (distance * 1000.0) * 100.0


def get_slope_percent(edge, default=0.0):
    """Zwraca zapisane nachylenie lub bezpiecznie wylicza je z danych krawędzi."""
    stored_slope = as_number(edge.get("slope_percent"), None)

    if stored_slope is not None:
        return abs(stored_slope)

    elevation_change = as_number(edge.get("elevation_change_m"), None)

    if elevation_change is None:
        elevation_gain = as_number(edge.get("elevation_gain_m"), None)
        elevation_loss = as_number(edge.get("elevation_loss_m"), None)

        if elevation_gain is not None or elevation_loss is not None:
            elevation_change = (elevation_gain or 0.0) - (elevation_loss or 0.0)

    calculated = calculate_slope_percent(
        elevation_change,
        edge.get("distance_km"),
    )
    return default if calculated is None else calculated


def estimate_hiking_time_minutes(
    edge,
    ascent_rate_m_per_hour=DEFAULT_ASCENT_RATE_M_PER_HOUR,
    descent_effort_factor=0.0,
):
    """
    Szacuje czas przejścia regułą zbliżoną do Naismitha.

    Czas składa się z marszu po płaskim oraz wysiłku związanego z podejściem.
    Dla algorytmu spersonalizowanego można też doliczyć część wysiłku zejścia.
    """
    distance = max(0.0, as_number(edge.get("distance_km"), 0))
    elevation_gain = max(
        0.0,
        as_number(edge.get("elevation_gain_m"), 0),
    )
    elevation_loss = max(
        0.0,
        as_number(edge.get("elevation_loss_m"), 0),
    )
    ascent_rate = max(
        1.0,
        as_number(
            ascent_rate_m_per_hour,
            DEFAULT_ASCENT_RATE_M_PER_HOUR,
        ),
    )

    flat_time = distance / DEFAULT_FLAT_SPEED_KMH * 60
    elevation_effort = (
        elevation_gain
        + elevation_loss * max(0.0, descent_effort_factor)
    ) / ascent_rate * 60

    return flat_time + elevation_effort


def edge_weight(edge, criterion="time"):
    """Zwraca porównywalny koszt jednej krawędzi grafu."""
    validate_criterion(criterion)

    distance = max(0.0, as_number(edge.get("distance_km"), 0))
    time = estimate_hiking_time_minutes(edge)
    elevation = max(
        0.0,
        as_number(edge.get("elevation_gain_m"), 0),
    )
    difficulty = clamp(
        as_number(edge.get("difficulty"), 1),
        1.0,
        MAX_TRAIL_DIFFICULTY,
    )

    if criterion == "distance":
        return distance

    if criterion == "time":
        return time

    if criterion == "elevation":
        # Dystans jest wyłącznie deterministycznym kosztem pomocniczym. Zapobiega
        # wybieraniu bardzo długich objazdów o identycznym przewyższeniu.
        return elevation + distance * 10

    if criterion == "difficulty":
        # Trudność jest ważona długością. Dzięki temu wynik nie zależy od
        # liczby technicznych węzłów OSM, na które podzielono ten sam szlak.
        return (
            difficulty * distance * 100
            + elevation
            + time
            + distance * 10
        )

    raise AssertionError("Kryterium zostało zweryfikowane powyżej.")


def custom_hikeup_edge_weight(
    edge,
    criterion="time",
    user_limits=None,
    shelter_nearby=False,
):
    """
    Profilowy koszt odcinka dla algorytmu Custom HikeUp.

    ``base_cost`` pochodzi dokładnie ze wspólnego ``edge_weight``. Pozostałe
    składniki są proporcjonalne do tej wartości, więc nie mieszamy kilometrów,
    minut i punktów trudności. Współczynniki profilu są centralnie zdefiniowane
    w ``experience_config.py``. Nachylenie jest ograniczane wyłącznie na potrzeby
    decyzji algorytmu; surowa wartość nadal trafia do diagnostyki trasy.
    """
    user_limits = user_limits or {}
    validate_criterion(criterion)

    distance = max(0.0, as_number(edge.get("distance_km"), 0))
    difficulty = clamp(
        as_number(edge.get("difficulty"), 1),
        1.0,
        MAX_TRAIL_DIFFICULTY,
    )
    raw_slope = get_slope_percent(edge)

    max_slope = max(
        5.0,
        as_number(
            user_limits.get("max_slope_percent"),
            25,
        ),
    )
    max_difficulty = max(
        1.0,
        as_number(
            user_limits.get("max_difficulty"),
            4,
        ),
    )
    ascent_rate = max(
        1.0,
        as_number(
            user_limits.get("preferred_elevation_per_hour"),
            250,
        ),
    )
    reasonable_slope = max(
        max_slope,
        as_number(
            user_limits.get("max_reasonable_slope_percent"),
            MAX_REASONABLE_SLOPE_PERCENT,
        ),
    )

    slope = min(raw_slope, reasonable_slope)
    estimated_time = estimate_hiking_time_minutes(
        edge,
        ascent_rate_m_per_hour=ascent_rate,
        descent_effort_factor=0.3,
    )
    flat_time = distance / DEFAULT_FLAT_SPEED_KMH * 60
    elevation_effort = max(0.0, estimated_time - flat_time)

    slope_excess = clamp(
        (slope - max_slope) / max_slope,
        0.0,
        1.5,
    )
    difficulty_excess = clamp(
        (difficulty - max_difficulty) / max_difficulty,
        0.0,
        1.0,
    )

    slope_factor = max(
        0.0,
        as_number(user_limits.get("slope_penalty_factor"), 0.8),
    )
    difficulty_factor = max(
        0.0,
        as_number(user_limits.get("difficulty_penalty_factor"), 0.6),
    )
    elevation_factor = max(
        0.0,
        as_number(user_limits.get("elevation_penalty_factor"), 0.4),
    )
    excess_factor = max(
        0.0,
        as_number(user_limits.get("limit_excess_penalty_factor"), 1.0),
    )
    shelter_bonus_factor = clamp(
        as_number(user_limits.get("shelter_bonus_factor"), 0.0),
        0.0,
        0.1,
    )

    base_cost = edge_weight(edge, criterion)
    slope_load = (slope / max_slope) ** 2
    difficulty_load = (difficulty / max_difficulty) ** 2
    elevation_load = (
        elevation_effort / max(flat_time + elevation_effort, 1.0)
    )

    slope_penalty = base_cost * slope_factor * slope_load
    difficulty_penalty = base_cost * difficulty_factor * difficulty_load
    elevation_penalty = base_cost * elevation_factor * elevation_load
    profile_penalty = base_cost * excess_factor * (
        slope_excess ** 2 + difficulty_excess ** 2
    )
    shelter_bonus = (
        base_cost * shelter_bonus_factor
        if shelter_nearby
        else 0.0
    )

    final_weight = (
        base_cost
        + slope_penalty
        + difficulty_penalty
        + elevation_penalty
        + profile_penalty
        - shelter_bonus
    )

    # Koszt pozostaje dodatni, co jest wymagane przez przeszukiwanie Dijkstry.
    return max(base_cost * 0.01, final_weight)

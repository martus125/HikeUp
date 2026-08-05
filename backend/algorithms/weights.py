"""Funkcje kosztu używane podczas wyznaczania tras."""

DEFAULT_FLAT_SPEED_KMH = 5.0
DEFAULT_ASCENT_RATE_M_PER_HOUR = 600.0
MAX_TRAIL_DIFFICULTY = 6.0
MAX_REASONABLE_SLOPE_PERCENT = 100.0


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

        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


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

    return time


def custom_hikeup_edge_weight(
    edge,
    criterion="time",
    user_limits=None,
):
    """
    Znormalizowany koszt odcinka dla algorytmu Custom HikeUp.

    Wszystkie kary są proporcjonalne do długości odcinka. Nachylenie jest
    ograniczane do fizycznie użytecznego zakresu, aby pojedynczy artefakt
    modelu wysokościowego nie wymuszał wielokilometrowego objazdu.
    """
    user_limits = user_limits or {}

    distance = max(0.0, as_number(edge.get("distance_km"), 0))
    difficulty = clamp(
        as_number(edge.get("difficulty"), 1),
        1.0,
        MAX_TRAIL_DIFFICULTY,
    )
    raw_slope = abs(as_number(edge.get("slope_percent"), 0))

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

    difficulty_exposure = (
        distance
        * 20
        * (difficulty / MAX_TRAIL_DIFFICULTY) ** 2
    )
    slope_penalty = distance * 30 * slope_excess ** 2
    difficulty_penalty = (
        distance * 60 * difficulty_excess ** 2
    )
    safety_cost = (
        difficulty_exposure
        + slope_penalty
        + difficulty_penalty
    )

    if criterion == "distance":
        return flat_time + elevation_effort * 0.25 + safety_cost * 0.5

    if criterion == "time":
        return estimated_time + safety_cost * 0.5

    if criterion == "elevation":
        return (
            flat_time * 0.35
            + elevation_effort * 1.2
            + safety_cost * 0.75
        )

    if criterion == "difficulty":
        return estimated_time * 0.5 + safety_cost * 2.0

    return estimated_time + safety_cost

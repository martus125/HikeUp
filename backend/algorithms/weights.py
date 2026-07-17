'''koszt przejścia jednego odcinka szlaku'''
def as_number(value, default=0.0):
    """
    Zamienia wartość z danych mapy na liczbę.

    Jest to potrzebne, ponieważ niektóre pola mogą być puste,
    mieć wartość None albo tekst "unknown".
    """
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


def edge_weight(edge, criterion="time"):
    """
    Funkcja zwraca koszt przejścia daną krawędzią grafu
    w zależności od wybranego kryterium.

    time       - trasa najszybsza
    distance   - trasa najkrótsza
    elevation  - trasa z uwzględnieniem przewyższenia
    difficulty - trasa z uwzględnieniem trudności
    """
    distance = as_number(edge.get("distance_km"), 0)
    time = as_number(edge.get("time_min"), 0)
    elevation = as_number(edge.get("elevation_gain_m"), 0)
    difficulty = as_number(edge.get("difficulty"), 1)

    if criterion == "distance":
        return distance

    if criterion == "time":
        return time

    if criterion == "elevation":
        return elevation + distance * 10

    if criterion == "difficulty":
        return difficulty * 100 + elevation + time + distance * 10

    return time

def custom_hikeup_edge_weight(
    edge,
    criterion="time",
    user_profile=None,
):
    """
    Oblicza koszt przejścia odcinka dla algorytmu Custom HikeUp.

    Oprócz podstawowych parametrów trasy uwzględnia:
    - profil użytkownika,
    - maksymalne zalecane nachylenie,
    - maksymalną zalecaną trudność.
    """
    distance = as_number(edge.get("distance_km"), 0)
    time = as_number(edge.get("time_min"), 0)
    elevation = as_number(edge.get("elevation_gain_m"), 0)
    difficulty = as_number(edge.get("difficulty"), 1)
    slope = as_number(edge.get("slope_percent"), 0)

    # Domyślne ograniczenia dla dorosłego użytkownika
    slope_limit = 35
    difficulty_limit = 7

    if user_profile:
        slope_limit = as_number(
            user_profile.get("slope_limit"),
            slope_limit,
        )
        difficulty_limit = as_number(
            user_profile.get("max_difficulty"),
            difficulty_limit,
        )

    # Kara za nachylenie zbliżające się do limitu
    if slope > slope_limit:
        slope_penalty = (slope - slope_limit) ** 2.5 * 10
    elif slope > slope_limit - 10:
        slope_penalty = (
            slope - slope_limit + 10
        ) ** 1.5 * 3
    else:
        slope_penalty = 0

    # Kara za trudność przekraczającą możliwości profilu
    if difficulty > difficulty_limit:
        difficulty_penalty = (
            difficulty - difficulty_limit
        ) ** 2 * 100
    else:
        difficulty_penalty = 0

    if criterion == "distance":
        return (
            distance * 20
            + time * 0.4
            + elevation * 0.04
            + difficulty * 25
            + slope_penalty * 5
            + difficulty_penalty
        )

    if criterion == "time":
        return (
            time
            + distance * 5
            + elevation * 0.05
            + difficulty * 30
            + slope_penalty * 6
            + difficulty_penalty
        )

    if criterion == "elevation":
        return (
            elevation * 0.12
            + time * 0.8
            + distance * 8
            + difficulty * 35
            + slope_penalty * 8
            + difficulty_penalty
        )

    if criterion == "difficulty":
        return (
            difficulty * 100
            + elevation * 0.08
            + time * 0.6
            + distance * 8
            + slope_penalty * 10
            + difficulty_penalty
        )

    # Wariant domyślny: zbalansowany koszt trasy
    return (
        time
        + distance * 8
        + elevation * 0.06
        + difficulty * 50
        + slope_penalty * 8
        + difficulty_penalty
    )
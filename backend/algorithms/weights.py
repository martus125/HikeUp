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
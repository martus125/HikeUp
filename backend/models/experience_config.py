"""
Mapowanie poziomów doświadczenia na limity tras.
Każdy poziom ma inne ograniczenia dotyczące stromości, trudności i przewyższenia.

Współczynniki kar są bezwymiarowe i skalują koszt bazowy krawędzi. Ich relacje
opisują konserwatywność profili (beginner/senior > intermediate > expert), a nie
wynik eksperymentu. Wartości są celowo zebrane tutaj, aby późniejszy benchmark
mógł je jawnie kalibrować bez zmiany implementacji algorytmu.
"""

PROFILE_MATCH_WEIGHTS = {
    "slope": 30.0,
    "difficulty": 25.0,
    "elevation": 25.0,
    "detour": 10.0,
    "shelters": 10.0,
}

EXPERIENCE_LIMITS = {
    "beginner": {
        "name": "Początkujący",
        "max_slope_percent": 15,           # Preferowany maksymalny % nachylenia
        "absolute_max_slope_percent": 45,  # Twarda granica rekomendacji
        "max_difficulty": 2,                # Skala SAC 1-6
        "max_elevation_gain_m": 300,        # Max przewyższenie w górę na trasę
        "max_consecutive_steep": 500,       # Max długość stromego fragmentu (m)
        "preferred_elevation_per_hour": 150, # Idealne tempo (m/h)
        "max_detour_ratio": 1.30,
        "max_acceptable_detour_ratio": 1.50,
        "alternative_destination_max_route_ratio": 1.35,
        "max_reasonable_slope_percent": 100,
        "slope_penalty_factor": 1.50,
        "difficulty_penalty_factor": 1.20,
        "elevation_penalty_factor": 0.80,
        "limit_excess_penalty_factor": 2.00,
        "shelter_preference_bonus_factor": 0.08,
        "shelter_preference_max_extra_ratio": 1.10,
    },
    "intermediate": {
        "name": "Średniozaawansowany",
        "max_slope_percent": 25,
        "absolute_max_slope_percent": 70,
        "max_difficulty": 4,
        "max_elevation_gain_m": 700,
        "max_consecutive_steep": 1000,
        "preferred_elevation_per_hour": 250,
        "max_detour_ratio": 1.35,
        "max_acceptable_detour_ratio": 1.50,
        "alternative_destination_max_route_ratio": 1.35,
        "max_reasonable_slope_percent": 100,
        "slope_penalty_factor": 0.80,
        "difficulty_penalty_factor": 0.60,
        "elevation_penalty_factor": 0.40,
        "limit_excess_penalty_factor": 1.00,
        "shelter_preference_bonus_factor": 0.07,
        "shelter_preference_max_extra_ratio": 1.10,
    },
    "advanced": {
        "name": "Zaawansowany",
        "max_slope_percent": 40,
        "absolute_max_slope_percent": 90,
        "max_difficulty": 6,
        "max_elevation_gain_m": 1500,
        "max_consecutive_steep": 2000,
        "preferred_elevation_per_hour": 400,
        "max_detour_ratio": 1.35,
        "max_acceptable_detour_ratio": 1.45,
        "alternative_destination_max_route_ratio": 1.35,
        "max_reasonable_slope_percent": 100,
        "slope_penalty_factor": 0.35,
        "difficulty_penalty_factor": 0.25,
        "elevation_penalty_factor": 0.20,
        "limit_excess_penalty_factor": 0.40,
        "shelter_preference_bonus_factor": 0.06,
        "shelter_preference_max_extra_ratio": 1.10,
    },
    "expert": {
        "name": "Ekspert",
        "max_slope_percent": 50,
        "absolute_max_slope_percent": 100,
        "max_difficulty": 6,
        "max_elevation_gain_m": 2500,
        "max_consecutive_steep": 3000,
        "preferred_elevation_per_hour": 500,
        "max_detour_ratio": 1.30,
        "max_acceptable_detour_ratio": 1.40,
        "alternative_destination_max_route_ratio": 1.35,
        "max_reasonable_slope_percent": 100,
        "slope_penalty_factor": 0.10,
        "difficulty_penalty_factor": 0.08,
        "elevation_penalty_factor": 0.05,
        "limit_excess_penalty_factor": 0.15,
        "shelter_preference_bonus_factor": 0.05,
        "shelter_preference_max_extra_ratio": 1.10,
    },
    "senior": {
        "name": "Senior",
        "max_slope_percent": 10,            # ← Bardzo małe nachylenie
        "absolute_max_slope_percent": 35,
        "max_difficulty": 2,
        "max_elevation_gain_m": 200,
        "max_consecutive_steep": 300,       # ← Krótkie strome fragmenty
        "preferred_elevation_per_hour": 100,
        "max_detour_ratio": 1.20,
        # Preferujemy mały objazd, ale dopuszczamy dłuższy wariant, jeśli
        # rzeczywiście usuwa naruszenia bezpieczeństwa. Powyżej 60% trasa
        # jest uznawana za zbyt odległą od pierwotnego celu.
        "max_acceptable_detour_ratio": 1.60,
        "alternative_destination_max_route_ratio": 1.35,
        "max_reasonable_slope_percent": 100,
        "slope_penalty_factor": 2.00,
        "difficulty_penalty_factor": 1.50,
        "elevation_penalty_factor": 1.00,
        "limit_excess_penalty_factor": 2.50,
        "shelter_preference_bonus_factor": 0.09,
        "shelter_preference_max_extra_ratio": 1.10,
    }
}


def get_limits(experience_level):
    """
    Pobierz limity dla danego poziomu doświadczenia.
    
    Args:
        experience_level: str - jeden z kluczy EXPERIENCE_LIMITS
    
    Returns:
        dict - limity dla danego poziomu (lub intermediate jeśli nie znaleziony)
    """
    resolved_level = (
        experience_level
        if experience_level in EXPERIENCE_LIMITS
        else "intermediate"
    )
    limits = dict(EXPERIENCE_LIMITS[resolved_level])
    limits["experience_level"] = resolved_level
    # Bonus jest domyślnie wyłączony. Aktywuje go dopiero jawna preferencja
    # użytkownika, dzięki czemu schroniska nie zmieniają tras innych osób.
    limits["prefer_shelters"] = False
    limits["shelter_bonus_factor"] = 0.0
    return limits


def as_preference_bool(value):
    """Normalizuje wartość logiczną otrzymaną z JSON lub bazy danych."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "tak"}
    return bool(value)


def apply_shelter_preference(limits, prefer_shelters):
    """Zwraca kopię limitów z aktywną lub wyłączoną preferencją schronisk."""
    configured_limits = dict(limits)
    enabled = as_preference_bool(prefer_shelters)
    configured_limits["prefer_shelters"] = enabled
    configured_limits["shelter_bonus_factor"] = (
        configured_limits.get("shelter_preference_bonus_factor", 0.0)
        if enabled
        else 0.0
    )
    return configured_limits


ROUTE_PREFERENCE_CRITERIA = {
    "najkrótsza": "distance",
    "najkrotsza": "distance",
    "shortest": "distance",
    "distance": "distance",
    "najszybsza": "time",
    "fastest": "time",
    "time": "time",
    "najłatwiejsza": "difficulty",
    "najlatwiejsza": "difficulty",
    "easy": "difficulty",
    "easiest": "difficulty",
    "difficulty": "difficulty",
    "najmniejsze przewyższenie": "elevation",
    "najmniejsze przewyzszenie": "elevation",
    "elevation": "elevation",
}


def criterion_from_route_preference(route_preference, default="time"):
    """Mapuje zapisaną preferencję profilu na kryterium algorytmów."""
    if not isinstance(route_preference, str):
        return default
    normalized = route_preference.strip().lower()
    return ROUTE_PREFERENCE_CRITERIA.get(normalized, default)


def infer_experience_level(age_years, experience_level):
    """
    Określ poziom doświadczenia na podstawie deklaracji i wieku.

    Jawnie wybrany poziom ma pierwszeństwo. Wiek 65+ uruchamia profil Senior
    tylko wtedy, gdy użytkownik nie zadeklarował doświadczenia.
    
    Args:
        age_years: int lub str - wiek użytkownika
        experience_level: str - deklarowany poziom doświadczenia
    
    Returns:
        str - ostateczny poziom doświadczenia
    """
    try:
        age = int(age_years) if age_years else None
    except (ValueError, TypeError):
        age = None

    # Jawna deklaracja doświadczenia ma pierwszeństwo przed samym wiekiem.
    if experience_level in EXPERIENCE_LIMITS:
        return experience_level
    
    # Wiek stanowi bezpieczną wartość domyślną wyłącznie bez deklaracji.
    if age and age >= 65:
        return "senior"
    
    # Domyślnie średniozaawansowany
    return "intermediate"


def get_all_levels():
    """Zwróć listę wszystkich dostępnych poziomów doświadczenia"""
    return list(EXPERIENCE_LIMITS.keys())


def get_level_name(experience_level):
    """Pobierz polskojęzyczną nazwę poziomu"""
    limits = get_limits(experience_level)
    return limits.get("name", experience_level)

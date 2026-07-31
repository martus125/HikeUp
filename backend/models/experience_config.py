"""
Mapowanie poziomów doświadczenia na limity tras.
Każdy poziom ma inne ograniczenia dotyczące stromości, trudności i przewyższenia.
"""

EXPERIENCE_LIMITS = {
    "beginner": {
        "name": "Początkujący",
        "max_slope_percent": 15,           # Maksymalny % nachylenia
        "max_difficulty": 2,                # Skala 1-7 (1=najłatwiej, 7=najtrudniej)
        "max_elevation_gain_m": 300,        # Max przewyższenie w górę na trasę
        "max_consecutive_steep": 500,       # Max długość stromego fragmentu (m)
        "preferred_elevation_per_hour": 150 # Idealne tempo (m/h)
    },
    "intermediate": {
        "name": "Średniozaawansowany",
        "max_slope_percent": 25,
        "max_difficulty": 4,
        "max_elevation_gain_m": 700,
        "max_consecutive_steep": 1000,
        "preferred_elevation_per_hour": 250
    },
    "advanced": {
        "name": "Zaawansowany",
        "max_slope_percent": 40,
        "max_difficulty": 6,
        "max_elevation_gain_m": 1500,
        "max_consecutive_steep": 2000,
        "preferred_elevation_per_hour": 400
    },
    "expert": {
        "name": "Ekspert",
        "max_slope_percent": 50,
        "max_difficulty": 7,
        "max_elevation_gain_m": 2500,
        "max_consecutive_steep": 3000,
        "preferred_elevation_per_hour": 500
    },
    "senior": {
        "name": "Senior",
        "max_slope_percent": 10,            # ← Bardzo małe nachylenie
        "max_difficulty": 2,
        "max_elevation_gain_m": 200,
        "max_consecutive_steep": 300,       # ← Krótkie strome fragmenty
        "preferred_elevation_per_hour": 100
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
    return EXPERIENCE_LIMITS.get(
        experience_level,
        EXPERIENCE_LIMITS["intermediate"]  # domyślnie średniozaawansowany
    )


def infer_experience_level(age_years, experience_level):
    """
    Określ poziom doświadczenia na podstawie wieku i deklaracji.
    
    Senior (65+) będzie zawsze traktowany jak senior, niezależnie od 
    deklarowanego doświadczenia (bezpieczeństwo!).
    
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
    
    # Jeśli wiek >= 65, zawsze senior - bez względu na deklarację
    if age and age >= 65:
        return "senior"
    
    # W innym razie użyj deklarowanego poziomu
    if experience_level in EXPERIENCE_LIMITS:
        return experience_level
    
    # Domyślnie średniozaawansowany
    return "intermediate"


def get_all_levels():
    """Zwróć listę wszystkich dostępnych poziomów doświadczenia"""
    return list(EXPERIENCE_LIMITS.keys())


def get_level_name(experience_level):
    """Pobierz polskojęzyczną nazwę poziomu"""
    limits = get_limits(experience_level)
    return limits.get("name", experience_level)
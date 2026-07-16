USER_PROFILES = {
    "teenager": {
        "age": 15,
        "name": "Nastolatek",
        "slope_limit": 25,
        "max_difficulty": 5,
        "elevation_per_hour": 200,
        "description": "Aktywny, brak doświadczenia górskiego",
    },
    "adult": {
        "age": 35,
        "name": "Dorosły",
        "slope_limit": 35,
        "max_difficulty": 7,
        "elevation_per_hour": 350,
        "description": "Pełne doświadczenie górskie",
    },
    "senior": {
        "age": 65,
        "name": "Senior",
        "slope_limit": 15,
        "max_difficulty": 3,
        "elevation_per_hour": 150,
        "description": "Ograniczenia zdrowotne, słaba wydolność",
    },
    "family": {
        "age": 40,
        "name": "Rodzina z dziećmi",
        "slope_limit": 20,
        "max_difficulty": 4,
        "elevation_per_hour": 200,
        "description": "Bezpieczeństwo dzieci, umiarkowane trasy",
    },
}
def get_profile(profile_key):
    return USER_PROFILES.get(profile_key, USER_PROFILES["adult"])
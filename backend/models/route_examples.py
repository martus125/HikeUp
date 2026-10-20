"""Repeatable comparison scenarios; these settings never update user accounts."""

ROUTE_EXAMPLES = [
    {
        "id": "murowaniec-krzyzne",
        "start": "way/358407058", "end": "node/1200864424",
        "start_name": "Murowaniec", "end_name": "Krzyżne",
        "profile": "intermediate", "profile_name": "Średniozaawansowany",
        "criterion": "distance",
        "description": "Porównanie najkrótszej trasy z łagodniejszym wariantem Custom. Dłuższy przebieg może zmniejszyć trudność i sumę podejść.",
    },
    {
        "id": "kopy-krzyzne",
        "start": "node/3633357479", "end": "node/1200864424",
        "start_name": "Przełęcz między Kopami", "end_name": "Krzyżne",
        "profile": "intermediate", "profile_name": "Średniozaawansowany",
        "criterion": "distance",
        "description": "Drugi początek wycieczki w tym samym rejonie. Pokazuje kompromis między dystansem a trudnością wariantu.",
    },
    {
        "id": "kondratowa-kopa",
        "start": "way/184188834", "end": "node/3560695684",
        "start_name": "Hala Kondratowa", "end_name": "Kopa Kondracka",
        "profile": "beginner", "profile_name": "Początkujący",
        "criterion": "distance",
        "description": "Przykład ostrzegania: Custom może zwrócić tę samą trasę, ale wskazuje przekroczenia ograniczeń początkującego.",
    },
]

EXAMPLES_BY_ID = {example["id"]: example for example in ROUTE_EXAMPLES}

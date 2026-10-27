# Schroniska w aplikacji

Własny kod, API, dane POI i testy używają typu `shelter`. Polskie komunikaty
używają słowa „schronisko”. `models/point_types.py` tłumaczy oryginalny typ OSM
na `shelter` przy imporcie i odczycie starszych plików. Surowe migawki OSM oraz
historyczne raporty audytu pozostają zapisami oryginalnego źródła.

Preferencja Custom oznacza odwiedzenie przypisanego węzła schroniska. Samo
przejście w promieniu 350 m nie wystarcza. Interfejs rozdziela liczbę schronisk
w pobliżu trasy i liczbę odwiedzonych węzłów schronisk.

Przypisanie schroniska do grafu korzysta ze wspólnego resolvera POI, w tym
kontroli odległości do węzła (maks. 100 m). Różne historyczne nazwy pola
przypisania są obsługiwane tak samo jak w zwykłym planowaniu.

Dla wariantu start → shelter → cel oceniana jest cała połączona ścieżka:
limity profilu, maksymalne nachylenie i trudność, długość stromego odcinka,
dodatkowy dystans (10%), czas (15% i 20 minut) oraz podejście (100 m).
Przy trasie już przekraczającej limity preferencja nie może zwiększać liczby
rodzajów naruszeń, trudności, maksymalnego nachylenia ani ciągłego stromego
odcinka powyżej większej z wartości: limit profilu lub wynik wariantu bazowego.

W funkcji pomocniczej preferencji promieniowej nakładające się promienie
wybierają największą siłę wpływu, niezależnie od kolejności punktów. Główny
wybór wariantu Custom opiera się na odwiedzeniu węzła, bez bonusu za bliskość.

Odrzucone warianty i powody są dostępne w
`profile_evaluation.shelter_rejected_variants`. Ostrzeżenia o przekroczeniu
limitów są wyświetlane przy wyniku algorytmu.

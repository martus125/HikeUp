# Audyt POI względem oficjalnych szlaków TPN — 20.10.2026

Po ręcznym przeglądzie pozostawiono 84 pinezki. Ich rekordy w `graph_nodes.json`
zawierają wyłącznie siedem podstawowych pól. Pełne dane tych 84 punktów sprzed
uproszczenia zachowano w `poi_verification.json`; aplikacja nie odczytuje tego
raportu. Poniższe liczby opisują wcześniejszy audyt 575 POI, a nie obecną listę.

## Źródło i kompletność

Pobrano warstwę `Szlaki turystyczne` z oficjalnego serwera GIS TPN:
https://gis.tpn.pl/server/rest/services/Topografia___wektor_MIL1/MapServer/9

Pobranie wykorzystało listę wszystkich ObjectID i partie po 100 obiektów.
Liczba pobranych obiektów zgadza się z liczbą ID: 276. Wybrano 240 obiektów
z typem zawierającym `pieszy`; nie używano samodzielnych tras narciarskich
ani rowerowych jako potwierdzenia szlaku pieszego. Pełny snapshot jest obok raportu.

## Wynik

- Sprawdzono wszystkie 575 POI, łącznie ze szczytami.
- Aktualny filtr aplikacji dopuszcza 239 POI.
- 141 z tych punktów spełnia kryteria geometryczne audytu.
- 98 dostępnych punktów wymaga sprawdzenia; wszystkie mają typ `peak`.
- Pozostałe 336 POI już nie są udostępniane przez aktualny filtr.
- Żaden z punktów ukrytych nie przeszedł wszystkich kryteriów tego audytu.

Przykłady odległości naturalnego obiektu od oficjalnej geometrii:

| Obiekt | Odległość | Obecnie dostępny |
|---|---:|---|
| Myślenickie Turnie | 34,91 m | tak |
| Sucha Czuba | 78,31 m | tak |
| Kalacka Kopa | 422,16 m | nie |
| Turnia nad Białem | 611,70 m | nie |

Limit 100 m do grafu OSM nie jest wystarczającą kontrolą zgodności z oficjalnym
szlakiem. Wcześniejszy skrypt kuratorski pomijał szczyty.

## Kryteria geometryczne

Współrzędne przeliczono do EPSG:32634, a odległości obliczono w metrach.
Kontrolowano oddzielnie naturalną lokalizację obiektu, marker i węzeł grafu.
Próg dla obiektu wynosi 30 m (dla czterech nazwanych wyjątków centroidowych
z istniejącego skryptu zachowano ich odrębne limity). Marker i węzeł muszą
znajdować się do 20 m od oficjalnej geometrii. Kontrolowano też istnienie
węzła połączonego krawędzią i odległość węzła od markera i obiektu.

Przejście kontroli nie stanowi potwierdzenia terenowego ani prawnego.
Niezaliczenie kontroli oznacza potrzebę sprawdzenia, a nie dowód zakazu wejścia.
Dokładność i generalizacja warstwy mogą wpływać na wynik, zwłaszcza przy szczytach.

## Ograniczenie grafu i dostępności

Sprawdzono też proste odcinki między końcami 121 047 krawędzi grafu:
22 709 mieści się w całości w korytarzu 20 m od oficjalnych szlaków pieszych;
98 338 nie mieści się w nim w całości. Graf jest znacznie szerszy od tej warstwy
TPN — wynik nie oznacza, że wszystkie niedopasowane odcinki są nielegalne.
W szczególności warstwa nie potwierdza sieci poza swoim obszarem.

Sam audyt POI nie gwarantuje oficjalnego przebiegu całej trasy: algorytm może
łączyć zgodne punkty końcowe przez inne drogi obecne w grafie OSM.
Nie wdrożono tu filtrowania całej sieci, kierunkowości ani zamknięć.

Aktualną dostępność należy sprawdzać osobno:
https://tpn.gov.pl/komunikat-turystyczny

## Pliki i odtworzenie

- `official_trail_points_audit.csv` — wszystkie 575 punktów, odległości i przyczyny.
- `official_trail_points_audit.json` — pełne wyniki i podsumowanie.
- `tpn_trails_snapshot.json` — źródłowa warstwa użyta do audytu.
- `../scripts/audit_official_trail_points.py` — uruchomienie z backendu:
  `python scripts/audit_official_trail_points.py`.

Skrypt używa lokalnego snapshotu i nie aktualizuje go samodzielnie. Nie zmienia
POI, ich widoczności ani grafu. Wyniki odnoszą się do stanu danych w chwili audytu.
Wymaga numpy, Shapely i pyproj, dostępnych w użytym środowisku projektu.

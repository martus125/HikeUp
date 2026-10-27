# Dostępność szlaków i pewność danych

## Działanie aplikacji

Wszystkie cztery algorytmy korzystają ze wspólnego grafu pieszych kierunków.
Zakazany kierunek nie trafia do grafu ani indeksu służącego do sumowania trasy.
Zapis ulubionych również sprawdza połączenie w dozwolonym kierunku.

- `foot` ma pierwszeństwo przed ogólnym `access`. `foot:forward` i
  `foot:backward` dotyczą kierunku oryginalnej drogi OSM.
- Dopuszczane wartości dostępu to brak tagu, yes, designated i permissive.
  Pozostałe wartości, np. no, private, customers, permit i destination,
  nie dopuszczają zwykłego turysty do planowania przejścia tranzytowego.
- `oneway:foot=yes/-1/no` określa pieszą kierunkowość. Na path, footway,
  steps, pedestrian i via_ferrata stosujemy zachowawczo także ogólne oneway,
  chyba że istnieje `oneway:foot`. Na ulicach ogólne oneway nie ogranicza pieszych.
- `closed=yes`, highway=construction/proposed i nierozpoznane wartości
  kierunkowości wykluczają odcinek.
- **Polityka sezonowa: wykluczenie przez cały rok.** Bez wyboru daty i pełnego
  parsera harmonogramów nie próbujemy oceniać, czy warunek aktualnie obowiązuje.
  Odcinki z seasonal innym niż no, warunkami foot/access/oneway oraz godzinami
  innymi niż 24/7 są pomijane. Może to wykluczyć szlak otwarty w dniu wycieczki.
  Komunikat o tej zasadzie jest widoczny w planerze.

Zasady tagowania: [dostęp OSM](https://wiki.openstreetmap.org/wiki/Key:access),
[piesza kierunkowość](https://wiki.openstreetmap.org/wiki/Key:oneway:foot),
[warunki dostępu](https://wiki.openstreetmap.org/wiki/Conditional_restrictions).
Ogólne oneway na ścieżkach jest niejednoznaczne; jego zachowawcza interpretacja
jest decyzją tego planera, a nie uniwersalną regułą OSM.

## Pewność trudności

`difficulty_known=true` oznacza rozpoznany sac_scale źródła, a nie pomiar
bezpieczeństwa trasy. Zachowujemy sac_scale i difficulty_source. Brak tagu lub
nieobsługiwana wartość daje difficulty_known=false i domyślną trudność 2.
Starsze dane bez flagi są traktowane jako niepotwierdzone, również gdy mają
już wpisaną trudność liczbową.

Każdy wynik podaje liczbę odcinków o nieznanej trudności, ich dystans i udział
w długości trasy. Warnings zawiera komunikaty dla użytkownika, a ocena profilu
ma assessment_complete=false, jeżeli brakuje trudności lub informacji o dostępie.
Frontend pokazuje wtedy ocenę jako wstępną i wyświetla ostrzeżenia. Dotyczy to
także propozycji łatwiejszych celów.

`within_safety_limits` nadal oznacza porównanie parametrów liczbowych z progami
modelu. Należy interpretować je łącznie z assessment_complete; nie jest
potwierdzeniem bezpieczeństwa ani bieżącego otwarcia szlaku.

## Aktualizacja obecnej mapy

Skrypt `scripts/enrich_access_data.py` pobiera drogi już występujące w mapie.
Zachowuje węzły, geometrię, dystans, wysokości, przewyższenia i nachylenie.
Aktualizuje tagi dostępu, trudność i informację o źródle. Sprawdza kolejność
węzłów OSM, żeby poprawnie zinterpretować również odwrócone krawędzie.
Drogi usunięte ze źródła i odcinki, których węzły przestały być kolejnymi węzłami
drogi, są wykluczane do czasu ponownej weryfikacji lub regeneracji geometrii.

Z katalogu backend:

```powershell
python scripts/enrich_access_data.py --fetch --apply
```

Zachowany `mapa/osm_access_snapshot.json` umożliwia odtworzenie bez sieci:

```powershell
python scripts/enrich_access_data.py --osm-file mapa/osm_access_snapshot.json --apply
```

Bez `--apply` skrypt tylko wyświetla raport. Czas danych OSM i statystyki są
w routing_data_metadata.access. Po aktualizacji trzeba **zrestartować backend**,
ponieważ mapa i graf są buforowane w procesie.

Generator nowej mapy również zachowuje tagi i flagi, zamiast odfiltrowywać je
przed importem. Jego ponowne uruchomienie nadal wymaga osobnego uzupełnienia
wysokości — aktualizacja tagów istniejącej mapy tego nie wymaga.

## Granice danych

To migawka tagów dróg OSM, bez połączenia z bieżącymi komunikatami TPN.
Nie analizujemy barier zapisanych jako osobne węzły ani relacji zakazów skrętu.
Brak tagu zakazu nie jest potwierdzeniem legalnego dostępu. Zmiany zamknięć,
warunki pogodowe i terenowe wymagają sprawdzenia przed wycieczką.

Testy `test_access_and_quality.py` obejmują kierunki, pierwszeństwo tagów,
zamknięcia, wszystkie algorytmy i kryteria, ostrzeżenia, import, aktualizację,
API oraz odmowę zapisu ulubionej w zakazanym kierunku.

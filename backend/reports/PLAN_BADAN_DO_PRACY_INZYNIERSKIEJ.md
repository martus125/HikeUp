# Plan weryfikacji i oceny aplikacji HikeUp

Data analizy: 3 listopada 2026 r. Dokument opisuje proponowane badania. Wynikami już wykonanymi są wyłącznie obserwacje wyraźnie wymienione w części 1. Nie zmieniano implementacji aplikacji.

## 1. Co rzeczywiście wynika z obecnej implementacji

Przeanalizowano implementacje czterech algorytmów, wspólne funkcje kosztu i statystyk, konfigurację profili, reguły dostępu, kontekst grafu, endpoint planowania, testy backendu, skrypty kontroli danych, zapisane przykłady oraz komponenty prezentujące wyniki.

- Dijkstra minimalizuje sumę kosztów `edge_weight` dla wybranego kryterium.
- A* korzysta z tych samych kosztów. Dla dystansu i czasu wykorzystuje odległość geograficzną; dla `elevation` i `difficulty` heurystyka wynosi zero. W tych dwóch przypadkach nie należy oczekiwać zasadniczej przewagi nad Dijkstrą.
- Greedy Best-First Search wybiera kierunek geograficznie. Wybrane kryterium wpływa na wycenę uzyskanej ścieżki, a nie kolejność przeszukiwania. Ta sama trasa dla czterech kryteriów może być poprawnym zachowaniem tej implementacji.
- Custom HikeUp jest metodą generowania i selekcji kandydatów: uwzględnia trasę bazową, wariant profilowy oraz warianty z filtrowaniem krawędzi. Ocenia ograniczenia całej trasy, objazd i opcjonalnie wariant przez schronisko. Nie przegląda wszystkich możliwych tras. Brak odpowiedniego kandydata nie dowodzi braku odpowiedniej trasy w grafie.
- Wybór akceptowalnego wariantu Custom odbywa się według kosztu bazowego, po zastosowaniu reguł dopuszczalności i preferowanego objazdu. `custom_score` i `profile_match_score` nie są globalną funkcją celu finalnej selekcji.
- Kryterium `elevation` ma koszt: podejście w metrach + 10 × dystans w km. Nie jest to ścisła minimalizacja samego podejścia, nawet jeśli komentarz nazywa dystans kosztem pomocniczym.
- Kryterium `difficulty` minimalizuje złożoną sumę: 100 × trudność × dystans + podejście + modelowy czas + 10 × dystans. Nie jest to minimalizacja maksymalnej klasy trudności. Skala SAC ma charakter porządkowy; jej średnia liczbowa jest wskaźnikiem modelu, nie pomiarem fizycznej trudności.
- Czas prezentowany w statystykach wszystkich tras jest liczony wspólnym modelem: 12 minut na kilometr + 0,1 minuty na metr podejścia. Profilowe tempo podejścia wpływa na koszt generowania wariantu Custom, ale nie zmienia tego wspólnego czasu prezentowanego w `totals`.
- Reguły dostępu uwzględniają kierunki i wykluczają odcinki sezonowe lub warunkowe niezależnie od daty. Aplikacja nie interpretuje kalendarza zamknięć i nie pobiera bieżących komunikatów.
- Parametry profili są założeniami projektowymi. W kodzie nie ma dowodu ich walidacji na rzeczywistych użytkownikach. Badanie może potwierdzić zgodność z modelem profilu, a nie fizjologiczną przydatność trasy dla danej osoby.
- `assessment_complete` sprawdza znajomość trudności i dostępu. Nie oznacza pełnej pewności wysokości, nachylenia, pogody ani bezpieczeństwa terenowego.

### Wykonane sprawdzenia

Uruchomiono z katalogu backendu:

```powershell
..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
..\.venv\Scripts\python.exe scripts\validate_routing_data.py
```

Wynik testów: **210 passed, 40 subtests passed**. Są to testy automatyczne; testy bazy wykorzystują zastąpione zależności i blokują prawdziwe połączenia. Wynik nie zastępuje sprawdzenia rzeczywistej bazy i interfejsu.

Walidator: 120 636 węzłów, 121 047 rekordów krawędzi, 84 POI i 8 schronisk; brak wykrytych blokad strukturalnych. Po zastosowaniu polityki dostępu kontekst zawiera 188 825 skierowanych łuków. Są to dwie różne liczby: rekord źródłowy może dopuszczać dwa kierunki.

Trudność ma znacznik `difficulty_known=True` dla 42 872 rekordów. Dla 78 175, czyli około 64,6%, nie jest potwierdzona. Dane dostępu nie są potwierdzone dla 338 rekordów. Odsetki te dotyczą rekordów, nie długości sieci ani długości konkretnej trasy. Brak trudności jest zastępowany wartością modelową, dlatego obecność liczby w polu `difficulty` nie oznacza kompletności danych.

Metadane mapy opisują DEM 90 m, nachylenie obliczone w oknie 180 m wzdłuż drogi OSM, 233 wartości ograniczone do pułapu oraz 18 339 krawędzi oznaczonych jako ograniczone rozdzielczością danych. Maksymalne nachylenie trasy jest maksimum wskaźników odcinkowych po takim przetwarzaniu, a nie pomiarem najstromszego miejsca w terenie.

Wykonano również pilotaż trzech zapisanych przykładów, zgodnie z ich profilem, dla dystansu, bez preferencji schronisk:

| Przykład | Dystans Dijkstra / Custom | Podejście Dijkstra / Custom | Wynik Custom |
|---|---:|---:|---|
| Murowaniec → Krzyżne, intermediate | 5,29 / 5,29 km | 688,67 / 688,67 m | ta sama ścieżka, `difficult_route` |
| Przełęcz między Kopami → Krzyżne, intermediate | 6,78 / 6,78 km | 790,50 / 790,50 m | ta sama ścieżka, `difficult_route` |
| Hala Kondratowa → Kopa Kondracka, beginner | 2,86 / 2,86 km | 628,63 / 628,63 m | ta sama ścieżka, `difficult_route` |

W każdym przypadku pozostał jeden unikatowy kandydat. Wynik nie dowodzi braku innych tras w całym grafie. Opisy pierwszych dwóch przykładów sugerujące łagodniejszy wariant wymagają aktualizacji albo ponownego udokumentowania. Nie należy używać ich jako gotowego dowodu poprawy.

Historyczny raport `OFFICIAL_TRAIL_AUDIT.md` dotyczy częściowo wcześniejszych 575 POI. Sam zaznacza tę różnicę. Jego dawnych liczb i informacji o braku obsługi kierunków nie należy przedstawiać jako opisu obecnej wersji.

## 2. Zalecany zakres pracy

Proponuję jeden rozdział „Weryfikacja i ocena rozwiązania” z czterema głównymi podrozdziałami badań:

1. Poprawność implementacji i wiarygodność danych wejściowych.
2. Ocena personalizacji i jakości wyboru trasy przez Custom HikeUp.
3. Porównanie jakości wyników i wydajności algorytmów na rzeczywistej sieci.
4. Weryfikacja funkcjonalna całej aplikacji.

Porównanie z zewnętrznym planerem jest badaniem uzupełniającym, możliwym jako piąty podrozdział. Nie powinno być głównym dowodem poprawności algorytmów, bo planer zewnętrzny może używać innego grafu, modelu czasu i reguł dostępu.

## 3. Badanie I: poprawność implementacji i danych

**Pytanie:** czy aplikacja poprawnie realizuje zadane funkcje kosztu, kierunki przejścia, sumowanie parametrów i obsługę sytuacji brzegowych?

### Metoda

Wykorzystać obecne testy jako bazę i przyporządkować je wymaganiom. Przygotować około 10–12 małych grafów, np. 5–10 węzłów i kilka alternatyw, z ręcznie policzonym wynikiem. Liczba oznacza scenariusze, nie wymóg dopisania tylu nowych plików lub testów.

| Scenariusz | Niezależnie sprawdzany wynik |
|---|---|
| Dwie drogi o różnej długości | minimum sumy dystansów |
| Krótka droga z dużym podejściem i dłuższa płaska | minimum jawnie policzonego czasu modelowego |
| Dwie drogi o różnym podejściu | minimum pełnego kosztu `elevation` |
| Różne klasy SAC i długości | minimum pełnego kosztu `difficulty` |
| Równoważne trasy | równy optymalny koszt; dopuszczalne różne ścieżki |
| Brak połączenia, nieznane ID, start równy celowi | zachowanie zgodne z ustalonym kontraktem API i funkcji |
| Ta sama droga w przeciwnych kierunkach | zamiana podejścia i zejścia, możliwy inny czas |
| Jednokierunkowość i zakaz pieszy | brak przejścia w zabronionym kierunku |
| Sezonowość / dostęp warunkowy | wykluczenie według obecnej, całorocznej polityki |
| Brak potwierdzonej trudności lub dostępu | udział braków i komunikat o niepełnej ocenie |
| Podział odcinka na mniejsze części z zachowaniem parametrów | zachowanie addytywnych kosztów klasycznych, z tolerancją numeryczną |
| Wartości blisko limitów i zaokrągleń | jawna interpretacja granicy; brak ukrycia istotnego przekroczenia |

Oczekiwanego wyniku nie wyliczać wyłącznie przez wywołanie tej samej funkcji, którą testujemy. Dla kilku grafów rozpisać rachunek w tabeli. Dodatkowo można użyć NetworkX jako niezależnej implementacji wyszukiwania, przekazując jej jawnie przygotowane wagi. To kontroluje algorytm przeszukiwania; nie potwierdza samo w sobie poprawności wspólnego wzoru na koszt.

Dla A* sprawdzić warunek dolnego oszacowania: na małych grafach porównać `h(v,t)` z dokładnym kosztem dojścia, a na rzeczywistych łukach zbadać spójność `h(u,t) <= w(u,v) + h(v,t)`. Dystans krawędzi nie powinien istotnie zaniżać odległości geograficznej jej końców. Ewentualne odstępstwa od zaokrągleń raportować, a nie zakładać z góry poprawności heurystyki.

Weryfikację danych rozszerzyć poza istniejący walidator: udział braków trudności/dostępu, dostępność połączeń między POI, odległość dopasowania POI do grafu, niepewność nachylenia i zgodność wybranych przebiegów z materiałem referencyjnym. Przejście walidatora oznacza spełnienie jego kontroli, nie pełną wiarygodność terenową danych.

**Miary:** liczba zaliczonych scenariuszy i asercji, liczba niepoprawnych ścieżek, różnica kosztu względem wzorca, liczba naruszeń kierunków, udział braków danych ważony długością.

**Kryterium akceptacji:** wszystkie obowiązkowe scenariusze poprawności zaliczone; różnice kosztu wyłącznie w uzasadnionej tolerancji. Dla surowych kosztów można przyjąć `abs(a-b) <= 1e-8 * max(1, abs(b))`. Nie stosować tej tolerancji do wartości z UI zaokrąglonych do jednego miejsca.

**Dowód:** raport pytest, tabela wymagań i testów, definicje grafów, ręczne rachunki oraz raport walidacji danych.

## 4. Badanie II: personalizacja i wzorzec optymalny na małych grafach

**Pytanie:** czy Custom wybiera trasę zgodną z zadanym modelem profilu, jaki kompromis uzyskuje oraz czy pomija dostępny wariant spełniający ograniczenia?

### A. Kontrolowane scenariusze decyzji

Przygotować około 8–10 małych grafów. Uwzględnić: krótką trudną i dłuższą łagodną trasę; identyczne końce dla różnych profili; brak wariantu zgodnego; dopuszczalny i nadmierny objazd; przekroczenie sumy podejść mimo dopuszczalnych pojedynczych krawędzi; zbyt długi ciąg stromych odcinków; niepełne dane; schronisko w dopuszczalnym i nadmiernym dodatkowym wysiłku; schronisko blisko geometrii, ale poza ścieżką w grafie.

Wartości graniczne sprawdzać poniżej progu, na progu i powyżej. Szczególnie ważne są zaokrąglenia: statystyki trasy są zaokrąglane przed częścią ocen. Niezależny rachunek na surowych danych powinien pokazać, czy wpływa to na decyzję.

Preferencję schronisk oceniać według odwiedzenia przypisanego węzła, a nie samego `shelters_count`, które zlicza obiekty w promieniu 350 m od trasy. Obecne ograniczenia dodatkowego wysiłku obejmują jednocześnie: dystans do 110% wariantu podstawowego, czas do 115% i nie więcej niż dodatkowe 20 min, podejście dodatkowe do 100 m, brak wzrostu maksymalnej trudności i nachylenia oraz pozostałe kontrole profilu. Dodatkowy dystans jest liczony względem standardowego wariantu Custom, a ogólny objazd względem najkrótszej trasy dystansowej.

Nie wymagać, aby każdy profil zawsze dawał inną trasę. Nie wymagać również monotonicznej poprawy każdej statystyki, bo ograniczenia i koszty konkurują ze sobą.

### B. Co oznacza „idealna trasa”

Dla głównego porównania wyłączyć preferencję schronisk i badać małe grafy, na których można wymienić wszystkie ścieżki proste od startu do celu. Dla każdej ścieżki niezależnie wyliczyć parametry i sprawdzić ograniczenia.

Zdefiniować wzorzec jako minimalny koszt bazowy wśród ścieżek spełniających twarde ograniczenia modelu oraz dopuszczalny objazd. Osobno wyznaczyć minimum w podzbiorze spełniającym preferowany objazd. Wynik Custom porównać z odpowiednią pulą, ponieważ implementacja daje pierwszeństwo tej drugiej. Miękki limit nachylenia nie jest tym samym co twardy limit rekomendacji.

To jest „optymalna trasa w zadanym modelu”, nie uniwersalnie najlepsza trasa dla człowieka. Ścieżki proste wystarczają do podstawowego eksperymentu bez wymogu odwiedzenia schroniska. Warianty przez schronisko badać osobno: implementacja może łączyć dwa odcinki z powtórzeniem węzłów, co wymagałoby innej definicji przestrzeni wzorca.

Istotny przypadek negatywny: wszystkie wygenerowane warianty mają naruszenia, ale istnieje inna dopuszczalna ścieżka. Taki wynik ujawnia ograniczenie metody kandydatowej. Jest wartościowym wynikiem pracy, a nie powodem usunięcia przypadku z tabeli.

Enumeracji nie uruchamiać na całej sieci Tatr. Liczba ścieżek może rosnąć bardzo szybko; małe grafy o kontrolowanej liczbie wariantów są tutaj właściwym narzędziem.

### Miary i interpretacja

- **Zgodność rekomendacji:** ile tras oznaczonych jako rekomendowane rzeczywiście spełnia sprawdzane niezależnie twarde ograniczenia i dopuszczalny objazd.
- **Wykrycie wariantu dopuszczalnego:** liczba przypadków, w których Custom zwrócił wariant dopuszczalny / liczba przypadków, w których wzorzec potwierdził jego istnienie.
- **Luka kosztu:** `100 * (C_custom - C_opt) / C_opt`, wyłącznie gdy obie trasy należą do tej samej zdefiniowanej puli, a `C_opt > 0`. Przy braku dopuszczalnego wyniku raportować osobną kategorię, nie kosztowy procent.
- Różnica dystansu, podejścia, maksymalnej klasy SAC, wskaźnika nachylenia i najdłuższego stromego fragmentu względem Dijkstry dla tej samej pary i kryterium.
- Liczba identycznych tras, zmian tras i ostrzeżeń; poprawność decyzji o schronisku.

`profile_match_score` podawać pomocniczo. Jest zdefiniowany przez autorkę modelu i nie może być jedynym dowodem jego jakości. Niezależny ewaluator nie powinien jedynie wywoływać `evaluate_route_profile`.

**Kryterium akceptacji:** poprawne egzekwowanie jawnych reguł i komunikatów. Odsetek odnalezionych wariantów oraz luka optymalności są wynikami badania; nie obiecywać z góry 100% skuteczności lub globalnej optymalności Custom.

**Dowód:** pełna lista ścieżek na małych grafach, wskazanie optimum, wynik Custom, ręcznie sprawdzone przykłady i zestawienie również przypadków niekorzystnych.

## 5. Badanie III: jakość i wydajność na rzeczywistej sieci

**Pytania:** jaki koszt tras i nakład obliczeń uzyskują cztery metody oraz jak często personalizacja zmienia wynik lub wykrywa przekroczenia modelu?

### Próba i procedura

1. Zamrozić wersję kodu, mapy i POI. Zapisać identyfikator wersji, sumy SHA-256 danych, środowisko Python, pakiety, system i sprzęt.
2. Przed pomiarem końcowym ustalić 24 skierowane pary POI: po 8 krótkich, średnich i długich. Długość wyznaczyć z dystansowego wyniku referencyjnego, np. przedziały do 5 km, 5–10 km i powyżej 10 km, jeśli lokalny zbiór umożliwia ich wypełnienie. Nie dostosowywać przedziałów po obejrzeniu wyników Custom.
3. Dobierać pary z listy dostępnych POI, ze stałym ziarnem losowania i zróżnicowaniem rejonów. Niedostępne połączenia odnotować; do próby wydajnościowej można dobierać kolejne według jawnej reguły. Osobną próbę nieosiągalnych celów zachować jako test funkcjonalny.
4. Dla 24 par zbadać cztery kryteria. Trzy metody klasyczne dają 288 konfiguracji. Custom dla pięciu profili, początkowo bez schronisk, daje 480 konfiguracji. Łącznie 768 konfiguracji jakościowych.
5. Preferencję schronisk włączyć w osobnym badaniu sparowanym, np. 8 par × 2 profile × tryb włączony/wyłączony, przy stałym kryterium. Dobór powinien obejmować różne możliwości dojścia do schroniska, a nie tylko sukcesy algorytmu.
6. Przeprowadzić pilotaż czasu na kilku konfiguracjach. Do właściwych pomiarów wybrać z góry podzbiór 12 par, dwa kryteria (`distance`, `time`), trzy metody klasyczne i Custom dla beginner oraz expert. To 120 konfiguracji czasowych. Wykonać 3 przebiegi rozgrzewające i 20 pomiarów każdej konfiguracji; kolejność zmieniać według ustalonego ziarna. Jeżeli pilotaż wymusi zmniejszenie liczby powtórzeń, ustalić ją przed pomiarem końcowym i jawnie podać.

Te liczby są projektem badania, nie przeprowadzonym eksperymentem. Powtórzenia czasu dla tej samej trasy nie są nowymi niezależnymi przypadkami jakościowymi.

### Warunki uczciwego porównania

- Wszystkie funkcje otrzymują ten sam przygotowany `routing_context`, te same POI i kryterium.
- Koszt Dijkstry zweryfikować dodatkowo niezależną implementacją na reprezentatywnych przypadkach. Dla A* porównywać koszt, nie wymagać identycznej ścieżki przy remisach.
- Custom w endpointcie korzysta z wcześniej wyliczonej trasy Dijkstry. Jego wewnętrzny czas nie obejmuje wtedy jej obliczenia. Główne porównanie metod prowadzić w wariancie samodzielnym, bez przekazania `baseline_route`, albo doliczyć koszt bazowy z osobnym opisem. Czas przyrostowy po udostępnieniu Dijkstry raportować oddzielnie.
- Mierzyć zewnętrznym zegarem całą funkcję wyznaczania wyniku. Wewnętrzne `execution_time_ms` obejmuje również część obliczania statystyk i obsługi kandydatów, a nie samo zdejmowanie węzłów z kolejki.
- Zimny start procesu i przygotowanie grafu zbadać oddzielnie, np. 5 nowych procesów. Czasy API obejmujące wszystkie cztery algorytmy, formatowanie i ewentualne alternatywne cele nie są czasem pojedynczego algorytmu.
- `visited_nodes` oznacza licznik przetwarzania według kodu, niekoniecznie liczbę unikatowych węzłów. W Custom liczniki sumują wiele wyszukiwań, zatem mogą przekroczyć liczbę węzłów grafu.
- Wykonywać pomiary na tym samym komputerze, bez równoległych pomiarów i pobierania danych. Nie wyciągać wniosków o skalowalności na podstawie samych różnych długości tras w jednym grafie.

### Miary i raport

Dla klasycznych metod: względna różnica kosztu wobec Dijkstry, odsetek osiągniętych celów, dystans, modelowy czas, podejście oraz liczniki przeszukiwania. Dla A* oczekiwana jest równość kosztu przy spełnionych warunkach heurystyki. Greedy może mieć większy koszt; mierzymy wielkość kompromisu.

Dla Custom: fizyczne/statystyczne parametry trasy i reguły profilu porównywane z Dijkstrą, liczba naruszeń, odsetek zmian ścieżki, udział rekomendacji kompletnych i niekompletnych. Na dużym grafie bez dokładnego wzorca nie nazywać różnicy kosztu „błędem względem optimum profilowego”.

Dla czasu: mediana i rozstęp międzykwartylowy powtórzeń każdej konfiguracji, następnie sparowane zestawienie między metodami na tych samych trasach. P95 raportować ewentualnie dla większego zbioru czasów żądań, z jawną liczebnością; z 20 powtórzeń pojedynczej konfiguracji jest mało stabilny. Nie łączyć kosztów minutowych, kilometrowych i punktowych we wspólną średnią.

Braki danych analizować dwutorowo: główna ocena zgodności profilu dla tras z kompletnymi informacjami oraz osobna tabela wyników z brakami. Pokazać liczebność obu grup; nie usuwać po cichu niepełnych przypadków. Kompletność danych o trudności i dostępie nadal nie rozwiązuje niepewności DEM.

**Dowód:** lista par i parametrów eksperymentu, wyniki JSON z identyfikatorami węzłów, surowe pomiary CSV, skrypt uruchamiający oraz wykresy/tabele utworzone z tych plików. Same zrzuty ekranu z czasami nie wystarczą.

## 6. Badanie IV: weryfikacja funkcjonalna całej aplikacji

**Pytanie:** czy użytkowniczka może wykonać zamierzone czynności, a warstwy interfejsu, API i bazy przekazują zgodne dane?

Przygotować około 15–20 scenariuszy akceptacyjnych z warunkami początkowymi, krokami, oczekiwanym wynikiem i dowodem. Wykorzystać istniejące testy backendu; brakujące sprawdzenia wykonać ręcznie w przeglądarce na oddzielnej bazie testowej.

Zakres: rejestracja i logowanie; błędne dane; zapis i ponowne odczytanie profilu; deklarowany profil a profil domyślny z wieku; planowanie jako gość i po zalogowaniu; wybór początku i celu z wyszukiwarki; zgodność wszystkich czterech kart i linii na mapie z odpowiedzią API; ostrzeżenia o brakach i przekroczeniach; brak połączenia; zmiana kryterium; preferencja schronisk; zapis/odczyt/usunięcie ulubionej trasy; izolacja ulubionych dwóch kont; wylogowanie; błąd sieci; czytelność na urządzeniu mobilnym; propozycje innych celów, jeśli rzeczywiście zostaną zwrócone dla przygotowanego przypadku.

W obecnym `App.jsx` wynik główny jest wybierany jako Dijkstra, a zapis ulubionych pobiera jego `pathIds`. Sprawdzić w rzeczywistej bazie zgodność zapisu i czytelność tego zachowania dla użytkowniczki. Interfejs pokazuje wiele wyników, a opis przebiegu odnosi się do Dijkstry.

Ważne dla dowodów graficznych: `RouteMap.jsx` celowo przesuwa kolorowe linie o -9, -3, +3 i +9 m, żeby je rozdzielić. Rozdzielone linie na zrzucie ekranu nie dowodzą różnych ścieżek! Zgodność przebiegów i porównania geometryczne opierać na oryginalnych identyfikatorach węzłów i współrzędnych z API, przed przesunięciem wizualnym.

Nie utożsamiać testów z zastąpioną bazą z pełną integracją. Dla rzeczywistej bazy użyć odrębnych kont i danych testowych oraz potwierdzić trwałość po ponownym odczycie. Nie jest potrzebny audyt bezpieczeństwa całego systemu, żeby rzetelnie sprawdzić podstawową izolację kont i walidację.

**Miary:** zaliczone scenariusze / wszystkie scenariusze, liczba rozbieżności UI–API–baza, liczba błędów blokujących główny scenariusz.

**Kryterium akceptacji:** brak błędów blokujących główne funkcje i poprawne komunikowanie ograniczeń. Osobno wymienić ograniczenia znane i funkcje niesprawdzone. Test wykonany przez autorkę nie jest badaniem użyteczności z udziałem użytkowników.

**Dowód:** tabela scenariuszy, reprezentatywne zrzuty ekranu, odpowiedzi API i odczytane rekordy bazy testowej. Nie publikować haseł ani tokenów sesji.

## 7. Badanie uzupełniające: porównanie z innym planerem

Wybrać jeden serwis, np. mapa-turystyczna.pl, i 6–8 przypadków z zamrożonej próby. Wybrać możliwie zbliżony tryb wyznaczania oraz te same współrzędne startu i celu; zapisać ustawienia, datę i link/zrzut wyniku.

Rozdzielić dwa pytania:

1. **Wybór przebiegu:** czy planery prowadzą tym samym korytarzem i przez te same rozgałęzienia? Różnice opisać na mapie wraz z możliwą przyczyną, np. regułami dostępu lub inną siecią.
2. **Opis tej samej trasy:** przy zgodnym przebiegu porównać długość, podejście i czas. Przy różnych przebiegach nie przedstawiać różnicy czasu jako błędu estymacji czasu.

Względną różnicę dystansu można podać jako `100 * (L_HikeUp - L_ref) / L_ref`. Jest to różnica względem serwisu, a nie błąd wobec prawdy terenowej. Podobnie dla modelowego czasu i podejścia. Nie ustalać arbitralnie, że różnica poniżej 5% dowodzi poprawności. Wyjaśnić pochodzenie danych i ograniczenia obu modeli.

Brak porównywalnego przebiegu również jest wynikiem. Serwis zewnętrzny nie stanowi wzorca „idealnej trasy dla seniora”, jeśli nie realizuje takiego samego modelu. Ten eksperyment może być ręczny; nie wymaga automatyzowania obcego serwisu ani płatnej integracji.

## 8. Powtarzalność i minimalny pakiet dowodowy

Przed badaniami końcowymi przygotować:

- `scenarios.csv`: ID, źródło doboru, start/koniec POI, węzły routingu, profil, kryterium, preferencja schronisk, grupa długości.
- `results.jsonl`: ID scenariusza, wersja danych i kodu, algorytm, ścieżka, koszt, statystyki, braki danych, ocena profilu, status i metryki.
- `timings.csv`: scenariusz, metoda, wariant pomiaru, numer powtórzenia, czas, stan rozgrzania; powtórzenia rozgrzewające oznaczone i wyłączone z agregacji.
- `acceptance.csv`: wymaganie, kroki, oczekiwany i rzeczywisty wynik, zaliczenie, odnośnik do dowodu.
- Opis środowiska, sumy kontrolne mapy/POI i kopię konfiguracji profili.
- Skrypty obliczające tabele i wykresy z surowych wyników.

Oczekiwane reguły i sposób doboru próby zapisać przed eksperymentem. Przykłady użyte do strojenia parametrów oddzielić od próby końcowej. Po zmianie parametrów profilu lub danych oznaczyć nową wersję i ponowić zależne pomiary. Nie wybierać jedynie przykładów, w których Custom zmienia trasę na korzystniejszą.

Obecnie istnieją testy i walidator, ale katalog `benchmarks` nie zawiera źródłowego runnera benchmarków. Do realizacji planu trzeba jeszcze przygotować: uruchamiacz eksperymentów i zapis wyników, mały niezależny ewaluator/wzorzec, zamrożoną listę scenariuszy oraz arkusz akceptacyjny. To nie wymaga tworzenia nowej aplikacji, ale jest rzeczywistą pracą do wykonania.

## 9. Proponowane sformułowanie do APD

> Celem pracy jest opracowanie i ocena aplikacji wspomagającej planowanie tras pieszych w rejonie Tatr, wykorzystującej algorytmy Dijkstry, A*, Greedy Best-First Search oraz autorską metodę generowania i wyboru wariantów trasy z uwzględnieniem modelu profilu użytkownika. Weryfikacja rozwiązania obejmie testy poprawności na kontrolowanych grafach, ocenę zgodności rekomendacji z przyjętymi ograniczeniami profilu oraz porównanie kosztu i nakładu obliczeniowego metod na ustalonym zbiorze przypadków z rzeczywistej sieci. Na małych grafach wynik metody autorskiej zostanie zestawiony z rozwiązaniem wzorcowym wyznaczonym przez przegląd dopuszczalnych ścieżek. Przeprowadzone zostaną również testy funkcjonalne aplikacji oraz analiza wpływu kompletności i rozdzielczości danych na interpretację wyników. Badania pozwolą określić zakres poprawnego działania rozwiązania, uzyskiwane kompromisy i ograniczenia zastosowanego modelu personalizacji.

Opcjonalne zdanie, tylko jeśli badanie zewnętrzne zostanie przyjęte do zakresu:

> Uzupełniająco wybrane przebiegi i parametry tras zostaną porównane z wynikami zewnętrznego planera turystycznego, z uwzględnieniem różnic danych wejściowych i reguł wyznaczania tras.

Nie deklarować udowodnienia bezpieczeństwa górskiego, rzeczywistego czasu marszu, optymalności wszystkich tras Custom, medycznej adekwatności profili ani przewagi nad wszystkimi planerami. Zaproponowane badania nie uzasadniają takich twierdzeń.

## 10. Źródła i odniesienia

- Kod: `algorithms/{dijkstra,astar,greedy,custom,weights,heuristics,common,access}.py`, `models/experience_config.py`, `services/routing_context.py`, `routes/map_routes.py`, `tests/`, `scripts/validate_routing_data.py`, `reports/OFFICIAL_TRAIL_AUDIT.md`, komponenty planera i mapy we frontendzie.
- Open-Meteo, Elevation API: https://open-meteo.com/en/docs/elevation-api — dokumentacja wskazuje Copernicus DEM GLO-90 o rozdzielczości 90 m. Rozdzielczość nie jest równoznaczna z błędem wysokości wynoszącym 90 m.
- NetworkX, `dijkstra_path`: https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.shortest_paths.weighted.dijkstra_path.html — gotowa implementacja referencyjna wyszukiwania po zadanych wagach.
- NetworkX, `all_simple_paths`: https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.simple_paths.all_simple_paths.html — enumeracja ścieżek prostych; koszt obliczeniowy uzasadnia ograniczenie do małych grafów.
- Mapa Turystyczna: https://mapa-turystyczna.pl/ — przykładowy planer do ręcznego porównania; jego interfejs udostępnia m.in. wariant turystyczny i najkrótszy.

Źródła internetowe sprawdzono 3 listopada 2026 r. Nie przeprowadzono jeszcze porównania konkretnych tras z planerem zewnętrznym.

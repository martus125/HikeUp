# Walidacja API i testy

Z katalogu `backend`, po aktywacji środowiska Python:

```powershell
python -m pip install -r requirements-dev.txt
python -B -m pytest -p no:cacheprovider -q tests
```

Z katalogu `frontend`:

```powershell
npm.cmd run lint
npm.cmd run build
```

Testy nie potrzebują PostgreSQL ani pobierania map. Repozytorium sesji jest
zastępowane magazynem w pamięci, operacje bazy są zastępowane kontrolowanymi
funkcjami, a połączenia z prawdziwą bazą są blokowane. Routing używa małych
grafów o znanych wynikach. Testy można uruchomić również z innego katalogu,
podając ścieżkę do `backend/tests`.

## Zakres

- Logowanie, odtworzenie sesji, rotacja, wygasanie i wylogowanie.
- Odmowa dostępu dla gości, CSRF, Origin i wymagany obiekt JSON.
- Właściciel profilu i ulubionych ustalany z sesji, ignorowanie obcego user_id.
- Usuwanie ulubionych z kontrolą właściciela, również warunek w zapytaniu SQL.
- Walidacja wieku, profili, preferencji, emaila, haseł, kryteriów i punktów.
- Walidacja danych ulubionych oraz istnienia i połączenia węzłów ścieżki.
- Cztery algorytmy, cztery kryteria, profile, kierunkowe przewyższenia,
  brak połączenia i preferencja odwiedzenia węzła schroniska.

Wcześniejsze testy odzyskano z commita `0ff52fe`. Dostosowano kontrakt metryk
i testy schronisk do obecnego kodu. Usunięto dwa testy wycofanej funkcji
`get_selectable_points`; nie przywracano usuniętej funkcji produktu.

## Kontrakt wejścia

- Wiek: liczba całkowita 1–120; null lub pusty tekst oznacza brak wieku.
  Frontend zamienia wartość pola liczbowego na liczbę przed wysłaniem.
- Doświadczenie: beginner, intermediate, advanced, expert, senior lub brak.
- Preferencja: wartości obsługiwane przez ROUTE_PREFERENCE_CRITERIA lub brak.
- Preferencja schronisk: wyłącznie JSON true/false.
- Email: tekst do 255 znaków, podstawowa kontrola formatu, usunięcie skrajnych
  spacji i małe litery. Hasło zachowuje oryginalne znaki, maks. 1024 znaki;
  przy rejestracji minimum 6.
- Kryterium: time, distance, elevation lub difficulty. Przy planowaniu brak
  kryterium pozwala zastosować preferencję profilu lub domyślne time.
- Ulubione: nazwy do 255 znaków; skończone parametry liczbowe 0–1000000;
  path zawiera start_id, end_id i 2–200000 node_ids. Punkty i węzły muszą
  istnieć, końce odpowiadać punktom, a kolejne węzły być połączone w grafie.
- Limit treści żądania: 16 MiB; przekroczenie daje odpowiedź JSON 413.

Błędne dane zwracają JSON z success=false i message oraz status 400.
Nieprawidłowy format treści daje 415, brak logowania 401, a naruszenie CSRF
lub Origin 403. Nieistniejący punkt planowania lub brak trasy daje 404.
Przesłane parametry liczbowe ulubionych są walidowane, ale nie są ponownie
wyliczane po stronie serwera.

## Sprawdzenie przed prezentacją

Testy automatyczne nie zastępują integracji z prawdziwą bazą i przeglądarką.
W lokalnej konfiguracji wykonaj: rejestracja → logowanie → zapis profilu →
planowanie → zapis ulubionej → odświeżenie → ponowne wyznaczenie → usunięcie
ulubionej → wylogowanie. Sprawdź też logowanie na istniejące konto, szczególnie
jeśli jego email był wcześniej zapisany wielkimi literami.

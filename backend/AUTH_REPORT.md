# Sprawozdanie: sesje i kontrola dostępu HikeUp

## Cel zmiany

Backend rozpoznaje użytkownika na podstawie sesji zapisanej w PostgreSQL.
Identyfikator `user_id` przesłany przez przeglądarkę nie wybiera właściciela
profilu, ulubionych ani profilu używanego do personalizacji trasy.

## Implementacja backendu

- `auth.py`: wspólna obsługa uwierzytelniania, dekorator `login_required`,
  ochrona CSRF i sprawdzanie nagłówka Origin dla żądań zmieniających dane.
- Po logowaniu serwer generuje losowy identyfikator sesji (32 bajty losowości).
  Ciasteczko `hikeup_session` ma `HttpOnly`, konfigurowalne `Secure` i `SameSite`.
  W bazie przechowywany jest skrót SHA-256 identyfikatora, a nie jego jawna wartość.
- Tabela `auth_sessions` zawiera skrót, klucz użytkownika, token CSRF i termin
  ważności. Klucz obcy usuwa sesje razem z kontem. Termin sprawdzany jest przy
  każdym odczycie sesji. Wygasłe rekordy są usuwane przy tworzeniu nowej sesji.
- Ponowne logowanie zastępuje bieżącą sesję nową. Wylogowanie usuwa rekord
  z bazy i ciasteczko; skopiowane wcześniej ciasteczko również przestaje działać.
- `GET /api/auth/me` zwraca aktualnego użytkownika i token CSRF. Nie zwraca
  identyfikatora sesji ani hasła. Token CSRF jest przechowywany przez React w pamięci.
- `POST /api/logout` unieważnia bieżącą sesję.
- `GET/PUT /api/profile` i `GET/POST /api/favorites` wymagają logowania.
  Właściciel operacji pochodzi wyłącznie z sesji.
- Stare adresy `/profile/<user_id>` i `/api/favorites/<user_id>` usunięto.
- `/api/route` pozostaje dostępne dla gości. Personalizacja korzysta wyłącznie
  z użytkownika rozpoznanego przez sesję, niezależnie od `user_id` w JSON.
- Żądania POST/PUT/PATCH/DELETE wymagają obiektu JSON. Przy aktywnej sesji
  wymagany jest poprawny `X-CSRF-Token`. Jeśli Origin jest obecny, musi należeć
  do skonfigurowanej listy adresów frontendu. Logowanie i rejestracja sprawdzają
  również, czy dane uwierzytelniające mają typ tekstowy.
- Odpowiedzi konta otrzymują `Cache-Control: no-store`.
- CORS dopuszcza ciasteczka tylko dla jawnie skonfigurowanych adresów.

## Implementacja frontendu

- Wspólny klient API wysyła `credentials: "include"` i token CSRF.
- Klient nie przesyła `user_id` do planowania i zapisu ulubionych.
- Profil odczytywany i aktualizowany jest przez `/api/profile`.
- Przy otwieraniu aplikacji `/api/auth/me` odtwarza stan zalogowania.
- Wylogowanie najpierw unieważnia sesję na serwerze, następnie czyści stan React.
  Błąd wylogowania jest pokazywany użytkownikowi.
- Odpowiedź 401 z chronionego API czyści lokalny stan konta i wynik trasy.
- Ulubione są pobierane z bazy po zalogowaniu. Usunięto używanie `localStorage`
  jako źródła listy ulubionych.
- Adres backendu pochodzi z `VITE_API_URL`; domyślnie jest lokalny.

## Konfiguracja i uruchomienie

Przykłady znajdują się w `backend/.env.example` i `frontend/.env.example`.
Nie zmieniano istniejącego pliku `.env` ani danych na zdalnym serwerze.

Backend lokalny:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/hikeup
FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
AUTH_SESSION_HOURS=24
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_SAMESITE=Lax
```

Frontend lokalny:

```dotenv
VITE_API_URL=http://localhost:5000
```

Wartości należy dopisać do własnych plików środowiskowych, zachowując właściwy
adres bazy. Używaj konsekwentnie localhost albo 127.0.0.1 po obu stronach.
Po zmianie konfiguracji uruchom ponownie backend i Vite.

W produkcji wymagane są HTTPS i `SESSION_COOKIE_SECURE=true`.
`FRONTEND_ORIGINS` musi zawierać dokładny adres frontendu, bez końcowego ukośnika.
Przy frontendzie i backendzie na różnych witrynach ustaw
`SESSION_COOKIE_SAMESITE=None`. Przeglądarki blokujące ciasteczka witryn trzecich
mogą nadal blokować taki układ; docelowo najlepiej udostępnić API pod tą samą
witryną co frontend (np. przez reverse proxy).
`VITE_API_URL` jest ustawiane na etapie budowania frontendu.

Tabela sesji jest tworzona przez istniejącą inicjalizację bazy przy uruchomieniu
aplikacji. Konto bazy używane do tego uruchomienia potrzebuje uprawnienia CREATE.
Zmiana nie wymaga nowych bibliotek. Sesje mają stały czas ważności, domyślnie
24 godziny; aktywność nie przedłuża go automatycznie.

## Weryfikacja

- Backend: `python -B -m pytest -p no:cacheprovider -q tests` — 77 testów
  i 40 podtestów zakończonych powodzeniem.
- Frontend: `npm.cmd run lint` — powodzenie.
- Frontend: `npm.cmd run build` — powodzenie.
- Nowe testy obejmują odmowę dostępu dla gości, zmianę właściciela przez JSON
  i query string, ignorowanie podrobionego user_id w routingu, CSRF, Origin,
  format danych, błędne logowanie, wygasanie, fałszywe ciasteczko, rotację
  i unieważnienie sesji także w drugim kliencie.
- Istniejące testy personalizacji dostosowano do tożsamości ustalanej po stronie
  serwera zamiast przez JSON żądania.

Testy uwierzytelniania używają izolowanego magazynu sesji zastępującego funkcje
bazy. Nie wykonywano migracji ani testów na produkcyjnej bazie PostgreSQL,
nie wdrażano zmian i nie wykonano ręcznego scenariusza w przeglądarce.
Po ustawieniu środowiska pozostaje sprawdzenie logowania, odświeżenia strony,
profilu, ulubionych i wylogowania w docelowej konfiguracji domen i HTTPS.

## Granice zakresu

Nie zmieniano algorytmów wyznaczania tras w ramach tej implementacji.
Nie dodawano usuwania ulubionych, resetowania hasła, limitowania prób logowania
ani zarządzania sesjami na innych urządzeniach. Wylogowanie dotyczy bieżącej sesji.
Zmiany algorytmów i danych istniejące wcześniej w katalogu roboczym zachowano.

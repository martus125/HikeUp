"""
Uzupełnia brakujące wysokości węzłów.

Skrypt:
- zachowuje już pobrane wysokości,
- pobiera tylko elevation równe 0,
- zapisuje postęp,
- może być uruchamiany wielokrotnie,
- bezpiecznie kończy działanie po osiągnięciu limitu API.
"""

import json
import os
import time
from collections import defaultdict
from pathlib import Path

import requests


BACKEND_DIR = Path(__file__).resolve().parent.parent

# Ważne: wczytujemy częściowo uzupełniony plik.
MAP_FILE = (
    BACKEND_DIR
    / "mapa"
    / "cala_mapa.json"
)

API_URL = "https://api.open-meteo.com/v1/elevation"

BATCH_SIZE = 50
REQUEST_DELAY_SECONDS = 2.0
MAX_RETRIES = 5
SAVE_EVERY_BATCHES = 20
MAX_BATCHES_PER_RUN = 100

# Grupujemy tylko praktycznie identyczne współrzędne. Zaokrąglenie do trzech
# miejsc powodowało skoki wysokości na granicach komórek o rozmiarze ~100 m.
COORDINATE_DECIMALS = 6


class ApiLimitReached(Exception):
    """Informacja o osiągnięciu limitu API."""


def as_number(value, default=None):
    """Bezpieczna zamiana wartości na liczbę."""
    try:
        if value is None:
            return default

        if isinstance(value, str) and value.strip().lower() in {
            "",
            "unknown",
            "none",
            "null",
        }:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def get_nodes_list(nodes):
    """Obsługuje nodes zapisane jako lista lub słownik."""
    if isinstance(nodes, list):
        return nodes

    if isinstance(nodes, dict):
        return list(nodes.values())

    raise TypeError(
        "Pole 'nodes' musi być listą albo słownikiem."
    )


def get_coordinates(node):
    """Pobiera współrzędne jednego węzła."""
    latitude = as_number(
        node.get("lat", node.get("latitude"))
    )

    longitude = as_number(
        node.get(
            "lng",
            node.get(
                "lon",
                node.get("longitude"),
            ),
        )
    )

    return latitude, longitude


def has_valid_elevation(node):
    """
    Sprawdza, czy węzeł ma już prawidłową wysokość.
    W Tatrach elevation = 0 traktujemy jako brak danych.
    """
    elevation = as_number(node.get("elevation"), 0)

    return elevation > 0


def coordinate_key(latitude, longitude):
    """
    Tworzy klucz dla punktów znajdujących się
    bardzo blisko siebie.
    """
    return (
        round(latitude, COORDINATE_DECIMALS),
        round(longitude, COORDINATE_DECIMALS),
    )


def split_into_batches(items, batch_size):
    """Dzieli dane na grupy."""
    for index in range(0, len(items), batch_size):
        yield items[index:index + batch_size]


def save_map(map_data):
    """
    Bezpiecznie zapisuje postęp.

    Najpierw zapisuje plik tymczasowy,
    a potem podmienia właściwy plik.
    """
    temporary_file = MAP_FILE.with_suffix(".tmp")

    with temporary_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            map_data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    os.replace(temporary_file, MAP_FILE)

    print("Zapisano aktualny postęp.")


def download_elevations(coordinate_batch):
    """
    Pobiera wysokości dla jednej grupy współrzędnych.
    """
    latitudes = [
        str(latitude)
        for latitude, _ in coordinate_batch
    ]

    longitudes = [
        str(longitude)
        for _, longitude in coordinate_batch
    ]

    response = requests.get(
        API_URL,
        params={
            "latitude": ",".join(latitudes),
            "longitude": ",".join(longitudes),
        },
        timeout=60,
    )

    if response.status_code == 429:
        raise ApiLimitReached(
            "API zwróciło kod 429 – osiągnięto limit zapytań."
        )

    response.raise_for_status()

    response_data = response.json()
    elevations = response_data.get("elevation")

    if elevations is None:
        raise ValueError(
            "Odpowiedź nie zawiera pola elevation."
        )

    if not isinstance(elevations, list):
        elevations = [elevations]

    if len(elevations) != len(coordinate_batch):
        raise ValueError(
            "Liczba wysokości nie zgadza się "
            "z liczbą współrzędnych."
        )

    return elevations


def download_with_retries(coordinate_batch):
    """
    Ponawia zapytanie przy chwilowych błędach sieciowych.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return download_elevations(coordinate_batch)

        except ApiLimitReached:
            raise

        except (
            requests.RequestException,
            ValueError,
        ) as error:
            print(
                f"Błąd próby {attempt}/{MAX_RETRIES}: "
                f"{error}"
            )

            if attempt == MAX_RETRIES:
                raise

            delay = 2 ** attempt

            print(
                f"Ponowna próba za {delay} sekund."
            )

            time.sleep(delay)

    return None


def prepare_missing_groups(nodes):
    """
    Grupuje brakujące węzły według zaokrąglonych
    współrzędnych.

    Bardzo bliskie węzły otrzymają tę samą wysokość,
    co odpowiada rozdzielczości używanego modelu terenu.
    """
    known_elevations = {}
    missing_groups = defaultdict(list)

    missing_coordinates = 0

    # Najpierw zbieramy już istniejące wysokości.
    for node in nodes:
        latitude, longitude = get_coordinates(node)

        if latitude is None or longitude is None:
            continue

        key = coordinate_key(latitude, longitude)

        if has_valid_elevation(node):
            known_elevations[key] = as_number(
                node.get("elevation")
            )

    # Potem grupujemy punkty bez wysokości.
    for node in nodes:
        if has_valid_elevation(node):
            continue

        latitude, longitude = get_coordinates(node)

        if latitude is None or longitude is None:
            missing_coordinates += 1
            continue

        key = coordinate_key(latitude, longitude)

        # Jeżeli w tej samej komórce mamy już wysokość,
        # nie wykonujemy nowego zapytania.
        if key in known_elevations:
            node["elevation"] = known_elevations[key]
        else:
            missing_groups[key].append(node)

    return missing_groups, missing_coordinates


def count_nodes(nodes):
    """Zlicza uzupełnione i brakujące wysokości."""
    completed = 0
    missing = 0

    for node in nodes:
        if has_valid_elevation(node):
            completed += 1
        else:
            missing += 1

    return completed, missing


def main():
    if not MAP_FILE.exists():
        raise FileNotFoundError(
            f"Nie znaleziono pliku: {MAP_FILE}"
        )

    print(f"Wczytywanie mapy: {MAP_FILE}")

    with MAP_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        map_data = json.load(file)

    raw_nodes = map_data.get("nodes")

    if raw_nodes is None:
        raise KeyError(
            "Plik nie zawiera pola 'nodes'."
        )

    nodes = get_nodes_list(raw_nodes)

    completed_before, missing_before = count_nodes(nodes)

    print()
    print(f"Wszystkie węzły: {len(nodes)}")
    print(
        f"Już uzupełnione: {completed_before}"
    )
    print(
        f"Jeszcze bez wysokości: {missing_before}"
    )

    missing_groups, missing_coordinates = (
        prepare_missing_groups(nodes)
    )

    # Zapisujemy wysokości skopiowane z pobliskich punktów.
    save_map(map_data)

    coordinates_to_download = list(
        missing_groups.keys()
    )

    total_batches = (
        len(coordinates_to_download)
        + BATCH_SIZE
        - 1
    ) // BATCH_SIZE

    print()
    print(
        f"Unikalne lokalizacje do pobrania: "
        f"{len(coordinates_to_download)}"
    )
    print(
        f"Liczba grup zapytań: {total_batches}"
    )
    print(
        f"Brak współrzędnych: "
        f"{missing_coordinates}"
    )
    print()

    updated_nodes = 0

    try:
        for batch_number, coordinate_batch in enumerate(
            split_into_batches(
                coordinates_to_download,
                BATCH_SIZE,
            ),
            start=1,
        ):
            # Kończymy po bezpiecznej liczbie grup.
            if batch_number > MAX_BATCHES_PER_RUN:
                print()
                print(
                    f"Osiągnięto limit "
                    f"{MAX_BATCHES_PER_RUN} grup "
                    f"dla jednego uruchomienia."
                )
                print("Zapisuję postęp i kończę.")
                break

            elevations = download_with_retries(
                coordinate_batch
            )

            for coordinates, elevation in zip(
                coordinate_batch,
                elevations,
            ):
                elevation_number = as_number(elevation)

                if elevation_number is None:
                    continue

                for node in missing_groups[coordinates]:
                    node["elevation"] = round(
                        elevation_number,
                        1,
                    )

                    updated_nodes += 1

            print(
                f"Grupa {batch_number}/{total_batches}: "
                f"uzupełniono {updated_nodes} węzłów"
            )

            if (
                batch_number
                % SAVE_EVERY_BATCHES
                == 0
            ):
                save_map(map_data)

            time.sleep(REQUEST_DELAY_SECONDS)

    except ApiLimitReached as error:
        print()
        print(error)
        print(
            "Skrypt zapisze postęp i zakończy działanie."
        )
        print(
            "Uruchom go ponownie po odnowieniu limitu."
        )

    except (
        requests.RequestException,
        ValueError,
    ) as error:
        print()
        print(f"Przerwano przez błąd: {error}")
        print(
            "Dotychczasowy postęp zostanie zapisany."
        )

    finally:
        save_map(map_data)

    completed_after, missing_after = count_nodes(nodes)

    print()
    print("Aktualny stan:")
    print(f"Uzupełnione: {completed_after}")
    print(f"Pozostało: {missing_after}")
    print(f"Plik: {MAP_FILE}")

if __name__ == "__main__":
    main()

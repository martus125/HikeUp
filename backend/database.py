import json
import os

import psycopg2
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()


def get_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("Brak DATABASE_URL w pliku .env")
    return psycopg2.connect(database_url)


def execute_schema(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            experience_level VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            height_cm INTEGER,
            experience_level VARCHAR(100),
            route_preference VARCHAR(100),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS favorite_routes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            route_name VARCHAR(255) NOT NULL,
            start_point_name VARCHAR(255),
            end_point_name VARCHAR(255),
            distance_km DOUBLE PRECISION,
            time_min INTEGER,
            elevation_gain_m INTEGER,
            criterion VARCHAR(100),
            path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    cursor.execute("ALTER TABLE favorite_routes ADD COLUMN IF NOT EXISTS start_point_name VARCHAR(255);")
    cursor.execute("ALTER TABLE favorite_routes ADD COLUMN IF NOT EXISTS end_point_name VARCHAR(255);")
    cursor.execute("ALTER TABLE favorite_routes ADD COLUMN IF NOT EXISTS distance_km DOUBLE PRECISION;")
    cursor.execute("ALTER TABLE favorite_routes ADD COLUMN IF NOT EXISTS time_min INTEGER;")
    cursor.execute("ALTER TABLE favorite_routes ADD COLUMN IF NOT EXISTS elevation_gain_m INTEGER;")
    cursor.execute("ALTER TABLE favorite_routes ADD COLUMN IF NOT EXISTS criterion VARCHAR(100);")
    cursor.execute("ALTER TABLE favorite_routes ADD COLUMN IF NOT EXISTS path TEXT;")


def init_database():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            execute_schema(cursor)


def create_user(name, email, password):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                password_hash = generate_password_hash(password)
                cursor.execute(
                    """
                    INSERT INTO users (name, email, password_hash)
                    VALUES (%s, %s, %s)
                    RETURNING id;
                    """,
                    (name, email, password_hash),
                )
                user_id = cursor.fetchone()[0]

        return {"success": True, "user_id": user_id}
    except psycopg2.errors.UniqueViolation:
        return {
            "success": False,
            "message": "Użytkownik z takim adresem email już istnieje.",
        }
    except Exception as error:
        return {
            "success": False,
            "message": f"Wystąpił błąd podczas rejestracji: {error}",
        }


def verify_user(email, password):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, name, email, password_hash, experience_level
                    FROM users
                    WHERE email = %s;
                    """,
                    (email,),
                )
                user = cursor.fetchone()

        if user is None:
            return {"success": False, "message": "Nieprawidłowy email lub hasło."}

        user_id, name, email, password_hash, experience_level = user
        if not check_password_hash(password_hash, password):
            return {"success": False, "message": "Nieprawidłowy email lub hasło."}

        return {
            "success": True,
            "user": {
                "id": user_id,
                "name": name,
                "email": email,
                "experience_level": experience_level,
            },
        }
    except Exception as error:
        return {
            "success": False,
            "message": f"Wystąpił błąd podczas logowania: {error}",
        }


def add_favorite_route(
    user_id,
    route_name,
    start_point_name,
    end_point_name,
    distance_km,
    time_min,
    elevation_gain_m,
    criterion,
    path,
):
    try:
        path_value = json.dumps(path, ensure_ascii=False) if isinstance(path, (list, dict)) else path

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO favorite_routes (
                        user_id,
                        route_name,
                        start_point_name,
                        end_point_name,
                        distance_km,
                        time_min,
                        elevation_gain_m,
                        criterion,
                        path
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        user_id,
                        route_name,
                        start_point_name,
                        end_point_name,
                        distance_km,
                        time_min,
                        elevation_gain_m,
                        criterion,
                        path_value,
                    ),
                )
                favorite_id = cursor.fetchone()[0]

        return {
            "success": True,
            "favorite_id": favorite_id,
            "message": "Trasa została dodana do ulubionych.",
        }
    except Exception as error:
        return {"success": False, "message": f"Błąd zapisu ulubionej trasy: {error}"}


def get_favorite_routes(user_id):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        route_name,
                        start_point_name,
                        end_point_name,
                        distance_km,
                        time_min,
                        elevation_gain_m,
                        criterion,
                        path,
                        created_at
                    FROM favorite_routes
                    WHERE user_id = %s
                    ORDER BY created_at DESC;
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall()

        favorites = [
            {
                "id": row[0],
                "route_name": row[1],
                "start_point_name": row[2],
                "end_point_name": row[3],
                "distance_km": row[4],
                "time_min": row[5],
                "elevation_gain_m": row[6],
                "criterion": row[7],
                "path": row[8],
                "created_at": str(row[9]),
            }
            for row in rows
        ]

        return {"success": True, "favorites": favorites}
    except Exception as error:
        return {"success": False, "message": f"Błąd pobierania ulubionych tras: {error}"}


def get_user_profile(user_id):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id, height_cm, experience_level, route_preference
                    FROM user_profiles
                    WHERE user_id = %s;
                    """,
                    (user_id,),
                )
                profile = cursor.fetchone()

        if profile:
            return {
                "user_id": profile[0],
                "height_cm": profile[1],
                "experience_level": profile[2] or "",
                "route_preference": profile[3] or "",
            }

        return {
            "user_id": user_id,
            "height_cm": "",
            "experience_level": "",
            "route_preference": "",
        }
    except Exception as error:
        return {
            "user_id": user_id,
            "height_cm": "",
            "experience_level": "",
            "route_preference": "",
            "message": f"Błąd pobierania profilu: {error}",
        }


def update_user_profile(user_id, height_cm, experience_level, route_preference):
    try:
        height_value = int(height_cm) if height_cm not in ("", None) else None

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO user_profiles (
                        user_id,
                        height_cm,
                        experience_level,
                        route_preference,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) DO UPDATE SET
                        height_cm = EXCLUDED.height_cm,
                        experience_level = EXCLUDED.experience_level,
                        route_preference = EXCLUDED.route_preference,
                        updated_at = CURRENT_TIMESTAMP;
                    """,
                    (
                        user_id,
                        height_value,
                        experience_level,
                        route_preference,
                    ),
                )

        return {
            "success": True,
            "message": "Profil użytkownika został zapisany.",
        }
    except Exception as error:
        return {
            "success": False,
            "message": f"Błąd zapisu profilu: {error}",
        }


import os
import psycopg2
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()


def get_connection():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("Brak DATABASE_URL w pliku .env")

    return psycopg2.connect(database_url)


def init_database():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            experience_level VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS trail_points (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            type VARCHAR(100),
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            elevation INTEGER
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS trail_edges (
            id SERIAL PRIMARY KEY,
            from_point_id INTEGER NOT NULL REFERENCES trail_points(id),
            to_point_id INTEGER NOT NULL REFERENCES trail_points(id),
            distance_km DOUBLE PRECISION NOT NULL,
            time_min INTEGER,
            elevation_gain INTEGER,
            difficulty VARCHAR(100),
            trail_color VARCHAR(100)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS favorite_routes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            start_point_id INTEGER NOT NULL REFERENCES trail_points(id),
            end_point_id INTEGER NOT NULL REFERENCES trail_points(id),
            route_name VARCHAR(255),
            algorithm VARCHAR(100),
            criterion VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    cur.close()
    conn.close()


def create_user(name, email, password):
    conn = get_connection()
    cur = conn.cursor()

    try:
        password_hash = generate_password_hash(password)

        cur.execute("""
            INSERT INTO users (name, email, password_hash)
            VALUES (%s, %s, %s)
            RETURNING id;
        """, (name, email, password_hash))

        user_id = cur.fetchone()[0]
        conn.commit()

        return {
            "success": True,
            "user_id": user_id
        }

    except psycopg2.errors.UniqueViolation:
        conn.rollback()

        return {
            "success": False,
            "message": "Użytkownik z takim adresem email już istnieje."
        }

    except Exception as error:
        conn.rollback()

        return {
            "success": False,
            "message": f"Wystąpił błąd podczas rejestracji: {error}"
        }

    finally:
        cur.close()
        conn.close()


def verify_user(email, password):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, name, email, password_hash, experience_level
            FROM users
            WHERE email = %s;
        """, (email,))

        user = cur.fetchone()

        if user is None:
            return {
                "success": False,
                "message": "Nieprawidłowy email lub hasło."
            }

        user_id, name, email, password_hash, experience_level = user

        if not check_password_hash(password_hash, password):
            return {
                "success": False,
                "message": "Nieprawidłowy email lub hasło."
            }

        return {
            "success": True,
            "user": {
                "id": user_id,
                "name": name,
                "email": email,
                "experience_level": experience_level
            }
        }

    except Exception as error:
        return {
            "success": False,
            "message": f"Wystąpił błąd podczas logowania: {error}"
        }

    finally:
        cur.close()
        conn.close()

# Ulubione trasy do bazy

def add_favorite_route(user_id, route_name, start_point_name, end_point_name,
                       distance_km, time_min, elevation_gain_m, criterion, path):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
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
        """, (
            user_id,
            route_name,
            start_point_name,
            end_point_name,
            distance_km,
            time_min,
            elevation_gain_m,
            criterion,
            path
        ))

        favorite_id = cur.fetchone()[0]
        conn.commit()

        return {
            "success": True,
            "favorite_id": favorite_id,
            "message": "Trasa została dodana do ulubionych."
        }

    except Exception as error:
        conn.rollback()

        return {
            "success": False,
            "message": f"Błąd zapisu ulubionej trasy: {error}"
        }

    finally:
        cur.close()
        conn.close()


def get_favorite_routes(user_id):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, route_name, start_point_name, end_point_name,
                   distance_km, time_min, elevation_gain_m, criterion, path, created_at
            FROM favorite_routes
            WHERE user_id = %s
            ORDER BY created_at DESC;
        """, (user_id,))

        rows = cur.fetchall()

        favorites = []

        for row in rows:
            favorites.append({
                "id": row[0],
                "route_name": row[1],
                "start_point_name": row[2],
                "end_point_name": row[3],
                "distance_km": row[4],
                "time_min": row[5],
                "elevation_gain_m": row[6],
                "criterion": row[7],
                "path": row[8],
                "created_at": str(row[9])
            })

        return {
            "success": True,
            "favorites": favorites
        }

    except Exception as error:
        return {
            "success": False,
            "message": f"Błąd pobierania ulubionych tras: {error}"
        }

    finally:
        cur.close()
        conn.close()
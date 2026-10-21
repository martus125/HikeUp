import { useState } from "react";

export function FavoriteRoutes({ user, favoriteRoutes, onDelete, onCalculate, loading }) {
  const [deletingId, setDeletingId] = useState(null);
  const [error, setError] = useState("");
  const userRoutes = user ? favoriteRoutes.filter((route) => route.userId === user.id) : [];

  async function handleDelete(favoriteId) {
    if (deletingId !== null) return;
    setDeletingId(favoriteId);
    setError("");
    try {
      await onDelete(favoriteId);
    } catch (failure) {
      setError(failure.message || "Nie udało się usunąć trasy.");
    } finally {
      setDeletingId(null);
    }
  }

  async function handleCalculate(route) {
    setError("");
    try {
      await onCalculate(route);
    } catch (failure) {
      setError(failure.message || "Nie udało się wyznaczyć trasy.");
    }
  }

  return (
    <div className="content-card">
      <h2>Ulubione trasy</h2>
      {user && error && <p role="alert">{error}</p>}

      {!user && <p>Zaloguj się, aby korzystać z ulubionych tras.</p>}

      {user && userRoutes.length === 0 && <p>Nie masz jeszcze zapisanych tras.</p>}

      {userRoutes.map((route) => (
        <article key={route.id} className="favorite-route">
          <h3>{route.name}</h3>
          <p>Dystans: {route.distance.toFixed(1)} km</p>
          <p>Czas: {route.time} min</p>
          <p>Przewyższenie: {route.elevation} m</p>
          <p>Kryterium: {route.criterion}</p>
          <div className="favorite-route-actions">
          <button
            type="button"
            className="favorite-route-calculate"
            disabled={loading || deletingId !== null}
            aria-label={`Wyznacz trasę ${route.name}`}
            onClick={() => handleCalculate(route)}
          >
            Wyznacz
          </button>
          <button
            type="button"
            className="favorite-route-delete"
            disabled={deletingId !== null}
            aria-label={`Usuń ${route.name} z ulubionych`}
            onClick={() => handleDelete(route.id)}
          >
            {deletingId === route.id ? "Usuwanie…" : "Usuń"}
          </button>
          </div>
        </article>
      ))}
    </div>
  );
}

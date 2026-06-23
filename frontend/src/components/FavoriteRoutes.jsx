//zakłądka z ulubionymi trasami
export function FavoriteRoutes({ user, favoriteRoutes }) {
  const userRoutes = user ? favoriteRoutes.filter((route) => route.userId === user.id) : [];

  return (
    <div className="content-card">
      <h2>Ulubione trasy</h2>

      {!user && <p>Zaloguj się, aby korzystać z ulubionych tras.</p>}

      {user && userRoutes.length === 0 && <p>Nie masz jeszcze zapisanych tras.</p>}

      {userRoutes.map((route) => (
        <article key={route.id}>
          <h3>{route.name}</h3>
          <p>Dystans: {route.distance.toFixed(1)} km</p>
          <p>Czas: {route.time} min</p>
          <p>Przewyższenie: {route.elevation} m</p>
          <p>Kryterium: {route.criterion}</p>
        </article>
      ))}
    </div>
  );
}

import { useEffect, useState } from "react";
import { fetchRouteExamples } from "../api/hikeupApi";

export function RecommendedRoutes({ onSelect, loading }) {
  const [examples, setExamples] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetchRouteExamples().then((data) => {
      if (!cancelled) setExamples(data.examples);
    }).catch((failure) => {
      if (!cancelled) setError(failure.message);
    });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="content-card">
      <h2>Polecane trasy</h2>
      {error && <p role="alert">{error}</p>}
      {!error && examples.length === 0 && <p>Ładowanie tras...</p>}
      {examples.map((example) => (
        <article key={example.id}>
          <h3>
            <button type="button" className="recommended-route-link"
              disabled={loading} onClick={() => onSelect(example)}>
              {example.start_name} → {example.end_name}
            </button>
          </h3>
          <p>{example.description}</p>
          <p>Profil przykładowy: {example.profile_name}. Kryterium: dystans.
            Preferencja schronisk wyłączona. Profil konta pozostaje bez zmian.</p>
        </article>
      ))}
    </div>
  );
}

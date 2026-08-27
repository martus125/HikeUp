const POINT_TYPE_LABELS = {
  peak: "szczyt",
  saddle: "przełęcz",
  viewpoint: "punkt widokowy",
  alpine_hut: "schronisko",
  shelter: "schronisko",
};

export function EasierRouteSuggestions({ alternatives, loading, onSelect }) {
  if (!Array.isArray(alternatives) || alternatives.length === 0) {
    return null;
  }

  return (
    <section className="easier-route-suggestions" aria-labelledby="easier-route-title">
      <div className="easier-route-heading">
        <div>
          <span className="easier-route-eyebrow">Propozycja Custom HikeUp</span>
          <h2 id="easier-route-title">Łatwiejsza trasa do podobnego celu</h2>
        </div>
        <p>
          Wybrany cel jest wymagający dla Twojego profilu. Możesz zamiast niego
          wybrać jeden z poniższych, lepiej dopasowanych wariantów.
        </p>
      </div>

      <div className="easier-route-grid">
        {alternatives.map((alternative) => {
          const route = alternative.route || {};
          const fullySuitable = route.within_safety_limits;

          return (
            <article key={alternative.id} className="easier-route-card">
              <div className="easier-route-card-title">
                <div>
                  <strong>{alternative.name}</strong>
                  <span>
                    {POINT_TYPE_LABELS[alternative.type] || alternative.type || "podobny cel"}
                    {alternative.elevation
                      ? ` · ${Number(alternative.elevation).toFixed(0)} m n.p.m.`
                      : ""}
                  </span>
                </div>
                <span className={fullySuitable ? "fit-badge" : "easier-badge"}>
                  {fullySuitable ? "zgodna z profilem" : "wyraźnie łatwiejsza"}
                </span>
              </div>

              <div className="easier-route-metrics">
                <span>{Number(route.distance_km || 0).toFixed(1)} km</span>
                <span>{Number(route.time_min || 0).toFixed(0)} min</span>
                <span>{Number(route.elevation_gain_m || 0).toFixed(0)} m podejścia</span>
                <span>trudność maks. {Number(route.max_difficulty || 0).toFixed(0)}</span>
                <span>nachylenie maks. {Number(route.max_slope_percent || 0).toFixed(1)}%</span>
                <span>dopasowanie {Number(route.profile_match_score || 0).toFixed(0)}/100</span>
              </div>

              {!fullySuitable && (
                <p className="easier-route-caution">
                  Ten wariant jest łatwiejszy od trasy do pierwotnego celu, ale
                  nadal może przekraczać część preferowanych limitów profilu.
                </p>
              )}

              <button
                type="button"
                className="primary-button easier-route-button"
                disabled={loading}
                onClick={() => onSelect(alternative)}
              >
                {loading ? "Wyznaczanie..." : "Wybierz i wyznacz tę trasę"}
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
}

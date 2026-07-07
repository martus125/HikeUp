// główny panel planowania trasy
import { getCharacteristicRoutePoints } from "../utils/points";
import { SearchInput } from "./SearchInput";

export function PlannerPanel({
  loadingGraph,
  startSearch,
  endSearch,
  activeSearch,
  filteredStartNodes,
  filteredEndNodes,
  criterion,
  routeResult,
  onStartFocus,
  onEndFocus,
  onBlurSearch,
  onStartSearchChange,
  onEndSearchChange,
  onStartSelect,
  onEndSelect,
  onCriterionChange,
  onCalculateRoute,
  onAddFavorite,
}) {
  const algorithmRoutes =
    routeResult?.routes?.length > 0 ? routeResult.routes : routeResult ? [routeResult] : [];

  return (
    <div className="planner-panel">
      {loadingGraph && <p>Ładowanie punktów mapy...</p>}

      <SearchInput
        label="A"
        value={startSearch}
        suggestions={filteredStartNodes}
        isActive={activeSearch === "start"}
        onFocus={onStartFocus}
        onBlur={onBlurSearch}
        onChange={onStartSearchChange}
        onSelect={onStartSelect}
      />

      <SearchInput
        label="B"
        value={endSearch}
        suggestions={filteredEndNodes}
        isActive={activeSearch === "end"}
        onFocus={onEndFocus}
        onBlur={onBlurSearch}
        onChange={onEndSearchChange}
        onSelect={onEndSelect}
      />

      <label className="criterion-label">
        Kryterium trasy
        <select value={criterion} onChange={(event) => onCriterionChange(event.target.value)}>
          <option value="time">Najszybsza trasa</option>
          <option value="distance">Najkrótsza trasa</option>
          <option value="difficulty">Najłatwiejsza / najmniejsze przewyższenie</option>
        </select>
      </label>

      <button className="primary-button" onClick={onCalculateRoute}>
        Wyznacz trasę
      </button>

      {routeResult && (
        <div className="route-result">
          <h2>Wyniki algorytmów</h2>

          <div className="algorithm-legend">
            {algorithmRoutes.map((route) => (
              <div key={route.algorithm} className="algorithm-legend-item">
                <span className={`algorithm-dot algorithm-${route.algorithm}`} />
                <span>{route.label || route.algorithm}</span>
              </div>
            ))}
          </div>

          <div className="algorithm-comparison">
            {algorithmRoutes.map((route) => (
              <article key={route.algorithm} className="algorithm-card">
                <h3>{route.label || route.algorithm}</h3>
                <p>Dystans: {Number(route.distance || 0).toFixed(1)} km</p>
                <p>Czas: {Number(route.time || 0).toFixed(0)} min</p>
                <p>Przewyższenie: {Number(route.elevation || 0).toFixed(0)} m</p>
                <p>Waga trasy: {Number(route.routeWeight || 0).toFixed(2)}</p>

                {route.metrics?.execution_time_ms !== undefined && (
                  <p>
                    Czas obliczeń:{" "}
                    {Number(route.metrics.execution_time_ms).toFixed(2)} ms
                  </p>
                )}

                {route.metrics?.visited_nodes !== undefined && (
                  <p>Odwiedzone węzły: {route.metrics.visited_nodes}</p>
                )}
              </article>
            ))}
          </div>

          <button className="secondary-button" onClick={onAddFavorite}>
            Dodaj trasę Dijkstry do ulubionych
          </button>

          <h3>Przebieg trasy Dijkstry</h3>

          {getCharacteristicRoutePoints(routeResult.routeNodes || []).length > 0 ? (
            <ol>
              {getCharacteristicRoutePoints(routeResult.routeNodes || []).map((node, index) => (
                <li key={node.id || `${node.name}-${index}`}>{node.name}</li>
              ))}
            </ol>
          ) : (
            <p>Brak punktów charakterystycznych na tej trasie.</p>
          )}
        </div>
      )}
    </div>
  );
}
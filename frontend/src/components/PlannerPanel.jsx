//główny panel planowania trasy
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
          <option value="elevation">Najmniejsze przewyższenie</option>
        </select>
      </label>

      <button className="primary-button" onClick={onCalculateRoute}>
        Wyznacz trasę
      </button>

      {routeResult && (
        <div className="route-result">
          <h2>Wynik trasy</h2>
          <p>Dystans: {routeResult.distance.toFixed(1)} km</p>
          <p>Czas: {routeResult.time} min</p>
          <p>Przewyższenie: {routeResult.elevation} m</p>

          <button className="secondary-button" onClick={onAddFavorite}>
            Dodaj do ulubionych
          </button>

          <h3>Przebieg trasy</h3>
          <ol>
            {routeResult.routeNodes.map((node, index) => (
              <li key={`${node.id}-${index}`}>{node.name || node.id}</li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

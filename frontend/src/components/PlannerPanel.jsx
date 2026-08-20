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
  onAlternativeSelect,
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
          <option value="elevation">Najmniejsze podejście</option>
          <option value="difficulty">Najłatwiejsza trasa</option>
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
                {route.recommendationStatus === "no_suitable_route" ? (
                  <div className="no-suitable-route">
                    <strong>
                      {route.message ||
                        "Brak trasy odpowiedniej dla wybranego profilu."}
                    </strong>

                    {route.comparisonRoute?.totals && (
                      <div className="comparison-route-summary">
                        <p>
                          Najkrótsza trasa Dijkstry jest dostępna wyłącznie
                          jako porównanie — nie jest rekomendacją Custom.
                        </p>
                        <p>
                          Dystans: {" "}
                          {Number(
                            route.comparisonRoute.totals.distance_km || 0,
                          ).toFixed(1)}{" "}
                          km
                        </p>
                        <p>
                          Maksymalne nachylenie: {" "}
                          {Number(
                            route.comparisonRoute.totals.max_slope_percent || 0,
                          ).toFixed(1)}%
                        </p>
                        <p>
                          Maksymalna trudność: {" "}
                          {Number(
                            route.comparisonRoute.totals.max_difficulty || 0,
                          ).toFixed(0)}
                        </p>
                      </div>
                    )}

                    {route.alternativeDestinations.length > 0 && (
                      <div className="alternative-destinations">
                        <h4>Łatwiejsze cele w pobliżu</h4>
                        {route.alternativeDestinations.map((alternative) => (
                          <button
                            key={alternative.id}
                            type="button"
                            className="alternative-destination"
                            onClick={() => onAlternativeSelect(alternative)}
                          >
                            <strong>{alternative.name}</strong>
                            <span>
                              {Number(alternative.route.distance_km).toFixed(1)} km,
                              {" "}
                              {Number(alternative.route.elevation_gain_m).toFixed(0)} m
                              podejścia, trudność maks. {" "}
                              {Number(alternative.route.max_difficulty).toFixed(0)}
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <>
                    <p>Dystans: {Number(route.distance || 0).toFixed(1)} km</p>
                    <p>Czas: {Number(route.time || 0).toFixed(0)} min</p>
                    <p>Przewyższenie: {Number(route.elevation || 0).toFixed(0)} m</p>
                    <p>
                      Trudność średnia: {Number(route.difficulty || 0).toFixed(2)}
                    </p>
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

                    {route.metrics?.analyzed_edges !== undefined && (
                      <p>Przeanalizowane krawędzie: {route.metrics.analyzed_edges}</p>
                    )}

                    {route.metrics?.queue_pushes !== undefined && (
                      <p>Dodania do kolejki: {route.metrics.queue_pushes}</p>
                    )}

                    {route.totals?.max_slope_percent !== undefined && (
                      <p>
                        Maksymalne nachylenie: {" "}
                        {Number(route.totals.max_slope_percent).toFixed(1)}%
                      </p>
                    )}

                    {route.totals?.shelters_count !== undefined && (
                      <p>Schroniska przy trasie: {route.totals.shelters_count}</p>
                    )}

                    {route.profileEvaluation?.experience_level && (
                      <div className="profile-evaluation">
                        <p>Profil: {route.profileEvaluation.experience_level}</p>
                        <p>
                          Dopasowanie profilu: {" "}
                          {Number(
                            route.profileEvaluation.profile_match_score || 0,
                          ).toFixed(0)}
                          /100
                        </p>
                        <p>
                          Status: trasa rekomendowana
                        </p>
                        {route.profileEvaluation.shelter_preference_enabled && (
                          <p>
                            Preferencja schronisk: {" "}
                            {route.profileEvaluation.shelter_preference_matched
                              ? "uwzględniona"
                              : "brak schroniska przy rozsądnym wariancie"}
                          </p>
                        )}
                      </div>
                    )}
                  </>
                )}

                {route.warnings?.length > 0 && (
                  <div className="route-warnings">
                    <strong>Uwagi profilu:</strong>
                    <ul>
                      {route.warnings.map((warning, index) => (
                        <li key={`${route.algorithm}-warning-${index}`}>
                          {warning}
                        </li>
                      ))}
                    </ul>
                  </div>
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

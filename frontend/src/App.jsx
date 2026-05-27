import { useEffect, useMemo, useRef, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Polyline,
  Marker,
  Popup,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./App.css";

const markerIcon = new L.Icon({
  iconUrl:
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl:
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

function App() {
  const plannerRef = useRef(null);

  const [activeTab, setActiveTab] = useState("plan");
  const [graph, setGraph] = useState(null);
  const [loadingGraph, setLoadingGraph] = useState(true);

  const [startId, setStartId] = useState("");
  const [endId, setEndId] = useState("");
  const [criterion, setCriterion] = useState("time");
  const [selectingPoint, setSelectingPoint] = useState("A");
  const [routeResult, setRouteResult] = useState(null);

  useEffect(() => {
    fetch("http://localhost:5000/api/graph")
      .then((response) => response.json())
      .then((data) => {
        setGraph(data);
        setLoadingGraph(false);
      })
      .catch((error) => {
        console.error("Błąd pobierania grafu:", error);
        setLoadingGraph(false);
      });
  }, []);
  useEffect(() => {
  window.scrollTo(0, 0);
}, []);

  const nodes = graph?.nodes || [];
  const edges = graph?.edges || [];

  const nodeById = useMemo(() => {
    const map = {};

    nodes.forEach((node) => {
      map[node.id] = node;
    });

    return map;
  }, [nodes]);

  const scrollToPlanner = () => {
    plannerRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const getWeight = (edge) => {
    if (criterion === "distance") return edge.distance_km;
    if (criterion === "elevation") return edge.elevation_gain_m || 0;
    return edge.time_min;
  };

  const buildAdjacencyList = () => {
    const adjacency = {};

    nodes.forEach((node) => {
      adjacency[node.id] = [];
    });

    edges.forEach((edge) => {
      adjacency[edge.from].push({
        to: edge.to,
        distance_km: edge.distance_km,
        time_min: edge.time_min,
        elevation_gain_m: edge.elevation_gain_m || 0,
        difficulty: edge.difficulty,
        weight: getWeight(edge),
      });

      adjacency[edge.to].push({
        to: edge.from,
        distance_km: edge.distance_km,
        time_min: edge.time_min,
        elevation_gain_m: edge.elevation_gain_m || 0,
        difficulty: edge.difficulty,
        weight: getWeight(edge),
      });
    });

    return adjacency;
  };

  const calculateRoute = () => {
    if (!startId || !endId) {
      alert("Wybierz punkt A i punkt B.");
      return;
    }

    if (startId === endId) {
      alert("Punkt A i punkt B nie mogą być takie same.");
      return;
    }

    const adjacency = buildAdjacencyList();

    const distances = {};
    const previous = {};
    const visited = new Set();

    nodes.forEach((node) => {
      distances[node.id] = Infinity;
      previous[node.id] = null;
    });

    distances[startId] = 0;

    while (visited.size < nodes.length) {
      let currentNode = null;
      let smallestDistance = Infinity;

      for (const nodeId in distances) {
        if (!visited.has(nodeId) && distances[nodeId] < smallestDistance) {
          smallestDistance = distances[nodeId];
          currentNode = nodeId;
        }
      }

      if (currentNode === null) break;
      if (currentNode === endId) break;

      visited.add(currentNode);

      adjacency[currentNode].forEach((neighbor) => {
        if (visited.has(neighbor.to)) return;

        const newDistance = distances[currentNode] + neighbor.weight;

        if (newDistance < distances[neighbor.to]) {
          distances[neighbor.to] = newDistance;
          previous[neighbor.to] = currentNode;
        }
      });
    }

    const pathIds = [];
    let current = endId;

    while (current) {
      pathIds.unshift(current);
      current = previous[current];
    }

    if (pathIds[0] !== startId) {
      alert("Nie znaleziono połączenia między tymi punktami.");
      setRouteResult(null);
      return;
    }

    let totalDistance = 0;
    let totalTime = 0;
    let totalElevation = 0;

    for (let i = 0; i < pathIds.length - 1; i++) {
      const from = pathIds[i];
      const to = pathIds[i + 1];

      const edge = edges.find(
        (item) =>
          (item.from === from && item.to === to) ||
          (item.from === to && item.to === from)
      );

      if (edge) {
        totalDistance += edge.distance_km;
        totalTime += edge.time_min;
        totalElevation += edge.elevation_gain_m || 0;
      }
    }

    const routeNodes = pathIds.map((id) => nodeById[id]);

    setRouteResult({
      pathIds,
      routeNodes,
      positions: routeNodes.map((node) => [node.lat, node.lng]),
      distance: totalDistance,
      time: totalTime,
      elevation: totalElevation,
    });
  };

  const handleMarkerClick = (nodeId) => {
    if (selectingPoint === "A") {
      setStartId(nodeId);
      setSelectingPoint("B");
    } else {
      setEndId(nodeId);
      setSelectingPoint("A");
    }
  };

  if (loadingGraph) {
    return <div className="loading-screen">Ładowanie mapy...</div>;
  }

  if (!graph) {
    return (
      <div className="loading-screen">
        Nie udało się pobrać grafu z backendu.
      </div>
    );
  }

  return (
    <>
      <section className="hero">
        <header className="navbar">
          <div className="logo">HikeUp</div>
          <button className="login-button">Zaloguj się</button>
        </header>

        <div className="hero-content">
          <h1>Odkrywaj góry z HikeUp</h1>
        </div>

        <div className="hero-button-wrapper">
          <button className="hero-button" onClick={scrollToPlanner}>
            Zaplanuj trasę
          </button>
        </div>
      </section>

      <section className="route-section" ref={plannerRef}>
        <main className="map-area">
          <MapContainer
            center={[49.23, 19.97]}
            zoom={12}
            scrollWheelZoom={true}
            className="map"
          >
            <TileLayer
              attribution="&copy; OpenStreetMap"
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {edges.map((edge, index) => {
              const from = nodeById[edge.from];
              const to = nodeById[edge.to];

              if (!from || !to) return null;

              return (
                <Polyline
                  key={`edge-${index}`}
                  positions={[
                    [from.lat, from.lng],
                    [to.lat, to.lng],
                  ]}
                  pathOptions={{
                    color: "#5c8f5a",
                    weight: 3,
                    opacity: 0.45,
                  }}
                />
              );
            })}

            {routeResult && (
              <Polyline
                positions={routeResult.positions}
                pathOptions={{
                  color: "#f26a00",
                  weight: 6,
                  opacity: 0.95,
                }}
              />
            )}

            {nodes.map((node) => (
              <Marker
                key={node.id}
                position={[node.lat, node.lng]}
                icon={markerIcon}
                eventHandlers={{
                  click: () => handleMarkerClick(node.id),
                }}
              >
                <Popup>
                  <strong>{node.name}</strong>
                  <br />
                  Wysokość: {node.elevation} m n.p.m.
                  <br />
                  Typ: {node.type}
                  <br />

                  <button
                    className="popup-button"
                    onClick={() => {
                      setStartId(node.id);
                      setSelectingPoint("B");
                    }}
                  >
                    Ustaw jako A
                  </button>

                  <button
                    className="popup-button"
                    onClick={() => {
                      setEndId(node.id);
                      setSelectingPoint("A");
                    }}
                  >
                    Ustaw jako B
                  </button>
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        </main>

        <aside className="planner-panel">
          <div className="tabs">
            <button
              className={activeTab === "plan" ? "tab active" : "tab"}
              onClick={() => setActiveTab("plan")}
            >
              Planuj
            </button>

            <button
              className={activeTab === "recommended" ? "tab active" : "tab"}
              onClick={() => setActiveTab("recommended")}
            >
              Polecane trasy
            </button>
          </div>

          {activeTab === "plan" && (
            <div className="planner-content">
              <div className="points-wrapper">
                <div className="point-row">
                  <div className="point-marker">A</div>

                  <div className="input-wrapper">
                    <select
                      className="point-select"
                      value={startId}
                      onChange={(event) => {
                        setStartId(event.target.value);
                        setSelectingPoint("B");
                      }}
                    >
                      <option value="">Punkt początkowy</option>

                      {nodes.map((node) => (
                        <option key={node.id} value={node.id}>
                          {node.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="point-row">
                  <div className="point-marker">B</div>

                  <div className="input-wrapper">
                    <select
                      className="point-select"
                      value={endId}
                      onChange={(event) => {
                        setEndId(event.target.value);
                        setSelectingPoint("A");
                      }}
                    >
                      <option value="">Punkt końcowy</option>

                      {nodes.map((node) => (
                        <option key={node.id} value={node.id}>
                          {node.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              <label className="field-label">Kryterium trasy</label>

              <select
                className="criterion-select"
                value={criterion}
                onChange={(event) => setCriterion(event.target.value)}
              >
                <option value="time">Najszybsza trasa</option>
                <option value="distance">Najkrótsza trasa</option>
                <option value="elevation">Najmniejsze przewyższenie</option>
              </select>

              <button className="route-button" onClick={calculateRoute}>
                Wyznacz trasę
              </button>

              {routeResult && (
                <div className="result-card">
                  <h2>Wynik trasy</h2>

                  <div className="result-grid">
                    <div className="result-box">
                      <span>Dystans</span>
                      <strong>{routeResult.distance.toFixed(1)} km</strong>
                    </div>

                    <div className="result-box">
                      <span>Czas</span>
                      <strong>{routeResult.time} min</strong>
                    </div>

                    <div className="result-box">
                      <span>Przewyższenie</span>
                      <strong>{routeResult.elevation} m</strong>
                    </div>
                  </div>

                  <div className="route-path">
                    <h3>Przebieg trasy</h3>

                    {routeResult.routeNodes.map((node, index) => (
                      <p key={node.id}>
                        {index + 1}. {node.name}
                      </p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === "recommended" && (
            <div className="planner-content">
              <h2 className="recommended-title">Polecane trasy</h2>

              <div className="recommended-card">
                <h3>Palenica Białczańska → Rysy</h3>
                <p>Przez Morskie Oko i Czarny Staw pod Rysami</p>
              </div>

              <div className="recommended-card">
                <h3>Kuźnice → Giewont</h3>
                <p>Przez Kalatówki, Halę Kondratową i Przełęcz Kondracką</p>
              </div>

              <div className="recommended-card">
                <h3>Kuźnice → Świnica</h3>
                <p>Przez Halę Gąsienicową i Liliowe</p>
              </div>
            </div>
          )}
        </aside>
      </section>
    </>
  );
}

export default App;
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

    const [showScrollTop, setShowScrollTop] = useState(false);

    useEffect(() => {
      const handleScroll = () => {
        if (window.scrollY > 400) {
          setShowScrollTop(true);
        } else {
          setShowScrollTop(false);
        }
      };

      window.addEventListener("scroll", handleScroll);

      return () => {
        window.removeEventListener("scroll", handleScroll);
      };
    }, []);

  const plannerRef = useRef(null);

  const [activeTab, setActiveTab] = useState("plan");
  const [graph, setGraph] = useState(null);
  const [loadingGraph, setLoadingGraph] = useState(true);

  const [startId, setStartId] = useState("");
  const [endId, setEndId] = useState("");
  const [criterion, setCriterion] = useState("time");
  const [selectingPoint, setSelectingPoint] = useState("A");
  const [routeResult, setRouteResult] = useState(null);
  const [favoriteRoutes, setFavoriteRoutes] = useState([]);

  useEffect(() => {
  window.scrollTo(0, 0);
}, []);

useEffect(() => {
  const savedFavorites = localStorage.getItem("hikeup_favorite_routes");

  if (savedFavorites) {
    setFavoriteRoutes(JSON.parse(savedFavorites));
  }
}, []);

//stany do logowania
const [showAuthModal, setShowAuthModal] = useState(false);
const [authMode, setAuthMode] = useState("login");

const [user, setUser] = useState(null);

const [loginEmail, setLoginEmail] = useState("");
const [loginPassword, setLoginPassword] = useState("");

const [registerName, setRegisterName] = useState("");
const [registerEmail, setRegisterEmail] = useState("");
const [registerPassword, setRegisterPassword] = useState("");

const [authMessage, setAuthMessage] = useState("");

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

  const handleRegister = async () => {
  if (!registerName || !registerEmail || !registerPassword) {
    setAuthMessage("Uzupełnij wszystkie pola rejestracji.");
    return;
  }

  try {
    const response = await fetch("http://localhost:5000/api/register", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: registerName,
        email: registerEmail,
        password: registerPassword,
      }),
    });

    const data = await response.json();

    if (response.ok && data.success) {
      setAuthMessage(data.message || "Konto zostało utworzone. Możesz się zalogować.");
      setAuthMode("login");
      setRegisterName("");
      setRegisterEmail("");
      setRegisterPassword("");
    } else {
      setAuthMessage(data.message || "Nie udało się zarejestrować użytkownika.");
    }
  } catch (error) {
    console.error("Błąd rejestracji:", error);
    setAuthMessage("Błąd połączenia z backendem.");
  }
};

const handleLogin = async () => {
  if (!loginEmail || !loginPassword) {
    setAuthMessage("Wpisz email i hasło.");
    return;
  }

  try {
    const response = await fetch("http://localhost:5000/api/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email: loginEmail,
        password: loginPassword,
      }),
    });

    const data = await response.json();

    if (response.ok && data.success) {
      setUser(data.user);
      setAuthMessage("");
      setShowAuthModal(false);
      setLoginEmail("");
      setLoginPassword("");
    } else {
      setAuthMessage(data.message || "Nieprawidłowy email lub hasło.");
    }
  } catch (error) {
    console.error("Błąd logowania:", error);
    setAuthMessage("Błąd połączenia z backendem.");
  }
};

const handleLogout = () => {
  setUser(null);
};

const addRouteToFavorites = async () => {
  if (!user) {
    setShowAuthModal(true);
    setAuthMode("login");
    setAuthMessage("Zaloguj się, aby dodać trasę do ulubionych.");
    return;
  }

  if (!routeResult) {
    alert("Najpierw wyznacz trasę.");
    return;
  }

  const startNode = routeResult.routeNodes[0];
  const endNode = routeResult.routeNodes[routeResult.routeNodes.length - 1];

  const favoriteData = {
    user_id: user.id,
    route_name: `${startNode.name} → ${endNode.name}`,
    start_point_name: startNode.name,
    end_point_name: endNode.name,
    distance_km: routeResult.distance,
    time_min: routeResult.time,
    elevation_gain_m: routeResult.elevation,
    criterion: criterion,
    path: routeResult.routeNodes.map((node) => node.name).join(" → "),
  };

  try {
    const response = await fetch("http://localhost:5000/api/favorites", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(favoriteData),
    });

    const data = await response.json();

    if (response.ok && data.success) {
      alert("Trasa została dodana do ulubionych i zapisana w bazie.");

      setFavoriteRoutes((prevFavorites) => [
        {
          id: data.favorite_id,
          userId: user.id,
          name: favoriteData.route_name,
          distance: favoriteData.distance_km,
          time: favoriteData.time_min,
          elevation: favoriteData.elevation_gain_m,
          criterion: favoriteData.criterion,
          path: favoriteData.path,
        },
        ...prevFavorites,
      ]);
    } else {
      alert(data.message || "Nie udało się dodać trasy do ulubionych.");
    }
  } catch (error) {
    console.error("Błąd zapisu ulubionej trasy:", error);
    alert("Błąd połączenia z backendem.");
  }
};

  return (
    <>
      <section className="hero">
        <header className="navbar">
          <div className="logo">HikeUp</div>
                {user ? (
//logowanie, a po zalogowaniu bedzie imie i wyloguj
        <button className="login-button" onClick={handleLogout}>
          {user.name} | Wyloguj
        </button>
      ) : (
        <button
          className="login-button"
          onClick={() => {
            setShowAuthModal(true);
            setAuthMode("login");
            setAuthMessage("");
          }}
        >
          Zaloguj się
        </button>

        
      )}
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
                    {showScrollTop && (
            <button
              className="scroll-top-btn"
              onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            >
              ↑
            </button>
          )}


      {showAuthModal && (
  <div className="auth-modal-overlay">
    <div className="auth-modal">
      <button
        className="auth-close"
        onClick={() => setShowAuthModal(false)}
      >
        ×
      </button>

      <div className="auth-tabs">
        <button
          className={authMode === "login" ? "auth-tab active" : "auth-tab"}
          onClick={() => {
            setAuthMode("login");
            setAuthMessage("");
          }}
        >
          Logowanie
        </button>

        <button
          className={authMode === "register" ? "auth-tab active" : "auth-tab"}
          onClick={() => {
            setAuthMode("register");
            setAuthMessage("");
          }}
        >
          Rejestracja
        </button>
      </div>

      {authMode === "login" && (
        <div className="auth-form">
          <h2>Zaloguj się</h2>
          <p>Uzyskaj dostęp do profilu i zapisanych tras.</p>

          <label>Email</label>
          <input
            type="email"
            placeholder="Wpisz email"
            value={loginEmail}
            onChange={(event) => setLoginEmail(event.target.value)}
          />

          <label>Hasło</label>
          <input
            type="password"
            placeholder="Wpisz hasło"
            value={loginPassword}
            onChange={(event) => setLoginPassword(event.target.value)}
          />

          <button className="auth-submit" onClick={handleLogin}>
            Zaloguj się
          </button>
        </div>
      )}

      {authMode === "register" && (
        <div className="auth-form">
          <h2>Utwórz konto</h2>
          <p>Zarejestruj się, aby zapisywać swoje trasy.</p>

          <label>Imię</label>
          <input
            type="text"
            placeholder="Wpisz imię"
            value={registerName}
            onChange={(event) => setRegisterName(event.target.value)}
          />

          <label>Email</label>
          <input
            type="email"
            placeholder="Wpisz email"
            value={registerEmail}
            onChange={(event) => setRegisterEmail(event.target.value)}
          />

          <label>Hasło</label>
          <input
            type="password"
            placeholder="Wpisz hasło"
            value={registerPassword}
            onChange={(event) => setRegisterPassword(event.target.value)}
          />

          <button className="auth-submit" onClick={handleRegister}>
            Zarejestruj się
          </button>
        </div>
      )}

      {authMessage && (
        <div className="auth-message">
          {authMessage}
        </div>
      )}
    </div>
  </div>
)}

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
              Polecane
            </button>

            <button
              className={activeTab === "favorites" ? "tab active" : "tab"}
              onClick={() => setActiveTab("favorites")}
            >
              Ulubione
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

                    <button className="favorite-button" onClick={addRouteToFavorites}>
                      Dodaj do ulubionych
                    </button>

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
                    {activeTab === "favorites" && (
            <div className="planner-content">
              <h2 className="recommended-title">Ulubione trasy</h2>

              {!user && (
                <p className="empty-favorites">
                  Zaloguj się, aby korzystać z ulubionych tras.
                </p>
              )}

              {user &&
                favoriteRoutes.filter((route) => route.userId === user.id).length === 0 && (
                  <p className="empty-favorites">
                    Nie masz jeszcze zapisanych tras.
                  </p>
                )}

              {user &&
                favoriteRoutes
                  .filter((route) => route.userId === user.id)
                  .map((route) => (
                    <div className="recommended-card" key={route.id}>
                      <h3>{route.name}</h3>
                      <p>Dystans: {route.distance.toFixed(1)} km</p>
                      <p>Czas: {route.time} min</p>
                      <p>Przewyższenie: {route.elevation} m</p>
                      <p>Kryterium: {route.criterion}</p>
                    </div>
                  ))}
            </div>
          )}
        </aside>
      </section>
    </>
  );
}

export default App;
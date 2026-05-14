import { useEffect, useState } from "react";
import "./App.css";

function App() {
  const [points, setPoints] = useState([]);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [criterion, setCriterion] = useState("time");
  const [route, setRoute] = useState(null);
  const [message, setMessage] = useState("");

  const [showLogin, setShowLogin] = useState(false);
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [user, setUser] = useState(null);

  useEffect(() => {
    fetch("http://127.0.0.1:5000/api/points")
      .then((response) => response.json())
      .then((data) => setPoints(data.points))
      .catch(() => {
        setMessage("Nie udało się pobrać punktów z backendu.");
      });
  }, []);

  const scrollToPlanner = () => {
    document.getElementById("planner")?.scrollIntoView({ behavior: "smooth" });
  };

  const calculateRoute = async () => {
    setMessage("");
    setRoute(null);

    if (!start || !end || !criterion) {
      setMessage("Wybierz punkt startowy, końcowy i kryterium trasy.");
      return;
    }

    const response = await fetch("http://127.0.0.1:5000/api/route", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ start, end, criterion }),
    });

    const data = await response.json();

    if (!data.success) {
      setMessage(data.message);
      return;
    }

    setRoute(data);
  };

  const loginUser = async () => {
    setMessage("");

    if (!loginEmail || !loginPassword) {
      setMessage("Podaj email i hasło.");
      return;
    }

    const response = await fetch("http://127.0.0.1:5000/api/login", {
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

    if (!data.success) {
      setMessage(data.message);
      return;
    }

    setUser(data.user);
    setShowLogin(false);
    setLoginEmail("");
    setLoginPassword("");
    setMessage("");
  };

  return (
    <div className="app">
      <section className="hero">
        <nav className="navbar">
          <div className="brand">HikeUp</div>

          <button className="login-top-button" onClick={() => setShowLogin(true)}>
            {user ? user.name : "Zaloguj się"}
          </button>
        </nav>

        <button className="plan-button" onClick={scrollToPlanner}>
          Zaplanuj trasę
        </button>
      </section>

      <section className="planner-section" id="planner">
        <aside className="planner-panel">
          <div className="tabs">
            <button className="tab active">PLANUJ</button>
            <button className="tab">SZUKAJ</button>
            <button className="tab">POLECANE TRASY</button>
          </div>

          <div className="panel-content">
            <div className="route-type">
              <span>▾</span>
              <span>Turystyczna</span>
            </div>

            <div className="point-row">
              <div className="pin-label">A</div>
              <select value={start} onChange={(e) => setStart(e.target.value)}>
                <option value="">Ustaw początek</option>
                {points.map((point) => (
                  <option key={point.id} value={point.id}>
                    {point.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="point-row">
              <div className="pin-label">B</div>
              <select value={end} onChange={(e) => setEnd(e.target.value)}>
                <option value="">Dodaj kolejny punkt</option>
                {points.map((point) => (
                  <option key={point.id} value={point.id}>
                    {point.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="criterion-box">
              <label>Kryterium trasy</label>
              <select
                value={criterion}
                onChange={(e) => setCriterion(e.target.value)}
              >
                <option value="time">Najszybsza trasa</option>
                <option value="distance">Najkrótsza trasa</option>
                <option value="difficulty">Najłatwiejsza trasa</option>
              </select>
            </div>

            <button className="calculate-button" onClick={calculateRoute}>
              Wyznacz trasę
            </button>

            {message && <p className="message">{message}</p>}

            {route && (
              <div className="route-result">
                <h3>Wynik trasy</h3>

                <div className="result-grid">
                  <div>
                    <span>Dystans</span>
                    <strong>{route.total_distance_km} km</strong>
                  </div>

                  <div>
                    <span>Czas</span>
                    <strong>{route.total_time_min} min</strong>
                  </div>

                  <div>
                    <span>Przewyższenie</span>
                    <strong>{route.total_elevation_gain_m} m</strong>
                  </div>

                  <div>
                    <span>Koszt</span>
                    <strong>{route.route_weight}</strong>
                  </div>
                </div>

                <h4>Przebieg trasy</h4>
                <ol className="route-list">
                  {route.path.map((point) => (
                    <li key={point.id}>{point.name}</li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        </aside>

        <section className="map-area">
          <div className="map-placeholder">
            <div className="map-label">Mapa szlaków</div>

            {route && (
              <div className="route-line-card">
                <strong>Wyznaczona trasa</strong>
                <p>{route.path.map((point) => point.name).join(" → ")}</p>
              </div>
            )}
          </div>
        </section>
      </section>

      {showLogin && (
        <div className="modal-overlay">
          <div className="login-modal">
            <button
              className="close-button"
              onClick={() => setShowLogin(false)}
            >
              ×
            </button>

            <h2>Logowanie</h2>
            <p>Zaloguj się, aby korzystać z funkcji użytkownika.</p>

            <label>Email</label>
            <input
              type="email"
              placeholder="np. marta@email.com"
              value={loginEmail}
              onChange={(e) => setLoginEmail(e.target.value)}
            />

            <label>Hasło</label>
            <input
              type="password"
              placeholder="Wpisz hasło"
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
            />

            <button className="calculate-button" onClick={loginUser}>
              Zaloguj
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
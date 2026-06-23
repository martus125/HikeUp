import { useEffect, useMemo, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";
import "./App.css";

import { fetchRoute, loginUser, registerUser, saveFavoriteRoute } from "./api/hikeupApi";
import { AuthModal } from "./components/AuthModal";
import { FavoriteRoutes } from "./components/FavoriteRoutes";
import { Header } from "./components/Header";
import { PlannerPanel } from "./components/PlannerPanel";
import { RecommendedRoutes } from "./components/RecommendedRoutes";
import { RouteMap } from "./components/RouteMap";
import { Tabs } from "./components/Tabs";
import { useMapData } from "./hooks/useMapData";
import { useScrollTopButton } from "./hooks/useScrollTopButton";
import {
  createPointMap,
  filterPoints,
  getPointName,
  getUniqueSortedPoints,
  normalizePointList,
} from "./utils/points";

function App() {
  const plannerRef = useRef(null);
  const showScrollTop = useScrollTopButton();
  const { graph, searchPoints, loadingGraph } = useMapData();

  const [activeTab, setActiveTab] = useState("plan");
  const [startId, setStartId] = useState("");
  const [endId, setEndId] = useState("");
  const [startSearch, setStartSearch] = useState("");
  const [endSearch, setEndSearch] = useState("");
  const [activeSearch, setActiveSearch] = useState(null);
  const [criterion, setCriterion] = useState("time");
  const [selectingPoint, setSelectingPoint] = useState("A");
  const [routeResult, setRouteResult] = useState(null);
  const [favoriteRoutes, setFavoriteRoutes] = useState([]);

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
    window.scrollTo(0, 0);
  }, []);

  useEffect(() => {
    const savedFavorites = localStorage.getItem("hikeup_favorite_routes");
    if (savedFavorites) {
      setFavoriteRoutes(JSON.parse(savedFavorites));
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("hikeup_favorite_routes", JSON.stringify(favoriteRoutes));
  }, [favoriteRoutes]);

  const nodes = useMemo(() => normalizePointList(graph.nodes), [graph.nodes]);
  const edges = useMemo(
    () => (Array.isArray(graph.edges) ? graph.edges : Object.values(graph.edges || {})),
    [graph.edges],
  );
  const nodeById = useMemo(() => createPointMap(nodes), [nodes]);
  const pointById = useMemo(() => createPointMap(searchPoints), [searchPoints]);
  const allSearchPoints = useMemo(() => {
    const source = searchPoints.length > 0 ? searchPoints : nodes;
    return getUniqueSortedPoints(source);
  }, [searchPoints, nodes]);

  const filteredStartNodes = useMemo(
    () => filterPoints(allSearchPoints, startSearch),
    [allSearchPoints, startSearch],
  );
  const filteredEndNodes = useMemo(
    () => filterPoints(allSearchPoints, endSearch),
    [allSearchPoints, endSearch],
  );

  function openLoginModal(message = "") {
    setShowAuthModal(true);
    setAuthMode("login");
    setAuthMessage(message);
  }

  function closeAuthModal() {
    setShowAuthModal(false);
    setAuthMessage("");
  }

  function handleModeChange(mode) {
    setAuthMode(mode);
    setAuthMessage("");
  }

  function selectStartPoint(point) {
    setStartId(point.id);
    setStartSearch(getPointName(point));
    setActiveSearch(null);
    setSelectingPoint("B");
  }

  function selectEndPoint(point) {
    setEndId(point.id);
    setEndSearch(getPointName(point));
    setActiveSearch(null);
    setSelectingPoint("A");
  }

  function handleMarkerClick(nodeId) {
    const node = pointById[nodeId] || nodeById[nodeId];
    if (!node) return;

    if (selectingPoint === "A") {
      selectStartPoint(node);
    } else {
      selectEndPoint(node);
    }
  }

  function scrollToPlanner() {
    plannerRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  async function calculateRoute() {
    if (!startId || !endId) {
      alert("Wybierz punkt A i punkt B z listy podpowiedzi albo klikając marker na mapie.");
      return;
    }

    if (startId === endId) {
      alert("Punkt A i punkt B nie mogą być takie same.");
      return;
    }

    try {
      const data = await fetchRoute({ start: startId, end: endId, criterion });
      const routeNodes = data.path || [];
      const positionsSource =
        Array.isArray(data.positions) && data.positions.length > 0 ? data.positions : routeNodes;

      const positions = positionsSource
        .map((point) => {
          if (Array.isArray(point)) {
            return [Number(point[0]), Number(point[1])];
          }

          return [
            Number(point.lat ?? point.latitude),
            Number(point.lng ?? point.lon ?? point.longitude),
          ];
        })
        .filter(([lat, lng]) => Number.isFinite(lat) && Number.isFinite(lng));

      setRouteResult({
        pathIds: data.path_ids || routeNodes.map((node) => node.id),
        routeNodes,
        positions,
        distance: data.total_distance_km || 0,
        time: data.total_time_min || 0,
        elevation: data.total_elevation_gain_m || 0,
        criterion: data.criterion,
      });
    } catch (error) {
      console.error("Błąd wyznaczania trasy:", error);
      alert(error.message || "Nie udało się wyznaczyć trasy.");
      setRouteResult(null);
    }
  }

  async function handleRegister() {
    if (!registerName || !registerEmail || !registerPassword) {
      setAuthMessage("Uzupełnij wszystkie pola rejestracji.");
      return;
    }

    try {
      const data = await registerUser({
        name: registerName,
        email: registerEmail,
        password: registerPassword,
      });

      setAuthMessage(data.message || "Konto zostało utworzone. Możesz się zalogować.");
      setAuthMode("login");
      setRegisterName("");
      setRegisterEmail("");
      setRegisterPassword("");
    } catch (error) {
      console.error("Błąd rejestracji:", error);
      setAuthMessage(error.message || "Błąd połączenia z backendem.");
    }
  }

  async function handleLogin() {
    if (!loginEmail || !loginPassword) {
      setAuthMessage("Wpisz email i hasło.");
      return;
    }

    try {
      const data = await loginUser({ email: loginEmail, password: loginPassword });
      setUser(data.user);
      setAuthMessage("");
      setShowAuthModal(false);
      setLoginEmail("");
      setLoginPassword("");
    } catch (error) {
      console.error("Błąd logowania:", error);
      setAuthMessage(error.message || "Nieprawidłowy email lub hasło.");
    }
  }

  function handleLogout() {
    setUser(null);
  }

  async function addRouteToFavorites() {
    if (!user) {
      openLoginModal("Zaloguj się, aby dodać trasę do ulubionych.");
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
      criterion,
      path: routeResult.routeNodes.map((node) => node.name).join(" → "),
    };

    try {
      const data = await saveFavoriteRoute(favoriteData);
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
    } catch (error) {
      console.error("Błąd zapisu ulubionej trasy:", error);
      alert(error.message || "Nie udało się dodać trasy do ulubionych.");
    }
  }

  return (
    <>
      <Header
        user={user}
        onLoginClick={() => openLoginModal()}
        onLogout={handleLogout}
        onPlanClick={scrollToPlanner}
      />

      {showScrollTop && (
        <button
          className="scroll-top-button"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        >
          ↑
        </button>
      )}

      {showAuthModal && (
        <AuthModal
          authMode={authMode}
          authMessage={authMessage}
          loginEmail={loginEmail}
          loginPassword={loginPassword}
          registerName={registerName}
          registerEmail={registerEmail}
          registerPassword={registerPassword}
          onClose={closeAuthModal}
          onModeChange={handleModeChange}
          onLoginEmailChange={setLoginEmail}
          onLoginPasswordChange={setLoginPassword}
          onRegisterNameChange={setRegisterName}
          onRegisterEmailChange={setRegisterEmail}
          onRegisterPasswordChange={setRegisterPassword}
          onLogin={handleLogin}
          onRegister={handleRegister}
        />
      )}

      <main ref={plannerRef} className="main-layout">
        <div className="map-wrapper">
          <RouteMap
            nodes={searchPoints}
            edges={edges}
            nodeById={nodeById}
            routeResult={routeResult}
            onMarkerClick={handleMarkerClick}
            onSetStart={selectStartPoint}
            onSetEnd={selectEndPoint}
          />
        </div>

        <section className="side-panel">
          <Tabs activeTab={activeTab} onTabChange={setActiveTab} />

          {activeTab === "plan" && (
            <PlannerPanel
              loadingGraph={loadingGraph}
              startSearch={startSearch}
              endSearch={endSearch}
              activeSearch={activeSearch}
              filteredStartNodes={filteredStartNodes}
              filteredEndNodes={filteredEndNodes}
              criterion={criterion}
              routeResult={routeResult}
              onStartFocus={() => {
                setActiveSearch("start");
                setSelectingPoint("A");
              }}
              onEndFocus={() => {
                setActiveSearch("end");
                setSelectingPoint("B");
              }}
              onBlurSearch={() => setTimeout(() => setActiveSearch(null), 150)}
              onStartSearchChange={(value) => {
                setStartSearch(value);
                setStartId("");
                setActiveSearch("start");
              }}
              onEndSearchChange={(value) => {
                setEndSearch(value);
                setEndId("");
                setActiveSearch("end");
              }}
              onStartSelect={selectStartPoint}
              onEndSelect={selectEndPoint}
              onCriterionChange={setCriterion}
              onCalculateRoute={calculateRoute}
              onAddFavorite={addRouteToFavorites}
            />
          )}

          {activeTab === "recommended" && <RecommendedRoutes />}
          {activeTab === "favorites" && <FavoriteRoutes user={user} favoriteRoutes={favoriteRoutes} />}
        </section>
      </main>
    </>
  );
}

export default App;

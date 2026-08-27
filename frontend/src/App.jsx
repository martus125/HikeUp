import { useEffect, useMemo, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";
import "./App.css";

import {
  fetchRoute,
  getUserProfile,
  loginUser,
  registerUser,
  saveFavoriteRoute,
  updateUserProfile,
} from "./api/hikeupApi";
import { AuthModal } from "./components/AuthModal";
import { EasierRouteSuggestions } from "./components/EasierRouteSuggestions";
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
  const [showUserPanel, setShowUserPanel] = useState(false);
  const [profile, setProfile] = useState({
    age_years: "",
    experience_level: "",
    route_preference: "",
    prefer_shelters: false,
  });
  const [profileMessage, setProfileMessage] = useState("");

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
  const [routeResult, setRouteResult] = useState(null);
  const [loadingRoutes, setLoadingRoutes] = useState(false);
  const [favoriteRoutes, setFavoriteRoutes] = useState(() => {
    const savedFavorites = localStorage.getItem("hikeup_favorite_routes");
    if (!savedFavorites) return [];

    try {
      const parsedFavorites = JSON.parse(savedFavorites);
      return Array.isArray(parsedFavorites) ? parsedFavorites : [];
    } catch {
      return [];
    }
  });

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
    localStorage.setItem("hikeup_favorite_routes", JSON.stringify(favoriteRoutes));
  }, [favoriteRoutes]);

  const nodes = useMemo(() => normalizePointList(graph.nodes), [graph.nodes]);
  const edges = useMemo(
    () => (Array.isArray(graph.edges) ? graph.edges : Object.values(graph.edges || {})),
    [graph.edges],
  );
  const nodeById = useMemo(() => createPointMap(nodes), [nodes]);
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
  }

  function selectEndPoint(point) {
    setEndId(point.id);
    setEndSearch(getPointName(point));
    setActiveSearch(null);
  }

  function handleMarkerClick() {}

  function scrollToPlanner() {
    plannerRef.current?.scrollIntoView({ behavior: "smooth" });
  }
  // Dobieranie kryterium trasy do preferencji użytkownika.
  // Stare angielskie wartości pozostają obsługiwane dla istniejących profili.
  function getCriterionFromPreference(routePreference) {
    if (routePreference === "najkrótsza" || routePreference === "shortest") {
      return "distance";
    }

    if (routePreference === "najszybsza" || routePreference === "fastest") {
      return "time";
    }

    if (routePreference === "najłatwiejsza" || routePreference === "easy") {
      return "difficulty";
    }

    if (routePreference === "najmniejsze przewyższenie") {
      return "elevation";
    }

    return criterion;
  }

  async function calculateRoute(options = {}) {
    const selectedEndId = options?.endOverride || endId;

    if (!startId || !selectedEndId) {
      alert("Wybierz punkt A i punkt B z listy podpowiedzi albo klikając marker na mapie.");
      return;
    }

    if (startId === selectedEndId) {
      alert("Punkt A i punkt B nie mogą być takie same.");
      return;
    }

    setLoadingRoutes(true);

    function normalizePositions(positionsSource, fallbackNodes = []) {
      const source =
        Array.isArray(positionsSource) && positionsSource.length > 0
          ? positionsSource
          : fallbackNodes;

      return source
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
    }

    function normalizeAlgorithmRoute(route) {
      const routeNodes = route.path || [];

      return {
        algorithm: route.algorithm || "dijkstra",
        label: route.label || route.algorithm || "Trasa",
        pathIds: route.path_ids || routeNodes.map((node) => node.id),
        routeNodes,
        positions: normalizePositions(route.positions, routeNodes),
        distance: Number(route.total_distance_km || 0),
        time: Number(route.total_time_min || 0),
        elevation: Number(route.total_elevation_gain_m || 0),
        difficulty: Number(route.total_difficulty || 0),
        routeWeight: Number(route.route_weight || 0),
        criterion: route.criterion || criterion,
        metrics: route.metrics || {},
        totals: route.totals || {},
        profileEvaluation: route.profile_evaluation || null,
        warnings: Array.isArray(route.warnings) ? route.warnings : [],
        recommendationStatus:
          route.recommendation_status || "recommended",
        message: route.message || "",
        alternativeDestinations: Array.isArray(route.alternative_destinations)
          ? route.alternative_destinations
          : [],
      };
    }

    try {
      const routeCriterion = criterion;

      const userId = user?.id || null;

      console.log("Wyznaczanie tras...", {
        startId,
        endId: selectedEndId,
        criterion: routeCriterion,
        userId,
      });

      const data = await fetchRoute({
        start: startId,
        end: selectedEndId,
        criterion: routeCriterion,
        user_id: userId,
      });

      console.log("ODPOWIEDŹ BACKENDU:", data);
      console.log("ALGORYTMY:", data.routes?.map((route) => route.algorithm));
      console.log("BŁĘDY ALGORYTMÓW:", data.algorithm_errors);

      const routes = Array.isArray(data.routes)
        ? data.routes
            .map(normalizeAlgorithmRoute)
            .filter((route) => route.positions.length > 1)
        : [normalizeAlgorithmRoute(data)].filter(
            (route) => route.positions.length > 1,
          );

      if (routes.length === 0) {
        throw new Error("Backend nie zwrócił poprawnej geometrii trasy.");
      }

      const primaryRoute =
        routes.find((route) => route.algorithm === "dijkstra") || routes[0];

      setRouteResult({
        ...primaryRoute,
        routes,
        pathIds: primaryRoute.pathIds,
        routeNodes: primaryRoute.routeNodes,
        positions: primaryRoute.positions,
        distance: primaryRoute.distance,
        time: primaryRoute.time,
        elevation: primaryRoute.elevation,
        difficulty: primaryRoute.difficulty,
        routeWeight: primaryRoute.routeWeight,
        criterion: routeCriterion,
      });
    } catch (error) {
      console.error("Błąd wyznaczania trasy:", error);
      alert(error.message || "Nie udało się wyznaczyć trasy.");
      setRouteResult(null);
    } finally {
      setLoadingRoutes(false);
    }
  }

  async function selectAndCalculateAlternative(point) {
    selectEndPoint(point);
    await calculateRoute({ endOverride: point.id });
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
    setShowUserPanel(false);
    setProfile({
      age_years: "",
      experience_level: "",
      route_preference: "",
      prefer_shelters: false,
    });
    setProfileMessage("");
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


  async function loadUserProfile() {
    if (!user) return;

    try {
      const data = await getUserProfile(user.id);

      setProfile({
        age_years: data.age_years || "",
        experience_level: data.experience_level || "",
        route_preference: data.route_preference || "",
        prefer_shelters: Boolean(data.prefer_shelters),
      });

      if (data.route_preference) {
        setCriterion(
          getCriterionFromPreference(data.route_preference),
        );
      }
    } catch (error) {
      console.error("Błąd pobierania profilu:", error);
      setProfileMessage("Nie udało się pobrać profilu.");
    }
  }

  async function handleSaveProfile(event) {
    event.preventDefault();

    if (!user) return;

    try {
      const data = await updateUserProfile(user.id, {
        age_years: profile.age_years,
        experience_level: profile.experience_level,
        route_preference: profile.route_preference,
        prefer_shelters: profile.prefer_shelters,
      });

      setCriterion(getCriterionFromPreference(profile.route_preference));
      alert(data.message || "Profil zaktualizowany!");
      setShowUserPanel(false);
      setProfileMessage("");
    } catch (error) {
      console.error("Błąd zapisu profilu:", error);
      alert(error.message || "Błąd aktualizacji profilu");
      setProfileMessage(error.message || "Nie udało się zapisać profilu.");
    }
  }

  function openUserPanel() {
    setShowUserPanel(true);
    setProfileMessage("");
    loadUserProfile();
  }

  return (
    <>
      <Header
        user={user}
        onLoginClick={() => openLoginModal()}
        onLogout={handleLogout}
        onPlanClick={scrollToPlanner}
        onUserPanelClick={openUserPanel}
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

      {showUserPanel && user && (
        <div className="modal-backdrop">
          <div className="auth-modal">
            <button
              className="modal-close"
              onClick={() => {
                setShowUserPanel(false);
                setProfileMessage("");
              }}
            >
              ×
            </button>

            <h2>Panel użytkownika</h2>

            <form className="auth-form" onSubmit={handleSaveProfile}>
              <label>
                Wiek (lata):
                <input
                  type="number"
                  min="1"
                  max="120"
                  value={profile.age_years}
                  onChange={(event) =>
                    setProfile({
                      ...profile,
                      age_years: event.target.value,
                    })
                  }
                  placeholder="np. 25"
                />
              </label>

              <label>
                Poziom doświadczenia:
                <select
                  value={profile.experience_level}
                  onChange={(event) =>
                    setProfile({
                      ...profile,
                      experience_level: event.target.value,
                    })
                  }
                >
                  <option value="">-- Wybierz --</option>
                  <option value="beginner">Początkujący</option>
                  <option value="intermediate">Średniozaawansowany</option>
                  <option value="advanced">Zaawansowany</option>
                  <option value="expert">Ekspert</option>
                  <option value="senior">Senior</option>
                </select>
                <p className="profile-field-help">
                  Bez ręcznego wyboru poziom zostanie dobrany z wieku: poniżej
                  20 lat — początkujący, 20–64 — średniozaawansowany, od 65 lat
                  — senior. Poziomy zaawansowany i ekspert wybiera się ręcznie.
                </p>
              </label>

              <label>
                Preferowana trasa:
                <select
                  value={profile.route_preference}
                  onChange={(event) =>
                    setProfile({
                      ...profile,
                      route_preference: event.target.value,
                    })
                  }
                >
                  <option value="">-- Wybierz --</option>
                  <option value="najkrótsza">Najkrótsza</option>
                  <option value="najszybsza">Najszybsza</option>
                  <option value="najłatwiejsza">Najłatwiejsza</option>
                  <option value="najmniejsze przewyższenie">
                    Najmniejsze przewyższenie
                  </option>
                </select>
              </label>

              <label className="profile-checkbox">
                <input
                  type="checkbox"
                  checked={profile.prefer_shelters}
                  onChange={(event) =>
                    setProfile({
                      ...profile,
                      prefer_shelters: event.target.checked,
                    })
                  }
                />
                <span>Chcę trasę przebiegającą przy schroniskach</span>
              </label>
              <p className="profile-field-help">
                Custom HikeUp uwzględni schronisko do 350 m od szlaku tylko
                wtedy, gdy wariant pozostaje bezpieczny i jest najwyżej o 10%
                dłuższy od najkrótszej akceptowalnej trasy.
              </p>

              <button type="submit" className="auth-submit">
                Zapisz profil
              </button>
            </form>

            {profileMessage && <p className="auth-message">{profileMessage}</p>}
          </div>
        </div>
      )}

      <main ref={plannerRef} className="main-layout">
        <div className="map-column">
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

          <EasierRouteSuggestions
            alternatives={
              routeResult?.routes?.find(
                (route) =>
                  route.algorithm === "custom_hikeup" &&
                  route.recommendationStatus === "difficult_route",
              )?.alternativeDestinations || []
            }
            loading={loadingRoutes}
            onSelect={selectAndCalculateAlternative}
          />
        </div>

        <section className="side-panel">
          <Tabs activeTab={activeTab} onTabChange={setActiveTab} />

          {activeTab === "plan" && (
            <PlannerPanel
              loadingGraph={loadingGraph}
              loadingRoutes={loadingRoutes}
              startSearch={startSearch}
              endSearch={endSearch}
              activeSearch={activeSearch}
              filteredStartNodes={filteredStartNodes}
              filteredEndNodes={filteredEndNodes}
              criterion={criterion}
              routeResult={routeResult}
              onStartFocus={() => {
                setActiveSearch("start");
              }}
              onEndFocus={() => {
                setActiveSearch("end");
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
              onCalculateRoute={() => calculateRoute()}
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

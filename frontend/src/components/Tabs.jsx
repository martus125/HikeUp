//przełączanie zakładek
export function Tabs({ activeTab, onTabChange }) {
  return (
    <div className="tabs">
      <button className={activeTab === "plan" ? "active" : ""} onClick={() => onTabChange("plan")}>
        Planuj
      </button>
      <button
        className={activeTab === "recommended" ? "active" : ""}
        onClick={() => onTabChange("recommended")}
      >
        Polecane
      </button>
      <button
        className={activeTab === "favorites" ? "active" : ""}
        onClick={() => onTabChange("favorites")}
      >
        Ulubione
      </button>
    </div>
  );
}

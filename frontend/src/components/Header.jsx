//góny pasek
export function Header({ user, onLoginClick, onLogout, onPlanClick }) {
  return (
    <section className="hero">
      <header className="navbar">
        <div className="logo">HikeUp</div>
        {user ? (
          <button className="login-button" onClick={onLogout}>
            {user.name} | Wyloguj
          </button>
        ) : (
          <button className="login-button" onClick={onLoginClick}>
            Zaloguj się
          </button>
        )}
      </header>

      <div className="hero-content">
        <h1>Odkrywaj góry z HikeUp</h1>
      </div>

      <div className="hero-button-wrapper">
        <button className="hero-button" onClick={onPlanClick}>
          Zaplanuj trasę
        </button>
      </div>
    </section>
  );
}

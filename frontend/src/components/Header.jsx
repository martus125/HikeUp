// główny pasek
export function Header({
  user,
  onLoginClick,
  onLogout,
  onPlanClick,
  onUserPanelClick,
}) {
  return (
    <section className="hero">
      <header className="navbar">
        <div className="logo">HikeUp</div>

        {user ? (
          <div className="user-menu">
            <button className="login-button" onClick={onUserPanelClick}>
              Panel użytkownika
            </button>

            <button className="login-button" onClick={onLogout}>
              {user.name} | Wyloguj
            </button>
          </div>
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

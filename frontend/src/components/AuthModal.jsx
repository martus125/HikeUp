//logowanie i reejstracja
export function AuthModal({
  authMode,
  authMessage,
  loginEmail,
  loginPassword,
  registerName,
  registerEmail,
  registerPassword,
  onClose,
  onModeChange,
  onLoginEmailChange,
  onLoginPasswordChange,
  onRegisterNameChange,
  onRegisterEmailChange,
  onRegisterPasswordChange,
  onLogin,
  onRegister,
}) {
  return (
    <div className="modal-backdrop">
      <div className="auth-modal">
        <button className="modal-close" onClick={onClose}>
          ×
        </button>

        <div className="auth-tabs">
          <button
            className={authMode === "login" ? "active" : ""}
            onClick={() => onModeChange("login")}
          >
            Logowanie
          </button>
          <button
            className={authMode === "register" ? "active" : ""}
            onClick={() => onModeChange("register")}
          >
            Rejestracja
          </button>
        </div>

        {authMode === "login" ? (
          <div className="auth-form">
            <h2>Zaloguj się</h2>
            <p>Uzyskaj dostęp do profilu i zapisanych tras.</p>
            <input
              type="email"
              placeholder="Email"
              value={loginEmail}
              onChange={(event) => onLoginEmailChange(event.target.value)}
            />
            <input
              type="password"
              placeholder="Hasło"
              value={loginPassword}
              onChange={(event) => onLoginPasswordChange(event.target.value)}
            />
            <button onClick={onLogin}>Zaloguj się</button>
          </div>
        ) : (
          <div className="auth-form">
            <h2>Utwórz konto</h2>
            <p>Zarejestruj się, aby zapisywać swoje trasy.</p>
            <input
              type="text"
              placeholder="Imię"
              value={registerName}
              onChange={(event) => onRegisterNameChange(event.target.value)}
            />
            <input
              type="email"
              placeholder="Email"
              value={registerEmail}
              onChange={(event) => onRegisterEmailChange(event.target.value)}
            />
            <input
              type="password"
              placeholder="Hasło"
              value={registerPassword}
              onChange={(event) => onRegisterPasswordChange(event.target.value)}
            />
            <button onClick={onRegister}>Zarejestruj się</button>
          </div>
        )}

        {authMessage && <p className="auth-message">{authMessage}</p>}
      </div>
    </div>
  );
}

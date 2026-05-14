const API_URL = "http://127.0.0.1:5000";

const registerButton = document.getElementById("registerButton");
const loginButton = document.getElementById("loginButton");
const authMessage = document.getElementById("authMessage");

if (registerButton) {
    registerButton.addEventListener("click", registerUser);
}

if (loginButton) {
    loginButton.addEventListener("click", loginUser);
}

async function registerUser() {
    const name = document.getElementById("registerName").value.trim();
    const email = document.getElementById("registerEmail").value.trim();
    const password = document.getElementById("registerPassword").value;

    if (!name || !email || !password) {
        showMessage("Uzupełnij wszystkie pola.", "error");
        return;
    }

    try {
        const response = await fetch(`${API_URL}/api/register`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                name: name,
                email: email,
                password: password
            })
        });

        const data = await response.json();

        if (!data.success) {
            showMessage(data.message, "error");
            return;
        }

        showMessage(data.message, "success");

        setTimeout(() => {
            window.location.href = "login.html";
        }, 1200);

    } catch (error) {
        showMessage("Nie udało się połączyć z serwerem.", "error");
    }
}

async function loginUser() {
    const email = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value;

    if (!email || !password) {
        showMessage("Podaj email i hasło.", "error");
        return;
    }

    try {
        const response = await fetch(`${API_URL}/api/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                email: email,
                password: password
            })
        });

        const data = await response.json();

        if (!data.success) {
            showMessage(data.message, "error");
            return;
        }

        localStorage.setItem("hikeupUser", JSON.stringify(data.user));

        showMessage("Zalogowano pomyślnie.", "success");

        setTimeout(() => {
            window.location.href = "index.html";
        }, 1000);

    } catch (error) {
        showMessage("Nie udało się połączyć z serwerem.", "error");
    }
}

function showMessage(message, type) {
    authMessage.textContent = message;
    authMessage.className = `auth-message ${type}`;
}
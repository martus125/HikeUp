const routeButton = document.getElementById("routeButton");
const routeResult = document.getElementById("routeResult");
const startSelect = document.getElementById("start");
const endSelect = document.getElementById("end");

const API_URL = "http://127.0.0.1:5000";

let map;
let routeLine;
let markers = [];

initializeMap();
loadPoints();

/*mapa*/

function initializeMap() {
    map = L.map("map").setView([49.25, 20.01], 12);

    L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
        maxZoom: 19,
        attribution: "© OpenStreetMap contributors © CARTO"
    }).addTo(map);
}

async function loadPoints() {
    try {
        const response = await fetch(`${API_URL}/api/points`);
        const data = await response.json();

        if (!data.success) {
            showPointsError();
            return;
        }

        fillSelect(startSelect, data.points);
        fillSelect(endSelect, data.points);
        showAllPointsOnMap(data.points);

    } catch (error) {
        showPointsError();
    }
}

function fillSelect(selectElement, points) {
    selectElement.innerHTML = '<option value="">Wybierz punkt</option>';

    points.forEach(point => {
        const option = document.createElement("option");
        option.value = point.id;
        option.textContent = point.name;
        selectElement.appendChild(option);
    });
}

function showPointsError() {
    startSelect.innerHTML = '<option value="">Nie udało się wczytać punktów</option>';
    endSelect.innerHTML = '<option value="">Nie udało się wczytać punktów</option>';
}

function showAllPointsOnMap(points) {
    points.forEach(point => {
        const marker = L.marker([point.lat, point.lng])
            .addTo(map)
            .bindPopup(point.name);

        markers.push(marker);
    });
}

routeButton.addEventListener("click", async function () {
    const start = startSelect.value;
    const end = endSelect.value;
    const criterion = document.getElementById("criterion").value;

    if (start === "" || end === "") {
        routeResult.innerHTML = `
            <div class="error">
                Wybierz punkt początkowy i punkt końcowy trasy.
            </div>
        `;
        return;
    }

    if (start === end) {
        routeResult.innerHTML = `
            <div class="error">
                Punkt początkowy i końcowy nie mogą być takie same.
            </div>
        `;
        return;
    }

    routeResult.classList.remove("empty-result");

    routeResult.innerHTML = `
        <div class="result-list">
            <p>Wyznaczanie trasy...</p>
        </div>
    `;

    try {
        const response = await fetch(`${API_URL}/api/route`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                start: start,
                end: end,
                criterion: criterion
            })
        });

        const data = await response.json();

        if (!data.success) {
            routeResult.innerHTML = `
                <div class="error">
                    ${data.message}
                </div>
            `;
            return;
        }

        const criterionName = getCriterionName(data.criterion);
        const formattedTime = formatTime(data.total_time_min);
        const pathNames = data.path.map(point => point.name);

        routeResult.innerHTML = `
            <div class="route-path">
                ${pathNames.join(" → ")}
            </div>

            <div class="result-list">
                <p><strong>Wybrane kryterium:</strong> ${criterionName}</p>
                <p><strong>Szacowany czas przejścia:</strong> ${formattedTime}</p>
                <p><strong>Długość trasy:</strong> ${data.total_distance_km} km</p>
                <p><strong>Suma trudności odcinków:</strong> ${data.total_difficulty}</p>
            </div>
        `;

        drawRouteOnMap(data.path);

    } catch (error) {
        routeResult.innerHTML = `
            <div class="error">
                Nie udało się połączyć z serwerem. Sprawdź, czy backend jest uruchomiony.
            </div>
        `;
    }
});

function drawRouteOnMap(path) {
    if (routeLine) {
        map.removeLayer(routeLine);
    }

    const coordinates = path.map(point => [point.lat, point.lng]);

    routeLine = L.polyline(coordinates, {
        weight: 5
    }).addTo(map);

    map.fitBounds(routeLine.getBounds(), {
        padding: [30, 30]
    });
}

function getCriterionName(criterion) {
    if (criterion === "time") {
        return "najszybsza trasa";
    }

    if (criterion === "distance") {
        return "najkrótsza trasa";
    }

    if (criterion === "difficulty") {
        return "najmniej trudna trasa";
    }

    return "brak";
}

function formatTime(minutes) {
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;

    if (hours === 0) {
        return `${remainingMinutes} min`;
    }

    if (remainingMinutes === 0) {
        return `${hours} h`;
    }

    return `${hours} h ${remainingMinutes} min`;
}
import { MapContainer, Marker, Polyline, Popup, TileLayer } from "react-leaflet";
import {
  DEFAULT_MAP_CENTER,
  DEFAULT_MAP_ZOOM,
  markerIcon,
} from "../constants/map";
import { getPointName } from "../utils/points";

const ROUTE_STYLES = {
  dijkstra: {
    color: "#2563eb",
    offsetMeters: -9,
  },
  astar: {
    color: "#9333ea",
    offsetMeters: -3,
  },
  greedy: {
    color: "#f97316",
    offsetMeters: 3,
  },
  custom_hikeup: {
    color: "#16a34a",
    offsetMeters: 9,
  },
  custom: {
    color: "#16a34a",
    offsetMeters: 9,
  },
  default: {
    color: "#111827",
    offsetMeters: 0,
  },
};

function normalizePosition(point) {
  if (Array.isArray(point)) {
    return [Number(point[0]), Number(point[1])];
  }

  return [
    Number(point.lat ?? point.latitude),
    Number(point.lng ?? point.lon ?? point.longitude),
  ];
}

function getShiftedRoutePositions(positions, offsetMeters) {
  if (!Array.isArray(positions) || positions.length < 2 || offsetMeters === 0) {
    return positions;
  }

  const normalizedPositions = positions.map(normalizePosition);

  return normalizedPositions.map((currentPoint, index) => {
    const [currentLat, currentLng] = currentPoint;

    const previousPoint =
      normalizedPositions[index - 1] || normalizedPositions[index];

    const nextPoint =
      normalizedPositions[index + 1] || normalizedPositions[index];

    const [previousLat, previousLng] = previousPoint;
    const [nextLat, nextLng] = nextPoint;

    const metersPerDegreeLat = 111_320;
    const metersPerDegreeLng =
      111_320 * Math.cos((currentLat * Math.PI) / 180);

    const directionX = (nextLng - previousLng) * metersPerDegreeLng;
    const directionY = (nextLat - previousLat) * metersPerDegreeLat;

    const directionLength = Math.sqrt(
      directionX * directionX + directionY * directionY,
    );

    if (directionLength === 0) {
      return [currentLat, currentLng];
    }

    const normalX = -directionY / directionLength;
    const normalY = directionX / directionLength;

    const shiftedLng =
      currentLng + (normalX * offsetMeters) / metersPerDegreeLng;

    const shiftedLat =
      currentLat + (normalY * offsetMeters) / metersPerDegreeLat;

    return [shiftedLat, shiftedLng];
  });
}

export function RouteMap({
  nodes,
  edges,
  nodeById,
  routeResult,
  onMarkerClick,
  onSetStart,
  onSetEnd,
}) {
  const algorithmRoutes =
    Array.isArray(routeResult?.routes) && routeResult.routes.length > 0
      ? routeResult.routes
      : routeResult?.positions?.length > 1
        ? [
            {
              algorithm: routeResult.algorithm || "dijkstra",
              label: routeResult.label || "Trasa",
              positions: routeResult.positions,
            },
          ]
        : [];

  return (
    <MapContainer
      center={DEFAULT_MAP_CENTER}
      zoom={DEFAULT_MAP_ZOOM}
      scrollWheelZoom
      className="map"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {edges.map((edge, index) => {
        const from = nodeById[edge.from];
        const to = nodeById[edge.to];

        if (!from || !to) return null;

        return (
          <Polyline
            key={`${edge.from}-${edge.to}-${index}`}
            positions={[
              [from.lat, from.lng],
              [to.lat, to.lng],
            ]}
            pathOptions={{
              color: "#9ca3af",
              weight: 1,
              opacity: 0.2,
            }}
          />
        );
      })}

      {algorithmRoutes.map((route, index) => {
        if (!Array.isArray(route.positions) || route.positions.length < 2) {
          return null;
        }

        const style = ROUTE_STYLES[route.algorithm] || ROUTE_STYLES.default;

        const shiftedPositions = getShiftedRoutePositions(
          route.positions,
          style.offsetMeters,
        );

        return (
          <Polyline
            key={`${route.algorithm}-${index}`}
            positions={shiftedPositions}
            pathOptions={{
              color: style.color,
              weight: 3,
              opacity: 0.95,
              lineCap: "round",
              lineJoin: "round",
            }}
          />
        );
      })}

      {nodes.map((node) => (
        <Marker
          key={node.id}
          position={[node.lat, node.lng]}
          icon={markerIcon}
          eventHandlers={{ click: () => onMarkerClick(node.id) }}
        >
          <Popup>
            <strong>{getPointName(node)}</strong>
            <br />
            Wysokość: {node.elevation || "brak danych"} m n.p.m.
            <br />
            Typ: {node.type || "punkt"}
            <div className="popup-actions">
              <button onClick={() => onSetStart(node)}>Ustaw jako A</button>
              <button onClick={() => onSetEnd(node)}>Ustaw jako B</button>
            </div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
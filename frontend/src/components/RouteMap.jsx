// odpowiada za wyświetlanie mapy i narysowanej trasy
import { MapContainer, Marker, Polyline, Popup, TileLayer } from "react-leaflet";
import { DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM, markerIcon } from "../constants/map";
import { getPointName } from "../utils/points";

export function RouteMap({
  nodes,
  edges,
  nodeById,
  routeResult,
  onMarkerClick,
  onSetStart,
  onSetEnd,
}) {
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
          />
        );
      })}

      {routeResult?.positions?.length > 1 && (
        <Polyline positions={routeResult.positions} weight={5} />
      )}

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

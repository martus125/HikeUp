//statyczne dane punktów
export function normalizePoint(point) {
  return {
    ...point,
    id: point.id,
    name: point.name || point.label || point.title || point.id,
    lat: Number(point.lat ?? point.latitude),
    lng: Number(point.lng ?? point.lon ?? point.longitude),
  };
}

export function normalizePointList(data) {
  const rawPoints = Array.isArray(data)
    ? data
    : Array.isArray(data?.points)
      ? data.points
      : Array.isArray(data?.nodes)
        ? data.nodes
        : data?.points && typeof data.points === "object"
          ? Object.values(data.points)
          : data?.nodes && typeof data.nodes === "object"
            ? Object.values(data.nodes)
            : data && typeof data === "object"
              ? Object.values(data)
              : [];

  return rawPoints
    .map(normalizePoint)
    .filter(
      (point) =>
        point.id &&
        point.name &&
        Number.isFinite(point.lat) &&
        Number.isFinite(point.lng),
    );
}

export function normalizeText(text) {
  return String(text || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

export function getPointName(point) {
  return String(point?.name || point?.label || point?.title || point?.id || "");
}

export function createPointMap(points) {
  return points.reduce((map, point) => {
    map[point.id] = point;
    return map;
  }, {});
}

export function getUniqueSortedPoints(points) {
  const uniquePoints = new Map();

  points.forEach((point) => {
    if (point?.id) {
      uniquePoints.set(point.id, point);
    }
  });

  return Array.from(uniquePoints.values()).sort((a, b) =>
    getPointName(a).localeCompare(getPointName(b), "pl"),
  );
}

export function filterPoints(points, query) {
  const search = normalizeText(query.trim());
  if (!search) return [];

  return points
    .filter((point) => {
      const name = normalizeText(getPointName(point));
      const id = normalizeText(point.id);
      const type = normalizeText(point.type);

      return (
        name.startsWith(search) ||
        name.includes(search) ||
        id.includes(search) ||
        type.includes(search)
      );
    })
    .slice(0, 8);
}

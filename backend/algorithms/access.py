"""Pedestrian access policy. Conditional/seasonal edges are excluded year-round.

No date parser or live closure feed is implied. Missing legacy tags remain
usable with an explicit uncertainty warning, not a claim of legal access.
"""

ACCESS_KEYS = (
    "highway", "access", "foot", "access:forward", "access:backward",
    "foot:forward", "foot:backward", "oneway", "oneway:foot", "seasonal",
    "access:conditional", "foot:conditional", "oneway:conditional",
    "oneway:foot:conditional", "access:forward:conditional", "access:backward:conditional",
    "foot:forward:conditional", "foot:backward:conditional", "opening_hours", "closed",
)
ALLOWED_ACCESS = {"", "yes", "designated", "permissive"}
NO = {"", "no", "false", "0"}
HIKING_HIGHWAYS = {"", "path", "footway", "steps", "pedestrian", "via_ferrata"}


def value(edge, key):
    return str(edge.get(key, "")).strip().lower()


def allowed_directions(edge):
    """Return allowed traversal directions relative to stored from/to."""
    if edge.get("source_geometry_matches") is False:
        return ()
    if value(edge, "closed") not in NO or value(edge, "highway") in {"construction", "proposed"}:
        return ()
    if value(edge, "seasonal") not in NO:
        return ()
    if any(value(edge, key) for key in ACCESS_KEYS if key.endswith(":conditional")):
        return ()
    if value(edge, "opening_hours") not in {"", "24/7"}:
        return ()

    oneway = value(edge, "oneway:foot")
    if not oneway and value(edge, "highway") in HIKING_HIGHWAYS:
        # Conservative hiking policy for ambiguous oneway on paths. Vehicle
        # oneway on residential/other roads does not constrain pedestrians.
        oneway = value(edge, "oneway")
    if oneway in {"yes", "true", "1"}:
        directions = (1,)
    elif oneway in {"-1", "reverse"}:
        directions = (-1,)
    elif oneway in NO:
        directions = (1, -1)
    else:
        return ()  # Unrecognised direction cannot be safely interpreted.

    orientation = edge.get("osm_direction", 1)
    result = []
    for direction in directions:
        suffix = "forward" if direction == 1 else "backward"
        # More specific pedestrian restrictions override generic access.
        access = next((value(edge, key) for key in (
            f"foot:{suffix}", "foot", f"access:{suffix}", "access") if value(edge, key)), "")
        if access in ALLOWED_ACCESS:
            result.append(direction * orientation)
    return tuple(result)


def difficulty_is_known(edge):
    return edge.get("difficulty_known") is True

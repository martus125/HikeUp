"""Canonical app types; external OSM values are translated at import."""

OSM_SHELTER_TYPE = "alpine_hut"
SHELTER_TYPE = "shelter"


def normalize_point_type(point_type):
    return SHELTER_TYPE if point_type == OSM_SHELTER_TYPE else point_type

"""Add OSM restrictions to an existing map without regenerating elevations.

python scripts/enrich_access_data.py --fetch --apply
python scripts/enrich_access_data.py --osm-file snapshot.json --apply
Without --apply only reports counts. Snapshot is retained for reproducibility.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import urllib.parse
import urllib.request

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from algorithms.access import ACCESS_KEYS, allowed_directions
from scripts.generate_full_map import SAC_LEVELS

DEFAULT_MAP = BACKEND / "mapa" / "cala_mapa.json"
DEFAULT_SNAPSHOT = BACKEND / "mapa" / "osm_access_snapshot.json"


def enrich(map_data, snapshot):
    ways = {f"way/{way['id']}": way for way in snapshot.get("elements", []) if way.get("type") == "way"}
    pairs_by_way = {}
    for way_id, way in ways.items():
        pairs = {}
        for start, end in zip(way.get("nodes", []), way.get("nodes", [])[1:]):
            pairs[(f"node/{start}", f"node/{end}")] = 1
            pairs[(f"node/{end}", f"node/{start}")] = -1
        pairs_by_way[way_id] = pairs
    stats = Counter()
    for edge in map_data["edges"]:
        way_id = edge.get("osm_way_id")
        way = ways.get(way_id)
        if way is None:
            edge["access_tags_known"] = False
            edge["difficulty_known"] = False
            edge["difficulty_source"] = "legacy_unverified"
            edge["source_geometry_matches"] = False
            stats["missing_ways"] += 1
            stats["excluded_edges"] += 1
            continue
        tags = way.get("tags", {})
        for key in ACCESS_KEYS:
            edge.pop(key, None)
            if key in tags:
                edge[key] = tags[key]
        direction = pairs_by_way[way_id].get((edge["from"], edge["to"]))
        edge["source_geometry_matches"] = direction is not None
        edge["osm_direction"] = direction or 1
        edge["access_tags_known"] = True
        edge["sac_scale"] = tags.get("sac_scale")
        edge["difficulty_known"] = tags.get("sac_scale") in SAC_LEVELS
        edge["difficulty_source"] = "osm:sac_scale" if edge["difficulty_known"] else "default"
        edge["difficulty"] = SAC_LEVELS.get(tags.get("sac_scale"), 2)
        stats["matched_edges"] += 1
        stats["geometry_mismatch"] += direction is None
        stats["difficulty_known"] += edge["difficulty_known"]
        directions = allowed_directions(edge)
        stats["excluded_edges"] += not directions
        stats["one_way_edges"] += len(directions) == 1
    map_data.setdefault("routing_data_metadata", {})["access"] = {
        "source": "OpenStreetMap / Overpass", "snapshot_time": snapshot.get("osm3s", {}).get("timestamp_osm_base"),
        "enriched_at": datetime.now(timezone.utc).isoformat(),
        "policy": "exclude_seasonal_and_conditional", "stats": dict(stats),
        "limitations": "Way tags only; no live closures, barrier-node or turn-restriction evaluation.",
    }
    return dict(stats)


def fetch_snapshot(map_data, endpoint):
    ids = sorted({int(edge["osm_way_id"].split("/")[1]) for edge in map_data["edges"] if edge.get("osm_way_id")})
    # Body includes node order so reverse-oriented legacy edges are handled.
    query = f"[out:json][timeout:180];way(id:{','.join(map(str, ids))});out body;"
    request = urllib.request.Request(endpoint, data=urllib.parse.urlencode({"data": query}).encode(),
        headers={"User-Agent": "HikeUp academic routing data audit", "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(request, timeout=210) as response:
        data = json.load(response)
    if data.get("remark") or not data.get("elements"):
        raise ValueError("Incomplete Overpass response; map was not changed")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map-file", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--osm-file", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--endpoint", default="https://overpass-api.de/api/interpreter")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.map_file.read_text(encoding="utf-8"))
    if args.fetch:
        snapshot = fetch_snapshot(data, args.endpoint)
        args.osm_file.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        snapshot = json.loads(args.osm_file.read_text(encoding="utf-8"))
    print(json.dumps(enrich(data, snapshot), indent=2))
    if args.apply:
        temporary = args.map_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        temporary.replace(args.map_file)
        print("Map updated; restart backend to refresh its routing cache.")


if __name__ == "__main__":
    main()

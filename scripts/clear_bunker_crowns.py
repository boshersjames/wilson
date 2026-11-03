"""Keep LiDAR tree crowns off bunkers. Rendered SpeedTree crowns come out ~1.3x the LiDAR crown radius (Wilson PC
build), so a tree must sit at least 1.3 x crown + 0.5 m from the sand. Far trees get a smaller crown; trees closer
than 4 m to the sand are moved out so a 4 m crown (5.2 m rendered) clears. Run in the build folder (map.osm, trees.csv)."""
import csv, json, xml.etree.ElementTree as ET
from pyproj import Transformer
from shapely.geometry import Polygon, Point
from shapely.ops import nearest_points
K, GAP = 1.3, 0.5
c = json.load(open("course.json"))
t = Transformer.from_crs("EPSG:4326", "EPSG:%d" % c["epsg"], always_xy=True)
r = ET.parse("map.osm").getroot(); nodes = {}
for n in r.iter("node"):
    e, nn = t.transform(float(n.get("lon")), float(n.get("lat"))); nodes[n.get("id")] = (e - c["sw_e"], nn - c["sw_n"])
B = [Polygon([nodes[q.get("ref")] for q in w.findall("nd")]) for w in r.iter("way")
     if any(q.get("k") == "golf" and q.get("v") == "bunker" for q in w.findall("tag"))]
rows = list(csv.DictReader(open("trees.csv"))); log = []
for tr in rows:
    for _ in range(3):
        x, z, rad = float(tr["x"]), float(tr["z"]), float(tr["crown_radius_m"])
        b = min(B, key=lambda q: q.distance(Point(x, z))); dist = b.distance(Point(x, z))
        if dist >= K * rad + GAP:
            break
        if dist >= 4:
            new = round((dist - GAP) / K, 1); log.append("tree %s: crown %.1f -> %.1f m" % (tr["id"], rad, new)); tr["crown_radius_m"] = new
        else:
            q = nearest_points(b, Point(x, z))[0]; vx, vz = x - q.x, z - q.y; L = max((vx * vx + vz * vz) ** .5, 0.1)
            newr = min(rad, 4.0); move = K * newr + GAP - dist
            tr["x"], tr["z"], tr["crown_radius_m"] = round(x + vx / L * move, 2), round(z + vz / L * move, 2), newr
            log.append("tree %s: moved %.1f m off the bunker, crown %.1f -> %.1f m" % (tr["id"], move, rad, newr))
w = csv.DictWriter(open("trees.csv", "w", newline=""), fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
print("\n".join(log)); print("%d changes" % len(log))
bad = [tr["id"] for tr in rows for b in B if b.distance(Point(float(tr["x"]), float(tr["z"]))) < K * float(tr["crown_radius_m"])]
print("trees whose rendered crown still reaches a bunker:", bad)

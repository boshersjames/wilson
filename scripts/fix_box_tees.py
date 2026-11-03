"""Tee colours that share one mapped tee box: put each on the box itself, at least 3 m from the colour already
there and 1.2 m inside the edge, keeping the yardage as close as possible. A tee pushed sideways off a box gets
a pad that merges with the box, and OPCD left those spots as rough (Wilson 2 and 9 Yellow, Harding 1 and 3 Yellow).
Usage: python fix_box_tees.py GKD heightmap_without_pads.raw   (in the build folder)"""
import json, math, sys, xml.etree.ElementTree as ET
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon, Point
gkd, hraw = sys.argv[1], sys.argv[2]
c = json.load(open("course.json")); S = c["size"]
t = Transformer.from_crs("EPSG:4326", "EPSG:%d" % c["epsg"], always_xy=True)
r = ET.parse("map.osm").getroot(); nodes = {}
for n in r.iter("node"):
    e, nn = t.transform(float(n.get("lon")), float(n.get("lat"))); nodes[n.get("id")] = (e - c["sw_e"], nn - c["sw_n"])
boxes = [Polygon([nodes[q.get("ref")] for q in w.findall("nd")]) for w in r.iter("way")
         if any(q.get("k") == "golf" and q.get("v") == "tee" for q in w.findall("tag"))]
H = np.fromfile(hraw, "<u2").reshape(2049, 2049) * c["terrain_height"] / 65535
d = json.load(open(gkd, encoding="utf-8-sig"))
COL = ("Black", "Blue", "White", "Green", "Yellow")
for h in d["Holes"]:
    T = {x["TeeType"]: x for x in h["Tees"]}; g = T["GreenCenterPoint"]["Position"]
    live = [T[k] for k in COL if T.get(k) and T[k]["Enabled"] and T[k]["Position"]]
    for tee in live:
        p = Point(tee["Position"]["x"], tee["Position"]["z"])
        if any(b.buffer(-1.0).contains(p) for b in boxes):
            continue                                    # already well on a box
        near = [b for b in boxes if b.distance(p) < 1.0]
        if not near:
            continue                                    # out in the open: gets its own pad
        box = min(near, key=lambda b: b.distance(p)); inner = box.buffer(-1.2)
        others = [Point(o["Position"]["x"], o["Position"]["z"]) for o in live if o is not tee and box.buffer(1).contains(Point(o["Position"]["x"], o["Position"]["z"]))]
        d0 = math.hypot(g["x"] - p.x, g["z"] - p.y); best = None
        for x in np.arange(box.bounds[0], box.bounds[2], 0.25):
            for z in np.arange(box.bounds[1], box.bounds[3], 0.25):
                q = Point(x, z)
                if not inner.contains(q):
                    continue
                sep = min([q.distance(o) for o in others] or [99])
                score = (sep >= 3.0, sep if sep < 3 else -abs(math.hypot(g["x"] - x, g["z"] - z) - d0))
                if best is None or score > best[0]:
                    best = (score, x, z, sep)
        if best is None:
            continue
        _, x, z, sep = best
        tee["Position"].update(x=round(float(x), 3), z=round(float(z), 3), y=round(float(H[int(round(z * 2048 / S)), int(round(x * 2048 / S))]), 3))
        pts = [tee["Position"]] + [T[a]["Position"] for a in ("AimPoint1", "AimPoint2") if T.get(a) and T[a]["Enabled"] and h["Par"] > 3] + [g]
        tee["Distance"] = round(sum(math.hypot(a["x"] - b["x"], a["z"] - b["z"]) for a, b in zip(pts, pts[1:])), 3)
        print("hole %d %s -> on its mapped box, %.1f m from the other colour, %d yds" % (h["HoleNumber"], tee["TeeType"], sep, round(tee["Distance"] / 0.9144)))
json.dump(d, open(gkd, "w", encoding="utf-8"), indent=1)

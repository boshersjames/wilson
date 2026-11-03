import json, re, sys
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
s = open("course.svg").read(); S = json.load(open("course.json"))["size"]
def layer(name):
    i = s.index('inkscape:label="%s"' % name); j = s.index('</g>', i); polys = []
    for d in re.findall(r' d="([^"]+)"', s[i:j]):
        for sub in re.split(r'[Zz]', d):
            pts = [(float(a), float(b)) for a, b in re.findall(r'(-?[\d.]+),(-?[\d.]+)', sub)]
            if len(pts) > 2: polys.append(Polygon(pts).buffer(0))
    return polys
tee = layer("Tee"); fw = unary_union(layer("Fairway"))
d = json.load(open("GriffithWilson.GKD", encoding="utf-8-sig"))
for h in d["Holes"]:
    for x in h["Tees"]:
        if x["TeeType"] in ("Black","Blue","White","Green","Yellow") and x["Enabled"] and x["Position"]:
            p = Point(x["Position"]["x"], S - x["Position"]["z"])
            inside = [t for t in tee if t.contains(p)]
            if not inside or min(t.exterior.distance(p) for t in inside) < 1.5:
                print(h["HoleNumber"], x["TeeType"], "on tee" if inside else "NOT on tee", "edge %.1f m" % (min(t.exterior.distance(p) for t in inside) if inside else -min(t.distance(p) for t in tee)), "fairway" if fw.contains(p) else "")
print("--- tee shapes enclosed by a fairway hole")
fwl = layer("Fairway")
for t in tee:
    for f in fwl:
        if f.convex_hull.contains(t.centroid) and any(Polygon(r).contains(t.centroid) for r in f.interiors):
            print("tee at x %.0f z %.0f area %.0f inside a fairway hole" % (t.centroid.x, S - t.centroid.y, t.area))

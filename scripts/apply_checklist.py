"""Apply BoJa's feedback checklist items that live in the GKD / data for Wilson.
Run in the Wilson build folder (course.json, map.osm, heightmap_2049.raw, GriffithWilson.GKD)."""
import json, math, sys, csv
import numpy as np
import xml.etree.ElementTree as ET
from pyproj import Transformer
from shapely.geometry import Polygon, Point

c = json.load(open("course.json")); S = c["size"]
gkd_path = sys.argv[1] if len(sys.argv) > 1 else "GriffithWilson.GKD"
d = json.load(open(gkd_path, encoding="utf-8-sig"))
t = Transformer.from_crs("EPSG:4326", "EPSG:%d" % c["epsg"], always_xy=True)
root = ET.parse("map.osm").getroot()
nodes = {}
for nd in root.iter("node"):
    e, n = t.transform(float(nd.get("lon")), float(nd.get("lat")))
    nodes[nd.get("id")] = (e - c["sw_e"], n - c["sw_n"])
tees, greens = [], []
for w in root.iter("way"):
    tg = {q.get("k"): q.get("v") for q in w.findall("tag")}
    p = [nodes[q.get("ref")] for q in w.findall("nd") if q.get("ref") in nodes]
    if len(p) > 3 and tg.get("golf") == "tee":
        tees.append(Polygon(p))
    if len(p) > 3 and tg.get("golf") == "green":
        greens.append(Polygon(p))

hm = np.fromfile("heightmap_2049.raw", "<u2").reshape(2049, 2049).astype(np.float64) * (c["terrain_height"] / 65535.0)
def height(x, z):
    i, j = z * 2048 / S, x * 2048 / S
    i0, j0 = int(i), int(j); fi, fj = i - i0, j - j0
    return float(hm[i0, j0] * (1 - fi) * (1 - fj) + hm[i0 + 1, j0] * fi * (1 - fj) + hm[i0, j0 + 1] * (1 - fi) * fj + hm[i0 + 1, j0 + 1] * fi * fj)

log = []
# 1. Never stack two tee colours: move the later one 3 m sideways (stay on the mapped box when possible)
for h in d["Holes"]:
    T = {x["TeeType"]: x for x in h["Tees"]}
    gc = T["GreenCenterPoint"]["Position"]
    placed = []
    for name in ("Black", "Blue", "White", "Green", "Yellow"):
        tee = T.get(name)
        if not tee or not tee["Enabled"] or not tee["Position"]:
            continue
        p = tee["Position"]
        if any(math.hypot(p["x"] - q["x"], p["z"] - q["z"]) < 3 for q in placed):
            dx, dz = gc["x"] - p["x"], gc["z"] - p["z"]; L = math.hypot(dx, dz)
            px, pz = -dz / L, dx / L
            cands = [(p["x"] + s * 3.5 * px, p["z"] + s * 3.5 * pz) for s in (1, -1)]
            cands.sort(key=lambda q: (not any(tp.contains(Point(q)) for tp in tees),
                                      min(math.hypot(q[0] - r["x"], q[1] - r["z"]) for r in placed) * -1))
            nx, nz = cands[0]
            log.append("hole %d: %s moved 3.5 m sideways off the %s spot" % (h["HoleNumber"], name,
                       "/".join(x["TeeType"] for x in h["Tees"] if x is not tee and x["Position"] and math.hypot(x["Position"]["x"] - p["x"], x["Position"]["z"] - p["z"]) < 3)))
            p.update(x=round(nx, 3), z=round(nz, 3), y=round(height(nx, nz), 3))
        placed.append(p)
    # 2. Par 3s aim at the green
    if h["Par"] == 3 and T.get("AimPoint1"):
        T["AimPoint1"].update(Enabled=True, Position=dict(gc))
        if T.get("AimPoint2"):
            T["AimPoint2"].update(Enabled=False, Position=None)
        log.append("hole %d: par 3, aim set to the green centre" % h["HoleNumber"])
    # re-measure tee distances (metres, tee -> aim points -> green) after moves
    for name in ("Black", "Blue", "White", "Green", "Yellow"):
        tee = T.get(name)
        if tee and tee["Enabled"] and tee["Position"]:
            pts = [tee["Position"]] + [T[a]["Position"] for a in ("AimPoint1", "AimPoint2") if T.get(a) and T[a]["Enabled"] and T[a]["Position"]] + [gc]
            if h["Par"] == 3:
                pts = [tee["Position"], gc]
            tee["Distance"] = round(sum(math.hypot(a["x"] - b["x"], a["z"] - b["z"]) for a, b in zip(pts, pts[1:])), 3)

# 3. Tee pads never inside OB / hazards
haz = [Polygon([(q["x"], q["z"]) for q in z["coords"]]) for z in d["Hazards"]]
oob = Polygon([(q["x"], q["z"]) for q in d["pOOB"]["coords"]])
for h in d["Holes"]:
    for x in h["Tees"]:
        if x["Enabled"] and x["Position"]:
            pt = Point(x["Position"]["x"], x["Position"]["z"])
            if not oob.contains(pt) or any(hz.buffer(2).contains(pt) for hz in haz):
                log.append("WARNING hole %d %s is in or within 2 m of OB/hazard" % (h["HoleNumber"], x["TeeType"]))
# 4. Drop zones: any hazard with a DZ must not be innerOOB
for z in d["Hazards"]:
    if z["hasDZ"] and z["innerOOB"]:
        z["innerOOB"] = False; log.append("hazard with drop zone: innerOOB set false")

# 5. Course details (no BoJa as author)
d.update(DefaultStimp=2, MaxStimp=5, GreenFirmnessDefault=0, FairwayFirmnessDefault=0,   # approved: stimp ~10, Normal greens, moderate fairways
         CourseImageFileName="Wilson.jpg",
         CourseName="Wilson - Griffith Park", Designer="jboshers", Location="Griffith Park, Los Angeles, California, USA",
         CityTown="Los Angeles", StateCountyProvince="California", Country="USA", KeywordParkland=True, KeywordHistoric=True,
         CourseLat=34.14396, CourseLong=-118.28944)
gy = [height(T["Position"]["x"], T["Position"]["z"]) for h in d["Holes"] for T in h["Tees"] if T["TeeType"] == "GreenCenterPoint"]
d["altitudeV2"] = round((np.mean(gy) + c["y_offset"]) * 3.28084)
log.append("altitude %d ft (mean green elevation)" % d["altitudeV2"])
json.dump(d, open(gkd_path, "w", encoding="utf-8"), indent=1)

# 6. Green slopes: flag greens with a fitted-plane slope over 3 %
rows = []
for h in d["Holes"]:
    gc = [x for x in h["Tees"] if x["TeeType"] == "GreenCenterPoint"][0]["Position"]
    g = min(greens, key=lambda p: p.distance(Point(gc["x"], gc["z"])))
    minx, minz, maxx, maxz = g.bounds
    pts = [(x, z) for x in np.arange(minx, maxx, 1.0) for z in np.arange(minz, maxz, 1.0) if g.contains(Point(x, z))]
    A = np.array([[x, z, 1] for x, z in pts]); H = np.array([height(x, z) for x, z in pts])
    (a, b, _), *_ = np.linalg.lstsq(A, H, rcond=None)
    plane = 100 * math.hypot(a, b)
    gx, gz = np.gradient(np.array(H)), None
    loc = []
    for x, z in pts:
        sx = (height(x + 1, z) - height(x - 1, z)) / 2; sz = (height(x, z + 1) - height(x, z - 1)) / 2
        loc.append(100 * math.hypot(sx, sz))
    rows.append([h["HoleNumber"], round(g.area), round(plane, 1), round(float(np.percentile(loc, 90)), 1), "REVIEW" if plane > 3 or np.percentile(loc, 90) > 5 else ""])
with open("green_slopes.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["hole", "green_m2", "overall_slope_pct", "p90_local_slope_pct", "flag"]); w.writerows(rows)
print("\n".join(log))
for r in rows: print(r)

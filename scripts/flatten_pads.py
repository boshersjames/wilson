"""Flatten the terrain under tee pads listed in tee_pads.csv (and every GKD tee) and set the GKD tee heights to match.
Pad = 7 x 9 m toward the green, levelled to its mean height, blended back to the slope over 3 m."""
import csv, json, math, sys
import numpy as np
from scipy import ndimage
c = json.load(open("course.json")); S = c["size"]; TH = c["terrain_height"]
hm = np.fromfile("heightmap_2049.raw", "<u2").reshape(2049, 2049).astype(np.float64) * TH / 65535
d = json.load(open("GriffithWilson.GKD", encoding="utf-8-sig"))
cell = S / 2048
zz, xx = np.mgrid[0:2049, 0:2049] * cell
pads = {(int(r["hole"]), r["tee"]) for r in csv.DictReader(open("tee_pads.csv"))}
n = 0
for h in d["Holes"]:
    T = {x["TeeType"]: x for x in h["Tees"]}
    g = T["GreenCenterPoint"]["Position"]
    for name in ("Black", "Blue", "White", "Green", "Yellow"):
        x = T.get(name)
        if not x or not x["Enabled"] or not x["Position"] or (h["HoleNumber"], name) not in pads:
            continue
        px, pz = x["Position"]["x"], x["Position"]["z"]
        ux, uz = g["x"] - px, g["z"] - pz; L = math.hypot(ux, uz); ux, uz = ux / L, uz / L
        r0 = slice(max(0, int((pz - 12) / cell)), int((pz + 12) / cell) + 1); c0 = slice(max(0, int((px - 12) / cell)), int((px + 12) / cell) + 1)
        a = (xx[r0, c0] - px) * ux + (zz[r0, c0] - pz) * uz; b = -(xx[r0, c0] - px) * uz + (zz[r0, c0] - pz) * ux
        out = np.maximum(np.abs(a) - 4.5, 0) ** 2 + np.maximum(np.abs(b) - 3.5, 0) ** 2
        out = np.sqrt(out)                                 # metres outside the pad rectangle
        sub = hm[r0, c0]
        level = float(sub[out == 0].mean())
        wgt = np.clip(1 - out / 3.0, 0, 1)
        hm[r0, c0] = sub * (1 - wgt) + level * wgt
        x["Position"]["y"] = round(level, 3); n += 1
raw = np.clip(hm / TH, 0, 1) * 65535
np.round(raw).astype("<u2").tofile("heightmap_2049.raw")
json.dump(d, open("GriffithWilson.GKD", "w", encoding="utf-8"), indent=1)
print("levelled %d tee pads in heightmap_2049.raw and set their GKD heights" % n)

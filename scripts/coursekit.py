#!/usr/bin/env python3
"""
coursekit: build the data for any GSPro / OPCD course from public USGS LiDAR, NAIP imagery and OpenStreetMap.

Each course lives in its own folder with a course.json. Run every step from inside that folder.

  python coursekit.py new  <name> <lat> <lon>     make ~/courses/<name>/course.json for a 2000 m square centred there
  python coursekit.py lidar  [--survey NAME]      download + clip USGS LiDAR      -> points.npz
  python coursekit.py lidar  --ept NAME           same, from the USGS EPT copy on AWS (much faster than rockyweb)
  python coursekit.py satellite                   NAIP aerial photo                -> satellite.jpg
  python coursekit.py heightmap                   Unity terrain (2049 x 2049 RAW)  -> heightmap_2049.raw  (+ import settings)
  python coursekit.py trees  [--buffer 150]       trees from LiDAR                 -> trees.csv, trees_on_satellite.png
  python coursekit.py brush  [--buffer 200]       brush / chaparral from LiDAR     -> shrubs.csv, brush_mask.png, brush_on_satellite.png
  python coursekit.py vegetation                  scrub/grass masks + clean shrubs -> terrain_masks/, shrubs_clean.csv
  python coursekit.py osm                         what map.osm has + cart paths    -> cartpaths.csv, osm_on_satellite.png
  python coursekit.py svg                         OPCD course drawing (draft)      -> course.svg, course_svg_preview.png
  python coursekit.py holes                       holes, greens, tee boxes + yards -> holes.csv, tees.csv, holes_on_satellite.png

"Near the holes" filters use golf=hole lines from map.osm in the course folder (OpenStreetMap export),
or a Greenkeeper file (--gkd), or nothing (--buffer 0).

Unity frame: x = metres east of the square's SW corner, z = metres north, y = elevation - y_offset.
"""
import argparse, csv, json, math, os, re, sys, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
import numpy as np
from scipy import ndimage

CFG = "course.json"
UA = {"User-Agent": "Mozilla/5.0 (coursekit GSPro course build)"}
NOT_VEG = [2, 6, 7, 9, 17, 18]


# ---------------------------------------------------------------- settings
def load_cfg():
    if not os.path.exists(CFG):
        sys.exit("No course.json here. cd into the course folder (or run: coursekit.py new <name> <lat> <lon>).")
    return json.load(open(CFG))


def save_cfg(c):
    json.dump(c, open(CFG, "w"), indent=2)


def utm_epsg(lon):
    zone = int((lon + 180) // 6) + 1
    return 6329 + zone, 26900 + zone, zone          # NAD83(2011) UTM (metres), NAD83 UTM wkid for ArcGIS, zone


def cmd_new(a):
    from pyproj import Transformer
    epsg, wkid, zone = utm_epsg(a.lon)
    e, n = Transformer.from_crs("EPSG:4326", "EPSG:%d" % epsg, always_xy=True).transform(a.lon, a.lat)
    folder = os.path.expanduser(os.path.join(a.root, a.name))
    os.makedirs(folder, exist_ok=True)
    cfg = {"name": a.name, "center_lat": a.lat, "center_lon": a.lon, "size": a.size,
           "epsg": epsg, "arcgis_wkid": wkid, "utm_zone": zone,
           "sw_e": round(e - a.size / 2, 2), "sw_n": round(n - a.size / 2, 2), "y_offset": None}
    if a.sw_e is not None:                           # reuse an existing frame (e.g. Tierra Rejada)
        cfg["sw_e"], cfg["sw_n"] = a.sw_e, a.sw_n
    if a.y_offset is not None:
        cfg["y_offset"] = a.y_offset
    json.dump(cfg, open(os.path.join(folder, CFG), "w"), indent=2)
    print("Created", os.path.join(folder, CFG))
    print(json.dumps(cfg, indent=2))
    print("\nNext:  cd %s  then run lidar, satellite, heightmap. Put an OpenStreetMap export there as map.osm." % folder)


# ---------------------------------------------------------------- downloads
def fetch(url, timeout=600, tries=8):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            wait = int(e.headers.get("Retry-After") or 0) or min(120, 10 * 2 ** (k // 2))
            print("    %s, retrying in %ds" % (e.code, wait)); time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            print("    network error (%s), retrying in 15s" % e); time.sleep(15)
    raise SystemExit("Gave up on " + url)


def square_bbox_ll(c):
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:%d" % c["epsg"], "EPSG:4326", always_xy=True)
    pts = [t.transform(e, n) for e in (c["sw_e"], c["sw_e"] + c["size"]) for n in (c["sw_n"], c["sw_n"] + c["size"])]
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)


def project_of(item):
    u = item.get("downloadURL", "")
    m = re.search(r"/Projects/([^/]+)/", u)
    return m.group(1) if m else item.get("title", "?")


def cmd_lidar(a):
    import laspy
    from pyproj import CRS, Transformer
    c = load_cfg()
    if a.ept:
        parts = lidar_from_ept(c, a.ept)
        x, n_, z, cl = (np.concatenate([p[i] for p in parts]) for i in range(4))
        np.savez_compressed("points.npz", x=x, n=n_, z=z, c=cl)
        g = cl == 2
        print("Saved %d points to points.npz (%.2f per m2). Ground %.1f to %.1f m." % (len(x), len(x) / c["size"] ** 2, z[g].min(), z[g].max()))
        c = load_cfg(); c["lidar_survey"] = a.ept; save_cfg(c)
        return
    bb = square_bbox_ll(c)
    q = urllib.parse.urlencode({"datasets": "Lidar Point Cloud (LPC)", "bbox": "%f,%f,%f,%f" % bb, "prodFormats": "LAS,LAZ", "max": 500})
    print("Asking USGS which surveys cover the square...")
    items = json.loads(fetch("https://tnmaccess.nationalmap.gov/api/v1/products?" + q, 120)[0]).get("items", [])
    groups = {}
    for it in items:
        groups.setdefault(project_of(it), []).append(it)
    if not groups:
        sys.exit("USGS has no LiDAR point clouds here.")
    def year(p):
        y = re.findall(r"(?:19|20)\d\d", p)
        return max(int(v) for v in y) if y else 0
    ranked = sorted(groups, key=lambda p: (year(p), len(groups[p])), reverse=True)
    print("Surveys found (newest first):")
    for p in ranked:
        print("   %-55s %3d tiles" % (p, len(groups[p])))
    pick = a.survey or ranked[0]
    if pick not in groups:
        sys.exit("No survey named %s above." % pick)
    print("Using", pick, "(override with --survey NAME)")

    os.makedirs("tiles", exist_ok=True)
    utm = CRS.from_epsg(c["epsg"])
    parts = []
    for it in groups[pick]:
        path = os.path.join("tiles", it["downloadURL"].rsplit("/", 1)[-1])
        if not os.path.exists(path):
            print("  downloading", os.path.basename(path), "(%.0f MB)" % ((it.get("sizeInBytes") or 0) / 1e6))
            urls = [it["downloadURL"]]
            if "rockyweb.usgs.gov/vdelivery/Datasets/Staged/" in urls[0]:
                urls.append(urls[0].replace("https://rockyweb.usgs.gov/vdelivery/Datasets/Staged/", "https://prd-tnm.s3.amazonaws.com/StagedProducts/"))
            data = None
            for k in range(12):
                u = urls[k % len(urls)]
                try:
                    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=600) as r:
                        data = r.read()
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 404 and len(urls) > 1 and u != urls[0]:
                        urls = urls[:1]                      # mirror doesn't have this survey; stop trying it
                        print("    mirror doesn't have this tile, using USGS only")
                        continue
                    wait = int(e.headers.get("Retry-After") or 0) or min(300, 30 * (k + 1))
                    print("    %s from %s, waiting %ds" % (e.code, u.split("/")[2], wait)); time.sleep(wait)
                except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                    print("    network error (%s), waiting 30s" % e); time.sleep(30)
            if data is None:
                sys.exit("Could not download %s; rerun later (finished tiles are kept)." % path)
            open(path, "wb").write(data); time.sleep(2)
        las = laspy.read(path)
        try:
            crs = las.header.parse_crs()
        except Exception:
            crs = None
        h = (crs.sub_crs_list[0] if crs is not None and crs.is_compound else crs) or utm
        zs = 1.0
        if crs is not None and crs.is_compound and len(crs.sub_crs_list) > 1:
            u = crs.sub_crs_list[1].axis_info[0].unit_name.lower()
            zs = 1200 / 3937 if "us survey foot" in u else 0.3048 if "foot" in u else 1.0
        xs, ys = np.asarray(las.x), np.asarray(las.y)
        if not h.equals(utm):
            xs, ys = Transformer.from_crs(h, utm, always_xy=True).transform(xs, ys)
        e, n = xs - c["sw_e"], ys - c["sw_n"]
        k = (e >= 0) & (e < c["size"]) & (n >= 0) & (n < c["size"])
        print("    %s: %d points in the square" % (os.path.basename(path), k.sum()))
        parts.append((e[k].astype(np.float32), n[k].astype(np.float32), (np.asarray(las.z)[k] * zs).astype(np.float32),
                      np.asarray(las.classification)[k].astype(np.uint8)))
    x, n_, z, cl = (np.concatenate([p[i] for p in parts]) for i in range(4))
    np.savez_compressed("points.npz", x=x, n=n_, z=z, c=cl)
    g = cl == 2
    print("Saved %d points to points.npz. Ground %.1f to %.1f m." % (len(x), z[g].min(), z[g].max()))
    c["lidar_survey"] = pick
    save_cfg(c)


EPT_ROOT = "https://s3-us-west-2.amazonaws.com/usgs-lidar-public/"


def lidar_from_ept(c, name, workers=16):
    """Full-resolution points from USGS's Entwine (EPT) copy of a survey on AWS. Much faster than the
    rockyweb tile server, and only the octree nodes overlapping the square are fetched."""
    import laspy
    from concurrent.futures import ThreadPoolExecutor
    from pyproj import Transformer
    base = EPT_ROOT + name + "/"
    info = json.loads(fetch(base + "ept.json", 120)[0])
    to_m = Transformer.from_crs("EPSG:%d" % c["epsg"], "EPSG:3857", always_xy=True)
    S = c["size"]
    corners = [to_m.transform(c["sw_e"] + i * S, c["sw_n"] + j * S) for i in (0, 1) for j in (0, 1)]
    qx0, qy0 = min(p[0] for p in corners) - 5, min(p[1] for p in corners) - 5
    qx1, qy1 = max(p[0] for p in corners) + 5, max(p[1] for p in corners) + 5
    b = info["bounds"]
    def node_box(d, x, y):
        w = (b[3] - b[0]) / 2 ** d
        return b[0] + x * w, b[1] + y * w, b[0] + (x + 1) * w, b[1] + (y + 1) * w
    def hits(d, x, y):
        x0, y0, x1, y1 = node_box(d, x, y)
        return x0 < qx1 and x1 > qx0 and y0 < qy1 and y1 > qy0
    keys, todo = [], ["0-0-0-0"]
    while todo:                                   # walk the hierarchy pages, keeping nodes that overlap the square
        h = json.loads(fetch(base + "ept-hierarchy/%s.json" % todo.pop(), 120)[0])
        for k, n in h.items():
            d, x, y, _ = map(int, k.split("-"))
            if not hits(d, x, y):
                continue
            if n == -1:
                todo.append(k)
            elif n > 0:
                keys.append(k)
    print("EPT %s: %d nodes overlap the square" % (name, len(keys)))
    if not keys:
        sys.exit("That survey has no points in the square.")
    to_utm = Transformer.from_crs("EPSG:3857", "EPSG:%d" % c["epsg"], always_xy=True)
    os.makedirs("ept_cache", exist_ok=True)
    def get(k):
        path = os.path.join("ept_cache", k + ".laz")
        if not os.path.exists(path):
            data = fetch(base + "ept-data/%s.laz" % k, 300)[0]
            open(path + ".part", "wb").write(data); os.replace(path + ".part", path)
        las = laspy.read(path)
        e, n = to_utm.transform(np.asarray(las.x), np.asarray(las.y))
        e, n = e - c["sw_e"], n - c["sw_n"]
        cl = np.asarray(las.classification)
        m = (e >= 0) & (e < S) & (n >= 0) & (n < S) & ~np.isin(cl, [7, 18])   # drop noise
        return (e[m].astype(np.float32), n[m].astype(np.float32), np.asarray(las.z)[m].astype(np.float32), cl[m].astype(np.uint8))
    parts, done = [], 0
    with ThreadPoolExecutor(workers) as ex:
        for p in ex.map(get, keys):
            parts.append(p); done += 1
            if done % 50 == 0 or done == len(keys):
                print("  %d / %d nodes" % (done, len(keys)), flush=True)
    return parts


def cmd_satellite(a):
    from PIL import Image
    import io
    c = load_cfg()
    S, px, tiles = c["size"], a.pixels, 2
    services = ["https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer/exportImage",
                "https://gis.apfo.usda.gov/arcgis/rest/services/NAIP/USDA_CONUS_PRIME/ImageServer/exportImage"]
    step, sub = S / tiles, px // tiles
    for svc in services:
        print("Trying", svc.split("/")[2])
        mosaic, ok = Image.new("RGB", (px, px)), True
        for row in range(tiles):
            for col in range(tiles):
                e0, n1 = c["sw_e"] + col * step, c["sw_n"] + S - row * step
                q = urllib.parse.urlencode({"bbox": "%f,%f,%f,%f" % (e0, n1 - step, e0 + step, n1), "bboxSR": c["arcgis_wkid"],
                                            "imageSR": c["arcgis_wkid"], "size": "%d,%d" % (sub, sub), "format": "jpgpng", "f": "image"})
                img = None
                for k in range(5):
                    try:
                        data, ct = fetch(svc + "?" + q, 180, 1)
                        if ct.startswith("image"):
                            img = Image.open(io.BytesIO(data)).convert("RGB"); break
                    except SystemExit:
                        pass
                    time.sleep(5 * (k + 1))
                if img is None:
                    ok = False; break
                mosaic.paste(img.resize((sub, sub)), (col * sub, row * sub))
                print("  piece %d of %d" % (row * tiles + col + 1, tiles * tiles))
            if not ok:
                break
        if ok:
            mosaic.save("satellite.jpg", quality=92)
            print("Saved satellite.jpg (%d px, %.2f m/px). In Unity: Max Size %d, Terrain Size %d." % (px, S / px, px, S))
            return
    sys.exit("Both imagery services failed.")


# ---------------------------------------------------------------- grids
def load_points():
    if not os.path.exists("points.npz"):
        sys.exit("No points.npz yet; run the lidar step first.")
    d = np.load("points.npz")
    return d["x"], d["n"], d["z"], d["c"]


def cell_grid(ix, iy, v, size, how):
    out = np.full((size, size), np.nan, np.float32)
    flat = iy.astype(np.int64) * size + ix
    if how == "mean":
        cnt = np.bincount(flat, minlength=size * size)
        tot = np.bincount(flat, weights=v.astype(np.float64), minlength=size * size)
        return np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan).reshape(size, size).astype(np.float32)
    o = np.lexsort((v, flat)); fs, vs = flat[o], v[o]
    ed = np.nonzero(np.diff(fs))[0]
    pick = np.r_[ed, len(fs) - 1] if how == "max" else np.r_[0, ed + 1]
    out.reshape(-1)[fs[pick]] = vs[pick]
    return out


def fill(a):
    bad = np.isnan(a)
    return a[tuple(ndimage.distance_transform_edt(bad, return_distances=False, return_indices=True))] if bad.any() else a


def ground_and_heights(c):
    x, n, z, cl = load_points()
    S = int(c["size"])
    ix, iy = np.clip(x.astype(int), 0, S - 1), np.clip(n.astype(int), 0, S - 1)
    g = cl == 2
    dtm = ndimage.gaussian_filter(fill(cell_grid(ix[g], iy[g], z[g], S, "mean")), 1.0)
    veg = ~np.isin(cl, NOT_VEG)
    under = ndimage.map_coordinates(dtm, [np.clip(n[veg] - 0.5, 0, S - 1), np.clip(x[veg] - 0.5, 0, S - 1)], order=1)
    h = np.nan_to_num(cell_grid(ix[veg], iy[veg], (z[veg] - under).astype(np.float32), S, "max"), nan=0.0)
    h[(h < 0) | (h > 60)] = 0
    return dtm, h


def cmd_heightmap(a):
    c = load_cfg()
    x, n, z, cl = load_points()
    S = int(c["size"])
    g = cl == 2
    ix, iy = np.clip(x[g].astype(int), 0, S - 1), np.clip(n[g].astype(int), 0, S - 1)
    dtm = fill(cell_grid(ix, iy, z[g], S, "mean"))
    res = 2049
    yy, xx = np.mgrid[0:res, 0:res] * (S / (res - 1))
    hm = ndimage.map_coordinates(dtm, [np.clip(yy - 0.5, 0, S - 1), np.clip(xx - 0.5, 0, S - 1)], order=1)
    base = float(np.floor(hm.min()) - 1) if c.get("y_offset") is None else float(c["y_offset"])
    top = float(np.ceil(hm.max() - base) + 1)
    raw = np.clip((hm - base) / top, 0, 1) * 65535
    raw.astype("<u2").tofile("heightmap_2049.raw")      # rows = north, little-endian = Unity "Windows" byte order
    c["y_offset"], c["terrain_height"] = base, top
    save_cfg(c)
    print("Wrote heightmap_2049.raw. Ground %.1f-%.1f m." % (hm.min(), hm.max()))
    print("Unity Terrain: Width %d, Length %d, Height %.0f, Heightmap Resolution 2049; Import Raw: Bit 16, 2049 x 2049, Byte Order Windows."
          % (S, S, top))
    print("Unity y = elevation - %.0f m (saved as y_offset in course.json)." % base)


# ---------------------------------------------------------------- near-the-holes zone
def play_lines(c, gkd=None):
    segs = []
    if gkd and os.path.exists(gkd):
        d = json.load(open(gkd, encoding="utf-8-sig"))
        for hole in d["Holes"]:
            T = {t["TeeType"]: t["Position"] for t in hole["Tees"] if t.get("Position")}
            route = [T[k] for k in ("AimPoint1", "AimPoint2", "GreenCenterPoint") if k in T]
            for k, p in T.items():
                if k not in ("AimPoint1", "AimPoint2", "GreenCenterPoint") and route:
                    q = [p] + route
                    segs += [(q[i]["x"], q[i]["z"], q[i + 1]["x"], q[i + 1]["z"]) for i in range(len(q) - 1)]
        print("Using hole routes from", gkd)
    elif os.path.exists("map.osm"):
        from pyproj import Transformer
        t = Transformer.from_crs("EPSG:4326", "EPSG:%d" % c["epsg"], always_xy=True)
        r = ET.parse("map.osm").getroot()
        nodes = {}
        for nd in r.iter("node"):
            e, n = t.transform(float(nd.get("lon")), float(nd.get("lat")))
            nodes[nd.get("id")] = (e - c["sw_e"], n - c["sw_n"])
        holes = 0
        for w in r.findall("way"):
            tg = {q.get("k"): q.get("v") for q in w.findall("tag")}
            if tg.get("golf") == "hole":
                p = [nodes[q.get("ref")] for q in w.findall("nd") if q.get("ref") in nodes]
                segs += [(p[i][0], p[i][1], p[i + 1][0], p[i + 1][1]) for i in range(len(p) - 1)]
                holes += 1
        print("Using %d golf hole lines from map.osm" % holes)
    return segs


def zone_mask(c, buffer, gkd=None):
    S = int(c["size"])
    if buffer <= 0:
        return np.ones((S, S), bool)
    segs = play_lines(c, gkd)
    if not segs:
        print("(no hole lines found, so no zone filter)")
        return np.ones((S, S), bool)
    yy, xx = np.mgrid[0:S, 0:S] + 0.5
    dist = np.full((S, S), 1e9, np.float32)
    for ax_, az, bx, bz in segs:
        dx, dz = bx - ax_, bz - az
        t = np.clip(((xx - ax_) * dx + (yy - az) * dz) / max(dx * dx + dz * dz, 1e-9), 0, 1)
        dist = np.minimum(dist, np.hypot(xx - ax_ - t * dx, yy - az - t * dz))
    return dist <= buffer


def osm_masks(c):
    """Rasterise map.osm: (exclude, course) masks on the 1 m grid (row 0 = south).
    exclude = buildings, parking, roads, residential/commercial land, playing surfaces (greens, tees, bunkers, water).
    course  = the golf course boundary (leisure=golf_course), or None if it isn't mapped."""
    S = int(c["size"])
    if not os.path.exists("map.osm"):
        return None, None
    from pyproj import Transformer
    from PIL import Image, ImageDraw
    t = Transformer.from_crs("EPSG:4326", "EPSG:%d" % c["epsg"], always_xy=True)
    r = ET.parse("map.osm").getroot()
    nodes = {}
    for nd in r.iter("node"):
        e, n = t.transform(float(nd.get("lon")), float(nd.get("lat")))
        nodes[nd.get("id")] = (e - c["sw_e"], S - (n - c["sw_n"]))      # image coords: y down
    ex = Image.new("L", (S, S), 0); dx = ImageDraw.Draw(ex)
    co = Image.new("L", (S, S), 0); dc = ImageDraw.Draw(co)
    road_w = {"motorway": 30, "motorway_link": 14, "trunk": 24, "primary": 20, "secondary": 16, "tertiary": 12,
              "residential": 10, "unclassified": 8, "service": 6}
    has_course = False
    for w in r.findall("way"):
        tg = {q.get("k"): q.get("v") for q in w.findall("tag")}
        p = [nodes[q.get("ref")] for q in w.findall("nd") if q.get("ref") in nodes]
        if len(p) < 2:
            continue
        if tg.get("leisure") == "golf_course" and len(p) > 2:
            dc.polygon(p, fill=255); has_course = True
        elif ("building" in tg or tg.get("amenity") == "parking" or tg.get("landuse") in ("residential", "commercial", "retail", "industrial")
              or tg.get("golf") in ("green", "tee", "bunker", "water_hazard", "lateral_water_hazard")) and len(p) > 2:
            dx.polygon(p, fill=255)
        elif tg.get("highway") in road_w and tg.get("golf") != "cartpath":
            dx.line(p, fill=255, width=road_w[tg["highway"]])
    for rel in r.findall("relation"):                     # course boundary mapped as a multipolygon
        tg = {q.get("k"): q.get("v") for q in rel.findall("tag")}
        if tg.get("leisure") == "golf_course":
            for m in rel.findall("member"):
                if m.get("type") == "way" and m.get("role") in ("outer", ""):
                    w = r.find("./way[@id='%s']" % m.get("ref"))
                    if w is not None:
                        p = [nodes[q.get("ref")] for q in w.findall("nd") if q.get("ref") in nodes]
                        if len(p) > 2:
                            dc.polygon(p, fill=255); has_course = True
    exclude = np.flipud(np.asarray(ex) > 0)
    course = np.flipud(np.asarray(co) > 0) if has_course else None
    print("OSM filter: %.1f ha excluded (buildings, parking, roads, built-up land, greens/tees/bunkers/water)%s"
          % (exclude.sum() / 1e4, ", course boundary found" if has_course else ", no course boundary mapped"))
    return exclude, course


def course_if_valid(c, course):
    """Only trust a mapped course boundary if it actually contains most of the holes."""
    if course is None:
        return None
    segs = play_lines(c, None)
    if not segs:
        return course
    S = int(c["size"])
    pts = [(int(min(max(v, 0), S - 1)), int(min(max(u, 0), S - 1))) for s_ in segs for (u, v) in ((s_[0], s_[1]), (s_[2], s_[3]))]
    share = np.mean([course[r, q] for r, q in pts])
    if share < 0.6:
        print("Ignoring the mapped golf_course boundary (only %.0f%% of the holes are inside it; probably another facility)" % (share * 100))
        return None
    return course


def green_share(c):
    if not os.path.exists("satellite.jpg"):
        return None
    from PIL import Image
    S = int(c["size"])
    sat = np.flipud(np.asarray(Image.open("satellite.jpg").convert("RGB").resize((S, S), Image.BILINEAR), dtype=np.float32))
    return ndimage.uniform_filter(sat[..., 1] / np.maximum(sat.sum(2), 1), 3)


def preview(c, mask_rgba, pts, title, name):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from PIL import Image
    except ImportError:
        return
    S = c["size"]
    fig, ax = plt.subplots(figsize=(18, 18), dpi=110)
    if os.path.exists("satellite.jpg"):
        ax.imshow(Image.open("satellite.jpg").convert("RGB"), origin="upper", extent=(0, S, 0, S))
    if mask_rgba is not None:
        ax.imshow(mask_rgba, origin="lower", extent=(0, S, 0, S))
    if len(pts):
        ax.scatter(pts[:, 0], pts[:, 1], s=2, c="red")
    ax.set_title(title); ax.set_xlim(0, S); ax.set_ylim(0, S)
    fig.savefig(name, bbox_inches="tight"); print("Wrote", name)


def need_offset(c):
    if c.get("y_offset") is None:
        sys.exit("Run the heightmap step first (it sets y_offset).")
    return c["y_offset"]


def cmd_trees(a):
    c = load_cfg(); yo = need_offset(c); S = int(c["size"])
    dtm, h = ground_and_heights(c)
    hs = ndimage.gaussian_filter(h, 1.0)
    peaks = (hs == ndimage.maximum_filter(hs, size=5)) & (hs >= a.min_height)
    py, px = np.nonzero(peaks)
    order = np.argsort(-hs[py, px]); py, px = py[order], px[order]
    taken, kept = np.zeros((S, S), bool), []
    dirs = [(np.cos(t), np.sin(t)) for t in np.linspace(0, 2 * np.pi, 16, endpoint=False)]
    for yy, xx in zip(py, px):
        if taken[yy, xx]:
            continue
        hh, radii = hs[yy, xx], []
        for dx, dy in dirs:
            r = 1
            while r < 15:
                sx, sy = int(round(xx + dx * r)), int(round(yy + dy * r))
                if not (0 <= sx < S and 0 <= sy < S) or hs[sy, sx] < 0.5 * hh:
                    break
                r += 1
            radii.append(r)
        rad = float(np.median(radii)); kept.append((xx, yy, hh, rad))
        rr = max(1, int(round(rad * 0.8)))
        Y, X = np.ogrid[max(0, yy - rr):min(S, yy + rr + 1), max(0, xx - rr):min(S, xx + rr + 1)]
        taken[max(0, yy - rr):min(S, yy + rr + 1), max(0, xx - rr):min(S, xx + rr + 1)] |= (X - xx) ** 2 + (Y - yy) ** 2 <= rr * rr
    zone = zone_mask(c, a.buffer, a.gkd)
    exclude, course = osm_masks(c)
    course = course_if_valid(c, course)
    if exclude is not None:
        zone &= ~ndimage.binary_dilation(exclude, iterations=2)
        if course is not None and a.course_margin >= 0:
            zone &= ndimage.binary_dilation(course, iterations=int(a.course_margin))
    n0 = len(kept)
    kept = [k for k in kept if zone[k[1], k[0]]]
    gs = green_share(c) if a.min_green > 0 else None
    if gs is not None:
        n1 = len(kept)
        kept = [k for k in kept if gs[k[1], k[0]] >= a.min_green]
        print("Satellite check dropped %d grey/tan crowns (roofs, poles, walls)" % (n1 - len(kept)))
    print("Kept %d of %d detected trees after the zone/OSM filters" % (len(kept), n0))
    with open("trees.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["id", "x", "z", "y", "height_m", "crown_radius_m"])
        for i, (xx, yy, hh, rad) in enumerate(kept):
            w.writerow([i, "%.2f" % (xx + .5), "%.2f" % (yy + .5), "%.2f" % (dtm[yy, xx] - yo), "%.1f" % hh, "%.1f" % rad])
    print("Wrote %d trees (>= %.1f m) to trees.csv" % (len(kept), a.min_height))
    preview(c, None, np.array([(k[0] + .5, k[1] + .5) for k in kept]).reshape(-1, 2), "%d trees" % len(kept), "trees_on_satellite.png")


def cmd_brush(a):
    from PIL import Image
    c = load_cfg(); yo = need_offset(c); S = int(c["size"])
    dtm, h = ground_and_heights(c)
    brush = ndimage.binary_opening(ndimage.binary_closing((h >= a.low) & (h <= a.high), iterations=2), iterations=1)
    brush &= zone_mask(c, a.buffer, a.gkd)
    exclude, course = osm_masks(c)
    course = course_if_valid(c, course)
    if exclude is not None:
        brush &= ~ndimage.binary_dilation(exclude, iterations=2)
        if course is not None and a.course_margin >= 0:
            brush &= ndimage.binary_dilation(course, iterations=int(a.course_margin))
    hs = ndimage.gaussian_filter(np.where(brush, h, 0), 0.8)
    win = max(3, int(round(a.spacing)) | 1)
    py, px = np.nonzero(brush & (hs == ndimage.maximum_filter(hs, size=win)) & (hs >= a.low))
    with open("shrubs.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["id", "x", "z", "y", "height_m", "crown_radius_m"])
        for i, (yy, xx) in enumerate(zip(py, px)):
            w.writerow([i, "%.2f" % (xx + .5), "%.2f" % (yy + .5), "%.2f" % (dtm[yy, xx] - yo), "%.1f" % h[yy, xx], "%.1f" % (a.spacing / 2)])
    Image.fromarray((np.flipud(brush) * 255).astype(np.uint8)).save("brush_mask.png")
    print("Brush %.1f ha; wrote %d shrubs to shrubs.csv and brush_mask.png" % (brush.sum() / 1e4, len(px)))
    ov = np.zeros((S, S, 4), np.float32); ov[brush] = (1, .45, 0, .45)
    preview(c, ov, np.c_[px + .5, py + .5], "Brush %.1f-%.1f m (orange), %d shrubs" % (a.low, a.high, len(px)), "brush_on_satellite.png")


def osm_layers(c):
    """Rasterise map.osm into named 1 m masks (row 0 = south): building, road, parking, built (schools, pitches),
    cartpath, path, green, tee, bunker, fairway, rough, water, orchard, course."""
    from pyproj import Transformer
    from PIL import Image, ImageDraw
    S = int(c["size"])
    t = Transformer.from_crs("EPSG:4326", "EPSG:%d" % c["epsg"], always_xy=True)
    r = ET.parse("map.osm").getroot()
    nodes = {}
    for nd in r.iter("node"):
        e, n = t.transform(float(nd.get("lon")), float(nd.get("lat")))
        nodes[nd.get("id")] = (e - c["sw_e"], S - (n - c["sw_n"]))
    names = ("building", "road", "parking", "built", "cartpath", "path", "green", "tee", "bunker", "fairway", "rough", "water", "orchard", "course")
    im = {k: Image.new("L", (S, S), 0) for k in names}
    dr = {k: ImageDraw.Draw(v) for k, v in im.items()}
    road_w = {"motorway": 30, "motorway_link": 14, "trunk": 24, "primary": 20, "secondary": 16, "tertiary": 12,
              "residential": 10, "unclassified": 8, "service": 6, "track": 4}
    def ways():
        for w in r.findall("way"):
            yield {q.get("k"): q.get("v") for q in w.findall("tag")}, [nodes[q.get("ref")] for q in w.findall("nd") if q.get("ref") in nodes]
        for rel in r.findall("relation"):
            tg = {q.get("k"): q.get("v") for q in rel.findall("tag")}
            for m in rel.findall("member"):
                if m.get("type") == "way" and m.get("role") in ("outer", ""):
                    w = r.find("./way[@id='%s']" % m.get("ref"))
                    if w is not None:
                        yield tg, [nodes[q.get("ref")] for q in w.findall("nd") if q.get("ref") in nodes]
    for tg, p in ways():
        if len(p) < 2:
            continue
        poly, g = len(p) > 2 and p[0] == p[-1], tg.get("golf")
        if g in ("green", "tee", "bunker", "fairway", "rough") and poly:
            dr[g].polygon(p, fill=255)
        elif g == "cartpath" or (tg.get("highway") in ("path", "footway", "cycleway") and g is None):
            dr["cartpath" if g == "cartpath" or tg.get("golf_cart") == "yes" else "path"].line(p, fill=255, width=3)
        elif (g in ("water_hazard", "lateral_water_hazard") or (tg.get("natural") == "water" and tg.get("water") not in ("river", "canal"))) and poly:   # rivers (LA River) are off-course channels
            dr["water"].polygon(p, fill=255)
        elif tg.get("leisure") == "golf_course" and poly:
            dr["course"].polygon(p, fill=255)
        elif "building" in tg and poly:
            dr["building"].polygon(p, fill=255)
        elif tg.get("amenity") == "parking" and poly:
            dr["parking"].polygon(p, fill=255)
        elif (tg.get("landuse") in ("residential", "commercial", "retail", "industrial", "construction") or tg.get("amenity") in ("school",)
              or tg.get("leisure") in ("pitch", "playground", "park", "swimming_pool")) and poly:
            dr["built"].polygon(p, fill=255)
        elif tg.get("landuse") in ("orchard", "vineyard", "farmland", "greenhouse_horticulture", "plant_nursery") and poly:
            dr["orchard"].polygon(p, fill=255)
        elif tg.get("highway") in road_w:
            dr["road"].line(p, fill=255, width=road_w[tg["highway"]])
    return {k: np.flipud(np.asarray(v) > 0) for k, v in im.items()}


def disk(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def cmd_vegetation(a):
    """Classify the square for the SoCal vegetation set (Tierra Rejada lessons):
    canyon hillsides are never bare, so every natural slope gets dense scrub; the scrub stops at a graded edge
    (deep rough, then golden grass) next to turf; homes, yards, roads, paths and orchards get none.
    Writes terrain_masks/*.mask for Tierra > Paint Grass and Brush, shrubs_clean.csv for Plant Shrubs
    (LiDAR shrubs in natural ground plus a lined-up edge row), shrubs_removed.csv, veg_classes.npz and a preview."""
    from PIL import Image
    c = load_cfg(); yo = need_offset(c); S = int(c["size"])
    L = osm_layers(c)
    dtm, h = ground_and_heights(c)
    sat = np.flipud(np.asarray(Image.open("satellite.jpg").convert("RGB").resize((S, S), Image.BILINEAR), dtype=np.float32))
    sm = ndimage.uniform_filter(sat, (5, 5, 1)); R_, G_, B_ = sm[..., 0], sm[..., 1], sm[..., 2]
    lum = sat.mean(2); tex = np.sqrt(np.maximum(ndimage.uniform_filter(lum ** 2, 7) - ndimage.uniform_filter(lum, 7) ** 2, 0))
    gshare = G_ / np.maximum(sm.sum(2), 1)
    irrigated = (gshare >= a.turf_green) & (tex < a.turf_smooth) & (h < 0.6)       # mown, watered grass (turf, lawns)
    paved = (sm.max(2) - sm.min(2) < 18) & (lum > 120)                               # grey concrete / asphalt / roofs
    canopy = ndimage.uniform_filter((h > 2.5).astype(np.float32), 15)

    near_home = ndimage.distance_transform_edt(~L["building"])
    developed = (near_home <= a.yard) | L["road"] | L["parking"] | L["built"] | \
                ((near_home <= a.lot) & (irrigated | paved)) | ndimage.binary_dilation(L["road"] & ~L["course"], disk(4))
    developed = ndimage.binary_closing(developed, disk(3))
    course = L["course"] if L["course"].any() else ndimage.distance_transform_edt(~L["green"]) < 400
    turf = L["green"] | L["tee"] | L["bunker"] | L["fairway"] | L["rough"] | L["water"] | \
           (irrigated & ndimage.binary_dilation(course, disk(10)) & ~developed)
    turf = ndimage.binary_opening(ndimage.binary_closing(turf, disk(2)), disk(2))
    lab, nl = ndimage.label(turf)                         # photo turf only counts if it joins mapped turf or is a big lawn
    osm_turf = L["green"] | L["tee"] | L["bunker"] | L["fairway"] | L["rough"] | L["water"]
    area = ndimage.sum(np.ones_like(lab), lab, index=np.arange(1, nl + 1))
    ok = np.zeros(nl + 1, bool); ok[np.unique(lab[osm_turf])] = True; ok[1:][area >= 2500] = True; ok[0] = False
    turf = ok[lab] | osm_turf
    bare = (lum > 145) & (gshare < 0.345) & (h < 0.3)                              # pale dirt
    trails = bare & ~ndimage.binary_opening(bare, disk(4))                          # thin pale lines: unmapped dirt tracks
    hard = L["cartpath"] | L["path"] | L["water"] | ndimage.binary_closing(trails, disk(1))
    if a.parkland:                                        # parkland (Griffith Park): irrigated rough runs under the trees between holes,
        turf |= ndimage.binary_dilation(course, disk(3)) & ~developed & ~hard   # so the whole mapped course is turf, never scrub
    orchard = L["orchard"] | ((canopy > a.woodland) & ~ndimage.binary_dilation(course, disk(15)))
    natural = ~developed & ~turf & ~ndimage.binary_dilation(hard, disk(2))
    natural = ndimage.binary_opening(natural, disk(2))
    natural &= ndimage.distance_transform_edt(~course) <= a.reach        # detail grass only draws ~150 m from the camera
    d_turf = ndimage.distance_transform_edt(~turf)
    deep = natural & (d_turf <= a.deep_band) & ndimage.binary_dilation(course, disk(30))
    grass = natural & (((d_turf > a.deep_band - 1) & (d_turf <= a.grass_band)) | orchard)
    scrub = natural & (d_turf > a.grass_band - 2) & ~orchard
    nog = L["green"] | L["tee"] | L["bunker"] | L["fairway"] | L["water"] | ndimage.binary_dilation(L["cartpath"] | L["path"], disk(1)) | \
          L["road"] | L["building"] | L["parking"]
    os.makedirs("terrain_masks", exist_ok=True)
    def save(m, name, blur=1.5):
        v = ndimage.gaussian_filter(m.astype(np.float32), blur) if blur else m.astype(np.float32); v[nog] = 0
        Image.fromarray(np.flipud(np.clip(v * 255, 0, 255)).astype(np.uint8)).save(os.path.join("terrain_masks", name), format="PNG")
    save(scrub, "brush_sage_scrub.mask"); save(grass, "grass_dry_hillside.mask"); save(deep, "grass_deep_rough.mask")
    Image.fromarray(np.flipud(nog * 255).astype(np.uint8)).save("terrain_masks/no_grass.mask", format="PNG")
    np.savez_compressed("veg_classes.npz", natural=natural, scrub=scrub, grass=grass, deep=deep, turf=turf, developed=developed, nog=nog)
    print("Scrub %.1f ha, golden grass %.1f ha, deep rough %.1f ha, turf %.1f ha, homes/yards/roads %.1f ha (no brush)"
          % tuple(m.sum() / 1e4 for m in (scrub, grass, deep, turf, developed)))

    # Plant Shrubs: LiDAR shrubs that stand in natural ground near play, plus a lined-up row along the scrub edge
    zone = zone_mask(c, a.buffer, None)
    keep, removed = [], []
    for row in csv.DictReader(open("shrubs.csv")):
        x, z = float(row["x"]), float(row["z"]); ix, iz = min(int(x), S - 1), min(int(z), S - 1)
        why = ("building or yard" if (near_home[iz, ix] <= a.yard or developed[iz, ix]) and not natural[iz, ix] else
               "road/parking" if L["road"][iz, ix] or L["parking"][iz, ix] else
               "cart path/trail" if ndimage.binary_dilation(hard[max(0, iz - 2):iz + 3, max(0, ix - 2):ix + 3]).any() else
               "playing surface" if turf[iz, ix] else
               "orchard/woodland" if orchard[iz, ix] else
               "outside play zone" if not zone[iz, ix] else None)
        (removed if why else keep).append((row, why))
    edge = scrub & ~ndimage.binary_erosion(scrub, disk(1)) & zone & (d_turf < a.grass_band + 3)
    ey, ex = np.nonzero(edge)
    rng = np.random.default_rng(7)
    taken = np.zeros((S, S), bool); edge_pts = []
    for k in rng.permutation(len(ex)):
        yy, xx = ey[k], ex[k]
        if taken[yy, xx]:
            continue
        taken[max(0, yy - 2):yy + 3, max(0, xx - 2):xx + 3] = True
        edge_pts.append((xx + .5, yy + .5, float(rng.uniform(1.0, 2.2))))
    with open("shrubs_clean.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["id", "x", "z", "y", "height_m", "crown_radius_m", "source"])
        i = 0
        for row, _ in keep:
            w.writerow([i, row["x"], row["z"], row["y"], row["height_m"], row["crown_radius_m"], "lidar"]); i += 1
        for x, z, hh in edge_pts:
            w.writerow([i, "%.2f" % x, "%.2f" % z, "%.2f" % (dtm[int(z), int(x)] - yo), "%.1f" % hh, "1.2", "edge"]); i += 1
    with open("shrubs_removed.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["id", "x", "z", "reason"])
        for row, why in removed:
            w.writerow([row["id"], row["x"], row["z"], why])
    from collections import Counter
    print("shrubs_clean.csv: %d LiDAR shrubs kept + %d edge-row shrubs; removed %d (%s)" % (
        len(keep), len(edge_pts), len(removed), ", ".join("%s %d" % kv for kv in Counter(w_ for _, w_ in removed).most_common())))
    ov = np.zeros((S, S, 4), np.float32)
    ov[grass] = (1, .8, .2, .5); ov[deep] = (1, 0, 1, .5); ov[scrub] = (.15, .55, .15, .55); ov[developed & ~turf] = (.3, .3, .3, .45)
    pts = np.array([(float(r_["x"]), float(r_["z"])) for r_, _ in keep] + [(p[0], p[1]) for p in edge_pts]).reshape(-1, 2)
    preview(c, ov, pts[::3], "Scrub (green), golden grass (yellow), deep rough (magenta), homes/roads (grey), shrubs (red, 1 in 3)", "vegetation_on_satellite.png")


def cmd_osm(a):
    from pyproj import Transformer
    import collections
    c = load_cfg(); yo = need_offset(c); S = int(c["size"])
    if not os.path.exists("map.osm"):
        sys.exit("No map.osm here. Export the course from openstreetmap.org/export and save it in this folder as map.osm.")
    t = Transformer.from_crs("EPSG:4326", "EPSG:%d" % c["epsg"], always_xy=True)
    r = ET.parse("map.osm").getroot()
    nodes = {}
    for nd in r.iter("node"):
        e, n = t.transform(float(nd.get("lon")), float(nd.get("lat")))
        nodes[nd.get("id")] = (e - c["sw_e"], n - c["sw_n"])
    ways = []
    for w in r.findall("way"):
        tg = {q.get("k"): q.get("v") for q in w.findall("tag")}
        ways.append((tg, [nodes[q.get("ref")] for q in w.findall("nd") if q.get("ref") in nodes]))
    golf = collections.Counter(tg["golf"] for tg, _ in ways if "golf" in tg)
    print("Golf features in map.osm:", dict(golf))
    print("Buildings:", sum(1 for tg, _ in ways if "building" in tg),
          " Parking areas:", sum(1 for tg, _ in ways if tg.get("amenity") == "parking"),
          " Fences/walls:", sum(1 for tg, _ in ways if tg.get("barrier") in ("fence", "wall", "retaining_wall")))
    def length(p): return sum(np.hypot(p[i + 1][0] - p[i][0], p[i + 1][1] - p[i][1]) for i in range(len(p) - 1))
    carts = [p for tg, p in ways if tg.get("golf") == "cartpath" and len(p) > 1]
    if not carts and a.paths_fallback:
        carts = [p for tg, p in ways if tg.get("highway") in ("path", "footway", "track") and len(p) > 1]
        print("No golf=cartpath ways; using %d paths/footways/tracks instead (check them!)" % len(carts))
    x, n, z, cl = load_points(); g = cl == 2
    dtm = fill(cell_grid(np.clip(x[g].astype(int), 0, S - 1), np.clip(n[g].astype(int), 0, S - 1), z[g], S, "mean"))
    with open("cartpaths.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["segment", "x", "z", "y"])
        for i, p in enumerate(carts):
            for ex, nz in p:
                yy = dtm[int(min(max(nz, 0), S - 1)), int(min(max(ex, 0), S - 1))] - yo
                w.writerow([i, "%.2f" % ex, "%.2f" % nz, "%.2f" % yy])
    print("Cart paths: %d, %.0f m in total -> cartpaths.csv" % (len(carts), sum(length(p) for p in carts)))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from PIL import Image
        fig, ax = plt.subplots(figsize=(18, 18), dpi=110)
        if os.path.exists("satellite.jpg"):
            ax.imshow(Image.open("satellite.jpg").convert("RGB"), origin="upper", extent=(0, S, 0, S))
        cols = {"green": "#2f9e44", "tee": "#8ce99a", "bunker": "#ffe066", "fairway": "#69db7c", "water_hazard": "#4dabf7", "rough": "#d3f9d8"}
        for tg, p in ways:
            if len(p) < 2:
                continue
            q = np.array(p)
            if tg.get("golf") in cols:
                ax.fill(q[:, 0], q[:, 1], color=cols[tg["golf"]], alpha=0.5)
            elif tg.get("golf") == "hole":
                ax.plot(q[:, 0], q[:, 1], "w--", lw=1); ax.text(q[0, 0], q[0, 1], tg.get("ref", ""), color="yellow", fontsize=12, weight="bold")
            elif "building" in tg:
                ax.fill(q[:, 0], q[:, 1], color="#868e96", alpha=0.8)
        for p in carts:
            q = np.array(p); ax.plot(q[:, 0], q[:, 1], color="red", lw=2)
        ax.set_xlim(0, S); ax.set_ylim(0, S)
        ax.set_title("OpenStreetMap: cart paths (red), greens/tees/fairways/bunkers/water, holes (dashed), buildings (grey)")
        fig.savefig("osm_on_satellite.png", bbox_inches="tight"); print("Wrote osm_on_satellite.png")
    except ImportError:
        pass


def hole_data(c):
    """From map.osm: per hole par/handicap tags, hole line, green centre and its tee boxes (yards back to front)."""
    from pyproj import Transformer
    yo = need_offset(c); S = int(c["size"])
    t = Transformer.from_crs("EPSG:4326", "EPSG:%d" % c["epsg"], always_xy=True)
    root = ET.parse("map.osm").getroot()
    nodes = {}
    for nd in root.iter("node"):
        e, n = t.transform(float(nd.get("lon")), float(nd.get("lat")))
        nodes[nd.get("id")] = (e - c["sw_e"], n - c["sw_n"])
    holes, greens, tees, tee_polys = [], [], [], []
    for w in root.findall("way"):
        tg = {q.get("k"): q.get("v") for q in w.findall("tag")}
        p = np.array([nodes[q.get("ref")] for q in w.findall("nd") if q.get("ref") in nodes])
        if len(p) < 2:
            continue
        g = tg.get("golf")
        cen = (p[:-1].mean(0) if (p[0] == p[-1]).all() else p.mean(0)) if len(p) > 2 else None
        if g == "hole":
            num = int(re.sub(r"\D", "", tg.get("ref", "")) or 0)
            loops = c.get("loops")                       # 27-hole clubs: [{"name", "osm_prefix"}], holes numbered loop by loop
            if loops and num:
                nm = tg.get("name", "")
                li = next((k for k, L in enumerate(loops) if L.get("osm_prefix") and nm.startswith(L["osm_prefix"])),
                          next((k for k, L in enumerate(loops) if not L.get("osm_prefix")), None))
                num = num + 9 * li if li is not None else 0
            holes.append({"hole": num, "par": tg.get("par", ""), "hcp": tg.get("handicap", ""), "line": p})
        elif g == "green" and cen is not None:
            greens.append(cen)
        elif g == "tee" and cen is not None:
            tees.append(cen); tee_polys.append(p)
    if not holes:
        sys.exit("No golf=hole lines in map.osm, so holes can't be worked out automatically.")
    greens, tees = np.array(greens).reshape(-1, 2), np.array(tees).reshape(-1, 2)
    x, n, z, cl = load_points(); g2 = cl == 2
    dtm = fill(cell_grid(np.clip(x[g2].astype(int), 0, S - 1), np.clip(n[g2].astype(int), 0, S - 1), z[g2], S, "mean"))
    yv = lambda q: float(dtm[int(min(max(q[1], 0), S - 1)), int(min(max(q[0], 0), S - 1))] - yo)
    starts = np.array([h["line"][0] for h in holes])
    owner = [int(np.argmin(np.hypot(*(starts - tp).T))) for tp in tees]
    for i, h in enumerate(holes):
        L = h["line"]
        gc = greens[np.argmin(np.hypot(*(greens - L[-1]).T))] if len(greens) else L[-1]
        if np.hypot(*(gc - L[-1])) > 40:
            gc = L[-1]
        h["green"] = gc
        mid = [q for q in L[1:-1]]
        h["path"] = mid                                  # every bend of the mapped hole line (yardages follow all of them)
        if len(mid) > 2:                                 # GSPro takes two aim points: keep the sharpest bends
            pts = [L[0]] + mid + [gc]
            turn = []
            for k in range(1, len(pts) - 1):
                v1, v2 = pts[k] - pts[k - 1], pts[k + 1] - pts[k]
                cosang = np.dot(v1, v2) / max(np.hypot(*v1) * np.hypot(*v2), 1e-6)
                turn.append((np.arccos(np.clip(cosang, -1, 1)), k - 1))
            keep = sorted(k for _, k in sorted(turn, reverse=True)[:2])
            h["aims"] = [mid[k] for k in keep]
        else:
            h["aims"] = mid
        rest = np.vstack(mid + [gc])
        boxes = []
        for j, tp in enumerate(tees):
            if owner[j] == i and np.hypot(*(tp - L[0])) < 150:
                route = np.vstack([tp, rest])
                # the box's usable length along the line of play: markers move up and back within one box
                u = rest[0] - tp; u = u / max(np.hypot(*u), 1e-6)
                sproj = (tee_polys[j] - tp) @ u
                lo, hi = sproj.min() + 1.5, sproj.max() - 1.5
                if hi < lo:
                    lo = hi = 0.0
                boxes.append((float(np.sum(np.hypot(*np.diff(route, axis=0).T)) / 0.9144), tp, tp + u * lo, tp + u * hi))
        h["boxes"] = sorted(boxes, key=lambda b: -b[0])
    unused = sum(1 for j in range(len(tees)) if np.hypot(*(tees[j] - starts[owner[j]])) >= 150)
    return sorted(holes, key=lambda h: h["hole"]), yv, unused


def cmd_holes(a):
    c = load_cfg()
    holes, yv, unused = hole_data(c)
    with open("holes.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["hole", "par", "handicap", "green_x", "green_z", "green_y", "tee_boxes", "yards_back_to_front"])
        for h in holes:
            gc = h["green"]
            w.writerow([h["hole"], h["par"], h["hcp"], "%.2f" % gc[0], "%.2f" % gc[1], "%.2f" % yv(gc), len(h["boxes"]), " / ".join("%.0f" % b[0] for b in h["boxes"])])
    with open("tees.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["hole", "box", "x", "z", "y", "yards"])
        for h in holes:
            for k, b in enumerate(h["boxes"]):
                w.writerow([h["hole"], k + 1, "%.2f" % b[1][0], "%.2f" % b[1][1], "%.2f" % yv(b[1]), "%.0f" % b[0]])
    print("%-4s %-4s %-4s %-6s %s" % ("hole", "par", "hcp", "boxes", "yards (back to front, along the mapped hole line)"))
    for h in holes:
        print("%-4s %-4s %-4s %-6s %s" % (h["hole"], h["par"] or "?", h["hcp"] or "?", len(h["boxes"]), " / ".join("%.0f" % b[0] for b in h["boxes"])))
    if unused:
        print("(%d tee boxes weren't near any hole's start: practice tees or unlinked)" % unused)
    print("Wrote holes.csv and tees.csv.")


GSP_SLOTS = ["Black", "White", "Green", "Blue", "Yellow", "Red", "Junior", "Par3"]
COLOR_ALIASES = {"gold": "Yellow", "yellow": "Yellow", "grey": "Green", "gray": "Green", "silver": "Green", "green": "Green",
                 "black": "Black", "blue": "Blue", "white": "White", "red": "Red", "junior": "Junior", "orange": "Junior"}


def read_card(path):
    """card.csv rows: par / par_w / hcp / hcp_w, then one row per tee colour: name, 18 yardages, rating_m, slope_m[, rating_w, slope_w]."""
    card = {"tees": []}
    for row in csv.reader(open(path)):
        if not row or not row[0].strip() or row[0].startswith("#"):
            continue
        key = row[0].strip()
        vals = [v.strip() for v in row[1:]]
        if key.lower() in ("par", "par_w", "hcp", "hcp_w"):
            card[key.lower()] = [int(v) for v in vals[:18]]
        elif key.lower() != "row":
            card["tees"].append({"name": key, "yards": [int(v) for v in vals[:18]],
                                 "sr": "%s/%s" % (vals[18], vals[19]) if len(vals) > 19 and vals[18] else "0.0/0"})
    return card


def fairway_aims(c, holes, pars):
    """Aim points at the centre of the widest part of the fairway: par 4 in the drive zone (190-290 yds from the
    back of the hole), par 5 one in the drive zone and one in the lay-up zone. Uses the Fairway layer of course.svg."""
    if not os.path.exists("course.svg"):
        return {}
    from PIL import Image, ImageDraw
    S = int(c["size"])
    svg = open("course.svg").read()
    i0 = svg.find('inkscape:label="Fairway"')
    if i0 < 0:
        return {}
    block = svg[i0:svg.find("</g>", i0)]
    fw = np.zeros((S, S), bool)
    for d in re.findall(r' d="([^"]+)"', block):
        for sp in re.split(r"(?=M )", d.strip()):
            pts = [tuple(float(v) for v in q.split(",")) for q in re.findall(r"(-?\d+\.?\d*,-?\d+\.?\d*)", sp)]
            if len(pts) > 2:
                im = Image.new("L", (S, S), 0); ImageDraw.Draw(im).polygon(pts, fill=255)
                fw ^= np.asarray(im) > 0
    fw = np.flipud(fw)                                    # row 0 = south, like the other grids
    half_width = ndimage.distance_transform_edt(fw)       # metres to the fairway edge
    yy, xx = np.mgrid[0:S, 0:S] + 0.5
    out = {}
    for h in holes:
        par = pars[h["hole"] - 1] if h["hole"] and h["hole"] <= len(pars) else 0
        if par < 4:
            continue
        L = np.vstack([h["line"][:-1], h["green"]])
        seg_len = np.hypot(*np.diff(L, axis=0).T); total = seg_len.sum()
        # along-hole distance and distance-from-line of every fairway pixel near this hole
        best_s = np.full((S, S), np.nan, np.float32); best_d = np.full((S, S), 1e9, np.float32)
        start = 0.0
        for (ax, az), (bx, bz), sl in zip(L[:-1], L[1:], seg_len):
            dx, dz = bx - ax, bz - az
            t = np.clip(((xx - ax) * dx + (yy - az) * dz) / max(sl * sl, 1e-9), 0, 1)
            dd = np.hypot(xx - ax - t * dx, yy - az - t * dz)
            closer = dd < best_d
            best_d = np.where(closer, dd, best_d); best_s = np.where(closer, start + t * sl, best_s)
            start += sl
        near = fw & (best_d < 40)
        yd = best_s / 0.9144; to_green = (total - best_s) / 0.9144
        zones = [(190, 290)] if par == 4 else [(190, 290), (330, 450)]
        aims = []
        for lo, hi in zones:
            z = near & (yd >= lo) & (yd <= hi) & (to_green >= 70)
            if not z.any():
                continue
            k = np.argmax(np.where(z, half_width, -1))
            r, q = np.unravel_index(k, z.shape)
            aims.append(np.array([q + 0.5, r + 0.5]))
        if aims:
            out[h["hole"]] = aims
    return out


def cmd_card(a):
    c = load_cfg()
    holes, yv, _ = hole_data(c)
    byn = {h["hole"]: h for h in holes}
    if a.loops:                                           # 27-hole club: front = first loop, back = second (scorecard_27.csv)
        names = [n_.strip() for n_ in a.loops.split(",")]
        order = [L["name"] for L in c["loops"]]
        idx = [order.index(n_) for n_ in names]
        rows = {}
        for r_ in csv.reader(open("scorecard_27.csv")):
            if r_ and not r_[0].startswith("#") and r_[0] != "loop":
                rows.setdefault(r_[1], {})[r_[0]] = [int(v) for v in r_[2:11]]
        card = {"tees": []}
        for k in ("par", "hcp"):
            card[k] = rows[k][names[0]] + rows[k][names[1]]
        card["hcp"] = [2 * v - 1 for v in rows["hcp"][names[0]]] + [2 * v for v in rows["hcp"][names[1]]]   # odd front, even back
        for tn, by in rows.items():
            if tn not in ("par", "hcp", "hcp_w") and names[0] in by and names[1] in by:
                card["tees"].append({"name": tn, "yards": by[names[0]] + by[names[1]], "sr": "0.0/0"})
        byn = {9 * k + j + 1: byn[9 * li + j + 1] for k, li in enumerate(idx) for j in range(9) if 9 * li + j + 1 in byn}
        a.name = a.name or "%s - %s/%s" % (c.get("club", c["name"]), names[0], names[1])
        a.scene = a.scene or c["name"] + "_" + "".join(n_.replace(" ", "") for n_ in names)
        print("Pairing %s (holes %s) + %s (holes %s)" % (names[0], "%d-%d" % (9 * idx[0] + 1, 9 * idx[0] + 9), names[1], "%d-%d" % (9 * idx[1] + 1, 9 * idx[1] + 9)))
    else:
        if not os.path.exists("card.csv"):
            sys.exit("No card.csv here (see coursekit docs for the format).")
        card = read_card("card.csv")
    slots = {}
    for t_ in card["tees"]:
        slot = a.map.get(t_["name"].lower()).title() if a.map and t_["name"].lower() in a.map else None
        slot = slot or COLOR_ALIASES.get(t_["name"].lower())
        if slot is None:
            sys.exit("Don't know which GSPro tee slot '%s' should use; pass --map %s=Blue (for example)." % (t_["name"], t_["name"]))
        slots[t_["name"]] = slot
    print("Tee colours -> GSPro slots:", ", ".join("%s->%s" % kv for kv in slots.items()))
    # Each colour goes to the spot inside a mapped tee box whose yardage best matches the card (markers move up and
    # back within a long box). Hand-placed tees override that: tee_pins.csv  hole,label,lat,lon
    # (label = a card colour, or back/front of a long box that isn't mapped)
    pins = {}
    if os.path.exists("tee_pins.csv"):
        from pyproj import Transformer
        tr = Transformer.from_crs("EPSG:4326", "EPSG:%d" % c["epsg"], always_xy=True)
        for row in csv.DictReader(open("tee_pins.csv")):
            e, n = tr.transform(float(row["lon"]), float(row["lat"]))
            pins.setdefault(int(row["hole"]), {})[row["label"].strip().lower()] = np.array([e - c["sw_e"], n - c["sw_n"]])
        print("Using hand-placed tees from tee_pins.csv for holes", sorted(pins))
        if a.loops:                                       # tee_pins.csv uses the 1-27 numbering
            pins = {9 * k + j + 1: pins[9 * li + j + 1] for k, li in enumerate(idx) for j in range(9) if 9 * li + j + 1 in pins}
    def ahead(h, tp):                                     # the hole line from the tee onward (a forward tee skips bends behind it)
        pts = np.vstack([h["line"][0]] + h["path"] + [h["green"]])
        best, k = 1e18, 0
        for i in range(len(pts) - 1):
            v = pts[i + 1] - pts[i]; t = np.clip(np.dot(tp - pts[i], v) / max(np.dot(v, v), 1e-9), 0, 1)
            dd = np.hypot(*(tp - pts[i] - t * v))
            if dd < best - 1e-6:
                best, k = dd, i
        return [q for q in pts[k + 1:-1]]
    def yards_from(h, tp):
        route = np.vstack([tp] + ahead(h, tp) + [h["green"]])
        return float(np.sum(np.hypot(*np.diff(route, axis=0).T)) / 0.9144)
    report, need = [], 0
    assign = {}
    for hn in range(1, 19):
        h = byn.get(hn)
        line = "%2d: " % hn
        hp = pins.get(hn, {})
        for t_ in card["tees"]:
            want = t_["yards"][hn - 1]
            if h is not None and t_["name"].lower() in hp:
                tp = hp[t_["name"].lower()]; yd = yards_from(h, tp)
                assign[(hn, t_["name"])] = (tp, yd)
                line += "%s %d=%.0f(pin)  " % (t_["name"], want, yd)
                continue
            if h is not None and "back" in hp and "front" in hp:
                b_, f_ = hp["back"], hp["front"]; yb, yf = yards_from(h, b_), yards_from(h, f_)
                k = float(np.clip((yb - want) / (yb - yf), 0, 1)) if yb != yf else 0.0
                tp = b_ + (f_ - b_) * k; yd = yards_from(h, tp)
                flag = "" if abs(yd - want) <= max(12, 0.06 * want) else " <-CHECK"
                need += bool(flag)
                assign[(hn, t_["name"])] = (tp, yd)
                line += "%s %d=%.0f(box)%s  " % (t_["name"], want, yd, flag)
                continue
            if h is None or not h["boxes"]:
                line += "%s %d ?  " % (t_["name"], want); need += 1; continue
            best = None
            for b in h["boxes"]:
                back, front = b[2], b[3]
                yb, yf = yards_from(h, back), yards_from(h, front)
                k = float(np.clip((yb - want) / (yb - yf), 0, 1)) if abs(yb - yf) > 0.5 else 0.0
                p_ = back + (front - back) * k
                y_ = yards_from(h, p_)
                if best is None or abs(y_ - want) < abs(best[0] - want):
                    best = (y_, p_)
            yd, tp = best
            off = yd - want
            flag = "" if abs(off) <= max(12, 0.06 * want) else " <-CHECK"
            if flag and a.line_tees and want < yd:            # forward tee not mapped: put it on the hole line at the card yardage
                route = np.vstack([tp] + ahead(h, tp) + [h["green"]])
                seg = np.hypot(*np.diff(route, axis=0).T); cum = np.r_[0, np.cumsum(seg)]
                s_at = cum[-1] - want * 0.9144
                i_ = int(np.clip(np.searchsorted(cum, s_at) - 1, 0, len(seg) - 1))
                tp = route[i_] + (route[i_ + 1] - route[i_]) * ((s_at - cum[i_]) / max(seg[i_], 1e-6))
                yd = yards_from(h, tp); flag = " (on hole line)"
            if "CHECK" in flag:
                need += 1
            assign[(hn, t_["name"])] = (tp, yd)
            line += "%s %d=%.0f%s  " % (t_["name"], want, yd, flag)
        report.append(line)
    print("\n".join(report))
    print("%d tee placements look off (no box within ~6%% of the card); pin those boxes like at Tierra Rejada." % need if need else "Every card yardage matched a mapped tee box.")

    tpl_path = a.template or os.path.expanduser("~/Tierra/greenkeeper/TierraRejada.GKD")
    if not os.path.exists(tpl_path):
        print("No template GKD at %s, so no GKD written (pass --template path/to/any.GKD)." % tpl_path)
        return
    d = json.load(open(tpl_path, encoding="utf-8-sig"))
    P = lambda q: {"x": round(float(q[0]), 3), "y": round(yv(q), 3), "z": round(float(q[1]), 3)}
    d.update({"SceneFolderName": a.scene or c["name"], "CourseName": a.name or c["name"], "CourseLat": c["center_lat"], "CourseLong": c["center_lon"],
              "Location": "", "CityTown": "", "StateCountyProvince": "", "Country": "", "Designer": "", "Homage": "",
              "CourseInfo": "", "CourseImageFileName": "", "HasAlternateLayouts": False, "BenchMarkComplete": False,
              "hazardCount": 0, "Hazards": [], "teeTypeCount": len(card["tees"])})
    for slot in GSP_SLOTS:
        d[slot.replace("Par3", "PAR3") + "SR"] = "0.0/0"
    for t_ in card["tees"]:
        d[slots[t_["name"]].replace("Par3", "PAR3") + "SR"] = t_["sr"]
    pars = card.get("par") or [int(byn[i]["par"] or 0) if i in byn else 0 for i in range(1, 19)]
    d["CoursePar"] = int(sum(pars))
    fa = fairway_aims(c, [dict(h, hole=n_) for n_, h in byn.items()], pars)
    if fa:
        for hn, aims in fa.items():
            byn[hn]["aims"] = aims
        print("Aim points: widest part of the fairway on %d holes (from course.svg); the rest follow the hole line." % len(fa))
    totals = {s_: 0.0 for s_ in GSP_SLOTS}
    new_holes = []
    days = ["Thursday", "Friday", "Saturday", "Sunday"]
    offsets = [(0, 0), (4, 3), (-4, 3), (3, -4)]
    for hn in range(1, 19):
        h = byn.get(hn)
        hole = {"Enabled": True, "HoleNumber": hn, "Par": pars[hn - 1], "Index": (card.get("hcp") or [0] * 18)[hn - 1], "Tees": [], "Pins": []}
        gc = h["green"] if h else np.array([0.0, 0.0])
        aims = h["aims"] if h and pars[hn - 1] > 3 else []
        for slot in GSP_SLOTS:
            names = [n_ for n_, s_ in slots.items() if s_ == slot]
            got = assign.get((hn, names[0])) if names else None
            if got:
                tp = got[0]
                route = np.vstack([tp] + (ahead(h, tp) if h else []) + [gc])
                dist = float(np.sum(np.hypot(*np.diff(route, axis=0).T)))
                totals[slot] += dist
                hole["Tees"].append({"TeeType": slot, "Enabled": True, "Distance": round(dist, 3), "Position": P(tp)})
            else:
                hole["Tees"].append({"TeeType": slot, "Enabled": False, "Distance": 0.0, "Position": None})
        for k in range(2):
            hole["Tees"].append({"TeeType": "AimPoint%d" % (k + 1), "Enabled": k < len(aims), "Distance": 0.0,
                                 "Position": P(aims[k]) if k < len(aims) else None})
        hole["Tees"].append({"TeeType": "GreenCenterPoint", "Enabled": False, "Distance": 0.0, "Position": P(gc) if h else None})
        for day, (ox, oz) in zip(days, offsets):
            hole["Pins"].append({"Day": day, "Position": P(gc + np.array([ox, oz]))})
        new_holes.append(hole)
    d["Holes"] = new_holes
    d["TeeTypeTotalDistance"] = [{"TeeType": s_, "Enabled": True, "Distance": round(totals[s_], 3), "Position": None} for s_ in GSP_SLOTS]
    if "pOOB" in d:
        d["pOOB"] = {"pointCount": 0, "coords": []}
    for k_, v_ in c.get("gkd", {}).items():              # course-wide settings (location, altitude, wind, keywords...)
        d[k_] = v_
    if a.ob:
        add_ob(d, c, byn, P, yv)
    out = (a.scene or c["name"]) + ".GKD"
    json.dump(d, open(out, "w"), separators=(",", ":"))
    print("Wrote %s (tees, greens, aim points, 4 pins per green). Open it in Greenkeeper, check, then Save there." % out)


def add_ob(d, c, byn, P, yv):
    """Draft OB the Tierra Rejada way: in bounds = turf, cart paths and a strip of natural ground beside them;
    homes, yards and roads are always out; brush islands between holes become interior OB (innerOOB);
    OSM water becomes water hazards. Every tee, aim point and green is checked to be in bounds."""
    from skimage import measure
    S = int(c["size"])
    V = np.load("veg_classes.npz")
    L = osm_layers(c)
    yy, xx = np.mgrid[0:S, 0:S] + 0.5
    play = np.zeros((S, S), bool)                         # this layout's holes only (tees -> aims -> green, 70 m each side)
    lines = []
    for hn, h in byn.items():
        pts = [h["line"][0]] + list(h["path"]) + [h["green"]]
        lines += [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    dist = np.full((S, S), 1e9, np.float32)
    for (ax_, az), (bx, bz) in lines:
        dx, dz = bx - ax_, bz - az
        t = np.clip(((xx - ax_) * dx + (yy - az) * dz) / max(dx * dx + dz * dz, 1e-9), 0, 1)
        dist = np.minimum(dist, np.hypot(xx - ax_ - t * dx, yy - az - t * dz))
    near = dist <= 70
    turf = V["turf"] & near
    paths = ndimage.binary_dilation(L["cartpath"], disk(3)) & (dist <= 90)
    room = ndimage.distance_transform_edt(~turf) <= 10    # 10 m of natural ground beside turf is playable
    inb = (turf | paths | (room & near)) & ~ndimage.binary_dilation(V["developed"] & ~V["turf"], disk(2))
    inb = ndimage.binary_closing(inb, disk(3)) & ~V["developed"] | turf
    must = np.zeros((S, S), bool)
    for h in d["Holes"]:                                  # every tee, aim point and pin gets at least 6 m of room
        for pos in [t_.get("Position") for t_ in h["Tees"]] + [p_["Position"] for p_ in h["Pins"]]:
            if pos:
                X, Z = int(pos["x"]), int(pos["z"])
                must[max(0, Z - 6):Z + 7, max(0, X - 6):X + 7] |= disk(6)[max(0, 6 - Z):13 - max(0, Z + 7 - S), max(0, 6 - X):13 - max(0, X + 7 - S)]
    inb |= must
    lab, n = ndimage.label(inb)
    keep = np.zeros(n + 1, bool); keep[np.unique(lab[(turf & (dist < 25)) | must])] = True; keep[0] = False
    inb = keep[lab]
    if ndimage.label(inb)[1] > 1:                        # join pieces along the hole lines (road crossings, bridges)
        inb |= (dist <= 4) & ~L["building"]
    full = ndimage.binary_fill_holes(inb)
    from PIL import Image as _I, ImageDraw as _D
    for _ in range(20):                                   # GSPro takes one boundary: link leftover pieces with a 6 m neck
        lab2, n2 = ndimage.label(full)
        if n2 <= 1:
            break
        sizes2 = np.bincount(lab2.ravel()); sizes2[0] = 0
        main = lab2 == np.argmax(sizes2)
        dmain, (iy, ix) = ndimage.distance_transform_edt(~main, return_indices=True)
        other = (lab2 > 0) & ~main
        k = np.argmin(np.where(other, dmain, np.inf)); oy, ox = np.unravel_index(k, other.shape)
        im = _I.new("L", (S, S), 0); _D.Draw(im).line([(ox, oy), (ix[oy, ox], iy[oy, ox])], fill=255, width=6)
        full |= np.asarray(im) > 0
        full = ndimage.binary_fill_holes(full)
    holes_ = full & ~inb & ~ndimage.binary_dilation(V["turf"] & near, disk(3))   # brush islands inside the boundary
    out_ = ndimage.binary_opening(holes_, disk(2))
    cont = max(measure.find_contours(np.pad(full, 1).astype(float), 0.5), key=len)
    cont = measure.approximate_polygon(cont, 1.0) - 1
    pts = [(float(q[1]), float(q[0])) for q in cont[:-1]]
    d["pOOB"] = {"pointCount": len(pts), "coords": [P(np.array(p_)) for p_ in pts]}
    hz = []
    il, ni = ndimage.label(out_)
    for i in range(1, ni + 1):
        m = il == i
        if m.sum() < 400 or (ndimage.binary_fill_holes(m) & ~m & inb).sum() > 20:   # skip patches wrapped around a tee or pin
            continue
        cc = max(measure.find_contours(np.pad(m, 1).astype(float), 0.5), key=len)
        cc = measure.approximate_polygon(cc, 1.0) - 1
        q = [P(np.array((float(v[1]), float(v[0])))) for v in cc[:-1]]
        hz.append({"pointCount": len(q), "coords": q, "DZpos": {"x": 0.0, "y": 0.0, "z": 0.0}, "freeDrop": False,
                   "innerOOB": True, "noAIL": False, "hasDZ": False, "islandGreen": False})
    n_inner = len(hz)
    wl, nw = ndimage.label(L["water"] & near)
    for i in range(1, nw + 1):
        m = wl == i
        if m.sum() < 50:
            continue
        cc = max(measure.find_contours(np.pad(m, 1).astype(float), 0.5), key=len)
        cc = measure.approximate_polygon(cc, 0.5) - 1
        q = [P(np.array((float(v[1]), float(v[0])))) for v in cc[:-1]]
        hz.append({"pointCount": len(q), "coords": q, "DZpos": {"x": 0.0, "y": 0.0, "z": 0.0}, "freeDrop": False,
                   "innerOOB": False, "noAIL": False, "hasDZ": False, "islandGreen": False})
    d["Hazards"], d["hazardCount"] = hz, len(hz)
    bad = []
    inside = full & ~out_
    for h in d["Holes"]:
        for t_ in h["Tees"] + [{"TeeType": "Pin " + p_["Day"], "Position": p_["Position"]} for p_ in h["Pins"]]:
            pos = t_.get("Position")
            if pos and not inside[min(int(pos["z"]), S - 1), min(int(pos["x"]), S - 1)]:
                bad.append("%d %s" % (h["HoleNumber"], t_["TeeType"]))
    print("OB: pOOB %d points, %d interior OB patches (brush between holes), %d water hazards. %s" % (
        len(pts), n_inner, len(hz) - n_inner, "Out of bounds by mistake: " + ", ".join(bad) if bad else "All tees, aim points and pins are in bounds."))


SVG_LAYERS = [("Rough", "rough", "#278438"), ("Deep", "deep", "#164B20"), ("Fairway", "fairway", "#43E561"),
              ("Tee", "tee", "#A0E5B8"), ("Green", "green", "#BCE5A4"), ("Bunker", "bunker", "#E5E5AA"), ("Water", "water", "#0000C0")]


def tee_pads(gkd, tee_img, S, R, w=7.0, l=9.0):
    """Draw a w x l m pad (long side toward the green) on the Tee layer under every GKD tee that has no mapped
    tee box (forward tees put on the hole line, moved stacked tees). Writes tee_pads.csv; returns the pad mask."""
    from PIL import Image, ImageDraw
    d = json.load(open(gkd, encoding="utf-8-sig"))
    have = np.asarray(tee_img) > 0
    N = have.shape[0]
    pad_img = Image.new("L", (N, N), 0); dp = ImageDraw.Draw(pad_img); dt = ImageDraw.Draw(tee_img)
    rows = []
    for h in d["Holes"]:
        T = {x["TeeType"]: x for x in h["Tees"]}
        g = T["GreenCenterPoint"]["Position"]
        for name in ("Black", "Blue", "White", "Green", "Yellow", "Red"):
            x = T.get(name)
            if not x or not x["Enabled"] or not x["Position"]:
                continue
            px, pz = x["Position"]["x"], x["Position"]["z"]
            col, row = int(px / R), int((S - pz) / R)
            if 0 <= row < N and 0 <= col < N and have[max(0, row - 1):row + 2, max(0, col - 1):col + 2].all():
                continue                                # already on a mapped box
            ux, uz = g["x"] - px, g["z"] - pz; L = math.hypot(ux, uz); ux, uz = ux / L, uz / L
            vx, vz = -uz, ux
            corners = [(px + sa * l / 2 * ux + sb * w / 2 * vx, pz + sa * l / 2 * uz + sb * w / 2 * vz)
                       for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            poly = [(cx / R, (S - cz) / R) for cx, cz in corners]
            dt.polygon(poly, fill=255); dp.polygon(poly, fill=255)
            rows.append([h["HoleNumber"], name, round(px, 2), round(pz, 2), round(x["Position"]["y"], 2)])
    with open("tee_pads.csv", "w", newline="") as fh:
        wr = csv.writer(fh); wr.writerow(["hole", "tee", "x", "z", "y"]); wr.writerows(rows)
    print("Tee pads: %d added (%g x %g m, 2 m first cut) for GKD tees with no mapped box -> tee_pads.csv" % (len(rows), w, l))
    return np.asarray(pad_img) > 0


def terrain_on_grid(c, N, R):
    """Heightmap (metres above y_offset) sampled on the svg pixel grid (row 0 = north edge)."""
    S = c["size"]
    hm = np.fromfile("heightmap_2049.raw", "<u2").reshape(2049, 2049).astype(np.float32) * (c["terrain_height"] / 65535.0)
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32) * R
    return ndimage.map_coordinates(hm, [(S - yy) * 2048 / S, xx * 2048 / S], order=1)


def green_approach(hole_lines, gx, gy, R):
    """Unit vector of play into the green at pixel (gx, gy): last segment of the nearest hole line end (within 40 m)."""
    best, d0 = None, 40 / R
    for _, p in hole_lines:
        d = np.hypot(*(p[-1] - (gx, gy)))
        if d < d0 and len(p) > 1:
            best, d0 = p[-1] - p[-2], d
    return None if best is None else best / max(np.hypot(*best), 1e-6)


def green_collar(c, green, hole_lines, R, side, back, bank=0.25):
    """Short-grass collar round each green (Tierra lesson: rough right off the green grabbed chips that should roll out).
    `side` m round the front and sides, `back` m on the far side from the approach, 1 m where the ground behind rises
    as a bank (rise/run > `bank`), so chips that run up a bank stay in rough like the real course."""
    N = green.shape[0]
    dist, (iy, ix) = ndimage.distance_transform_edt(~green, return_indices=True)
    dist = dist * R
    H = terrain_on_grid(c, N, R)
    slope = (H - H[iy, ix]) / np.maximum(dist, 0.5)
    glab, ng = ndimage.label(green)
    ux, uy, cx, cy = (np.zeros(ng + 1) for _ in range(4))
    for i, (gy, gx) in enumerate(ndimage.center_of_mass(green, glab, range(1, ng + 1)), start=1):
        cx[i], cy[i] = gx, gy
        u = green_approach(hole_lines, gx, gy, R)
        if u is not None:
            ux[i], uy[i] = u
    near = glab[iy, ix]
    yy, xx = np.mgrid[0:N, 0:N]
    behind = ((xx - cx[near]) * ux[near] + (yy - cy[near]) * uy[near]) > 0
    width = np.where(behind, back, side)
    width = np.where(slope > bank, 1.0, width)
    return (dist > 0) & (dist <= width)


def bunker_profiles(c, bunker, green, hole_lines, R):
    """bunkers.csv for the Unity bunker tool (Tierra lesson: deep round bowls played like fairway, balls ran through).
    Depth by area (0.25 m < 60 m2, 0.35 m to 150 m2, 0.5 m above), flat floor (< 3 deg), steep face (25-30 deg)
    toward the green, gentle entry (< 12 deg) from the approach side."""
    S = c["size"]
    blab, nb = ndimage.label(bunker)
    glab, ng = ndimage.label(green)
    gcen = np.array(ndimage.center_of_mass(green, glab, range(1, ng + 1))).reshape(-1, 2)
    rows = []
    for i, (by, bx) in enumerate(ndimage.center_of_mass(bunker, blab, range(1, nb + 1)), start=1):
        area = float((blab == i).sum() * R * R)
        if area < 4:
            continue
        depth = 0.25 if area < 60 else 0.35 if area <= 150 else 0.5
        hole, kind, face = "", "fairway", None
        if len(gcen):
            gd = np.hypot(gcen[:, 1] - bx, gcen[:, 0] - by) * R
            k = int(np.argmin(gd))
            if gd[k] < 45:                              # greenside: face toward that green
                kind, face = "greenside", (gcen[k, 1] - bx, gcen[k, 0] - by)
        if hole_lines:
            dl = [np.min(np.hypot(*(np.array(_densify(p)) - (bx, by)).T)) for _, p in hole_lines]
            j = int(np.argmin(dl)); hole = hole_lines[j][0]
            if face is None:                            # fairway bunker: face toward that hole's green
                face = tuple(hole_lines[j][1][-1] - (bx, by))
        bearing = (np.degrees(np.arctan2(face[0], -face[1])) % 360) if face is not None else ""
        rows.append([i, hole, kind, round(bx * R, 1), round(S - by * R, 1), round(area, 1), depth,
                     "" if bearing == "" else round(float(bearing)), 3, 28, 12])
    with open("bunkers.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["bunker", "hole", "kind", "x", "z", "area_m2", "depth_m", "face_bearing_deg", "floor_max_deg", "face_max_deg", "entry_max_deg"])
        w.writerows(rows)
    print("bunkers.csv: %d bunkers, depth 0.25/0.35/0.5 m by size, flat floors, steep face toward the green (bearing = compass direction of the face)" % len(rows))


def _densify(p, step=4.0):
    out = [p[0]]
    for a_, b_ in zip(p[:-1], p[1:]):
        n_ = max(1, int(np.hypot(*(b_ - a_)) / step))
        out += [a_ + (b_ - a_) * t_ for t_ in np.linspace(0, 1, n_ + 1)[1:]]
    return out


def cmd_svg(a):
    """Draft OPCD SVG: greens/tees/bunkers/water from OSM, fairways from OSM or detected from the photo,
    deep rough from the brush mask, rough = the rest of the course. Image coords: x east, y = size - north (metres)."""
    from PIL import Image, ImageDraw
    from pyproj import Transformer
    try:
        from skimage import measure
    except ImportError:
        sys.exit("Needs scikit-image:  ~/venv/bin/python -m pip install scikit-image")
    c = load_cfg(); S = int(c["size"]); R = a.res; N = int(S / R)
    if not os.path.exists("map.osm") or not os.path.exists("satellite.jpg"):
        sys.exit("Needs map.osm and satellite.jpg in this folder.")
    t = Transformer.from_crs("EPSG:4326", "EPSG:%d" % c["epsg"], always_xy=True)
    root = ET.parse("map.osm").getroot()
    nodes = {}
    for nd in root.iter("node"):
        e, n = t.transform(float(nd.get("lon")), float(nd.get("lat")))
        nodes[nd.get("id")] = ((e - c["sw_e"]) / R, (S - (n - c["sw_n"])) / R)
    names = ("green", "tee", "bunker", "water", "fairway", "line", "course", "exclude")
    imgs = {k: Image.new("L", (N, N), 0) for k in names}
    drw = {k: ImageDraw.Draw(v) for k, v in imgs.items()}
    road_w = {"motorway": 30, "motorway_link": 14, "trunk": 24, "primary": 20, "secondary": 16, "tertiary": 12, "residential": 10, "service": 6}
    hole_lines = []                                  # (ref, pixel points tee -> green)
    for w in root.findall("way"):
        tg = {q.get("k"): q.get("v") for q in w.findall("tag")}
        p = [nodes[q.get("ref")] for q in w.findall("nd") if q.get("ref") in nodes]
        if len(p) < 2:
            continue
        g = tg.get("golf")
        poly = len(p) > 2
        if g == "hole":
            drw["line"].line(p, fill=255, width=max(1, int(1 / R)))
            hole_lines.append((tg.get("ref", "?"), np.array(p)))
        elif g in ("green", "tee", "bunker", "fairway") and poly:
            drw[g].polygon(p, fill=255)
        elif (g in ("water_hazard", "lateral_water_hazard") or (tg.get("natural") == "water" and tg.get("water") not in ("river", "canal"))) and poly:   # rivers (LA River) are off-course channels
            drw["water"].polygon(p, fill=255)
        elif tg.get("leisure") == "golf_course" and poly:
            drw["course"].polygon(p, fill=255)
        elif ("building" in tg or tg.get("amenity") == "parking" or tg.get("landuse") in ("residential", "commercial", "retail", "industrial")) and poly:
            drw["exclude"].polygon(p, fill=255)
        elif tg.get("highway") in road_w and g != "cartpath":
            drw["exclude"].line(p, fill=255, width=int(road_w[tg["highway"]] / R))
    pads = tee_pads(a.gkd, imgs["tee"], S, R) if a.gkd else None   # GKD tees with no mapped box get their own pad
    M = {k: np.asarray(v) > 0 for k, v in imgs.items()}
    line_dist = ndimage.distance_transform_edt(~M["line"]) * R
    feats = M["green"] | M["tee"] | M["bunker"] | M["water"]

    # course area: mapped boundary if it holds the holes, else a corridor around holes and features
    course = M["course"]
    if not course.any() or course[M["line"]].mean() < 0.6:
        course = (line_dist < a.corridor) | (ndimage.distance_transform_edt(~(feats | M["fairway"])) * R < 20)
        print("Course area: %d m around the hole lines (no usable golf_course boundary in map.osm)" % a.corridor)
    else:
        print("Course area: mapped golf_course boundary")
    course &= ~M["exclude"]

    # fairways: use OSM where a hole has one, otherwise detect smooth bright turf along the hole line
    sat = np.asarray(Image.open("satellite.jpg").convert("RGB").resize((N, N), Image.BILINEAR), dtype=np.float32)
    lum = sat.mean(2); gr = sat[..., 1] / np.maximum(sat.sum(2), 1)
    k = max(3, int(round(7 / R)) | 1)
    tex = np.sqrt(np.maximum(ndimage.uniform_filter(lum ** 2, k) - ndimage.uniform_filter(lum, k) ** 2, 0))
    grs = ndimage.uniform_filter(gr, k)
    it = max(1, int(round(3 / R)))
    cand = (tex < a.smooth) & (grs >= a.min_green) & (line_dist < a.fw_corridor) & ~ndimage.binary_dilation(feats, iterations=max(1, int(1 / R)))
    cand = ndimage.binary_closing(ndimage.binary_opening(cand, iterations=it), iterations=it)
    lab, _ = ndimage.label(cand)
    det = np.isin(lab, np.unique(lab[(line_dist < 18) & (lab > 0)])) & (lab > 0)
    det = ndimage.binary_fill_holes(ndimage.binary_closing(det, iterations=int(round(5 / R))))
    osm_fw = M["fairway"]
    if osm_fw.any():
        flab, _ = ndimage.label(det)
        covered = np.unique(flab[ndimage.binary_dilation(osm_fw, iterations=int(10 / R)) & (flab > 0)])
        det &= ~np.isin(flab, covered)              # drop detections where OSM already has a fairway
    fairway = (osm_fw | det) & course
    print("Fairways: %.1f ha from OSM, %.1f ha detected from the photo (draft - check in Inkscape)" % (osm_fw.sum() * R * R / 1e4, (det & course).sum() * R * R / 1e4))

    deep = np.zeros_like(fairway)
    if os.path.exists("veg_classes.npz"):            # from the vegetation step: natural ground stays bare terrain for scrub painting
        from PIL import Image as _I
        V = np.load("veg_classes.npz")
        rs = lambda m: np.asarray(_I.fromarray(np.flipud(m).astype(np.uint8) * 255).resize((N, N), _I.NEAREST)) > 0
        course &= ~(rs(V["scrub"]) | rs(V["grass"]))
        deep = rs(V["deep"]) & course
        fairway &= course
        print("Using veg_classes.npz: scrub and golden-grass ground left out of the rough mesh, deep rough = the band next to turf")
    elif os.path.exists("brush_mask.png"):
        bm = np.asarray(Image.open("brush_mask.png").convert("L").resize((N, N), Image.NEAREST)) > 0   # stored north-up
        deep = bm & course
    if a.collar > 0 and M["green"].any():
        collar = green_collar(c, M["green"], hole_lines, R, a.collar, a.collar_back)
        fairway |= collar & ~M["exclude"]
        course |= collar & ~M["exclude"]
        deep &= ndimage.distance_transform_edt(~M["green"]) * R > a.deep_off_green
        print("Green collars: %.0f m sides, %.0f m back, 1 m on uphill banks; deep rough kept %.0f m off greens" % (a.collar, a.collar_back, a.deep_off_green))
    if pads is not None and pads.any():                # 2 m first cut round the added pads
        cut = ndimage.binary_dilation(pads, iterations=max(1, int(round(2 / R)))) & ~M["tee"] & ~M["exclude"]
        fairway |= cut; course |= cut
        # a pad on the fairway edge left a notch that OPCD filled with fairway (Wilson 2, 9, 14 Yellow):
        # wrap any pad that touches fairway in a closed 3 m fairway ring so it is a clean hole in the fairway
        plab, npad = ndimage.label(pads)
        it3 = max(1, int(round(3 / R)))
        for i in range(1, npad + 1):
            ring = ndimage.binary_dilation(plab == i, iterations=it3)
            if (ring & fairway & ~cut).any():
                add = ring & ~M["tee"] & ~M["green"] & ~M["bunker"] & ~M["water"]
                fairway |= add; course |= add
        # a pad that still sits on the fairway edge (ring blocked by a mapped tee box) gets a 3 m rough moat instead,
        # so it never touches fairway
        filled = ndimage.binary_fill_holes(fairway)
        for i in range(1, npad + 1):
            pi = plab == i
            if (ndimage.binary_dilation(pi, iterations=it3) & fairway).any() and not filled[pi].all():
                fairway &= ~ndimage.binary_dilation(pi, iterations=it3)
    if M["bunker"].any():
        bunker_profiles(c, M["bunker"], M["green"], hole_lines, R)
    # one class per pixel, highest priority wins
    label = np.zeros((N, N), np.uint8)
    for code, m in ((1, course), (2, deep), (3, fairway), (4, M["tee"]), (5, M["green"]), (6, M["bunker"]), (7, M["water"])):
        label[m] = code
    near_course = ndimage.binary_dilation(course, iterations=int(round(25 / R)))
    label[~course & ~feats] = 0
    label[~near_course] = 0          # ignore greens/tees/bunkers/water mapped outside the course (creeks, other facilities)

    out = ['<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
           '<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
           'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" width="%dmm" height="%dmm" viewBox="0 0 %d %d" version="1.1">' % (S, S, S, S)]
    counts = {}
    for code, (title, pid, col) in enumerate(SVG_LAYERS, start=1):
        out.append('<g inkscape:groupmode="layer" id="layer_%s" inkscape:label="%s">' % (pid, title))
        m = label == code
        m = ndimage.binary_opening(m, iterations=1) if code in (1, 2, 3) else m
        comp, n = ndimage.label(m)
        sl = ndimage.find_objects(comp)
        idx = 0
        for i, s_ in enumerate(sl, start=1):
            if s_ is None:
                continue
            sub = np.pad((comp[s_] == i).astype(float), 1)
            if sub.sum() * R * R < (max(a.min_area, 150) if code in (2, 3) else a.min_area):
                continue
            loops = []
            for cont in measure.find_contours(sub, 0.5):
                cont = measure.approximate_polygon(cont, tolerance=a.simplify / R)
                if len(cont) < 4:
                    continue
                ys = (cont[:, 0] - 1 + s_[0].start + 0.5) * R
                xs = (cont[:, 1] - 1 + s_[1].start + 0.5) * R
                loops.append("M " + " L ".join("%.3f,%.3f" % (x, y) for x, y in zip(xs, ys)) + " Z")
            if loops:
                out.append('<path id="%s_%d" style="fill:%s;fill-opacity:1;fill-rule:evenodd;stroke:none" d="%s"/>' % (pid, idx, col, " ".join(loops)))
                idx += 1
        counts[title] = idx
        out.append("</g>")
    out.append("</svg>")
    open("course.svg", "w").write("\n".join(out))
    print("Wrote course.svg:", ", ".join("%s %d" % kv for kv in counts.items()))
    print("Areas (ha):", ", ".join("%s %.1f" % (t_, (label == i).sum() * R * R / 1e4) for i, (t_, _, _) in enumerate(SVG_LAYERS, start=1)))

    try:
        cols = np.array([[0, 0, 0, 0]] + [[int(cl[1:3], 16), int(cl[3:5], 16), int(cl[5:7], 16), 150] for _, _, cl in SVG_LAYERS], np.uint8)
        ov = Image.fromarray(cols[label], "RGBA")
        base = Image.open("satellite.jpg").convert("RGBA").resize((N, N))
        prev = Image.alpha_composite(base, ov)
        prev.thumbnail((2000, 2000))
        prev.save("course_svg_preview.png")
        print("Wrote course_svg_preview.png")
    except Exception as e:
        print("(preview skipped: %s)" % e)


# ---------------------------------------------------------------- cli
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("new"); p.add_argument("name"); p.add_argument("lat", type=float); p.add_argument("lon", type=float)
    p.add_argument("--size", type=float, default=2000); p.add_argument("--root", default="~/courses")
    p.add_argument("--sw-e", type=float); p.add_argument("--sw-n", type=float); p.add_argument("--y-offset", type=float)
    p = sp.add_parser("lidar"); p.add_argument("--survey"); p.add_argument("--ept", help="read this survey from USGS's EPT copy on AWS (fast), e.g. USGS_LPC_CA_SoCal_Wildfires_B3_2018_LAS_2019")
    p = sp.add_parser("satellite"); p.add_argument("--pixels", type=int, default=4096)
    sp.add_parser("heightmap")
    p = sp.add_parser("trees"); p.add_argument("--min-height", type=float, default=3.0); p.add_argument("--buffer", type=float, default=150); p.add_argument("--gkd")
    p.add_argument("--min-green", type=float, default=0.355, help="satellite green share a crown needs (0 = off)")
    p.add_argument("--course-margin", type=float, default=60, help="metres beyond the mapped course boundary to keep (-1 = ignore boundary)")
    p = sp.add_parser("brush"); p.add_argument("--low", type=float, default=0.5); p.add_argument("--high", type=float, default=3.5)
    p.add_argument("--spacing", type=float, default=3.0); p.add_argument("--buffer", type=float, default=200); p.add_argument("--gkd")
    p.add_argument("--course-margin", type=float, default=60, help="metres beyond the mapped course boundary to keep (-1 = ignore boundary)")
    p = sp.add_parser("vegetation"); p.add_argument("--buffer", type=float, default=200, help="Plant Shrubs only within this distance of play")
    p.add_argument("--yard", type=float, default=14, help="metres around each house that are yard (no brush)")
    p.add_argument("--lot", type=float, default=40, help="lawns and paving within this distance of a house are developed")
    p.add_argument("--deep-band", type=float, default=4, help="deep rough band between turf and natural ground (m)")
    p.add_argument("--grass-band", type=float, default=9, help="golden grass band out to this distance, then scrub (m)")
    p.add_argument("--turf-green", type=float, default=0.365); p.add_argument("--turf-smooth", type=float, default=7.0)
    p.add_argument("--reach", type=float, default=250, help="paint natural ground only this far outside the course boundary (m)")
    p.add_argument("--woodland", type=float, default=0.45, help="canopy share that makes ground orchard/woodland (no scrub)")
    p.add_argument("--parkland", action="store_true", help="treat everything inside the mapped golf course boundary as turf (tree-lined parkland, no scrub between holes)")
    p = sp.add_parser("osm"); p.add_argument("--paths-fallback", action="store_true", help="use footpaths if no golf=cartpath")
    sp.add_parser("holes")
    p = sp.add_parser("card"); p.add_argument("--template"); p.add_argument("--name"); p.add_argument("--scene")
    p.add_argument("--loops", help="27-hole club: two loop names from course.json, e.g. Ridgeline,Creekside (card from scorecard_27.csv)")
    p.add_argument("--line-tees", action="store_true", help="forward tees with no mapped box go on the hole line at the card yardage")
    p.add_argument("--ob", action="store_true", help="also draft OB (pOOB, interior OB in brush) and water hazards")
    p.add_argument("--map", type=lambda v: dict(kv.lower().split("=", 1) for kv in v.split(",")), help="e.g. grey=Green,gold=Yellow")
    p = sp.add_parser("svg"); p.add_argument("--res", type=float, default=0.5, help="metres per pixel when tracing")
    p.add_argument("--corridor", type=float, default=60, help="course width around hole lines if no boundary is mapped")
    p.add_argument("--collar", type=float, default=3, help="short-grass collar round greens, metres (0 = none)")
    p.add_argument("--gkd", help="add a tee pad under every tee in this GKD that has no mapped tee box")
    p.add_argument("--collar-back", type=float, default=5, help="collar width behind the green (away from the approach)")
    p.add_argument("--deep-off-green", type=float, default=6, help="keep deep rough at least this far off greens")
    p.add_argument("--fw-corridor", type=float, default=38, help="max distance of detected fairway from the hole line")
    p.add_argument("--smooth", type=float, default=5.5, help="max photo texture for mown fairway (higher = more)")
    p.add_argument("--min-green", type=float, default=0.37, help="min green share of RGB for fairway")
    p.add_argument("--min-area", type=float, default=25, help="drop pieces smaller than this (m2)")
    p.add_argument("--simplify", type=float, default=0.15, help="outline simplification (m)")
    a = ap.parse_args()
    {"card": cmd_card, "holes": cmd_holes, "svg": cmd_svg, "osm": cmd_osm, "new": cmd_new, "lidar": cmd_lidar, "satellite": cmd_satellite, "heightmap": cmd_heightmap,
     "trees": cmd_trees, "brush": cmd_brush, "vegetation": cmd_vegetation}[a.cmd](a)


if __name__ == "__main__":
    main()

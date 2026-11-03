# Wilson Golf Course, Griffith Park (Los Angeles)

5500 Griffith Park Dr, Los Angeles, CA 90027. City of LA municipal course, opened 1927 (George C. Thomas Jr. era), former LA Open venue. Par 72, 7,002 yds from the Black tees. Shares Griffith Park with Harding (`../harding/`), which sits between Wilson's west holes and its east holes along the I-5.

## Card (men's card used in GSPro, confirmed by BoJa 2026-10-28)
`card.csv`: yardages from the club scorecard (BoJa's screenshots), Combo row and women's numbers from golfpass.com.
| Tee | Yards | M rating/slope | W rating/slope | GSPro slot |
|---|---|---|---|---|
| Black | 7,002 | 73.0/126 | 79.9/139 | Black |
| Blue | 6,718 | 71.7/122 | 78.3/135 | Blue |
| White | 6,382 | 70.2/118 | 76.4/131 | White |
| White/Yellow combo | 5,956 | 68.2/113 | 74.0/126 | Green |
| Yellow | 5,276 | 65.0/105 | 70.2/118 | Yellow |
Pars 5 4 3 4 4 4 4 4 5 / 4 3 4 4 5 3 4 4 4 (72). Men's HCP 13 3 7 17 15 9 5 1 11 / 4 6 16 14 10 18 2 12 8. Women play 8 and 16 as par 5 (74).

## Frame and data
Shared Griffith Park frame (`../course.json`): 2000 m square, centre 34.1405, -118.28425, EPSG:6340 SW corner 380594.21 E, 3777479.33 N, y = elevation - 120 m. Heightmap and satellite in `../`. LiDAR: USGS 3DEP CA_LosAngeles_1_B23 (QL1, 2023-24).
BoJa's course centre 34.14396, -118.28944 = Unity x 525.9, z 1389.7 (near hole 1 tee).

## Build status (2026-10-28)
- `map.osm`: Wilson-only golf features from BoJa's OSM export (18 holes, 38 tees, 20 greens, 25 bunkers, 1 water hazard, 27 cart paths, only 3 fairways).
- `holes.csv`, `tees.csv`: OSM hole lines are within 7 yds of the Black card on every hole.
- `GriffithWilson.GKD` (draft, Moorpark GKD as template, `coursekit card --line-tees --ob --map combo=Green`): every Black and Blue tee matched a mapped box; forward tees with no box were put on the hole line at card yardage (Combo/Yellow on 1, 4, 11, 12, 14, 16; Yellow on 3, 8, 10, 13, 17, 18; White on 11 and 14). Aim points at the widest fairway on 15 holes, 4 pins per green.
  OB draft: pOOB 427 points around Wilson (Harding in the middle is OB), 4 interior OB patches, 1 water hazard (pond by 4 green). `ob_preview.jpg`. Check the long interior OB strip in the woods west of 17/18 against the flyover; it may be playable woods.
- Trees, brush and vegetation were run with the whole-park map (both courses) and `--parkland`, so Harding shows as turf in Wilson's scene, not scrub. `trees.csv` 2,256 LiDAR trees (both courses), `shrubs_clean.csv`, `terrain_masks/`.
- `course.svg`: Rough 51 ha, Fairway 13.2 ha incl. green collars (2.9 ha from OSM, rest traced from the photo: check in Inkscape), Tee, Green, Bunker, Water from OSM. The LA River (OSM natural=water, water=river) is left out of the water layer.

## Play-feel lessons from Tierra (applied 2026-10-28)
- **Green collars** (in `course.svg`): a fairway-height collar round every green, 3 m on the front and sides, 5 m behind (away from the hole line's approach), only 1 m where the ground behind rises as a bank (rise/run > 0.25) so chips running up a bank stay in rough. Deep rough kept at least 6 m off greens. `coursekit svg --collar 3 --collar-back 5 --deep-off-green 6`.
- **Bunkers that play like sand** (`bunkers.csv`, for the Unity bunker tool): keep every bunker on the OPCD Bunker layer so SetMeshMaterials gives it sand, then grade by size: 0.25 m deep under 60 m2, 0.35 m to 150 m2, 0.5 m above; flat floor (< 3 deg) so the ball settles, steep face (up to ~28 deg) on the side given by `face_bearing_deg` (compass direction toward the green), gentle entry (< 12 deg) on the approach side. Greenside bunkers face their green, fairway bunkers face their hole's green. GSPro's own sand penalty is mild and can't be changed from the course (found on Tierra).
- `scripts/coursekit.py` here has both changes plus the LA River fix (water=river/canal is not a hazard).

## BoJa feedback checklist (/mnt/project-files/course-build/BOJA_FEEDBACK_CHECKLIST.md), status for Wilson 2026-10-28
Done in the data (`scripts/apply_checklist.py` on the GKD, `scripts/coursekit.py svg` for the drawing):
- Bunkers: sand layer, `bunkers.csv` depth/floor/face plan. Green collars 3 m / 5 m back / 1 m on banks, deep rough 6 m off greens.
- Tees never stacked: where two colours shared a spot (Combo = White or Yellow yardage on every hole, and White/Blue on 2), the forward one moved 3.5 m sideways, on the mapped box where possible. Distances re-measured.
- Tee yardages vs card: Black and Blue within 4 yds everywhere. White sits on a real box 11 yds long of the card on 1 and 2 and 6 yds on 5 (Combo too on 5); check in the flyover.
- Par 3s (3, 11, 15) aim at the green centre. Other aim points at the widest fairway in the drive zone.
- No tee in or within 2 m of OB or a hazard. No hazard with a drop zone (so no innerOOB problem); the pond by 4 green is a plain water hazard.
- Course name "Wilson - Griffith Park", Designer field "jboshers" (BoJa's choice 10/28, all courses), Los Angeles; altitude 448 ft; Parkland + Historic keywords. Rating 73.0/126 from the Black tees.
- Cart paths: from OSM (27 paths, 12.2 km), like Harding's.
- Trees: LiDAR positions checked against the satellite (`trees_on_satellite.png` in the shared build folder).
- Big misses: Harding (between Wilson's west and east holes) is OB; Wilson's parallel fairways stay in play, as on the real course.
Flag for BoJa: `green_slopes.csv` - 12 greens have an overall slope over 3 % in the LiDAR (1, 2, 3, 4, 5, 8, 9, 10, 13, 15, 16, 17; steepest 17 at 4.8 %). Not smoothed, same as Tierra (waiting on review/scans).
To do on the PC build (Unity side): own project C:\GSP\Wilson_Project; Flyover reads the project GKD; no compile errors; GKD already set to the approved DefaultStimp 2, MaxStimp 5, green and fairway firmness 0, splash Wilson.jpg; warm tan sand; bunker grading from `bunkers.csv`; tree LOD/billboards like Tierra and canopy colliders at ~80% of crown with a tee shot sweep; nets/fences solid colliders; cart paths darker than white concrete and lifted 4 cm; smooth fairway patch edges; backdrop terrain 1-2 km with fog (Griffith Park hills and the I-5 side); buildings matched to photos.

## PC build round 1 fixes (2026-10-28)
- **Tee pads:** 25 GKD tees had no mapped box (mostly Yellow, Combo on 1/4/11/12/14/16, White on 11/14, plus the tees moved off stacked spots). Each now has a 7 x 9 m pad on the Tee layer (long side toward the green) with a 2 m first cut, from `coursekit.py svg --gkd GriffithWilson.GKD` (list in `tee_pads.csv`). `scripts/flatten_pads.py` levels the terrain under each pad in this folder's `heightmap_2049.raw` (3 m blend) and sets the GKD tee heights to match. So Wilson's heightmap now differs from Harding's at those pads only.
- **Bunker crowns:** 8 LiDAR trees on 6 bunkers overlapped the sand. All are real trees on the satellite (`bunker_trees_check.png`), but per the checklist (no crowns over sand, Penmar) every one now clears its bunker by at least 0.5 m. Crowns trimmed: 1155 (hole 3) 15 to 10 m, 417 (7) 13.5 to 9.5 m, 1679 (9) 11.5 to 5 m, 970 (15) 12.5 to 7.9 m, 100 (1) 7 to 6.2 m, 315 (18) 5.5 to 4.1 m. Trunks moved off the sand: 746 (15) by 3 m with its crown cut to 5 m, 496 (18) by 2.8 m. No crown overlaps a bunker now.

## PC build round 2 fixes (2026-10-28)
- **Yellow tees on 2, 9 and 14 came out on fairway after OPCD.** Their pads sat on the fairway edge, next to a mapped box, so the fairway outline had a tee-shaped notch that OPCD filled. coursekit svg now wraps any pad touching fairway in a closed 3 m fairway ring, and gives it a 3 m rough moat where a mapped box blocks the ring, so no pad touches the fairway edge. 14 Yellow moved onto the unlinked mapped box beside it (x 1120.5, z 662.2, 407 yds vs card 403), which is very likely the real forward tee. Now 24 pads. `scripts/svg_check.py` lists any GKD tee not inside the Tee layer, and every tee passes.
- **Bunker clearance at 1.3x crown:** rendered crowns are about 1.3x the LiDAR crown radius, so `scripts/clear_bunker_crowns.py` keeps every tree at least 1.3 x crown + 0.5 m from sand (11 trees trimmed or moved). No rendered crown reaches a bunker.

## PC build round 3 fix (2026-10-29)
- **2 and 9 Yellow on rough after OPCD.** Cause: when tees were de-stacked, the second colour had been pushed 3.5 m sideways to the edge of the shared mapped box, so its pad merged with the box into one jagged shape, and OPCD left that spot as rough. Probably the same as Harding 1 and 3 Yellow. `scripts/fix_box_tees.py` now puts every colour that shares a mapped box on the box itself, at least 3 m from the other colour and 1.2 m inside the edge, with yardage kept as close as possible. Moved: 2 White and Yellow, 5 Green, 6 Black, 7 Yellow, 9 Yellow, 13 Green, 17 Green. No pad touches a mapped box now, and no two colours are within 3 m. 19 pads remain, all in the open.

## Flyovers (from BoJa)
Front 9 https://youtu.be/zK3th5k1jfM · Back 9 https://youtu.be/8REieRe2TAQ

## Repo note (2026-11-03)
This folder is now its own repo (split out of the moorpark branch `claude/project-thread-flaaah`, `griffith-park/wilson`) wired to the course-build toolkit via `course.json`.
wilson/ had its own `heightmap_2049.raw` (levelled under the tee pads) and `satellite.jpg`; nothing was copied from the shared `griffith-park/` level.

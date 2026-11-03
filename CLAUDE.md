# Wilson GSPro course

Real course rebuilt for GSPro (Unity 2018.2.8f1, OPCD). Toolkit: `../course-build` (the course-build repo). Read its
`README.md` once, then the skill for the element you are working on in `../course-build/skills/`. All thresholds come from
`../course-build/rules/*.json`; this course's overrides are in `course.json` under `rule_overrides`.

## Where things are
- `course.json`: frame, paths, GKD fields, tee slot map, overrides. Every script reads paths from here.
- Unity project: `C:\GSP\Wilson_Project`. Editor tools in `Assets\Editor\` are copies from `../course-build\unity\shared\`; sync with
  `../course-build\automation\Run-CourseAutomation.ps1 -SyncTools`.
- Automation output: `C:\GSP\Wilson_Project\AutomationOutput\latest.txt` then that folder's `summary.md` and `shots\`.
- Never change `C:\GSProV1\Core\GSP\Courses\` without backing up the GKD first.

## Driving Unity
- Unity closed: `../course-build\automation\Run-CourseAutomation.ps1 -Config automation\Wilson.json [-Steps "a,b"]`.
- Unity open: `../course-build\automation\Send-UnityCommand.ps1 <ping|run|shots|invoke|describe|menu|save|refresh>`.

## Process
Follow `course-build-gates`: one hole, one edit, photo pair each; control hole before/after on course-wide passes; back up
scene, terrain and GKD before every change. Run the LiDAR review (D1-D18) before the first gate and record answers in
`course_photos/decisions.csv`.

## Cost discipline
Measure with tools, not eyes. Colour: `colour_match.py`. Green edges: the edge survey. Pins: the pin-area test. Read the
summary a tool writes; open a render only when a number says something is wrong.

## This course
Split out of the moorpark repo (branch `claude/project-thread-flaaah`, `griffith-park/wilson`). `README.md` has the full data history.
- Frame: the Griffith Park frame shared with Harding: 2000 m square centred on 34.1405, -118.28425 (EPSG:6340,
  SW 380594.21 E, 3777479.33 N), y = elevation - 120 m, Unity Terrain 2000 x 227 x 2000. Ground 121.0 to 345.8 m.
- `heightmap_2049.raw` is the shared heightmap levelled under Wilson's tee pads (`scripts/flatten_pads.py`, `tee_pads.csv`);
  `satellite.jpg` (NAIP 4096 px, 0.49 m/px) was already in the wilson folder, so nothing was copied from griffith-park/.
- Survey: USGS 3DEP `CA_LosAngeles_1_B23` (QL1, 2023-24), 23.9 pts/m2.
- `course.json` carries coursekit's keys beside the toolkit's (`gkd_settings` is coursekit's); keep both in step.
  `paths.gkd` is `GriffithWilson.GKD` at the repo root. `scripts/coursekit.py` is Wilson's copy of coursekit.
- `trees.csv` covers both courses (whole-park vegetation run); Harding in the middle is OB.
- Open questions: the long interior OB strip in the woods west of 17/18; White tees long of the card on 1, 2, 5; 12 greens over
  3% slope (steepest 17 at 4.8%), not smoothed.

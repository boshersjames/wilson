# First headless toolkit run (2026-11-03)

Run from the course folder, course-build at 02dcbcb Skills: additive Tools section in all 23 (exact toolkit commands, rule keys, and 'no tool yet' gaps); no existing text changed.

## doctor.py

```
ok   course.json                            /home/user/wilson/course.json
ok   paths.toolkit                          /home/user/course-build
ok   heightmap size                         8396802 bytes (= 2049^2 x 2)
ok   gkd parses                             Wilson - Griffith Park: 18 holes, 18 enabled
ok   svg greens match gkd                   20 outlines, 18 of 18 enabled holes matched
ok   paths.satellite                        /home/user/wilson/satellite.jpg
ok   paths.trees_csv                        /home/user/wilson/trees.csv
WARN paths.signs                            missing (/home/user/wilson/progress/hole_signs.json)
WARN paths.photos_root                      missing (/home/user/wilson/course_photos)
ok   python numpy                           
ok   python scipy                           
ok   python matplotlib                      
ok   python PIL                             
ok   python pyproj                          
ok   python laspy                           
ok   python pillow_heif                     
ok   tool git                               
ok   tool git-lfs                           
ok   tool ffmpeg                            
ok   tool yt-dlp                            
info unity_project                          C:/GSP/Wilson_Project not on this machine
info automation latest run                  none here

0 FAIL, 2 WARN
[exit 0]
```

## gkd_tools.py check

```
25 checks, 0 failing
[exit 0]
```

## green_report.py --smooth 0.6

```
# Green report (GriffithWilson, surface: course heightmap order 3, low-pass sigma 0.6 m)

Rules: pin area <= 1.7 deg over 17 points, pins >= 3 m from the edge, >= 4 valid areas >= 3 m apart; internal slope 1-3%.

| hole | area m2 | relief m | slope mean/p90 % | >3% | pins fail | pin angles | usable % | areas | flag | pass |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 467 | 1.39 | 5.5 / 7.9 | 97 | 4/4 | Thu:2.6 Fri:2.5 Sat:2.7 Sun:2.1 | 4 | 3 | steep >3% | FAIL |
| 2 | 627 | 1.21 | 4.7 / 7.0 | 92 | 4/4 | Thu:2.1 Fri:1.8 Sat:2.4 Sun:2.3 | 15 | 15 | steep >3% | FAIL |
| 3 | 478 | 0.97 | 4.3 / 6.0 | 93 | 4/4 | Thu:3.0 Fri:2.1 Sat:3.0 Sun:3.5 | 11 | 8 | steep >3% | FAIL |
| 4 | 545 | 1.08 | 3.3 / 4.6 | 59 | 4/4 | Thu:3.0 Fri:2.9 Sat:2.0 Sun:1.9 | 32 | 25 | steep >3% | FAIL |
| 5 | 497 | 1.33 | 5.0 / 6.8 | 95 | 4/4 | Thu:3.2 Fri:2.5 Sat:6.0 Sun:2.8 | 4 | 5 | steep >3% | FAIL |
| 6 | 314 | 0.61 | 3.5 / 5.6 | 58 | 4/4 | Thu:2.6 Fri:1.8 Sat:3.4 Sun:2.1 | 26 | 13 | steep >3% | FAIL |
| 7 | 420 | 0.70 | 2.9 / 4.8 | 42 | 3/4 | Thu:2.9 Fri:2.4 Sat:3.1 Sun:1.0 | 51 | 23 |  | FAIL |
| 8 | 490 | 0.83 | 3.8 / 6.5 | 61 | 4/4 | Thu:3.2 Fri:2.9 Sat:1.8 Sun:3.9 | 26 | 20 | steep >3% | FAIL |
| 9 | 428 | 1.01 | 3.9 / 5.6 | 75 | 4/4 | Thu:3.3 Fri:2.0 Sat:2.7 Sun:2.4 | 11 | 11 | steep >3% | FAIL |
| 10 | 424 | 1.01 | 4.5 / 7.6 | 69 | 3/4 | Thu:4.1 Fri:1.3 Sat:3.2 Sun:3.2 | 23 | 13 | steep >3% | FAIL |
| 11 | 333 | 0.76 | 3.8 / 6.8 | 60 | 2/4 | Thu:1.7 Fri:1.6 Sat:1.3 Sun:4.0 | 31 | 11 | steep >3% | FAIL |
| 12 | 622 | 0.72 | 3.0 / 5.1 | 42 | 1/4 | Thu:1.7 Fri:2.7 Sat:1.0 Sun:1.4 | 55 | 39 | steep >3% | FAIL |
| 13 | 475 | 1.28 | 5.1 / 8.0 | 89 | 3/4 | Thu:2.4 Fri:2.9 Sat:2.3 Sun:1.7 | 14 | 10 | steep >3% | FAIL |
| 14 | 439 | 0.80 | 3.1 / 5.2 | 46 | 1/4 | Thu:1.3 Fri:0.8 Sat:1.5 Sun:2.0 | 54 | 24 | steep >3% | FAIL |
| 15 | 384 | 0.87 | 3.8 / 5.6 | 72 | 3/4 | Thu:1.8 Fri:1.5 Sat:2.5 Sun:2.1 | 21 | 13 | steep >3% | FAIL |
| 16 | 272 | 0.78 | 3.9 / 5.4 | 84 | 3/4 | Thu:2.1 Fri:1.7 Sat:3.8 Sun:2.2 | 32 | 12 | steep >3% | FAIL |
| 17 | 349 | 1.08 | 5.4 / 8.5 | 97 | 4/4 | Thu:1.9 Fri:1.9 Sat:3.7 Sun:2.3 | 4 | 3 | steep >3% | FAIL |
| 18 | 339 | 0.79 | 4.2 / 6.0 | 78 | 4/4 | Thu:2.1 Fri:3.7 Sat:2.0 Sun:3.1 | 13 | 7 | steep >3% | FAIL |
wrote progress/green_report
[exit 0]
```

## flyover_gate.py --end-fit --no-plots

```
no signs file at /home/user/wilson/progress/hole_signs.json: provisional sign spots from the back tees
hole  1: 626 frames  25.0 s (x1.00) yaw/1s 1.92 pitch/1s 4.50 | end pitch -27.9 (pin -27.9) h 14.8 m, 24.5 m short | terrain 14.8 m crown 5.1 m (tree 2224, lift 0.0/0.0) | first: crown 7.4 sight 7.5 in-frame True | green 97% (cut off 0, pull-back 0.0) pin True sight 7.8 -> OK
hole  2: 510 frames  20.4 s (x1.00) yaw/1s 0.75 pitch/1s 4.35 | end pitch -27.6 (pin -27.6) h 16.2 m, 30.0 m short | terrain 16.2 m crown 5.6 m (tree 581, lift 0.0/0.0) | first: crown 11.3 sight 11.4 in-frame True | green 100% (cut off 0, pull-back 0.0) pin True sight 6.8 -> OK
hole  3: 317 frames  12.7 s (x1.00) yaw/1s 1.46 pitch/1s 3.82 | end pitch -24.9 (pin -24.9) h 16.6 m, 30.0 m short | terrain 16.5 m crown 6.0 m (tree 26, lift 0.0/10.0) | first: crown 10.0 sight 10.1 in-frame True | green 100% (cut off 0, pull-back 0.0) pin True sight 8.8 -> OK
hole  4: 458 frames  18.3 s (x1.00) yaw/1s 2.38 pitch/1s 4.50 | end pitch -29.0 (pin -29.0) h 15.0 m, 25.5 m short | terrain 14.9 m crown -0.8 m (tree 2058, lift 0.0/0.0) | first: crown 1.5 sight 1.4 in-frame True | green 96% (cut off 0, pull-back 0.0) pin True sight 15.6 -> FAIL  [opening NOT fixed within 6 m (crown 1.5 m, sign sightline 1.4 m, sign in frame True, rise -0.8 m from crown of tree 2058)]
hole  5: 434 frames  17.4 s (x1.00) yaw/1s 2.03 pitch/1s 4.50 | end pitch -27.6 (pin -27.6) h 16.6 m, 28.0 m short | terrain 16.6 m crown 3.1 m (tree 775, lift 0.0/1.3) | first: crown 5.9 sight 5.9 in-frame True | green 91% (cut off 0, pull-back 0.0) pin True sight 6.0 -> OK
hole  6: 496 frames  19.8 s (x1.00) yaw/1s 3.10 pitch/1s 4.50 | end pitch -29.3 (pin -29.3) h 11.9 m, 20.5 m short | terrain 11.9 m crown 4.3 m (tree 1179, lift 0.0/0.0) | first: crown 6.8 sight 5.5 in-frame True | green 100% (cut off 0, pull-back 0.0) pin True sight 4.9 -> OK
hole  7: 505 frames  20.2 s (x1.00) yaw/1s 1.27 pitch/1s 4.50 | end pitch -36.0 (pin -36.0) h 17.3 m, 23.0 m short | terrain 17.3 m crown -1.0 m (tree 128, lift 0.0/16.5) | first: crown 7.2 sight 7.3 in-frame True | green 100% (cut off 0, pull-back 0.0) pin True sight 13.5 -> FAIL  [opening NOT fixed within 6 m (crown 7.2 m, sign sightline 7.3 m, sign in frame True, rise -1.0 m from crown of tree 128)]
hole  8: 535 frames  21.4 s (x1.00) yaw/1s 0.25 pitch/1s 4.50 | end pitch -28.4 (pin -28.4) h 15.3 m, 26.0 m short | terrain 15.3 m crown 3.3 m (tree 1714, lift 0.0/0.0) | first: crown 4.8 sight 4.6 in-frame True | green 91% (cut off 0, pull-back 0.0) pin True sight 5.3 -> OK
hole  9: 665 frames  26.6 s (x1.00) yaw/1s 1.35 pitch/1s 4.50 | end pitch -29.6 (pin -29.6) h 14.7 m, 24.5 m short | terrain 14.4 m crown 7.5 m (tree 1129, lift 0.0/0.0) | first: crown 9.2 sight 8.7 in-frame True | green 95% (cut off 0, pull-back 0.0) pin True sight 11.6 -> OK
hole 10: 517 frames  20.7 s (x1.00) yaw/1s 1.35 pitch/1s 4.50 | end pitch -29.5 (pin -29.5) h 13.8 m, 23.5 m short | terrain 13.8 m crown 3.0 m (tree 1705, lift 0.0/0.0) | first: crown 3.8 sight 3.9 in-frame True | green 100% (cut off 0, pull-back 0.0) pin True sight 14.1 -> OK
hole 11: 317 frames  12.7 s (x1.00) yaw/1s 4.50 pitch/1s 3.57 | end pitch -19.3 (pin -19.3) h 23.9 m, 67.0 m short | terrain 23.9 m crown 4.7 m (tree 412, lift 0.0/7.9) | first: crown 8.3 sight 8.7 in-frame True | green 75% (cut off 14, pull-back 5.0) pin True sight 4.5 -> FAIL
hole 12: 480 frames  19.2 s (x1.00) yaw/1s 1.06 pitch/1s 4.50 | end pitch -30.2 (pin -30.2) h 16.1 m, 27.0 m short | terrain 15.9 m crown -1.3 m (tree 932, lift 0.0/0.0) | first: crown 5.3 sight 4.7 in-frame True | green 94% (cut off 0, pull-back 0.0) pin True sight 5.3 -> FAIL  [opening NOT fixed within 6 m (crown 5.3 m, sign sightline 4.7 m, sign in frame True, rise -1.3 m from crown of tree 932)]
hole 13: 496 frames  19.8 s (x1.00) yaw/1s 1.57 pitch/1s 4.50 | end pitch -28.6 (pin -28.6) h 15.7 m, 26.5 m short | terrain 15.6 m crown -1.3 m (tree 329, lift 0.0/0.0) | first: crown 2.8 sight 2.8 in-frame True | green 100% (cut off 0, pull-back 0.0) pin True sight 11.3 -> FAIL  [opening NOT fixed within 6 m (crown 2.8 m, sign sightline 2.8 m, sign in frame True, rise -1.3 m from crown of tree 329)]
hole 14: 662 frames  26.5 s (x1.00) yaw/1s 0.21 pitch/1s 4.50 | end pitch -29.0 (pin -29.0) h 14.5 m, 24.5 m short | terrain 14.4 m crown 5.9 m (tree 978, lift 0.0/0.0) | first: crown 12.7 sight 9.7 in-frame True | green 100% (cut off 0, pull-back 0.0) pin True sight 20.5 -> OK
hole 15: 317 frames  12.7 s (x1.00) yaw/1s 4.50 pitch/1s 3.43 | end pitch -13.5 (pin -13.5) h 16.2 m, 60.0 m short | terrain 16.2 m crown 9.7 m (tree 226, lift 0.0/0.0) | first: crown 16.3 sight 16.3 in-frame True | green 67% (cut off 18, pull-back 5.5) pin True sight 10.2 -> FAIL
hole 16: 546 frames  21.8 s (x1.00) yaw/1s 1.31 pitch/1s 4.50 | end pitch -29.4 (pin -29.4) h 12.3 m, 20.5 m short | terrain 12.3 m crown 7.4 m (tree 1814, lift 0.0/0.0) | first: crown 9.6 sight 10.0 in-frame True | green 100% (cut off 0, pull-back 0.0) pin True sight 7.3 -> OK
hole 17: 513 frames  20.5 s (x1.00) yaw/1s 0.54 pitch/1s 4.50 | end pitch -29.4 (pin -29.4) h 13.1 m, 22.0 m short | terrain 12.9 m crown 0.5 m (tree 1985, lift 0.0/0.0) | first: crown 3.3 sight 2.5 in-frame True | green 100% (cut off 0, pull-back 0.0) pin True sight 8.2 -> FAIL  [opening NOT fixed within 6 m (crown 3.3 m, sign sightline 2.5 m, sign in frame True, rise 0.5 m from crown of tree 1985)]
hole 18: 508 frames  20.3 s (x1.00) yaw/1s 0.15 pitch/1s 4.50 | end pitch -29.0 (pin -29.0) h 12.5 m, 21.0 m short | terrain 12.5 m crown 3.3 m (tree 705, lift 0.0/0.0) | first: crown 7.9 sight 7.0 in-frame True | green 100% (cut off 0, pull-back 0.0) pin True sight 5.7 -> OK
Failed holes: 4, 7, 11, 12, 13, 15, 17

Poster frames (first / rise / mid / approach / end) per hole are in flyover_gate.json; shots for the PC render in flyover_shots.json (8902 frames).
[exit 1]
```

## gate_report.py

```
# Gate report: GriffithWilson (18 holes)

Sources: flyover, lidar-proxy. Missing: Unity CourseGreenChecks (checks/greens_all18.csv): run Course Checks > Greens on the PC.

GKD checks: all pass

| hole | source | step cm | lip cm | col dy | tiers | crown m | pins fail | usable % | areas | fall dir | flyover | result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | lidar-proxy+flyover | - | - | - | - | - | 4 | 32 | 25 | - | FAIL | **FAIL** flyover warn: pins(lidar) |
| 7 | lidar-proxy+flyover | - | - | - | - | - | 3 | 51 | 23 | - | FAIL | **FAIL** flyover warn: pins(lidar) |
| 11 | lidar-proxy+flyover | - | - | - | - | - | 2 | 31 | 11 | - | FAIL | **FAIL** flyover warn: pins(lidar) |
| 12 | lidar-proxy+flyover | - | - | - | - | - | 1 | 55 | 39 | - | FAIL | **FAIL** flyover warn: pins(lidar) |
| 13 | lidar-proxy+flyover | - | - | - | - | - | 3 | 14 | 10 | - | FAIL | **FAIL** flyover warn: pins(lidar) |
| 15 | lidar-proxy+flyover | - | - | - | - | - | 3 | 21 | 13 | - | FAIL | **FAIL** flyover warn: pins(lidar) |
| 17 | lidar-proxy+flyover | - | - | - | - | - | 4 | 4 | 3 | - | FAIL | **FAIL** flyover warn: pins(lidar),areas(lidar) |
| 1 | lidar-proxy+flyover | - | - | - | - | - | 4 | 4 | 3 | - | PASS | PASS warn: pins(lidar),areas(lidar) |
| 2 | lidar-proxy+flyover | - | - | - | - | - | 4 | 15 | 15 | - | PASS | PASS warn: pins(lidar) |
| 3 | lidar-proxy+flyover | - | - | - | - | - | 4 | 11 | 8 | - | PASS | PASS warn: pins(lidar) |
| 5 | lidar-proxy+flyover | - | - | - | - | - | 4 | 4 | 5 | - | PASS | PASS warn: pins(lidar) |
| 6 | lidar-proxy+flyover | - | - | - | - | - | 4 | 26 | 13 | - | PASS | PASS warn: pins(lidar) |
| 8 | lidar-proxy+flyover | - | - | - | - | - | 4 | 26 | 20 | - | PASS | PASS warn: pins(lidar) |
| 9 | lidar-proxy+flyover | - | - | - | - | - | 4 | 11 | 11 | - | PASS | PASS warn: pins(lidar) |
| 10 | lidar-proxy+flyover | - | - | - | - | - | 3 | 23 | 13 | - | PASS | PASS warn: pins(lidar) |
| 14 | lidar-proxy+flyover | - | - | - | - | - | 1 | 54 | 24 | - | PASS | PASS warn: pins(lidar) |
| 16 | lidar-proxy+flyover | - | - | - | - | - | 3 | 32 | 12 | - | PASS | PASS warn: pins(lidar) |
| 18 | lidar-proxy+flyover | - | - | - | - | - | 4 | 13 | 7 | - | PASS | PASS warn: pins(lidar) |
wrote progress/gate_report
[exit 1]
```

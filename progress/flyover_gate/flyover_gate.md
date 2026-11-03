# Flyover gate (data pass)

Inputs: GKD `GriffithWilson.GKD`, signs `progress/hole_signs.json`, trees `trees.csv`, greens `course.svg`, heightmap `heightmap_2049.raw`, pin index 0.

Pass = yaw and pitch under 5 deg in every 1 s window, opening camera clear of crowns with the sign in frame and unhidden, terrain clearance 5 m+, crown clearance 1.5 m+ on the whole path, no part of the green cut off ahead or to the side in the end frame (the part under the camera is reported, not failed), pin in frame and not behind a crown.

| Hole | s | yaw/1s | pitch/1s | end pitch (target) | end h / short (used) | terrain min (after rise) | crown min (tree, frame), lift rise/flight | first: crown / sight / in frame | green: in / under cam / cut off (pull-back to fit) | pin | result | opening move |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 25.0 | 1.9 | 4.5 | -27.9 (-27.9) | 14.8 / 24.5 | 14.8 | 5.1 (2224, f448), 0.0 / 0.0 | 7.4 / 7.5 / yes | 97% / 2 / 0 (0 m) | in, sight 7.8 | **OK** |  |
| 2 | 20.4 | 0.8 | 4.3 | -27.6 (-27.6) | 16.2 / 30.0 | 16.2 | 5.6 (581, f352), 0.0 / 0.0 | 11.3 / 11.4 / yes | 100% / 0 / 0 (0 m) | in, sight 6.8 | **OK** |  |
| 3 | 12.7 | 1.5 | 3.8 | -24.9 (-24.9) | 16.6 / 30.0 | 16.5 | 6.0 (26, f188), 0.0 / 10.0 | 10.0 / 10.1 / yes | 100% / 0 / 0 (0 m) | in, sight 8.8 | **OK** |  |
| 4 | 18.3 | 2.4 | 4.5 | -29.0 (-29.0) | 15.0 / 25.5 | 14.9 | -0.8 (2058, f48), 0.0 / 0.0 | 1.5 / 1.4 / yes | 96% / 3 / 0 (0 m) | in, sight 15.6 | **FAIL** | opening NOT fixed within 6 m (crown 1.5 m, sign sightline 1.4 m, sign in frame True, rise -0.8 m from crown of tree 2058) |
| 5 | 17.4 | 2.0 | 4.5 | -27.6 (-27.6) | 16.6 / 28.0 | 16.6 | 3.1 (775, f322), 0.0 / 1.3 | 5.9 / 5.9 / yes | 91% / 6 / 0 (0 m) | in, sight 6.0 | **OK** |  |
| 6 | 19.8 | 3.1 | 4.5 | -29.3 (-29.3) | 11.9 / 20.5 | 11.9 | 4.3 (1179, f60), 0.0 / 0.0 | 6.8 / 5.5 / yes | 100% / 0 / 0 (0 m) | in, sight 4.9 | **OK** |  |
| 7 | 20.2 | 1.3 | 4.5 | -36.0 (-36.0) | 17.3 / 23.0 | 17.3 | -1.0 (128, f88), 0.0 / 16.5 | 7.2 / 7.3 / yes | 100% / 0 / 0 (0 m) | in, sight 13.5 | **FAIL** | opening NOT fixed within 6 m (crown 7.2 m, sign sightline 7.3 m, sign in frame True, rise -1.0 m from crown of tree 128) |
| 8 | 21.4 | 0.2 | 4.5 | -28.4 (-28.4) | 15.3 / 26.0 | 15.3 | 3.3 (1714, f56), 0.0 / 0.0 | 4.8 / 4.6 / yes | 91% / 5 / 0 (0 m) | in, sight 5.3 | **OK** |  |
| 9 | 26.6 | 1.4 | 4.5 | -29.6 (-29.6) | 14.7 / 24.5 | 14.4 | 7.5 (1129, f564), 0.0 / 0.0 | 9.2 / 8.7 / yes | 95% / 4 / 0 (0 m) | in, sight 11.6 | **OK** |  |
| 10 | 20.7 | 1.4 | 4.5 | -29.5 (-29.5) | 13.8 / 23.5 | 13.8 | 3.0 (1705, f50), 0.0 / 0.0 | 3.8 / 3.9 / yes | 100% / 0 / 0 (0 m) | in, sight 14.1 | **OK** |  |
| 11 | 12.7 | 4.5 | 3.6 | -19.3 (-19.3) | 23.9 / 67.0 | 23.9 | 4.7 (412, f236), 0.0 / 7.9 | 8.3 / 8.7 / yes | 75% / 0 / 14 (5 m) | in, sight 4.5 | **FAIL** |  |
| 12 | 19.2 | 1.1 | 4.5 | -30.2 (-30.2) | 16.1 / 27.0 | 15.9 | -1.3 (932, f68), 0.0 / 0.0 | 5.3 / 4.7 / yes | 94% / 5 / 0 (0 m) | in, sight 5.3 | **FAIL** | opening NOT fixed within 6 m (crown 5.3 m, sign sightline 4.7 m, sign in frame True, rise -1.3 m from crown of tree 932) |
| 13 | 19.8 | 1.6 | 4.5 | -28.6 (-28.6) | 15.7 / 26.5 | 15.6 | -1.3 (329, f82), 0.0 / 0.0 | 2.8 / 2.8 / yes | 100% / 0 / 0 (0 m) | in, sight 11.3 | **FAIL** | opening NOT fixed within 6 m (crown 2.8 m, sign sightline 2.8 m, sign in frame True, rise -1.3 m from crown of tree 329) |
| 14 | 26.5 | 0.2 | 4.5 | -29.0 (-29.0) | 14.5 / 24.5 | 14.4 | 5.9 (978, f498), 0.0 / 0.0 | 12.7 / 9.7 / yes | 100% / 0 / 0 (0 m) | in, sight 20.5 | **OK** |  |
| 15 | 12.7 | 4.5 | 3.4 | -13.5 (-13.5) | 16.2 / 60.0 | 16.2 | 9.7 (226, f160), 0.0 / 0.0 | 16.3 / 16.3 / yes | 67% / 0 / 18 (6 m) | in, sight 10.2 | **FAIL** |  |
| 16 | 21.8 | 1.3 | 4.5 | -29.4 (-29.4) | 12.3 / 20.5 | 12.3 | 7.4 (1814, f484), 0.0 / 0.0 | 9.6 / 10.0 / yes | 100% / 0 / 0 (0 m) | in, sight 7.3 | **OK** |  |
| 17 | 20.5 | 0.5 | 4.5 | -29.4 (-29.4) | 13.1 / 22.0 | 12.9 | 0.5 (1985, f58), 0.0 / 0.0 | 3.3 / 2.5 / yes | 100% / 0 / 0 (0 m) | in, sight 8.2 | **FAIL** | opening NOT fixed within 6 m (crown 3.3 m, sign sightline 2.5 m, sign in frame True, rise 0.5 m from crown of tree 1985) |
| 18 | 20.3 | 0.1 | 4.5 | -29.0 (-29.0) | 12.5 / 21.0 | 12.5 | 3.3 (705, f430), 0.0 / 0.0 | 7.9 / 7.0 / yes | 100% / 0 / 0 (0 m) | in, sight 5.7 | **OK** |  |

End spot: 12 m short of the pin, 8 m over the ground (v4 default 12 / 8), pulled back per hole until the green fits (--end-fit).

Failed holes: 4, 7, 11, 12, 13, 15, 17

Poster frames (first / rise / mid / approach / end) per hole are in flyover_gate.json; shots for the PC render in flyover_shots.json (8902 frames).

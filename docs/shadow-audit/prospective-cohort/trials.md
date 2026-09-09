| trial | agent execution s | how the agent stopped | agent steps | snapshots | v0 present | log present | main equals v0 | sealed reward (incidental) |
|---|---|---|---|---|---|---|---|---|
| opus-overlay-01 | 1298 | harness timeout | 19 | 1 | True | True | True | 0.0 |
| opus-overlay-02 | 1298 | harness timeout | 25 | 1 | True | True | True | 0.0 |
| opus-overlay-03 | 1298 | harness timeout | 26 | 1 | True | True | True | 0.0 |
| opus-overlay-04 | 1298 | harness timeout | 23 | 1 | True | True | True | 0.0 |

What each trial left under `methods/` beside `main/`, `versions/` and the log, read from the job directory (regular files, bytecode caches excluded):

| trial | other entries under methods/ | files | bytes |
|---|---|---|---|
| opus-overlay-01 | `tools` | 10 | 1208134209 |
| opus-overlay-02 | none | 0 | 0 |
| opus-overlay-03 | none | 0 | 0 |
| opus-overlay-04 | none | 0 | 0 |

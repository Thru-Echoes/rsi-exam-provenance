| trial | agent execution s | how the agent stopped | agent steps | snapshots | v0 present | log present | main equals v0 | sealed reward (incidental) |
|---|---|---|---|---|---|---|---|---|
| campaign-H1 | 265 | agent finished | 49 | 10 | True | True | False | 0.19354212 |
| campaign-H2 | 274 | agent finished | 55 | 10 | True | True | False | 0.2043194 |
| campaign-H3 | 281 | agent finished | 50 | 9 | True | True | False | 0.14868332 |
| campaign-H4 | 257 | agent finished | 40 | 7 | True | True | False | 0.09384983 |
| campaign-H5 | 267 | agent finished | 71 | 5 | True | True | False | 0.14273383 |
| campaign-H6 | 339 | agent finished | 63 | 13 | True | True | False | 0.21062443 |
| campaign-O1 | 862 | agent finished | 23 | 2 | True | True | False | 0.58542111 |
| campaign-O2 | 956 | agent finished | 24 | 3 | True | True | False | 0.52101864 |
| campaign-S1 | 348 | harness timeout | 10 | 2 | True | True | False | 0.17856798 |
| campaign-S2 | 289 | agent finished | 14 | 2 | True | True | False | 0.29844793 |
| campaign-S3 | 348 | harness timeout | 17 | 3 | True | True | False | 0.44393779 |

What each trial left under `methods/` beside `main/`, `versions/` and the log, read from the job directory (regular files, bytecode caches excluded):

| trial | other entries under methods/ | files | bytes |
|---|---|---|---|
| campaign-H1 | `.provenance`, `notes.md`, `results` | 13 | 18031 |
| campaign-H2 | `.provenance`, `notes.md`, `results` | 13 | 17652 |
| campaign-H3 | `.provenance`, `notes.md`, `results` | 13 | 17764 |
| campaign-H4 | `.provenance`, `notes.md`, `results` | 11 | 17882 |
| campaign-H5 | `.provenance`, `notes.md`, `results` | 9 | 12116 |
| campaign-H6 | `.provenance`, `notes.md`, `results` | 16 | 22812 |
| campaign-O1 | `.provenance`, `notes.md`, `results` | 6 | 12648 |
| campaign-O2 | `.provenance`, `notes.md`, `results` | 6 | 7659 |
| campaign-S1 | `.provenance`, `results` | 3 | 1714 |
| campaign-S2 | `.provenance`, `notes.md`, `results` | 5 | 3880 |
| campaign-S3 | `.provenance`, `results` | 6 | 8555 |

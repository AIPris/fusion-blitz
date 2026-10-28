# Benchmarks: Fusion 360 modelling with and without the skill

The same three modelling tasks were given to a fresh Claude agent in three setups: no skill, skill v1 and skill v2
(the version in this repository). Every build ran through the Fusion MCP on a real Fusion 360 desktop session and was
graded afterwards by script, not by the agent's own report.

![Bar chart of the time to build each part: no skill, skill v1 and skill v2](time-per-task.svg)

## Results

Mean over the three tasks:

| Setup | Mean time | vs no skill | Mean tokens | Fusion script calls, 3 tasks (failed) | Checks passed, 3 tasks |
|---|---:|---:|---:|---:|---:|
| No skill | 474 s | – | 126,836 | 24 (5) | 36/39 |
| Skill v1 | 282 s | 1.7× faster | 104,409 | 7 (1) | 39/39 |
| Skill v2 | 124 s | 3.8× faster | 89,394 | 7 (1) | 39/39 |

Per task (wall-clock time of the agent run, number of `fusion_mcp_execute` script calls):

| Task | No skill | Skill v1 | Skill v2 |
|---|---:|---:|---:|
| Cable comb | 298 s, 5 calls (0 failed) | 208 s, 3 calls (1 failed) | 164 s, 4 calls (1 failed) |
| Wall hook | 410 s, 7 calls (1 failed) | 342 s, 2 calls (0 failed) | 87 s, 1 call (0 failed) |
| Project box | 713 s, 12 calls (4 failed) | 296 s, 2 calls (0 failed) | 122 s, 2 calls (0 failed) |

Speed-up over no skill: v1 1.4× / 1.2× / 2.4× and v2 1.8× / 4.7× / 5.8× on comb / hook / box. Every task was faster with
the skill in both versions. Raw numbers per run are in [`runs/`](runs), aggregated in [`results.json`](results.json).

## What was tested

Three parts, each described in plain language with exact dimensions. The prompts are in
[`harness/driver.py`](harness/driver.py); the task text is repeated here.

<details>
<summary><b>Cable comb</b>: slots, through holes, rounded corners</summary>

Model a desk cable comb: a bar 90 mm long (x), 28 mm deep (y) and 12 mm tall (z) with one corner at the origin. Cut
five slots from the top, each 7 mm wide (x), running through the full depth (y) and 8 mm deep (z), pitch 16 mm, the set
of slots centred along the length. Two 4.5 mm mounting holes straight down through the whole bar at x = 4.75 mm and
x = 85.25 mm, y = 14 mm. Round the four vertical corner edges of the bar with R3.
</details>

<details>
<summary><b>Wall hook</b>: plate, holes, an arm on the front face, fillets on convex and concave edges</summary>

Model a wall hook: a mounting plate 50 mm wide (x), 70 mm tall (z) and 5 mm thick (y), with its back face on y = 0,
its bottom edge on z = 0 and x running from 0 to 50. Two 5 mm holes through the plate along y, at x = 25, z = 12 and at
x = 25, z = 58. A round hook arm, 12 mm diameter and 35 mm long, sticking out of the front face (y = 5, toward +y),
centred at x = 25, z = 35. Round the four plate corners (the edges parallel to y) with R4, the free end of the arm with
R2, and the joint between arm and plate with R2.
</details>

<details>
<summary><b>Project box</b>: shell by cut, posts, blind pilot holes, a slot pattern in one wall, rounded corners</summary>

Model a small project box with an open top. Outside size 70 mm (x) by 50 mm (y) by 30 mm (z), one corner at the origin,
2.5 mm walls and a 2.5 mm floor. Four round screw posts, 8 mm diameter, rising from the floor to z = 28 mm, centred
7.5 mm in from the outside faces in both x and y at each corner, i.e. at (7.5, 7.5), (62.5, 7.5), (7.5, 42.5) and
(62.5, 42.5); each post has a 2.8 mm pilot hole, 12 mm deep from the post top. Six ventilation slots, 2 mm wide (x) and
14 mm tall (z), cut through the front wall only (the wall at y = 0), the bottom of the slots at z = 8 mm, pitch 6 mm,
the set centred along x. Round the four vertical outside corner edges of the box with R5.
</details>

## How the runs were made

- **Agent:** Claude Sonnet 5.5 (`claude-sonnet-5-5`) at `xhigh` effort, started as a fresh Claude Code subagent per
  run. Both setups had the same tools (the Fusion MCP, file access and an optional advisor tool). The skill setups were
  told to read `SKILL.md` first; the no-skill setup was not.
- **Same instructions:** the prompt asks for millimetres, Z up, every key dimension a named user parameter, fully
  constrained sketches, healthy features, one solid body, and STEP, STL, F3D and a preview PNG. The agent cannot ask
  questions and has to leave one new document open and unsaved.
- **One run per task and setup, one after another.** Fusion has a single active document, so runs cannot overlap.
- **Environment:** Windows 11, Fusion 2705.1.25 with its built-in MCP server, other (unsaved) documents open in the
  same Fusion session.
- **Time and tokens** are what Claude Code reported for the agent run (`timing.json`): total wall-clock seconds
  including reading the skill, and total tokens. **Fusion calls** are counted from the agent's transcript with
  [`harness/transcript_stats.py`](harness/transcript_stats.py); a call counts as failed when the tool result is
  flagged as an error or the MCP result says `"success": false`.

## How the runs were graded

[`harness/grade.py`](harness/grade.py) runs inside Fusion, read-only, against the finished document, and
[`harness/step_check.py`](harness/step_check.py) re-imports the delivered STEP file with build123d. Thirteen checks per run:

1. the document exists and was left open
2. exactly one solid body
3. bounding-box size matches the request (±0.05 mm)
4. the part sits where requested (bounding-box minimum corner, ±0.05 mm)
5. volume within 0.2 % of the reference model
6. cylindrical faces (holes, posts, fillets) match the reference by radius
7. every timeline feature is healthy
8. every sketch is fully constrained
9. at least N named user parameters
10. at least half of the sketch dimensions are driven by named parameters
11. STEP, STL, F3D and the preview PNG were delivered and are not empty
12. the other documents open in Fusion are unchanged
13. the delivered STEP re-imports as one valid solid with the reference size, position and volume

The reference volumes and radii come from [`harness/golden.py`](harness/golden.py), which builds each part once with the
helper. The per-run results, including the evidence string for every check, are in `runs/<task>/<setup>/grading.json`.

## Caveats

Please read these before you quote the numbers.

- **Small sample.** Three tasks, one run per task and setup, no repeats. There is no variance between repeated runs
  here; the spread you can see is between tasks (the speed-up ranges from 1.2× to 5.8×). The mean of three tasks is not
  a confidence interval.
- **v2 is tuned on these tasks.** After v1 was measured, the skill was rewritten using what those runs showed (right-sized
  checks, `probe`, `what_if`, better views, and so on) and measured on the same three tasks. v2's numbers are therefore
  in-sample. **v1 against no skill (1.7×) is the cleaner comparison.** Expect less than 3.8× on tasks the skill was not
  tuned on.
- **The tasks sit inside what the helper wraps:** extrude, cut, holes, patterns, fillets. Revolve, shell, loft, sweep and
  threads are not wrapped and were not tested.
- **The 92 % pass rate of the no-skill setup is one run.** In the project box, the no-skill agent added R2.5 fillets on
  the inside corners that the request did not ask for. The geometry is valid, but it fails three checks (volume,
  cylinder radii, STEP volume), so 36 of 39 checks passed. On the other two parts the no-skill agent matched the
  reference volumes exactly.
- **The grading references were built with the helper.** They are plain geometry (volume, bounding box, radii), and the
  no-skill agents matched them exactly on the comb and the hook, which argues against a bias toward the skill. It is
  still a point to keep in mind.
- **One failed call in v2 is a helper bug that has since been fixed.** The v2 comb run crashed on `ff.new(replace=True)`
  because of a stale registry entry for a document that had been closed outside the helper. The fix landed before the
  hook and box runs and is part of the published v2; the comb build script still contains its workaround. The one
  failed v1 call (also comb) has a different cause: a Fusion API `RuntimeError` ("Didn't roll editing feature back")
  while the agent inspected a fillet.
- **The original runs also allowed reading a local folder of example Fusion scripts**, identical for both setups. The
  published driver leaves that sentence out, so a re-run starts from a slightly less helpful baseline.
- **Time is wall-clock time.** It includes model latency and Fusion's own time, and it moves with load on the machine.

## Reproduce it

You need Fusion running with its MCP server enabled, Claude Code with the `fusion-local` server registered, and `uv`
(for the STEP re-import). The harness is plain Python.

1. Inside Fusion (for example through `fusion_mcp_execute`, with `benchmarks/harness` on `sys.path`) call
   `grade.snapshot(r"<dir>/docs_before.json")` to record the documents that are open now.
2. `python benchmarks/harness/driver.py 1 <bench_dir> <dir>/docs_before.json` writes a prompt and a grading spec for
   every task and setup into `<bench_dir>/iteration-1/`.
3. Run each `prompt.txt` in a fresh Claude Code subagent, one at a time.
4. After each run, grade the document inside Fusion with `grade.grade(r"<run_dir>/spec.json")`, then
   `uv run --python 3.12 --with build123d-mcp==0.3.91 python benchmarks/harness/step_check.py <run_dir>`, then
   `python benchmarks/harness/transcript_stats.py <agent_transcript.jsonl> <run_dir>/metrics.json`. Close the benchmark
   document with `grade.close_named("ZZ_bench_...")`; never use the MCP document-close action.
5. Copy `timing.json`, `metrics.json` and `grading.json` of each run into `benchmarks/runs/<task>/<setup>/` and run
   `python benchmarks/report.py` to rebuild `results.json`, the chart and the tables.

## What is in this folder

| Path | Content |
|---|---|
| `runs/<task>/<setup>/` | `timing.json`, `metrics.json` and `grading.json` of every run, copied unchanged from the benchmark workspace |
| `results.json`, `time-per-task.svg` | aggregated results and the chart, both generated by `report.py` |
| `report.py` | aggregation, chart and the tables above; standard library only |
| `harness/` | `driver.py` (tasks, prompts, grading specs), `grade.py` and `golden.py` (run inside Fusion), `step_check.py`, `transcript_stats.py` |

The generated CAD files, the raw agent prompts and the transcripts are not included. They embed local file paths and
the names of unrelated open documents. The three preview images in [`../examples/`](../examples) come from the v2 runs.

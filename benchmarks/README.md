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

The reference volumes and radii of tasks 1 to 3 come from [`harness/golden.py`](harness/golden.py), which builds each part
once with the helper; task 4 has an independent reference, see below. The per-run results, including the evidence string
for every check, are in `runs/<task>/<setup>/grading.json`.

## Task 4: flanged eccentric elbow spool (defined and verified, not yet run)

The first three tasks stay inside what the helper wraps. This one does not. It is a 90 degree piping spool with an inlet
and an outlet flange, an eccentric reducer, a sensor boss at 45 degrees on the bend, four gusset ribs and two lifting
lugs. The Fusion build has 27 features on 25 sketches (17 extrudes, 3 lofts, 2 revolves, 3 chamfers, one fillet loop and
one circular pattern), plus 26 construction planes, 3 construction axes and 45 named user parameters.

Revolve, loft, construction axes, an angled work plane and the circular pattern were not wrapped by `fusion_fast` v2, so
this was the task that exercised the skill's fallback to the raw API (`m.root`, `m.design`); v2.1 wraps all of them
except the angled plane. One trap on the way: in a
parametric design Fusion refuses a work plane made with `setByPlane` (direct modelling only), so the tilted plane for
the boss has to be built from two offset planes, an axis and an angle.

![The spool as built in Fusion](spool-reference.png)

<details>
<summary>The task text, 734 words (exactly what the agent is given)</summary>

Model a flanged eccentric reducing elbow (a piping spool) as one solid body. Millimetres, Z up. The centreline lies in the XZ plane (y = 0) except for the offset of the outlet. The inlet face is the plane x = 0 and the centreline starts at the origin.

Pipe: the main pipe is 88.9 mm outside diameter with a 78.9 mm bore (5 mm wall); the reduced pipe is 60.3 mm outside diameter with a 50.3 mm bore. The bore runs clear from the inlet face to the outlet face and nothing (boss, ribs, lugs) intrudes into it.

Centreline, in order: (1) straight along +X from x = 0 to x = 160; (2) a 90 degree bend of radius 150 turning towards +Z, arc centre (160, 0, 150), from (160, 0, 0) to (310, 0, 150); (3) straight along +Z at x = 310 from z = 150 to z = 250; (4) an eccentric reducer from z = 250 to z = 330: a straight-sided (ruled, no guide rails) transition from the 88.9 mm circle centred on x = 310, y = 0 to the 60.3 mm circle centred on x = 310, y = 14.3, so the outer surfaces line up along the +Y side; the bore makes the same transition from 78.9 mm to 50.3 mm with the same two circle centres; (5) straight along +Z at x = 310, y = 14.3 from z = 330 to z = 398, which is the outlet face.

Inlet flange (axis along X): a disc of 200 mm diameter, 20 mm thick (x = 0 to 20), with 8 holes of 18 mm diameter on a 160 mm bolt circle at 22.5 + k * 45 degrees measured from +Z in the YZ plane; an annular groove in the x = 0 face, 104 mm inner and 114 mm outer diameter, 3 mm deep; a conical weld-neck hub from 116 mm diameter at x = 20 to the 88.9 mm pipe diameter at x = 60; 1.5 mm x 45 degree chamfers on both outer edges of the disc.

Outlet flange (axis along Z through x = 310, y = 14.3): a disc of 165 mm diameter, 18 mm thick (z = 380 to 398), with 4 holes of 18 mm diameter on a 125 mm bolt circle at 45 + k * 90 degrees measured from +X in the XY plane; an annular groove in the z = 398 face, 66 mm inner and 78 mm outer diameter, 2.5 mm deep; 1.5 mm x 45 degree chamfers on both outer edges of the disc. Four gusset ribs under the disc, each an 8 mm thick right triangle lying in a plane that contains the outlet axis, at 0, 90, 180 and 270 degrees (parallel to the XZ and YZ planes): the right angle is 28 mm from the outlet axis (inside the pipe wall, so the rib fuses with it) on the underside of the disc (z = 380), one leg runs 32 mm outwards along the underside (to 60 mm from the axis), the other runs 40 mm down along the pipe (to z = 340).

Sensor boss: a 30 mm diameter cylinder whose axis passes through the centreline point of the bend at 45 degrees, (266.066, 0, 43.934), and points radially away from the bend centre, direction (0.7071, 0, -0.7071). It runs from that centreline point out to 70 mm along its axis, with a 1.5 mm x 45 degree chamfer on the edge of its free end. A 12 mm diameter hole along the axis from the free end down to 30 mm from the centreline point opens into the bore.

Lifting lugs: two 10 mm thick plates (y = -5 to +5) on the vertical run, in the XZ plane, z = 175 to 225, from x = 240 to x = 380 (they pass through the pipe axis), each end finished with a semicircle of radius 25 centred at (380, 200) and (240, 200), so the plates reach x = 215 and x = 405. A 25 mm diameter hole through each plate at those centres. Where the plates meet the outside of the pipe they are blended with 4 mm fillets along the whole junction (both flat faces and the top and bottom faces).

Add nothing else: no other fillets, chamfers, threads or welds.
</details>

**The expected values come from two independent routes.** [`reference_spool.py`](harness/reference_spool.py) builds the
part with build123d (OpenCascade); no Fusion and no skill helper are involved. [`golden_spool.py`](harness/golden_spool.py)
builds it in Fusion with the helper plus raw API calls. They agree:

| | build123d reference | Fusion golden build |
|---|---:|---:|
| Volume | 1,719,679.341 mm³ | 1,719,673.142 mm³ (3.6 ppm lower) |
| Surface area | 446,803.17 mm² | 446,800.40 mm² |
| Centre of mass | (179.489, 3.562, 129.911) | (179.488, 3.562, 129.911) |
| Bounding box | 405 × 200 × 498 from (0, -100, -100) | the same |
| Faces | 77 | 77 |
| Cylinder radii | 16 distinct values | the same 16 |

**How task 4 is graded.** The same 13 checks as the other tasks, with four additions. All new keys are optional, so
tasks 1 to 3 are graded as before, apart from the volume accuracy noted below.

- Volume is checked at two levels: within 0.1 % (the part is roughly right) and within 0.005 % (every feature is there;
  the 1.5 mm chamfer on the boss alone is 0.006 %).
- The set of cylindrical-face radii replaces the face counts, because a kernel may split one cylinder into one or two
  faces.
- The centre of mass must be within 0.1 mm of the reference.
- 142 probe points (65 that must be solid, 77 that must be empty) sit either side of
  every hole, groove, wall, rib, lug and chamfer edge ([`spool_probes.py`](harness/spool_probes.py)). A feature in the wrong
  place or of the wrong size fails here even when volume and centre of mass cannot tell. The reference and the Fusion
  build classify every probe the same way, and none lies within 0.2 mm of a surface.

That makes 15 checks inside Fusion plus the STEP re-import, 16 in total. To see whether the grader discriminates, the
golden build was broken in seven ways, one parameter each, and graded again:

| Change to the golden model | Checks passed | Failing checks |
|---|---:|---|
| none | 15/15 | – |
| reducer offset flipped to the -Y side | 13/15 | centre of mass, probes |
| all chamfers 1.0 instead of 1.5 mm | 14/15 | strict volume (0.086 % off) |
| inlet bolt circle 150 instead of 160 mm | 14/15 | probes |
| lug holes 22 instead of 25 mm diameter | 10/15 | both volume checks, radius set, centre of mass, probes |
| ribs 6 instead of 8 mm thick | 11/15 | both volume checks, centre of mass, probes |
| outlet groove 3 instead of 2.5 mm deep | 12/15 | strict volume, centre of mass, probes |
| boss hole stops short of the bore | 13/15 | strict volume, probes |

(Before the probes sat at the hole edges, the bolt-circle change passed all checks: volume and centre of mass do not
change when a symmetric hole circle is resized. Probes at the hole centres alone did not catch it either.)

Design notes for anyone extending this:

- **Fusion's `body.volume` is 0.086 % low on this part** (1,718,202.84 mm³ against 1,719,673.14 mm³ from
  `getPhysicalProperties` at very high accuracy), which would fail a perfect model against the strict tolerance.
  `grade.py` and `golden.py` now read the very-high-accuracy volume. The first three tasks were graded with `body.volume`
  before this change; rebuilding their golden models shows the two accuracies agree to better than 0.01 ppm on those
  simple parts (and match the stored references within 0.02 ppm), so their grading is unchanged. The helper's own
  `report` read `body.volume` in v2, where its default 0.2 % tolerance absorbed the difference; v2.1 reads the
  very-high-accuracy volume too.
- **The STEP re-import is 0.06 % larger than Fusion's own volume** for this part, so `step_check.py` keeps its 0.2 %
  tolerance and the strict comparisons stay inside Fusion.
- **A boolean comparison of two STEP solids was tried and dropped.** OpenCascade returns garbled pieces (even negative
  volumes) when two nearly identical solids share almost all their faces.
- **The OpenCascade reference needed two workarounds.** The bore tools abut each other and must be fused into one tool
  (cutting them separately in one boolean loses about 100 mm³), and the finished solid is flagged invalid at the hole and
  bore intersection until `fix()` has run; the volume is identical before and after.

Not run with agents yet. What to look for: whether the skill's lead survives when the helper covers only part of the
work, how many Fusion calls the unwrapped features cost with and without it, and whether the tilted work plane trips both
setups. Those are questions, not results.

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
   every task (now four, including the spool) and setup into `<bench_dir>/iteration-1/`.
3. Run each `prompt.txt` in a fresh Claude Code subagent, one at a time.
4. After each run, grade the document inside Fusion with `grade.grade(r"<run_dir>/spec.json")`, then
   `uv run --python 3.12 --with build123d-mcp==0.3.91 python benchmarks/harness/step_check.py <run_dir>`, then
   `python benchmarks/harness/transcript_stats.py <agent_transcript.jsonl> <run_dir>/metrics.json`. Close the benchmark
   document with `grade.close_named("ZZ_bench_...")`; never use the MCP document-close action.
5. Copy `timing.json`, `metrics.json` and `grading.json` of each run into `benchmarks/runs/<task>/<setup>/` and run
   `python benchmarks/report.py` to rebuild `results.json`, the chart and the tables. `report.py` aggregates the tasks
   listed in its `TASKS`; add `spool` there once it has runs.

To regenerate the task 4 reference and re-check its probe points:
`uv run --python 3.12 --with build123d-mcp==0.3.91 python benchmarks/harness/reference_spool.py --probes`.

To rebuild the task 4 golden model in Fusion, run this through `fusion_mcp_execute`. It builds the part in a scratch
document called `ZZ_golden_spool`, runs the checkpoints and exports STEP, STL, F3D and preview images:

```python
import sys
for p in (r"<repo>/skills/fusion-fast-modeling/scripts", r"<repo>/benchmarks/harness"):
    if p not in sys.path:
        sys.path.insert(0, p)
import golden_spool

def run(_context: str):
    golden_spool.build(r"<out_dir>")
```

## What is in this folder

| Path | Content |
|---|---|
| `runs/<task>/<setup>/` | `timing.json`, `metrics.json` and `grading.json` of every run, copied unchanged from the benchmark workspace |
| `results.json`, `time-per-task.svg` | aggregated results and the chart, both generated by `report.py` |
| `report.py` | aggregation, chart and the tables above; standard library only |
| `harness/` | `driver.py` (tasks, prompts, grading specs), `grade.py` and `golden.py` (run inside Fusion), `step_check.py`, `transcript_stats.py` |
| `harness/reference_spool.py`, `golden_spool.py`, `spool_probes.py` | task 4: the build123d reference, the Fusion golden build, and the grader's probe points |
| `spool-reference.png` | the task 4 part as built in Fusion |

The generated CAD files, the raw agent prompts and the transcripts are not included. They embed local file paths and
the names of unrelated open documents. The three preview images in [`../examples/`](../examples) come from the v2 runs.

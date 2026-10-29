# Fusion Blitz: a Claude Code skill for faster Fusion 360 modelling

![License: MIT](https://img.shields.io/badge/license-MIT-blue)
![Claude Code skill](https://img.shields.io/badge/Claude%20Code-skill-d97757)
![Autodesk Fusion 360](https://img.shields.io/badge/Autodesk-Fusion%20360-orange)
![MCP](https://img.shields.io/badge/MCP-fusion--local-lightgrey)

**Fusion Blitz** is an [Agent Skill](https://code.claude.com/docs/en/skills) for Claude Code (the skill itself is
called `fusion-fast-modeling`) that builds, edits and exports parametric models in **Autodesk Fusion 360** through
Fusion's built-in **MCP server**, the Model Context Protocol endpoint of the desktop app. It gives Claude a tested
Python helper for the Fusion API, a one-file build loop and numeric checkpoints, so an AI-assisted CAD session lands on
a correct, fully parametric part in one or two script calls instead of a trial-and-error loop.

In the current benchmark (skill v2.3, no advisor tool), agents with the skill built three small parts in **73 s instead
of 398 s (5.4× faster)**, used **35 % fewer tokens** and needed **5 Fusion script calls instead of 30**. On a much harder
part, a flanged piping spool with 27 Fusion features, the skill took **482 s instead of 1,123 s (2.3× faster)**.

![Bar chart of the time to build four Fusion 360 parts, with and without the skill: comb 362 s against 59 s, hook 400 s against 82 s, box 432 s against 78 s, spool 1,123 s against 482 s](benchmarks/time-per-task.svg)

| Setup | Mean time, 3 small parts | vs no skill | Mean tokens | Fusion script calls, 3 parts (failed) | Checks passed, 3 parts |
|---|---:|---:|---:|---:|---:|
| No skill | 398 s | – | 120,384 | 30 (13) | 36/39 |
| **Skill v2.3 (this repo)** | **73 s** | **5.4× faster** | **78,023** | **5 (1)** | **39/39** |

| Task | No skill | Skill v2.3 |
|---|---:|---:|
| Cable comb | 362 s, 7 calls (3 failed) | 59 s, 2 calls (1 failed) |
| Wall hook | 400 s, 12 calls (4 failed) | 82 s, 2 calls (0 failed) |
| Project box | 432 s, 11 calls (6 failed) | 78 s, 1 call (0 failed) |
| Piping spool, 2 runs each | 1,123 s (887–1,359), 29 calls (5 failed) | 482 s (448–516), 6 calls (1 failed) |

Same prompts, same model (Claude Sonnet 5.5), graded by script, and every agent was told not to use the advisor tool.
**Read the caveats before you quote these numbers:**

- **Small samples.** One run per part and setup, two for the spool. The no-skill spool runs alone differ by 470 s
  (887 s and 1,359 s), so the direction is clear but the size of the gap is not.
- **The skill was developed against these tasks.** v2 was tuned on the three small parts and v2.1 to v2.3 on the
  spool, so the numbers are in-sample. Expect less on a part the skill has never seen.
- **Quality is not the difference.** Every skill run passed all checks. The no-skill project box scored 10 of 13 only
  because the agent added inside fillets the request did not ask for (valid geometry, but off specification).
- **The first benchmark allowed the advisor tool** and measured an older version (v2: 3.8× faster, in-sample). Those
  numbers are kept, with the reasons they are not comparable, in [benchmarks/README.md](benchmarks/README.md), which also
  has the method, every run and every limitation.

## What you get

- **One build file, rebuilt from scratch.** The whole model is a `build()` in a `.py` file. When something fails you
  fix it with a small edit and run it again; nothing is re-sent in full and the file is the reproducible source of
  the model.
- **`fusion_fast`, a tested helper for the Fusion Python API** (`adsk.core` / `adsk.fusion`). It works in millimetres,
  in world coordinates and picks geometry by position, so Claude never has to think about centimetres, sketch axes or
  edge indexes.
- **Numeric checkpoints instead of screenshots.** After each stage `m.report(...)` checks bounding box, volume,
  body count, cylinder radii, feature health and sketch constraints, and fails in the same call, naming the stage. For
  every cut it also prints how much of the cut tool sat in material, so a misplaced hole shows up without hand-computed
  coordinates.
- **Seams found, not calculated.** `m.edges_between(a, b)` returns the edges where two joined features meet, ready for
  a fillet.
- **Parametric by default.** The request becomes named user parameters and expressions, so the model stays editable in
  Fusion; `m.what_if(...)` proves the geometry follows them.
- **Safe next to your real work.** It only touches documents it created itself, never saves or closes yours, and warns
  if one of your documents changed while it ran.
- **Exports that are verified:** STEP, STL, native F3D and Z-up preview PNGs.

## Fusion 360 API problems it handles for you

Most of the time in AI-driven Fusion modelling goes to round trips and failed API calls, not to Fusion. These are the
traps the helper removes (details in [SKILL.md](skills/fusion-fast-modeling/SKILL.md)):

| What you see | Cause | What the skill does |
|---|---|---|
| `VCS_SKETCH_OVER_CONSTRAINTS` when two holes sit at the same height | two driving dimensions with the same value from the same origin | draws the geometry 0.013 mm off target and lets the dimension expression pull it exact |
| "no target body to cut" on a through-all cut | a one-sided `setAllExtent` cut fails once a join exists | cuts a long finite distance (1000 mm) instead |
| the extrusion fills the whole face | a sketch on a face has the face outline projected in | deletes the reference curves on creation |
| sizes off by 10× | Fusion stores lengths in cm and volumes in cm³ | every length you pass in is mm |
| sketch coordinates mirrored or swapped | sketch axes depend on the plane (on `yz`, x = −world Z) | you give world coordinates, the helper maps them |
| a second body appears | a `join` whose profile touches nothing | `expect_bodies=1` fails the checkpoint |
| the "iso" view shows the part on its side | the view cube assumes Y-up | explicit Z-up cameras for the preview images |
| lost edge references after patterns and fillets | history not regenerated | `m.settle(...)` |
| a sweep path whose arcs come back with swapped ends | Fusion keeps sketch arcs counter-clockwise | `Sketch.route(...)` draws and dimensions a straight-and-arc path |
| the STEP file looks ten times too small | Fusion declares `SI_UNIT(.CENTI.,.METRE.)` in its STEP output | nothing to fix; check an export by re-importing it |
| `Körper2`, `Ebene1`, `Unbenannt` | default names are localised | everything is addressed by names you give it |

## Quick start

**Requirements**

- Autodesk Fusion (desktop app, running). Tested with Fusion 2705.1.25 on Windows 11.
- Fusion's MCP server switched on under **Preferences > General > API**
  ([Autodesk's documentation](https://help.autodesk.com/view/fusion360/ENU/?guid=FMCP-OVERVIEW)). It accepts local
  connections only and needs no sign-in.
- Claude Code with that server registered under the name `fusion-local` (the skill refers to the tool
  `mcp__fusion-local__fusion_mcp_execute`). Use the port shown in Fusion's preferences; it was 27182 in the tested
  setup:

```bash
claude mcp add --transport http fusion-local http://127.0.0.1:27182/mcp
```

**Install the skill** (personal skills live in `~/.claude/skills/`, project skills in `.claude/skills/`)

```bash
git clone https://github.com/AIPris/fusion-blitz.git
mkdir -p ~/.claude/skills
cp -r fusion-blitz/skills/fusion-fast-modeling ~/.claude/skills/
```

```powershell
git clone https://github.com/AIPris/fusion-blitz.git
New-Item -ItemType Directory -Force "$HOME\.claude\skills" | Out-Null
Copy-Item -Recurse fusion-blitz\skills\fusion-fast-modeling "$HOME\.claude\skills\"
```

**Use it.** Open Claude Code and describe the part. The skill loads on its own when a request is about modelling in
Fusion, or call it with `/fusion-fast-modeling`:

> Model a wall hook in Fusion: a mounting plate 50 mm wide (x), 70 mm tall (z) and 5 mm thick (y), back face on y = 0.
> Two 5 mm holes along y at x = 25, z = 12 and z = 58. A round arm, 12 mm diameter and 35 mm long, out of the front
> face, centred at x = 25, z = 35. R4 plate corners, R2 on the arm tip and on the arm-plate joint.

Claude writes `build_<job>.py`, runs it in Fusion, fixes what the checkpoints flag, exports STEP, STL and F3D, and
leaves the finished document open and unsaved.

## Example results

The three small benchmark parts, as built by Claude with the skill. Each part has a build script you can read in
[`examples/`](examples) (written during the v2 benchmark runs; they still run unchanged and pass their checkpoints with
v2.3).

<table>
<tr>
<td align="center"><img src="examples/comb_iso.png" width="260" alt="Desk cable comb modelled in Fusion 360: 90 x 28 x 12 mm bar with five slots, two mounting holes and R3 corners"><br><b>Cable comb</b><br><a href="examples/build_comb.py">build_comb.py</a></td>
<td align="center"><img src="examples/hook_iso.png" width="260" alt="Wall hook modelled in Fusion 360: 50 x 70 mm plate, two holes, a 12 mm round arm with R2 fillets"><br><b>Wall hook</b><br><a href="examples/build_hook.py">build_hook.py</a></td>
<td align="center"><img src="examples/box_iso.png" width="260" alt="Open-top project box modelled in Fusion 360: four screw posts with pilot holes, six front vent slots, R5 corners"><br><b>Project box</b><br><a href="examples/build_box.py">build_box.py</a></td>
</tr>
</table>

The hard part, the flanged piping spool (the benchmark's reference build, see
[benchmarks/README.md](benchmarks/README.md#task-4-flanged-eccentric-elbow-spool)):

<img src="benchmarks/spool-reference.png" width="420" alt="Flanged eccentric reducing elbow spool in Fusion 360: two flanges with bolt holes, a 90 degree bend, an eccentric reducer, a 45 degree sensor boss, four gusset ribs and two lifting lugs">

## How a build looks

A build is a short script of named parameters, features and checkpoints (adapted from
[`examples/build_comb.py`](examples/build_comb.py)):

```python
import fusion_fast as ff

m = ff.new("Cable_Comb", replace=True)
m.params(bar_len=90, bar_w=28, bar_h=12, slot_w=7, slot_d=8, slot_pitch=16, slot_count="5", corner_r=3)

base = m.sketch("xy", name="Bar")                       # coordinates are world (x, y), in mm
base.rect(0, 0, "bar_len", "bar_w")                     # strings are Fusion expressions, so the model stays parametric
m.extrude(base, "bar_h", body="Comb")
m.report("bar", expect_size=(90, 28, 12), expect_volume=90 * 28 * 12, expect_bodies=1)   # raises here, naming the stage, if off

m.fillet("Corner_Fillet", ("corner_r", m.edges(parallel="z", x=[0, 90], y=[0, 28])))
```

[`SKILL.md`](skills/fusion-fast-modeling/SKILL.md) has the full helper cheat sheet: sketches on world planes and faces,
extrude and cut, hole sets, rings and polygons, rectangular and circular patterns, mirrors, sweeps along dimensioned
routes, lofts, revolves, construction axes, edge and face selection by position (and by the seam between two
features), fillets and chamfers, `report`, `probe`, `what_if`, export and views.

## Limitations

- Tested on Windows 11 with Fusion 2705.1.25 and Claude Code only. The helper uses just the Fusion API, but other
  platforms are untested.
- It drives the **local desktop MCP server** (`fusion_mcp_execute` scripts), not Autodesk's cloud MCP servers.
- Wrapped: sketches, extrude, cut, holes, rings, polygons, rectangular and circular patterns, mirror, sweep (with a
  dimensioned straight-and-arc route), loft, revolve, construction axes, fillets, chamfers, edge selection by position
  and between features, probes, export, views. Not wrapped: native threads, shell and angled work planes. For those,
  `SKILL.md` tells Claude to use the raw API inside the same build file and to finish with a checkpoint.
- The benchmark covers four parts and a handful of runs. See [benchmarks/README.md](benchmarks/README.md) for what it
  does and does not show.
- Geometry checks do not prove strength, fit or printability. Review parts before you manufacture them.

## Repository layout

```text
skills/fusion-fast-modeling/    the skill: SKILL.md, scripts/fusion_fast.py (helper), scripts/example_build.py (template)
examples/                       build scripts and preview images produced with the skill in the benchmark
benchmarks/                     method, per-run results, chart, report script and the grading harness
```

Skill versions are tagged. `v1.0.0` is the first draft, measured in benchmark iteration 1. `v2.0.0` is the iteration-2
version. `v2.1.0` adds the helpers a spool-like part needs (sweep, loft, revolve, circular pattern, construction axes, a
dimensioned route) and reads volumes at very high accuracy. `v2.2.0` replaces hand-computed volumes by probes and adds
rings and polygons. `v2.3.0` (current) adds `edges_between` and the per-cut material share and trims the probing
advice. The development log, with every spool run on the way, is in [benchmarks/README.md](benchmarks/README.md).

## License

[MIT](LICENSE). Fusion 360 and Autodesk are trademarks of Autodesk, Inc. This project is independent and is not
affiliated with or endorsed by Autodesk or Anthropic.

---
name: fusion-fast-modeling
description: Build, change and export parametric models in Autodesk Fusion 360 quickly and reliably through the fusion-local MCP (fusion_mcp_execute scripts). Use whenever the user wants something modelled, modified or exported in Fusion 360 / "Fusion" - brackets, holders, trays, enclosures, plates with holes, fillets, patterns, STEP/STL/F3D files, print parts - even if they never say "skill" or "script". Ships a tested Python helper (fusion_fast) that removes the Fusion API boilerplate and the known API traps (cm units, flipped sketch planes, same-height hole dimensions, through-all cuts, face-sketch projection), plus a build-script loop that rebuilds the whole model in one call.
---

# Fusion fast modelling

Almost all the time in Fusion modelling goes to round trips and failed API calls, not to Fusion (a whole
part builds in seconds). Three habits remove most of it:

1. **One build file, rebuilt from scratch.** Write the whole model as a `build()` in a `.py` file, run it with a
   five-line stub, and when something fails fix it with a small `Edit` and run again. Nothing is re-sent in full and
   the file is the reproducible source of the model.
2. **Use the `fusion_fast` helper** (`scripts/fusion_fast.py`, next to this file). It works in millimetres, in
   world coordinates and by position, so you never think about cm, sketch axes or edge indexes.
3. **Check with numbers, not screenshots.** Work out the expected bounding box and volume by hand and pass them to
   `m.report(...)` after each stage. A wrong model (a join that touched nothing, a cut that missed) then fails in the
   same call, naming the stage. Look at one rendering at the end.

## The loop

1. Parse the request into named parameters (`m.params`). Derived values are expressions, not numbers, so the model
   stays editable in Fusion.
2. Copy `scripts/example_build.py` to the job folder as `build_<job>.py` and edit it. It shows a body, holes on two
   different planes, a fillet, checkpoints and export.
3. Run it through this stub (`<SKILL_DIR>` = this skill's base directory, `<JOB_DIR>` = the job folder):

```python
import sys, importlib
for p in (r"<SKILL_DIR>\scripts", r"<JOB_DIR>"):
    if p not in sys.path:
        sys.path.insert(0, p)
import fusion_fast, build_<job>
importlib.reload(fusion_fast)      # Fusion's Python keeps imported modules alive between calls,
importlib.reload(build_<job>)      # so reload or you run yesterday's code

def run(_context: str):
    build_<job>.build(r"<JOB_DIR>")    # exports STEP / STL / F3D and PNG views there
```

4. On an error, read the message (it names the stage and the check), `Edit` the build file, run the stub again.
   `ff.new(name, replace=True)` closes the previous attempt and starts clean. Never wrap `run` in try/except: the
   traceback is your debugger.
5. When it passes, open the PNG once (`views` gives iso, top, front, ...) to confirm it is what was asked for.
6. Leave the finished document open and unsaved. Report the source path, export paths, and the checks that
   actually ran, as in the report line (do not claim a check that was not run).

If the project has its own output convention (an `AGENTS.md`, an `outputs/` folder), follow it: job folder
`outputs/<job>/` holding `build_<job>.py`, STEP, STL, F3D, PNGs and a short summary.

## Helper cheat sheet (all lengths in mm; a number is mm, a string is a Fusion expression)

| Call | Does |
|---|---|
| `m = ff.new(name, replace=False)` / `ff.open_model(name)` | new parametric document / re-attach to one `ff.new` made |
| `m.params(width=40, wall="3 mm", half="width / 2", cols="4")` | user parameters (create or update); counts are unitless strings |
| `sk = m.sketch("xy"\|"xz"\|"yz", at=0, name=)` | sketch on a world plane, offset along its normal by `at` (number or expression) |
| `sk = m.sketch(face)` | sketch on an axis-aligned planar face, e.g. `m.face(normal="+z")` |
| `sk.rect(u, v, w, h, center=False)`, `sk.circle(u, v, dia)` | fully dimensioned; `(u, v)` are world coordinates of the two axes in the plane, in x,y,z order: xy -> (x, y), xz -> (x, z), yz -> (y, z) |
| `m.extrude(sk, dist, op="new"\|"join"\|"cut"\|"intersect", toward="+"\|"-"\|"sym", body=, name=)` | `dist="all"` goes through everything; `toward` is the world direction along the plane's normal axis |
| `m.holes(plane, [(u, v), ...], dia, depth="all", toward="-", at=0, name=)` | circles plus one cut. `at` is the surface you drill from, `toward` points into the material |
| `m.pattern(feat, "x", count, spacing, axis2=, count2=, spacing2=)`, `m.mirror(feat, "yz")` | rectangular pattern (counts/spacings may be parameters) and mirror |
| `m.edges(parallel=, curve=, convex=, min_len=, x=, y=, z=)` | edges by position: `x=4` or `z=(0, 5)` (None = open end), `parallel="y"`, `curve="circle"`, `convex=60` (outside corners) |
| `m.face(normal="+z", at=None)` | planar face by outward normal (outermost one if `at` is None) |
| `m.fillet(name, (r, edges), ...)`, `m.chamfer(name, d, edges)` | one feature; several (radius, edges) pairs blend together |
| `m.settle(param)` | regenerate through a parameter round trip (see quirks) |
| `m.report(stage, expect_size=(x, y, z), expect_volume=, expect_bodies=)` | checkpoint: raises on unhealthy features, under-constrained sketches, wrong size/volume/body count |
| `m.export(dir, stem, kinds=("f3d","step","stl"))`, `m.views(dir, stem, names=("iso","top"))`, `m.close()` | files verified to exist; Z-up views; close only models `ff.new` made |

Names you give things (bodies, features, sketches) are how you find them again. Fusion's defaults are localised
(a German UI says `Körper2`, `Ebene1`, `Unbenannt`), so never look anything up by a default name.

## Safety

The user's Fusion usually holds many open, unsaved documents. `ff.new` refuses a name that is already open and
`ff.open_model` / `m.close` only touch documents `ff.new` made. Never save, never close the user's documents, and
never use the MCP `document close` action (it closes whatever is active). Prove nothing else changed with
`ff.open_documents()` before and after if it matters.

## Quirks the helper already handles (know them if you drop to the raw API)

- Fusion stores lengths in cm and volumes in cm^3: mm x 0.1, mm^3 x 0.001. `evaluateExpression(expr, "mm")` returns cm.
- Sketch axes depend on the plane (on `yz` sketch x = -world Z) and origin-plane axes can be reversed. Convert with
  `sketch.modelToSketchSpace(...)`; never assume.
- Two driving dimensions from the origin with the same value (two holes at the same height) fail with
  `VCS_SKETCH_OVER_CONSTRAINTS`. The helper draws geometry 0.013 mm off target and lets the expression pull it exact.
- A one-sided `setAllExtent` cut fails with "no target body to cut" once a join exists, even far from it. A long finite
  distance (1000 mm) cuts the same material.
- A sketch made on a face comes with the face outline projected in; "all profiles" then extrudes the whole face.
  The helper deletes reference curves on creation.
- A `join` whose profile touches nothing quietly makes a second body. `expect_bodies=1` catches it.
- Fusion's view-cube names ("iso", "top") assume Y-up and show Z-up models on their side; `views` uses explicit cameras.
- A fresh build whose last features are fillets or chamfers after patterns can report lost edge references until
  the history is regenerated from a changed state: `m.settle("<some mm parameter>")` once, then `m.report`.
- `m.edges(convex=60)` also returns hole rims (they are outside corners of the material). Combine it with
  `parallel=`, `curve=` or a `z=` range to pick what you mean.
- A native thread, shell, revolve, loft or sweep is not wrapped. Use the raw API in the same build file
  (`m.root`, `m.design`), query `fusion_mcp_read` with `queryType="apiDocumentation"` before guessing a signature,
  and still finish with `m.report` (and add the wrapper here if you needed it twice).

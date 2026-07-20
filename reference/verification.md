# Mechanism verification — r1/r2/r3 with real geometry

Design 3D mechanisms (servo → linkage → fin/arm/…) so they are **interference-free, drivable
through the full range of motion, and fixed (not floating)**. This complements the authoring
rules ([rules.md](rules.md)): authoring makes an *editable* model; verification proves the
*mechanism is correct*. Applies whether you generate geometry with a code CAD kernel
(build123d etc.) and import STEP, or model natively — **always pass the harness before
declaring done**.

Executable harness (real boolean intersection / sweep / fixation / linkage) →
[verification-harness.md](verification-harness.md).

## Acceptance gates (r1–r3) — must all hold before "done"
- **r1.** No pair of parts interferes (static, neutral pose).
- **r2.** From the driver (servo horn / crank), every moving part can be driven through its full
  range, and at every pose across the range nothing interferes.
- **r3.** No part floats; each touches / is fastened to some structure.

These are **pass/fail gates, not intentions.** Do not say "done" until the harness is green.

## Why "clash / floating / dead-linkage / disconnected-rod" recur → prevention
The common root cause is **using weak verification (approximation, neutral-only, visual,
assumption, trusting a silent pass) as proof of correctness.** Replace it with strong
verification (real geometry, all poses, numeric, adversarial).

| Symptom | Recurrence cause = weak check | Prevention = strong check |
|---|---|---|
| **Clash / interpenetration (r1)** | bbox/AABB, or eyeballing "probably clears" | **Real solid boolean per pair** `(a & b).volume > ε`. Never trust bbox. |
| **Clashes when moving (r2)** | verified only at neutral | **Sweep every joint to its limits** and re-boolean the moving part vs all parts at each pose. |
| **Floats (r3)** | placed but contact never confirmed | **Each part touches structure** (boolean contact or fastening). Detect isolated parts. |
| **Rod not connected / dead center** | endpoint coords eyeballed/assumed | Rod endpoint **coincides (dist ≈ 0)** with its attach point; **transmission angle** is not a dead point (≈0°/180°). |
| **"Pass" but actually wrong** | no marker / silence treated as correctness | **Adversarial**: inspect/render the real solid. Suspect exactly where the checker is silent. |
| **Pull direction is oblique / transmission dies** | only "connected" checked, not force direction | **Cable departure angle vs pin motion ≤ 25°** (pull = cosθ; 90° = 0). |
| **Shaft/part can pull out** | contact check ignores constraint *direction* | Nudge rotating/sliding parts along the constraint axis ±; assert the retainer still intersects > 0. |
| **Printed part is line-contact chunks** | union is "1 solid" but knife-edge joined | **solid count = 1** and design rule "union overlap ≥ 1.5 mm" (0.05 is for inter-part clearance only). |
| **Mount has no fastening holes** | "contact exists" treated as fixed | Probe the screw holes: position correspondence, through-clearance, surrounding material. |

## P1–P6 — prevention principles (apply during design AND at completion)
| # | Principle | Meaning | For |
|---|---|---|---|
| **P1** | **See it as real geometry** | Interference = **boolean intersection volume** `(a&b).volume`. bbox/AABB/tessellation are aids only, never the verdict. | r1 |
| **P2** | **See every pose** | r2 holds only when *driven*. Sweep each joint to its limits (min/0/max, finer preferred) and re-boolean at each. | r2 |
| **P3** | **Prove fixation** | r3 is "connected", not "placed". State 1:1 how each part is fixed to which structure. **Design the mounts first.** | r3 |
| **P4** | **Linkage in numbers** | (a) rod endpoint = attach point (dist 0), (b) rod length constant over range (parallelogram) or RSSR satisfied, (c) transmission angle not a dead point (≈90° at neutral). | rods / dead center |
| **P5** | **Whitelist intentional contact** | Explicitly exclude designed contacts (bearing⇔shaft / ball joint / fin⇔pivot / mount⇔plate / bonded face / wall penetration / flexible-cable routing) and flag only *real* collisions — but **don't over-exclude and hide true clashes** (reason per line). | r1/r2 noise |
| **P6** | **Distrust the pass** | Even all-green, **render one real solid at the range limits and look.** Suspect exactly the whitelisted spots. Don't loosen thresholds/ranges silently (needs human approval). | everything |

> They interlock: **P1×P2 → r1/r2, P3 → r3, P4 → drive, P5 → denoise, P6 → catch misses.**
> Drop one and a symptom returns (bbox-only=P1 → interpenetration / neutral-only=P2 → moving clash /
> place-only=P3 → floating / eyeball-only=P4 → dead center & disconnection).

## Functional geometry — static coexistence is not enough
Checking only "zero interference / has contact / is sealed" lets **functional** defects through:
a driven cable leaving at 90° (transmission dead), a tray joined at 0.05 mm (no strength),
missing fastening holes, a pivot free to pull out, a slot merged with a bore so a "hole" is open.
Add these five views (implemented in the harness):

| View | Check |
|---|---|
| **Transmission direction** | Driven cable's first segment vs pin motion direction ≤ 25° (pull = cosθ). "Connected" ≠ "can pull". |
| **Retention / constraint** | Nudge every rotating/sliding part along each constraint direction ±; assert the retainer intersects > 0 (no pull-out). |
| **Manufacturing integrity** | Every printed part solid-count = 1; union members overlap ≥ 1.5 mm (detect knife-edge / line contact). |
| **Fastening features** | For every pair declared "screwed": both holes' position correspondence (from a single-source constant), through-clearance, surrounding material (annulus). |
| **Closed hole / clamp load path** | Slots/holes stay *closed* (not merged with an adjacent bore into an opening); and for clamped joints, the load actually transmits along the load direction (existence ≠ load-path — a strap can pass a slot with contact yet apply no clamp force). |

## Two-loop review (inner deterministic + outer independent)
- **Inner loop** = this deterministic harness, automated and re-run every change.
- **Outer loop** = an **independent reviewer** given only *r1–r3 + the STEP/renders* — **not** the
  whitelist or the design intent — asked to refute. **Perspective independence ≠ execution
  independence**: if you write the outer prompt in the inner vocabulary (interference / floating /
  sealed), the blind spots are shared. Frame the outer loop from **function** (does it swim / assemble /
  hold?). A human's solid-model review is the strongest outer loop — point-cloud renders hide
  line-contact and open slots that a solid display shows at a glance.

## C18 — translate outer findings into inner checks
**An outer-loop finding (independent audit / human review) is not closed by fixing the design
alone. Add the corresponding deterministic inner check so it is auto-detected forever — only then
is it closed.** Every recurring class of defect becomes a permanent check.

## Budget / rejection hygiene
- Overlap budgets (for intentional bonded/contact/press-fit representation) must be **derived from
  a physical joint model**, with a rationale comment — never a "calibration value to make the run
  pass" (that is P5 abuse).
- **Rejecting an audit finding also requires a physical basis** (measured value + physical model).
  An unfounded "it's a gland, so it must be fine" once hid a true 57%-embedded part.

## Completion gate
```
r1 all-pair real interference == 0
r2 sweep interference == 0 (each joint to its range limits)
r3 floating == 0 (every part has a fixation target)
linkage: endpoint dist ≈ 0 / rod length var ≈ 0 / transmission angle 45–135°
adversarial render inspected
→ only then is "r1–r3 met" true. One red = not met (report the volume/location honestly, never fake a pass).
```

## Behavior
- Confirm r1–r3 as the acceptance criteria first. Design mounts first; state each part's fixation 1:1 (P3).
- Re-run the harness on every change; ship artifacts (STEP/zip) only after all-green.
- If interference / floating / disconnection remains, **report the volume and location honestly** —
  never fake a pass. Loosening a threshold or range needs human approval.
- Completion report = the finding + the artifact + the verification result
  (all-pair real interference 0 / sweep 0 / fixation OK).

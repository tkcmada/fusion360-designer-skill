# Verification harness — prove r1/r2/r3 on real geometry

A reusable harness that judges by **real boolean intersection** and never uses bbox/AABB/visual/
assumption as the verdict. See [verification.md](verification.md) for the r1–r3 gates and the
P1–P6 principles this implements. Code is shown in a code-CAD kernel style (build123d `Part` /
`Compound`); adapt the boolean/bbox calls to your kernel.

## P1–P6 ↔ harness steps
| Principle | Step |
|---|---|
| **P1 real geometry** | §1 r1 all-pair boolean `(a&b).volume` |
| **P2 every pose** | §3 r2 range-of-motion sweep |
| **P3 prove fixation** | §4 r3 fixation (isolated = floating) |
| **P4 linkage in numbers** | §5 endpoint dist 0 / rod-length var / transmission angle |
| **P5 whitelist intentional contact** | §2 JOINTS (minimal, reasoned) |
| **P6 distrust the pass** | §6 adversarial render + §7 gate |

## 0. Part list
Assemble all parts as `[(name, part)]` in master coordinates. Make moving mechanisms a function
of angle, `build(angle)`, for sweeping.

## 1. r1 — all-pair real interference (bbox forbidden)
```python
def clash(a, b):
    ii = a & b                          # boolean intersection — NOT bbox
    return ii.volume if (ii is not None and ii.volume > 1e-3) else 0.0

def check_r1(parts, is_joint):
    viol = []
    for i in range(len(parts)):
        for j in range(i+1, len(parts)):
            ni, pi = parts[i]; nj, pj = parts[j]
            if is_joint(ni, nj):        # intentional contact excluded (P5)
                continue
            v = clash(pi, pj)
            if v > 3.0:                 # a few mm^3+ counts as real interference
                viol.append((ni, nj, round(v)))
    return viol                         # empty => r1 OK
```

## 2. Whitelist intentional contact (P5) — do not over-exclude
Exclude only "by-design touching" pairs, by substring. Keep it minimal so true clashes aren't hidden.
```python
JOINTS = [
  ("shaft","bearing"), ("shaft","crank"), ("crank","pushrod"), ("pushrod","horn"),
  ("horn","servo"), ("pivot","fin"), ("pedestal","fin"), ("pedestal","pivot"),
  ("mount","<held-part>"), ("plate","<mounted>"), ("cap","penetrator"),
  ("hull","<wall-penetrating-part>"),   # wall penetration is normal
  ("cable","<small-cap-fitting>"),      # flexible cable may route around
]
def is_joint(a,b):
    return any((x in a and y in b) or (x in b and y in a) for x,y in JOINTS)
```
- **radial/bore exclusion**: external fin / wall-penetrating shafts have `radial > bore` by design → exclude from the bore check by name.
- **the whitelist is itself audited**: write *why* each line is excluded. Don't casually add lines and erase a true clash (P6).
- Prefer **longest-substring match** so `"pec cable clip"` isn't swallowed by a `"pec cable"` rule.

## 3. r2 — range-of-motion sweep (neutral alone is invalid)
Drive each joint to its limits; at each pose re-boolean **moving part × all parts.**
```python
def check_r2(build, fixed_parts, angles):          # angles = (-lim, ..., +lim)
    viol = []
    for ang in angles:
        for (nm, p, kind) in build(ang):
            if kind != "link":  continue           # moving parts only
            for (fnm, fp) in fixed_parts:
                if clash(p, fp) > 3.0:
                    viol.append((ang, nm, fnm))
    return viol
```
- At least `-limit / 0 / +limit`, finer preferred. Sweep each of multiple joints independently.
- The moving-part set **must include the driven final output** (the fin/arm) — don't rotate the
  linkage and forget to rotate what it drives.

## 4. r3 — fixation (detect floating)
Each part touches ≥ 1 structure/neighbor (boolean contact), or has a corresponding mount.
```python
def check_r3(parts, structure_names):   # structure = hull/plate/cap/mount …
    floating = []
    for nm, p in parts:
        if nm in structure_names:  continue
        touched = any(clash(p, q) > 0.5 or _adjacent(p, q)   # contact or near (fastened)
                      for qn, q in parts if qn != nm)
        if not touched:
            floating.append(nm)          # floating in space
    return floating
```
- **Design the mounts first** (P3): camera→bulkhead, servo→cradle, board→base plate. Be able to
  state "this part is fixed to which structure, how", 1:1.
- If a part is fixed by hook-and-loop/adhesive/fastener with no solid contact, **model the fixing
  part (the mount)** so it appears in the check.

## 5. Linkage connection & transmission (prevent disconnection / dead center) — P4
```python
# (a) endpoint connection: rod end == attach point
assert np.linalg.norm(rod_end - horn_point) < 0.5       # ≈ 0 coincidence
# (b) rod length constant over range (parallelogram) or RSSR solvable
Ls = [np.linalg.norm(cb(a) - hb(a)) for a in sweep];  assert max(Ls)-min(Ls) < 0.5
# (c) transmission angle (arm vs rod): ~90° good, near 0/180° = dead center = not drivable
ang = degrees(acos(abs(dot(arm, rod)) / (norm(arm)*norm(rod))))  # target ~90° neutral, 45–135° over range
```
- If the arm is parallel to the rod at neutral (transmission angle ≈ 0), **the servo turns but the
  output doesn't move** (dead center). Phase-shift so neutral sits at ≈ 90°.

## 6. Adversarial render (P6)
- Render the real solid at neutral **and at the range limits** (three-view / iso), and **look** for
  interpenetration / floating / disconnection.
- Even with all checks green, always look at one. Suspect the whitelisted spots.

## 7. Pass gate
```
r1 all-pair real interference == 0
r2 sweep interference == 0 (each joint to its range limits)
r3 floating == 0 (every part has a fixation target)
linkage: endpoint dist ≈ 0 / rod length var ≈ 0 / transmission angle 45–135°
adversarial render inspected
→ only then is "r1–r3 met" true. One red = not met (report volume/location honestly, no fake pass).
```

## Check taxonomy (deterministic checks by category)
Each recurring defect class becomes a permanent check (the C18 rule in [verification.md](verification.md)).
Categories that have paid off in practice:

| Cat | Check |
|---|---|
| **JT** joint/whitelist | No blanket wildcard whitelist. Excluded pairs must assert contact (0 < gap < 1 mm, or fit-volume only). |
| **FX** fixation graph | Build a contact graph; every part is reachable from a structure root. No skip-lists. **FX-2**: each printed part = one connected solid; union members overlap ≥ 1.5 mm. |
| **WT** watertight | Enumerate every through-hole in a pressure boundary; a mating seal (penetrator/window/plug) exists (probe). **WT volume balance**: part volume = analytic (disk − declared holes) within ±3% → detects undeclared holes. |
| **MT** mate | Mates by matched reference points (dist ≈ 0) derived from part constants; a bare spline = fail; receiving feature exists. **MT retention**: nudge along constraint axis ±; retainer intersects > 0. **MT engagement**: project the intersection along the axis, require engagement length ≥ threshold. |
| **FIT** fit table | Shaft Ø ↔ hole Ø, cable Ø ↔ bore etc. matched against a single-source table. **FIT spacing**: penetrator spacing ≥ threshold, computed from the single source. **FIT-3 fastening**: hole probe non-intersecting + surrounding annular material. |
| **SW** sweep | Moving-part set includes the driven final output; re-boolean all pairs at each range limit. |
| **CL** clearance | Minimum clearance, not zero-overlap: moving⇔fixed ≥ 3 mm, adjacent fixed ≥ 2 mm. |
| **CQ** contact quality | Fixation checked for area, support location under CG, and reaction (clamp). Line/point contact ≠ fixed. Require (part, support-set, min contact area) for every mounted item. |
| **CB** cable | Separate housing (fixed + clips) from inner (moving). Entry angle within ±15° of axis. **Departure angle ≤ 25°** (pull = cosθ). **Bend anchor**: within 8 mm of any path bend > 25° there is a real clip. |
| **CT** contact budget | Contact pairs also get an overlap budget (default ~30 mm^3). Intentional representation (receiving pocket, clip groove, fairlead pass-through, fastener seat) needs a physics-derived per-case budget + rationale. Pairs with bond keep the bond budget; the two are distinct. |
| **TD** insertability | Nudge each part along its assembly path; the cross-section clears the holes/frames on the way (a wide part's diagonal < bore Ø). Split + anti-rotation tab (square < round bore) if needed. |
| **BS** closed-hole / clamp path | **BS-1**: bridge material outside each slot ≥ threshold (a slot isn't merged with a bore into an opening). **BS-2 clamp load path**: floor material exists between the strap and the base; the strap doesn't skim the base plane at the crossing; strap⇔part gap ≤ 0.3 (existence ≠ load transmission). **BS-3 clamped stack**: head seats on the mating part and head↔nut clamp a continuous solid stack (air gap = fail, tip past the nut = fail). |
| **COTS** real envelope | Model COTS from official-drawing dimensions as source-commented constants (not a placeholder envelope); check window/mating clearance against the real size. Prefer feature placement over bbox-center placement. |
| **LG** ledger | Reconcile the designed-mount ledger ↔ the export part list ("designed but not implemented" = fail). Reconcile artifact file count = manifest count. |
| **RD** render | Emit a per-mechanism close-up incl. range limits; hand it to an independent visual review. |

## Measurement pitfalls (lessons on the checker side)
- **Distance via exact BRep extrema**, not a tessellation-vertex KD-tree: on a smooth cylinder the
  vertices bias to the end rings and mis-measure a mid-surface contact (e.g. a real ~2 mm contact
  read as 100 mm).
- **Longest-substring match** for whitelist classification (`"pec cable clip"` must not be swallowed
  by a `"pec cable"` rule).
- **Fit-pair contact judged analytically**, not by mesh distance (a coaxial 0.3 mm annulus is judged
  by containment / reference point).
- **Small-graze threshold**: use a low intersection epsilon (e.g. 0.5 mm^3). A high one (3.0) let a
  real ~1 mm^3 contact slip through.

## Common pitfalls (worked)
- **bbox says "clear" but a corner interpenetrates** → always boolean.
- **Neutral OK but the range limit clashes** → r2 sweep is mandatory, esp. where a crank/horn swings.
- **Placed but floating** → forgot the mount; decide the fixation target first (P3).
- **Looks connected but a dead-center transmission angle 0 = won't move** → transmission angle in numbers; phase-shift 90°.
- **Over-stuffed whitelist hides a true clash** → exclude minimally, reason per line.
- **Rotation sign mistake** → track a real point with a marker cylinder and verify the mapping numerically (don't trust a hand matrix).
- **COTS part larger than its printed mount** → when substituting a printed integral feature with a
  COTS part, model the COTS real envelope + its swept motion first; verify the mount and clearances
  hold before assuming a drop-in.

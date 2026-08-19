---
name: drafting-geecs-scans
description: Compose a validated geecs_schemas ScanRequest YAML for the operator to run in GEECS-Console. Use when asked to set up, prepare, or draft a scan (jet scan, magnet sweep, noscan data collection, optimization). This drafts scans — it does NOT execute them; real data-taking scans run only in the GEECS engine.
---

# Drafting GEECS Scans (composition, not execution)

Real BELLA/HTU data-taking scans run in the **GEECS engine** (scan numbers,
s-files, event schema, DG645 shot control) — not in OSPREY. Until the
GEECS-side scan MCP exists, your scan capability is **drafting a
`ScanRequest` YAML** that the operator reviews and runs in GEECS-Console.
Never present a draft as a started or completed scan.

## Workflow

1. **Gather intent**: what to sweep (or noscan/optimize), range and step,
   shots per step, which diagnostics must be saved, trigger handling.
2. **Resolve names — never invent them.** Axis `variable` names come from the
   experiment's scan-variables catalog (single devices and composite/pseudo
   variables like `ALine_e_beam_angle_offset_x`); `save_sets` entries name
   files in the experiment's `save_devices/` catalog (e.g. `Amp4Out`,
   `BCaveMagSpec`); `trigger_profile` names a shot-control configuration.
   If you don't know the exact catalog name, ask the operator or consult
   facility knowledge — an unresolved name goes in the draft as an explicit
   `# TODO(operator): confirm name` comment, never a guess.
3. **Compose the YAML** against the schema below.
4. **Sanity-check units and ranges** against live readbacks (read the
   channel's current value first; a jet scan from 4.0 to 6.0 mm should
   bracket the current position, not sit 40 mm away).
5. **Hand off**: save the YAML as an artifact, show it, and tell the
   operator to run it in GEECS-Console. Per-experiment presets live at
   `scanner_configs/experiments/<Exp>/presets/` in GEECS-Plugins-Configs —
   a good place for drafts the operator wants to keep.

## ScanRequest schema (geecs-schemas 0.9.x, schema_version 1)

Top-level fields (`mode` is required; everything else has defaults):

- `mode`: `step` (sweep axes) | `noscan` (collect without moving) |
  `optimize` (algorithm picks settings)
- `axes`: list of `{variable, positions}`; positions are
  `{start, end, step}` or `{values: [...]}`. Multiple axes form a grid —
  first axis is the outermost (slowest) loop. Empty for noscan/optimize.
- `shots_per_step`: shots at each position (or total, for noscan)
- `acquisition`: `strict` (every device in every row, shot-by-shot) |
  `free_run` (machine-rate trigger, timestamp matching)
- `save_sets`: list of save-set names; devices are unioned. These carry the
  completeness/image-saving guarantees.
- `background_telemetry`: true/false/unset — best-effort snapshot columns of
  every other live device (never stalls the scan); unset inherits default
- `trigger_profile` / `trigger_variant`: shot-control profile to drive;
  unset means the scan does not manage the trigger
- `actions`: `{setup: [], per_step: [], closeout: []}` — named action plans
- `description`: free text for scan metadata and the experiment log
- `background`: true marks data as background/calibration
- `optimization`: only with `mode: optimize` — `{variables: {name: [lo, hi]},
  objectives: {name: MINIMIZE|MAXIMIZE}, evaluator: {module, class_name,
  kwargs}, generator: {name, options}, max_iterations,
  move_to_best_on_finish}`

Reference example:

```yaml
schema_version: 1
mode: step
axes:
  - variable: jet_z
    positions: {start: 4.0, end: 6.0, step: 0.5}
shots_per_step: 10
acquisition: free_run
save_sets: [undulator_baseline, aux_diagnostics]
trigger_profile: htu_shot_control
actions:
  setup: [pre_scan_ebeam]
  per_step: []
  closeout: []
description: "jet z scan with probe"
```

The authoritative field reference is
`docs/geecs_schemas/schema_reference.md` in GEECS-Plugins — if this skill
and that document disagree, that document wins.

## Hard rules

- Drafting only: never claim a scan ran, and never try to execute one via
  Python, the control system, or any other tool path.
- Live moves outside a scan (single setpoint changes) are ordinary
  channel writes with their own approval flow — not this skill.
- `acquisition` values are GEECS-engine vocabulary (`strict`/`free_run`),
  not knobs you can emulate elsewhere.

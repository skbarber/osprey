---
name: drafting-geecs-scans
description: Compose, validate, and submit a geecs_schemas ScanRequest through the geecs MCP server. Use when asked to set up, draft, run, or submit a scan (jet scan, magnet sweep, noscan data collection, optimization), or to check on a running scan. Execution happens in the GEECS engine via its queueserver — this skill drafts the request and submits it through the approval-gated geecs tools.
---

# GEECS Scans (draft → validate → submit)

Real BELLA/HTU data-taking scans run in the **GEECS engine** (scan numbers,
s-files, event schema, DG645 shot control), reached through its
bluesky-queueserver. The `geecs` MCP tools are the submission path:
`validate_scan_request` (read, free), `submit_scan` (approval-gated),
`scan_progress` / `scan_status` (read), `stop_scan` (approval-gated),
`get_scan_result` / `get_scan_analysis` (read). GEECS-Console is a peer
client of the same queue — never tell the operator that pasting into the
console is required; submitting here is a first-class path.

## Workflow

1. **Gather intent**: what to sweep (or noscan/optimize), range and step,
   shots per step, which diagnostics must be saved, trigger handling.
2. **Resolve names — never invent them.** Use `list_scan_configs` for every
   catalog: `scan_variables` (single devices and composite/pseudo variables
   like `ALine_e_beam_angle_offset_x`), `save_sets` (e.g. `Amp4Out`,
   `BCaveMagSpec`), `trigger_profiles`, `actions`, `presets`. A name not in
   its catalog does not go in the request — ask the operator instead of
   guessing.
3. **Compose the request** against the schema below.
4. **Sanity-check units and ranges** against live readbacks (read the
   channel's current value first; a jet scan from 4.0 to 6.0 mm should
   bracket the current position, not sit 40 mm away).
5. **Validate**: run `validate_scan_request` on the composed request. Fix
   what it refuses; surface its warnings to the operator verbatim.
6. **Submit** with `submit_scan` — the approval prompt is the operator's
   review, so present the request's key facts (mode, axes, shots, save
   sets, trigger profile) in the message that accompanies it. If the tool
   returns `needs_acknowledgement` warnings, relay them to the operator and
   resubmit only with their explicit go-ahead, passing the acknowledged
   names. If it refuses because the queue is not empty, report the pending
   items — never clear the queue on your own initiative (`clear_queue` is
   its own approval-gated, operator-requested action).
7. **Track and report**: `scan_progress` while it runs, `get_scan_result`
   when it finishes. Report the scan number and outcome; on failure,
   remember the failed item returns to the *front* of the queue and say so.

An operator may also just want the YAML (to keep as a preset or run from
the console) — saving the draft as an artifact and stopping there is fine
when asked. Per-experiment presets live at
`scanner_configs/experiments/<Exp>/presets/` in GEECS-Plugins-Configs.

## ScanRequest schema (geecs-schemas 0.11.x, schema_version 1)

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
- `submission`: leave unset — the MCP server stamps provenance itself
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

- The geecs MCP tools are the ONLY execution path: never run a scan via
  Python, the control system, or any other tool. Never claim a scan ran
  without a `submit_scan` success and a scan number to show for it.
- One scan in flight: never stack queue items, and never call
  `clear_queue` except at the operator's explicit request.
- Live moves outside a scan (single setpoint changes) are ordinary
  channel writes with their own approval flow — not this skill.
- `acquisition` values are GEECS-engine vocabulary (`strict`/`free_run`),
  not knobs you can emulate elsewhere.

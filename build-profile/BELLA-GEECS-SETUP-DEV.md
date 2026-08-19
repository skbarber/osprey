# BELLA assistant setup — htu-assistant (GEECS + OSPREY)

**Audience:** the Claude Code agent (or human) working on the OSPREY-based
`htu-assistant`.

**BELLA is an EPICS facility from OSPREY's point of view.** GEECS-Plugins
ships a caproto **Channel Access gateway** (`GeecsCAGateway`, deployed on
`192.168.6.14`) that serves every enabled GEECS device variable as real
EPICS PVs — readback at `<experiment>:<device>:<variable>`, setpoint at
`…:SP`. Writes ride GEECS's native blocking set: a CA put completes only
when the device reports convergence, and a device-rejected set (e.g. out of
the device's GEECS-configured limits) fails the put with the device's own
error. OSPREY talks to it through its stock `epics_connector` with **zero
BELLA-specific code** — the gateway is the integration.

The authoritative client contract is **`GeecsCAGateway/PV_CONTRACT.md`** in
GEECS-Plugins (`dev` branch) — read it before wiring anything. The gateway
self-reports its installed version at `undulator:cagateway:version`.

Client operating semantics that differ from a stock EPICS IOC (normative
detail in the contract; the assistant carries these as the
`geecs-semantics` rule, and the profile sets the matching config):

- **Write timeouts must be ≥ 30 s** (`connector.epics.timeout` and
  `write_verification.timeout` in the profile): put-completion on an `:SP`
  is the physical move finishing; slow stages legitimately take 10–30 s.
- **Check `<experiment>:<device>:connected` before trusting readbacks**: a
  down device serves its last cached value silently, and a never-streamed
  variable reads as a clean `0.0`/`NO_ALARM` placeholder.
- **Reads are cheap** (gateway stream cache — never touch the device);
  **writes serialize one-in-flight per device**.
- **There is no abort**: cancelling a write abandons the wait; the
  hardware completes its move.
- Enums with numeric labels resolve **by value, not index**; path/long
  strings are char arrays (read as strings).

---

## Part 1 — Channel finder: hierarchical, generated from the GEECS DB

The channel finder runs in **hierarchical** mode (the `control-assistant`
preset default) over the **complete gateway served set** — 114 devices,
~6,000 channels including `:SP` companions, per-device `connected`, 140 PVA camera-image channels (listed, marked unreadable via CA — see below), and the
gateway's own diagnostics. Hierarchical navigation makes the full set
affordable; no curation subset is needed.

### How it's produced (never hand-edit the JSON)

The database is generated, in `build-profile/` of the osprey checkout:

- `scripts/extract_geecs.py` — drives GeecsCAGateway's own config builder
  (`GatewayConfig.from_geecs_experiment("Undulator")`), so extracted
  names/units/limits/settability are exactly the gateway's served set
  (every `get='yes'` variable ∪ settables of enabled devices). Run it with
  the GeecsCAGateway venv's Python, on a machine with lab-network access
  and the GEECS INI pair. It writes a snapshot JSON.
- `scripts/generate_hierarchical.py` — renders the snapshot into the OSPREY
  hierarchical channel database at
  `project/data/channel_databases/hierarchical.json`; the `project/`
  convention directory mirrors it onto the built tree.

To refresh after a GEECS DB change: rerun both scripts, then `osprey build`
(run anywhere inside this repo; output renders into `build/`).

Tree shape: `experiment → GEECS device type → device → variable [→ SP]`,
producing `undulator:<device>:<variable>[:SP]`.

### Naming requirement — tree keys ARE the PV components

**Tree keys must be the normalized PV components** — lowercase, every run
of characters outside `[A-Za-z0-9_]` collapsed to a single `_`, per
`PV_CONTRACT.md` (`Position.Axis 1` → `position_axis_1`). This is not
cosmetic: the finder's runtime path composes channel names from the
*selected tree keys*, so friendly keys produce PV names the gateway does
not serve. The GEECS-native name lives in each entry's description (e.g.
"GEECS name 'Enable_Output'. Output enable…"), which keeps operator
vocabulary searchable. The generator enforces this and hard-fails on
normalized-name collisions.

Descriptions carry the curated facility semantics: BCave = high-power
laser + LPA target + diagnostics; ACave = VISA undulator bunker; ALine =
e-beam transport from the EMQ triplet; chicane = FEL bunch decompressor;
Bldg 148 = primary laser bay; Gaia = pump laser; Ghost = leakage beam;
`HP_Daq` = gas-jet high-pressure controller. Inferred-from-name entries
are marked "(name-derived)".

Gateway self-diagnostics are in the tree:
`undulator:cagateway:{heartbeat, devices_connected, uptime, version,
restart}`. Heartbeat and devices_connected are the liveness signals
OSPREY's native system-health panel watches.

### Verification status

Live spot-check 2026-07-23 from a dev Mac with
`EPICS_CA_ADDR_LIST=192.168.6.14`: 12/12 sampled PVs connected with live
values (heartbeat ticking, `devices_connected` = 105 of 113 DB-enabled
devices). The full set is gateway-derived but not individually
live-verified; disconnected devices time out on caget. Two standing rules
for the database:

1. **Calibration/trust lives in the descriptions, nowhere else** — any
   caveat ("unverified", "mm not µm") must be in the entry's description
   or the model treats the entry as stated fact.
2. **Keep the companion facility-knowledge doc in sync** with what is
   verified-live vs. convention.

---

## Part 2 — Scans: the GEECS engine owns data-taking

A real BELLA scan claims a sequential **scan number** (`scans/ScanNNN/`),
writes the **s-file** the analysis stack reads, records a **versioned
event schema** to GEECS's Tiled, drives **DG645 shot control** (free-run
time-sync vs. strict single-shot), windows camera saving, executes
composite (pseudo) scan variables with end-of-scan restore, and runs
pre-flight checks against the live device set. All of that lives in the
GEECS engine (`GeecsBluesky`/`BlueskyScanner`). Accordingly:

- **OSPREY's native bluesky stack is not deployed** — no bridge, no
  OSPREY-side Tiled, no plan/results/health panels, bluesky MCP server
  disabled, bluesky skills removed. See `build-profile/profile.yml`.
- **The assistant's scan capability is composition, not execution**: the
  `drafting-geecs-scans` skill composes a validated
  `geecs_schemas.ScanRequest` YAML for the operator to run in
  GEECS-Console. Schema reference:
  `docs/geecs_schemas/schema_reference.md` in GEECS-Plugins;
  per-experiment presets (`scanner_configs/experiments/<Exp>/presets/`)
  are exactly ScanRequests and are the target format. Axis `variable`
  names come from the experiment scan-variables catalog (including
  composite variables like `ALine_e_beam_angle_offset_x`); `save_sets`
  name files under `save_devices/`. Hard rule: **never invent catalog
  names** — unresolved names go in as explicit operator TODOs.

**Do not** run GEECS scans through anything OSPREY-side: the
`free_run`/`strict` acquisition modes are `ScanRequest.acquisition`
vocabulary belonging to the GEECS engine, and nothing OSPREY-side may
import `geecs_bluesky` — it fights OSPREY's connector-mediation mandate.

Single setpoint changes outside a scan are ordinary OSPREY channel writes
(epics_connector → gateway, with limits + approval), not scan business.

---

## Part 3 — Facility-side prerequisites

- **PVA to the camera fleet** (images): `EPICS_PVA_ADDR_LIST` with the
  13-server fleet list + `EPICS_PVA_AUTO_ADDR_LIST=NO` in `.env` (roster of
  record: `HOSTS` in `GeecsPvaGateway/deploy/gen_fleet_status.py`). Camera
  images are pvAccess NTNDArray PVs (`undulator:<camera>:image`) served by
  per-server GeecsPvaGateway instances — Phoebus/p4p territory; OSPREY's
  channel tools are CA-only and cannot read them. `p4p` is installed in the
  build venv for the eventual sanctioned image path.
- **Channel Access to the gateway**: the OSPREY host/containers need
  `EPICS_CA_ADDR_LIST=192.168.6.14` (CA on standard port 5064) — the
  profile sets this as an env default and wires both connector gateways
  to that address. Verify with `caget undulator:cagateway:heartbeat`.
- **Tiled** at `http://192.168.6.14:8000` (read side; GEECS engine runs
  land there under the versioned event schema — see
  `GeecsBluesky/EVENT_SCHEMA.md` for column meanings). There is no
  OSPREY-side Tiled; this is the only catalog.
- **GEECS MySQL** on the same host — needed only by the channel-database
  extraction tooling (`build-profile/scripts/`), never at assistant runtime.
- The GEECS INI pair (`config.ini` / `Configurations.INI`) is needed only
  on the machine that runs the extraction tooling. Nothing in the built
  assistant reads it; it stays out-of-band on GEECS machines, never
  committed anywhere.
- An LLM `provider:`/`model:` pair with real credentials — the profile
  uses **CBorg** (`CBORG_API_KEY` in the repo `.env`).
- **`.env` must also carry**
  `CONFIG_FILE=<absolute-path-to-this-repo>/build/config.yml` — a
  workaround for a framework bug (hooks are launched without `CONFIG_FILE`,
  so the limits hook resolves its database against the repo root instead of
  the build zone; its empty-database failsafe then denies every write as
  "channel not in limits database"). Machine-specific absolute path: set it
  fresh on every new clone/machine. Remove when upstream ships
  `CONFIG_FILE` in hook environments (tracked: als-apg/osprey#636).

## Current profile state (cross-reference)

`build-profile/` in the osprey checkout is the source of truth: the
`control-assistant` preset **minus** the virtual accelerator and the
entire bluesky stack; live EPICS via 192.168.6.14 with writes enabled and
software limits checking **on**, over a generated limits database
(`scripts/generate_channel_limits.py`, same extract as the channel
database): one entry per settable `:SP` with min/max mirroring the GEECS
DB; readbacks and unlisted channels are refused. Layered write safety:
OSPREY software limits (client pre-flight) → gateway EPICS control limits
on `:SP` (CA-layer rejection) → GEECS device-side limits and hardware
interlocks (final authority) → per-write human approval throughout.
Services: PostgreSQL/ARIEL, OpenObserve, event dispatcher + worker,
multi-user web terminals (roster still placeholder `alice`/`bob`);
channel finder as in Part 1.

## Cross-checking

- `GeecsCAGateway/PV_CONTRACT.md` — the client API contract (naming,
  `:SP` semantics, `.DESC`, heartbeat/liveness, write behavior). The one
  document to trust over anything here.
- `GeecsCAGateway/DEPLOYMENT.md` — the served-set definition and a
  new-client onboarding recipe.
- `docs/geecs_schemas/schema_reference.md` — every ScanRequest/config
  field, generated from the schemas.
- `build-profile/scripts/` (osprey checkout) — the extraction + generation
  pipeline for the channel database, and the snapshot it last ran from.
- The old `bella-profiles` prototype is reference-only; its scanner
  wiring predates the gateway and must not be copied.

# HTU Assistant — build profile

This directory is the source of truth for the **HTU Assistant**, an OSPREY
agent for the HTU laser system at LBNL. It was created by the OSPREY build
interview on 2026-07-23. Edit the files here (never a rendered project) and
rebuild whenever something changes.

## Build and run it

This directory is an OSPREY **deployment repo**: `profile.yml` + convention
directories (`rules/`, `skills/`, `project/`, `scripts/`) are the durable
source; `build/` is derived output (wiped every build); `var/` is durable
runtime state; `.env` holds the keys.

```bash
osprey build     # render build/ from the profile (run anywhere in this repo)
osprey up -d     # start the deployment
osprey web       # launch the web terminal
osprey status    # see what's running
```

## What was decided in the interview

- **System**: the HTU laser system at LBNL.
- **Services**: the full `control-assistant` stack minus the virtual
  accelerator — PostgreSQL + ARIEL search, OpenObserve telemetry, the event
  dispatcher/worker pair, the Bluesky bridge + Tiled catalog with its web
  panels (PLAN/RESULTS/HEALTH), and the multi-user web-terminal tier. The
  virtual-accelerator simulator is dropped (`virtual_accelerator: null` in
  `profile.yml`): HTU is a laser on live EPICS, and the sim would squat CA
  port 5064. `osprey up -d` stands the services up after building.
- **Web-terminal users**: the roster is inherited from the preset and still
  lists the placeholder users `alice` (read-only) and `bob` (read-write).
  Replace them with real HTU users by overriding
  `modules.web_terminals` in `profile.yml` before deploying the web tier.
- **Connection**: live EPICS, via the gateway at `192.168.6.14` (standard CA
  port 5064 for both read and write). If HTU runs a separate write gateway or
  a non-standard port, fix the two `write_access` lines in `profile.yml`.
- **Privilege**: read **and write** (`control_system.writes_enabled: true`
  is pinned in `profile.yml`), so every write still passes the
  framework's approval prompt, writable-channel check, and per-channel limits
  before it reaches the machine — with GEECS device limits and hardware
  interlocks as the final authority (see the limits section below).
- **AI service**: LBNL's CBorg gateway, at the haiku tier
  (`model: haiku` resolves via CBorg's registry). `CBORG_API_KEY` lives in this repo's `.env`
  (already populated).
- **Historical data**: not needed for now — no archiver is configured. To add
  one later, wire an archiver under the `config:` section of `profile.yml`
  (OSPREY ships EPICS Archiver Appliance and MongoDB connectors).

## The channel database is real (generated from the GEECS DB)

`project/data/channel_databases/hierarchical.json` is **generated, not
hand-written**: `scripts/extract_geecs.py` pulls the Undulator experiment from
the GEECS MySQL DB using GeecsCAGateway's own config builder (so names,
units, limits, and settability match exactly what the gateway serves), and
`scripts/generate_hierarchical.py` renders the tree. 114 devices, ~6,000
channels, verified 1:1 against the gateway's computed PV names.

- Tree shape: `experiment → GEECS device type → device → variable [→ SP]`;
  channel names are `undulator:<device>:<variable>[:SP]` per
  `GeecsCAGateway/PV_CONTRACT.md`.
- Branch descriptions were curated in the 2026-07-23 interview (BCave =
  laser + LPA target, ACave = VISA undulator, ALine = transport from the EMQ
  triplet, chicane = FEL bunch decompressor, Bldg 148 = laser bay, Gaia =
  pump laser, Ghost = leakage beam, HP_Daq = gas-jet pressure controller).
  Name-derived guesses are marked "(name-derived)" in their descriptions.
- To refresh after a GEECS DB change: rerun the two tools (extract needs the
  lab network), then rebuild the project. Don't hand-edit the JSON.

**Channel limits are generated too** (`scripts/generate_channel_limits.py`,
same extract as the channel database): one entry per settable `:SP` PV with
min/max mirroring the GEECS DB limits (2,702 writable setpoints, plus the
gateway restart PV); everything else — readbacks and unlisted channels — is
refused. Limits checking is enabled in the profile. The layered write
safety is: OSPREY software limits (client pre-flight) → gateway EPICS
control limits on `:SP` (CA-layer rejection) → GEECS device-side limits and
hardware interlocks (final authority) → per-write human approval prompt
throughout. Refresh limits together with the channel database when the
GEECS DB changes.

## Left at preset defaults

Everything else — the operator skills and agents (channel finder, data
visualizer, diagnosis workflow, logbook search), safety rules, approval
hooks, output style, service ports, and the dispatch trigger set — comes
straight from the `control-assistant` preset and was not customized. The
deploy auto-generates the dispatcher bearer tokens
(`EVENT_DISPATCHER_TOKEN`, `DISPATCH_WORKER_TOKEN`) into `.env` on first
`osprey up`.

## Layout and inheritance

```
build-profile/               # OSPREY deployment repo
  profile.yml                # the decisions above, as overrides on the preset
  rules/                     # facility rules (geecs-semantics.md)
  skills/                    # facility skills (drafting-geecs-scans, ...)
  project/data/              # generated channel database + limits (mirrored onto build/)
  scripts/                   # extract + generate pipeline, and the DB snapshot
  .env                       # API keys and CA env (durable, never rendered)
  var/                       # durable runtime state (never wiped)
  build/                     # derived output — wiped and re-rendered every build
```

- **Preset** (`control-assistant`): bundled upstream, edited by PR'ing OSPREY.
- **This repo**: the facility's source of truth.
- **`build/`**: derived, regenerable — never edit it in place.

## Known workaround carried in `.env` (recreate on every new clone)

`.env` is untracked (secrets zone), so a fresh clone must recreate it:
API keys (`CBORG_API_KEY`), `EPICS_CA_ADDR_LIST=192.168.6.14`, **and**
`CONFIG_FILE=<absolute-path-to-this-repo>/build/config.yml`. The last one
works around a framework bug — hooks launch without `CONFIG_FILE` and the
limits hook then denies every write as "channel not in limits database."
Tracked upstream as als-apg/osprey#636 — remove when fixed.

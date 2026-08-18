# HTU Assistant — build profile

This directory is the source of truth for the **HTU Assistant**, an OSPREY
agent for the HTU laser system at LBNL. It was created by the OSPREY build
interview on 2026-07-23. Edit the files here (never a rendered project) and
rebuild whenever something changes.

## Build it

```bash
osprey build htu-assistant build-profile/profile.yml
```

## What was decided in the interview

- **System**: the HTU laser system at LBNL.
- **Services**: the full `control-assistant` stack minus the virtual
  accelerator — PostgreSQL + ARIEL search, OpenObserve telemetry, the event
  dispatcher/worker pair, the Bluesky bridge + Tiled catalog with its web
  panels (PLAN/RESULTS/HEALTH), and the multi-user web-terminal tier. The
  virtual-accelerator simulator is dropped (`virtual_accelerator: null` in
  `profile.yml`): HTU is a laser on live EPICS, and the sim would squat CA
  port 5064. `osprey deploy up` stands the services up after building.
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
  before it reaches the machine. Per the interview, hard safety enforcement
  lives at the hardware level; the software limits shipped here are therefore
  permissive placeholders, not engineering limits.
- **AI service**: LBNL's CBorg gateway, using CBorg's default model
  (`anthropic/claude-haiku`). Set `CBORG_API_KEY` in the project's `.env`
  before first run (the build writes an `.env.template` listing it).
- **Historical data**: not needed for now — no archiver is configured. To add
  one later, wire an archiver under the `config:` section of `profile.yml`
  (OSPREY ships EPICS Archiver Appliance and MongoDB connectors).

## The channel database is real (generated from the GEECS DB)

`overlays/data/channel_databases/hierarchical.json` is **generated, not
hand-written**: `tools/extract_geecs.py` pulls the Undulator experiment from
the GEECS MySQL DB using GeecsCAGateway's own config builder (so names,
units, limits, and settability match exactly what the gateway serves), and
`tools/generate_hierarchical.py` renders the tree. 113 devices, 5,799
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

**Channel limits are generated too** (`tools/generate_channel_limits.py`,
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
`osprey deploy up`.

## Layout and inheritance

```
build-profile/
  profile.yml          # the decisions above, as overrides on the preset
  overlays/
    data/              # placeholder channel database + limits (replace!)
    rules/ skills/ agents/   # drop-in facility customizations (empty)
  README.md            # this file
```

- **Preset** (`control-assistant`): bundled upstream, edited by PR'ing OSPREY.
- **Profile** (this directory): your facility's source of truth.
- **Project** (output of `osprey build`): derived, regenerable — never edit it in place.

## Next steps

After building, install the deploy skill and follow it to get the assistant
running with its dependencies and credentials:

```bash
osprey skills install osprey-build-deploy
```

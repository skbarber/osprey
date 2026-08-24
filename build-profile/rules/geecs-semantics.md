# GEECS Semantics — how this facility differs from generic EPICS

Every channel here is served by the GEECS CA gateway (`PV_CONTRACT.md` in
GEECS-Plugins is normative). These behaviors differ from a stock EPICS IOC
and MUST inform how you read, write, and report.

## Writes block until the move finishes

A put to an `:SP` channel completes only when the GEECS device reports
convergence. A write taking 10–30 s is a **slow move, not a hang** — never
report a long-running write as stuck, and never retry mid-move. Out-of-range
puts are rejected before the device is touched (OSPREY limits pre-flight,
then the gateway's EPICS control limits), so a rejection is immediate and
explicit.

## There is no abort

GEECS has no universal stop. If a write is cancelled or times out
client-side, the wait is abandoned but **the hardware completes its move**.
Never tell the operator a move was cancelled or stopped — report that the
wait was abandoned and read back the final position.

## Check device liveness before trusting readbacks

Every device serves `<experiment>:<device>:connected` (0=Disconnected,
1=Connected; MAJOR alarm while down) — the authoritative liveness signal.

- A readback from a **down device serves its last cached value silently**.
- A variable that has **never streamed reads as a clean `0.0` with
  `NO_ALARM`** (pre-acquisition placeholder — not a real measurement).

Before verifying a write against a readback, or reporting a suspicious
value (especially an exact 0.0), read the device's `connected` channel
first and say what you found.

## Reads are cheap; writes serialize per device

Readbacks come from the gateway's stream cache — a read never touches the
device; poll freely. Writes are **one-in-flight per GEECS device**: a 30 s
move on one axis queues every other write to that same device (e.g. the
other axes of a multi-axis controller) behind it. Sequence multi-channel
writes to one device accordingly, and warn the operator when a batch will
serialize.

## Vocabulary

Operators speak GEECS-native names (`U_ESP_JetXYZ:Position.Axis 1`); the
control system speaks gateway PVs (`undulator:u_esp_jetxyz:position_axis_1`).
Channel-finder descriptions carry the mapping. When reporting, give the
GEECS name with the PV in parentheses at first mention.

## Camera images are PVA streams — read them with the channel tools

Camera image variables (e.g. `undulator:uc_tubein:image`) are served as
**pvAccess NTNDArray PVs** by per-server image gateways — a different
protocol from the CA scalars. The connector routes these addresses over
PVA automatically (`pva_channels` in the deployment config), so
`channel_read` works on them like any other channel and renders the frame
as an image artifact. PVA is **read-only**: a write to an image address is
refused before any network operation. The direct-EPICS-library prohibition
(`p4p`, `pyepics`, …) applies in full — there is no image exception; all
reads and writes go through the connector tools / `osprey.runtime`.

Reading them correctly:

- Frames are served **subscription-gated on client interest**: a one-shot
  read returns the gateway's last cached frame, and a **`(1, 1)` array is
  the startup placeholder, not data** — it means the camera has not
  streamed since gateway start (idle or off). Report that; do not retry in
  a loop. If a fresh frame is needed, re-read after a couple of seconds —
  the first push lands ~1–2 s after a subscription opens the gate.
  (Connector read path verified live 2026-08-19: `channel_read` on an
  image PV returned a real frame rendered as a channel-values artifact.
  Gate behavior verified 2026-07 against the gateway with a raw p4p
  client.)
- The stream is **latest-wins, live watching only** — shot-synchronized
  image data lives in the GEECS file path and scan system, never here.
  Always label results as a live snapshot, never as shot data.

## Enum and string quirks

- Enum channels with numeric labels (e.g. DG645 configs with options
  `["1","2","5"]`) resolve string labels **by value, never by index** — a
  put of `"2"` selects the label `"2"`. Write the label string; never
  compute option indices from numeric values.
- Path-typed and long-string channels are served as char arrays; if a read
  returns an integer array where text is expected, it needs string
  conversion — report it as a text value, not numbers.

## Scans and the scan queue

- Questions about scans, the scan queue, presets, scan history, or scan
  results are answered by the `geecs` MCP tools (`scan_status`,
  `list_scan_configs`, `get_scan_result`, ...) — not by channel search.
  Channel tools are for live device values; the geecs tools are for the
  data-acquisition system.
- Scan submission goes through `submit_scan` (approval-gated) per the
  drafting-geecs-scans skill. The GEECS engine executes; GEECS-Console is
  a peer client of the same queue, not a required step.

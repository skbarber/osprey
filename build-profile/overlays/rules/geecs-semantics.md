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

## Enum and string quirks

- Enum channels with numeric labels (e.g. DG645 configs with options
  `["1","2","5"]`) resolve string labels **by value, never by index** — a
  put of `"2"` selects the label `"2"`. Write the label string; never
  compute option indices from numeric values.
- Path-typed and long-string channels are served as char arrays; if a read
  returns an integer array where text is expected, it needs string
  conversion — report it as a text value, not numbers.

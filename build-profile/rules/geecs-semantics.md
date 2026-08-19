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

## Camera images are PVA streams — NOT readable via channel tools

Camera image variables (e.g. `undulator:uc_tubein:image`) are served as
**pvAccess NTNDArray PVs** by per-server image gateways — a different
protocol from the CA scalars. The channel tools (`channel_read` etc.) speak
CA only: attempting to read an image PV will time out, and that timeout
means "wrong protocol," never "camera down."

### Sanctioned image access: read-only p4p in python execution

**Facility exception to the direct-EPICS-library prohibition** (which
otherwise stands in full; interim until OSPREY gains native PVA support —
tracked as als-apg/osprey#637): for **image PVs only**, you MAY use `p4p`
in python execution, **read-only** — a `Context("pva")` with
`monitor`/`get` and never a `put`. Rationale: the prohibition protects the write path
(limits, approval, audit); a read-only image monitor has no write path.
All scalar reads and ALL writes stay on the connector tools / `osprey.runtime`.

The correct idiom is a **held monitor**, because subscriptions are gated on
client interest — a bare `get` returns a cached or placeholder frame
(a `(1, 1)` array is the startup placeholder, not data), and the first
fresh frame lands ~1–2 s after subscribing:

```python
import time
from p4p.client.thread import Context

frames = []
ctx = Context("pva")
sub = ctx.monitor("undulator:uc_tubein:image", frames.append)
time.sleep(3)          # hold the gate open past one push interval
sub.close(); ctx.close()
img = frames[-1]       # newest frame; verify img.shape != (1, 1)
```

Then analyze/display normally (`numpy` stats, `save_artifact` for the
gallery). Rules of the road:

- Close every monitor/context — a leaked subscription keeps the camera
  gate open for nothing.
- The stream is **latest-wins, live watching only** — shot-synchronized
  image data lives in the GEECS file path and scan system, never here.
  Always label results as a live snapshot, never as shot data.
- If no frame beyond the placeholder arrives, the camera is idle or off —
  report that; do not retry in a loop.

## Enum and string quirks

- Enum channels with numeric labels (e.g. DG645 configs with options
  `["1","2","5"]`) resolve string labels **by value, never by index** — a
  put of `"2"` selects the label `"2"`. Write the label string; never
  compute option indices from numeric values.
- Path-typed and long-string channels are served as char arrays; if a read
  returns an integer array where text is expected, it needs string
  conversion — report it as a text value, not numbers.

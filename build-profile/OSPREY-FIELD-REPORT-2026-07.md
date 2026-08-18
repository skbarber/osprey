# OSPREY field report — BELLA HTU deployment (2026-07)

Findings from deploying OSPREY against a production laser-plasma facility
(BELLA HTU at LBNL). Facility context, kept to one paragraph: our control
system (GEECS) is fronted by a Channel Access gateway, so OSPREY runs the
**stock `epics_connector` with zero facility-specific code** — which
worked, and is the strongest validation of the connector architecture we
can offer. The full served set (113 devices, ~5,800 channels) runs through
the hierarchical channel finder; writes go through the generated limits
database with approval. The findings below are facility-agnostic — each
would behave identically at any EPICS site.

They share one theme: **contracts that agentic consumers depend on need to
be load-bearing in the tool layer, not aspirational in the prompt layer.**
A GUI shows a human the red border; an LLM narrates around whatever the
tool result doesn't say — plausibly and confidently.

---

## 1. Tool-path selection is unranked

Two sanctioned paths exist for a channel write: the controls MCP tools
(`channel_write`) and python execution via `osprey.runtime`. The shipped
prompts delegate channel *finding* and mandate `osprey.runtime` *within*
Python, but nothing ranks the two paths for a plain read/write. Observed:
the same one-line operator request ("set X to 100 amps")
nondeterministically chose python-execute after ~10 prior runs choosing
the controls tools — and thereby hit finding #2.

Suggestion: shipped rules (or the tool descriptions themselves) should
state when each path applies — e.g. "single reads/writes: controls tools;
python execution: analysis over retrieved data / multi-step computation."
Facility profiles shouldn't each rediscover and patch this.

## 2. A configured-but-absent python executor goes undetected until an agent trips on it

The `control-assistant` preset pins `execution.execution_method:
container` (for Bluesky launch-token arming). A profile that removes the
Bluesky stack — supported via `bluesky: null` — silently inherits
container execution with no container stack to execute in. Nothing
validates executor availability at build, deploy, or session start; the
configuration is simply wrong until the first `execute` call fails.

Downstream symptom, worth a note: the resulting socket error surfaced to
the agent without identifying *which* connection failed, and the agent
reported "the control system is unavailable — check the gateway" to the
operator. The control system was fine. Infrastructure-layer failures
(executor backend, MCP transport) should be labeled as such in tool
results so an agent can classify them — but the primary fix is upstream:
don't let a session start against an execution backend that isn't there
(or decouple the container default from the Bluesky stack it exists for).

## 3. Readback verification discards the alarm state it already holds

`epics_connector.write_channel` readback verification compares values
numerically and returns `success=True, verified=False` with a "readback
mismatch" note. The readback's alarm status/severity — already fetched
into `ChannelMetadata` by `read_channel` — is not consulted or reported.
Observed consequence: a device-rejected write (readback PV in
`INVALID/WRITE_ALARM`) was reported by the agent as "setpoint written,
supply may still be ramping" — fabricated physics, because the one field
that explained the mismatch never reached it.

This is generic EPICS, not facility-specific: records clamping at
DRVH/DRVL, disabled records, and devices in local mode all produce "put
accepted, readback wrong, alarm raised."

Suggestions (independent):
- On failed readback verification, include the readback's alarm
  status/severity (as names, not pyepics numeric codes) in the result.
- Distinguish result states: converged / mismatch-with-alarm (arguably
  `success=False`) / mismatch-without-alarm.
- Revisit `success=True` when the readback *read itself* fails.

## 4. Read-after-write is aspirational

The shipped safety rules instruct "always read back after writing," but
nothing enforces it; observed sessions report "IOC callback confirmed"
without stating the resulting value. Where verification level is
`callback`, the tool result contains no readback for the agent to report
even if it wanted to.

Suggestion: either default setpoint-style writes to readback-level
verification, or include a post-write readback value in the write result
regardless of verification level. Enforcement in the tool beats
instruction in the prompt.

---

## What worked (for calibration)

The gateway-fronted facility ran on a stock profile with zero framework
changes: `extends` + `exclude` + config overrides + overlays absorbed a
heavy customization (Bluesky stack removed, custom skills/rules/data
injected); the hierarchical finder handled the full 5,800-channel set; and
the generated limits database, connector pre-flight, and approval flow
produced exactly the right operator-facing refusal on an out-of-range
write, with the correct range quoted. The findings above are offered in
the spirit of: the architecture holds; the seams need tightening for LLM
consumers specifically.

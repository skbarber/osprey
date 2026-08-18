"""Generate the OSPREY hierarchical channel database for the HTU assistant.

Input:  undulator_extract.json — the GEECS DB snapshot produced by
        extract_geecs.py (which drives GeecsCAGateway's own config builder, so
        names/units/limits/settability match exactly what the gateway serves).
Output: ../overlays/data/channel_databases/hierarchical.json

Tree shape (grouping chosen in the build interview, 2026-07-23):

    experiment (undulator) -> GEECS device type -> device -> variable [-> SP]

The devicetype level is navigation-only (absent from naming_pattern); channel
names follow the gateway PV contract: ``undulator:<device>:<variable>[:SP]``
with every component normalized per GeecsCAGateway/geecs_ca_gateway/pv_naming.py.

Branch descriptions come from three sources, in order of authority:
  1. Facts confirmed in the build interview (see DEVICE_DESC / notes below).
  2. Instrument-class facts from the GEECS devicetype.
  3. Cautious name-derived inference, phrased as such.
Variable descriptions are rule-based from the GEECS metadata (units, limits,
settability) plus standard LabVIEW/GEECS variable-name conventions.

Rerun after refreshing the snapshot:
    python extract_geecs.py Undulator   # needs lab network (GEECS DB)
    python generate_hierarchical.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).parent
EXTRACT = HERE / "undulator_extract.json"
OUT = HERE.parent / "overlays" / "data" / "channel_databases" / "hierarchical.json"

# --- PV-name normalization -------------------------------------------------
# MUST match GeecsCAGateway geecs_ca_gateway/pv_naming.py exactly (the naming
# contract): runs of non-[A-Za-z0-9_] -> "_", strip "_", lowercase.
_INVALID = re.compile(r"[^A-Za-z0-9_]+")


def norm(name: str) -> str:
    return _INVALID.sub("_", name.strip()).strip("_").lower()


# --- Curated descriptions ---------------------------------------------------
# HTU context (confirmed in interview): the Hundred Terawatt Undulator (HTU)
# beamline at BELLA, LBNL. BCave is a radiation bunker holding the high-power
# laser, the LPA (laser-plasma accelerator) target, and diagnostics; ACave is
# the connected bunker holding the VISA undulator; ALine is the electron
# transport line from the EMQ triplet to the undulator. The chicane is a
# bunch decompressor for FEL operation. Building 148 is the primary laser bay.

ROOT_DESC = (
    "HTU (Hundred Terawatt Undulator) beamline at BELLA, LBNL. A laser-plasma "
    "accelerator (LPA) driven by the high-power laser in BCave produces "
    "electron beams that are transported along the ALine (from the EMQ "
    "triplet) into the VISA undulator in ACave for FEL studies. Channels are "
    "served over EPICS as undulator:<device>:<variable>[:SP] by the GEECS CA "
    "gateway."
)

# Device-type branch descriptions: instrument class + role at HTU.
DEVTYPE_DESC = {
    "AerotechStage": "Aerotech precision motion stage controller. At HTU: U_CompAerotech, the laser compressor stage.",
    "AgilisPiezoStage": "Newport Agilis piezo motor controller. At HTU: the chicane motor axes.",
    "CaenELSEasyDriver": "CAEN ELS Easy-Driver bipolar corrector power supplies. Power the steering corrector magnets: S1-S4 H/V on the ALine transport, VS1-VS5 H/V along the VISA undulator.",
    "CaenELSFastPS": "CAEN ELS FAST-PS power supplies. Power the chicane dipoles (inner/outer families) and the ACave magnetic-spectrometer magnet.",
    "DG535": "Stanford Research DG535 digital delay generator (machine timing).",
    "DG645": "Stanford Research DG645 digital delay generators — shot control and trigger timing.",
    "DaqPad_NI6009": "National Instruments USB-6009 multifunction DAQ pads: analog/digital I/O behind the vacuum gauges, gas-jet backing pressure, ALine filter inserters, and VISA plungers.",
    "ESP301": "Newport ESP301 3-axis motion controller.",
    "ESP302": "Newport ESP302 3-axis motion controller.",
    "FROG": "Frequency-resolved optical gating (Grenouille) pulse-length/phase diagnostic for the drive laser.",
    "FilterWheels": "Motorized filter wheels (ND/bandpass) on the laser diagnostic beam paths.",
    "GaiaSVEReader": "Status/parameter reader for the Thales Gaia pump laser.",
    "HASO4_3": "Imagine Optic HASO4 wavefront sensor.",
    "HallProbeLS455": "Lake Shore 455 gaussmeter Hall probes monitoring spectrometer dipole fields in ACave and BCave.",
    "HamamatsuSpectrometerDAQ": "Hamamatsu spectrometer DAQ.",
    "HexapodPI": "Physik Instrumente hexapod (6-DOF positioner).",
    "Highland T564 DDG": "Highland Technology T564 digital delay generator (machine timing).",
    "MagSpecCamera": "Cameras imaging the BCave magnetic-spectrometer screens — segments of the dispersed electron energy spectrum.",
    "MagSpecStitcher": "Software device that stitches the BCave MagSpec camera images into a single electron energy spectrum.",
    "PI_StageE727": "Physik Instrumente E-727 piezo controller. At HTU: final steering mirror piezo.",
    "Picomotor8742dotNet": "New Focus 8742 picomotor controller. At HTU: pilot-beam (blue diode) alignment actuators, usually not in use.",
    "PicoscopeV2": "Pico Technology USB oscilloscopes digitizing the integrating-current-transformer (ICT) charge signals.",
    "Point Grey Camera": "FLIR/Point Grey machine-vision cameras: e-beam profile screens and laser-diagnostic views. Standard GEECS camera controls (exposure, gain, ROI analysis, background, saving).",
    "Productivity1000PLC": "AutomationDirect Productivity 1000 PLCs — facility digital/analog I/O and interlocks.",
    "SMC100": "Newport SMC100 single-axis motion controller.",
    "TDK-Lambda Z": "TDK-Lambda Z+ programmable power supply. At HTU: BCave magnetic-spectrometer magnet supply.",
    "TDK-Lambda Z Bipolar": "TDK-Lambda Z+ supplies with bipolar output stage. At HTU: the EMQ (electromagnet quadrupole) triplet that focuses the LPA beam into the transport line.",
    "TRAServer_VISA": "Generic multi-axis motor racks exposed through a VISA-protocol translation server (assorted stages, no single subsystem).",
    "Thorlabs CCS175 Spectrometer": "Thorlabs CCS175 compact spectrometer in the Building 148 laser bay.",
    "ThorlabsWFS": "Thorlabs wavefront sensor on the Ghost leakage beam.",
    "VelmexStage": "Velmex stepper-motor stage.",
    "ZaberASeries": "Zaber A-series motorized stages.",
}

# Confirmed or curated per-device descriptions. Pattern-matched families
# (steering correctors, VISA e-beam cams, MagSpec cams) are handled in code.
DEVICE_DESC = {
    "U_CompAerotech": "Laser compressor Aerotech stage (grating separation).",
    "U_ChicaneMotors": "Chicane piezo motor axes (magnet/slit positioning).",
    "U_ChicaneInner": "Chicane inner-dipole pair power supply. The chicane decompresses the LPA bunch for FEL operation.",
    "U_ChicaneOuter": "Chicane outer-dipole pair power supply. The chicane decompresses the LPA bunch for FEL operation.",
    "UC_ChicaneSlit": "Camera viewing the chicane slit plane (dispersed beam / energy selection view).",
    "U_ACaveMagSpecPS": "ACave magnetic-spectrometer dipole power supply.",
    "U_BCaveMagSpecPS": "BCave magnetic-spectrometer dipole power supply.",
    "U_ACaveHallProbe": "Hall probe in the ACave spectrometer dipole (Lake Shore 455).",
    "U_BCaveHallProbe": "Hall probe in the BCave spectrometer dipole (Lake Shore 455).",
    "U_BCaveMagSpec": "Stitcher combining the three BCave MagSpec cameras into one electron energy spectrum.",
    "UC_HiResMagCam": "High-resolution electron-spectrometer camera.",
    "U_EMQTripletBipolar": "EMQ triplet power supply (bipolar, per-channel): the electromagnet quadrupole triplet focusing the LPA electron beam into the ALine.",
    "U_ESP_JetXYZ": "Gas-jet target XYZ positioning stages (LPA target in BCave).",
    "U_HP_Daq": "High-pressure controller for the gas-jet target (backing-gas pressure control and readback).",
    "U_VisaPlungers": "Insertable plunger diagnostics along the VISA undulator.",
    "U_VacuumGauge": "Vacuum gauge readouts (NI DAQ analog inputs) for the beamline vacuum.",
    "U_Aline3Filter": "ALine station-3 filter/actuator I/O (NI DAQ).",
    "U_DG645_ShotControl": "Main shot-control delay generator: per-channel trigger delays and amplitudes for machine timing.",
    "U_1HzShiftedBox": "1 Hz shifted timing box (DG535) — shifted-trigger generation.",
    "U_MRC_TimingBox": "MRC timing box (deprecated — largely unused).",
    "U_Highland": "Highland T564 delay generator (machine timing).",
    "U_TRAServer01": "Multi-axis motor rack 01 (generic stage axes via VISA server).",
    "U_TRAServer03": "Multi-axis motor rack 03 (generic stage axes via VISA server).",
    "U_BCaveICT": "BCave integrating current transformer (ICT) charge monitor, digitized by Picoscope.",
    "U_UndulatorExitICT": "ICT charge monitor at the undulator exit, digitized by Picoscope.",
    "U_PLC": "Main facility PLC (digital/analog I/O, interlocks).",
    "U_148_PLC": "PLC in Building 148, the primary laser bay.",
    "U_148Spectrometer": "Thorlabs CCS175 spectrometer in the Building 148 laser bay.",
    "U_GaiaSVEReader": "Thales Gaia pump-laser status reader.",
    "UC_GaiaMode": "Camera viewing the Gaia pump-laser mode.",
    "U_GhostWFS": "Wavefront sensor on the Ghost leakage beam (low-power replica of the main drive laser).",
    "UC_GhostFocus": "Camera viewing the Ghost leakage-beam focus.",
    "UC_GhostUpstream": "Camera viewing the Ghost leakage beam upstream.",
    "U_GhostFilters": "Filter wheel on the Ghost leakage-beam diagnostic path.",
    "U_LowPowerGhostWFSFilter": "Filter wheel ahead of the Ghost wavefront sensor (low-power path).",
    "U_ProbeFilters": "Filter wheel on the probe-beam diagnostic path.",
    "U_ProbeCamStage": "Probe-camera positioning stage (SMC100).",
    "U_HASO_Filters": "Filter wheel ahead of the HASO wavefront sensor.",
    "U_HasoLift": "HASO wavefront sensor (lift station).",
    "U_MI_CoarseFilters": "Mode-imager coarse filter wheel.",
    "U_MI_FineFilters": "Mode-imager fine filter wheel.",
    "UC_ModeImager": "Mode-imager camera (laser mode at selected image planes).",
    "U_ModeImagerESP": "Mode-imager positioning stages (Newport ESP).",
    "U_BlueDiodePicos": "Picomotor actuators aligning the blue-diode pilot beam (not the main laser); usually not in use.",
    "UC_TC_Output": "Camera used for laser alignment at the target-chamber output.",
    "U_FROG_Grenouille": "Grenouille (FROG) pulse-duration/phase diagnostic for the drive laser.",
    "U_Hexapod": "PI hexapod 6-DOF positioner.",
    "U_PIFinalSteering": "Final steering mirror piezo (PI E-727).",
    "UC_FinalSteeringLeak": "Camera on the final-steering mirror leakage.",
    "UC_DMSurface": "Camera viewing the deformable-mirror surface.",
    "U_UndulatorSpecStage": "Undulator spectrometer positioning stage (Zaber).",
    "UC_UndulatorImagingSpec": "Undulator imaging-spectrometer camera (undulator radiation).",
    "UC_UndulatorRad2": "Undulator radiation camera 2.",
    "UC_DiagnosticsPhosphor": "Camera on a phosphor diagnostics screen (name-derived).",
    "UC_Phosphor1": "Camera on phosphor screen 1 (name-derived).",
    "UC_BCaveIn": "Camera at the BCave entrance region (name-derived).",
    "UC_TopView": "Top-view camera of the target area (name-derived).",
    "UC_TubeIn": "Camera at a tube/transport entrance (name-derived).",
    "UC_TargetIn": "Camera viewing the target entrance region (name-derived).",
    "U_Velmex": "Velmex stepper stage.",
    "U_Zaber": "Zaber stage axes.",
    "U_TCAlignStages": "Target-chamber alignment stages (Zaber).",
    "U_Amp4TelStage": "Amplifier-4 telescope stage (Zaber).",
    "U_StretchterXMCC": "Stretcher X-axis stage (Zaber).",
    "U_ESP302_01": "Newport ESP302 motion controller 01 (assorted axes).",
    "U_ESP302_02": "Newport ESP302 motion controller 02 (assorted axes).",
    "U_GratingMode": None,  # covered by camera fallback with name-derived subject
}

# Laser-chain cameras: name-derived, uniform phrasing.
_AMP_CAM = re.compile(r"^UC_Amp(\d)(Depletion_South|_IR_input|_IR_output)$")
_AMP_SUBJECT = {
    "Depletion_South": "pump depletion (south side) of amplifier {n}",
    "_IR_input": "the IR input of amplifier {n}",
    "_IR_output": "the IR output of amplifier {n}",
}

# --- Variable description rules ---------------------------------------------

_EXACT_VARS = {
    "exposure": "Camera exposure time",
    "gain": "Camera gain",
    "Analysis": "Enable on-camera image analysis",
    "AnalysisROI": "Enable analysis region of interest",
    "AnalysisROITop": "Analysis ROI top edge (pixels)",
    "AnalysisROIBottom": "Analysis ROI bottom edge (pixels)",
    "AnalysisROILeft": "Analysis ROI left edge (pixels)",
    "AnalysisROIRight": "Analysis ROI right edge (pixels)",
    "AnalysisThreshold": "Analysis pixel threshold",
    "BackgroundPath": "Path to the background image used by analysis",
    "CompressionQuality": "Saved-image compression quality",
    "localsavingpath": "Local path where the device saves per-shot data",
    "LocalSavingPath": "Local path where the device saves per-shot data",
    "save": "Enable per-shot data saving",
    "Save": "Enable per-shot data saving",
    "Lineout": "Enable lineout extraction",
    "AutoTrigger": "Enable software auto-trigger",
    "Current": "Output current",
    "Voltage": "Output voltage (readback)",
    "Enable_Output": "Output enable",
    "Reset": "Fault reset",
    "fire": "Software fire/trigger",
    "Inhibit": "Trigger inhibit",
    "EnableTrigger": "Enable scope trigger",
    "TriggerThreshold": "Scope trigger threshold",
    "PreTriggerSamples": "Samples recorded before the trigger",
    "PostTriggerSamples": "Samples recorded after the trigger",
    "GUInumPoints": "Number of displayed points",
    "PythonAnalysis": "Enable Python analysis",
    "timestamp": "Device timestamp of the last update",
    "systimestamp": "System (LabVIEW) timestamp of the last update",
    "acq_timestamp": "Hardware acquisition timestamp of the last shot",
    "stepsize": "Motion step size",
    "automotoroff": "Automatically disable motors after moves",
    "ResetBeforeMove": "Reset controller before each move",
}

_VAR_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^Position\.Axis (\d+)$"), "Stage position, axis {0}"),
    (re.compile(r"^Home\.Axis (\d+)$"), "Home command, axis {0}"),
    (re.compile(r"^Enable\.Axis (\d+)$"), "Motor enable, axis {0}"),
    (re.compile(r"^Disable\.Axis (\d+)$"), "Motor disable, axis {0}"),
    (re.compile(r"^backlash\.Axis (\d+)$"), "Backlash compensation, axis {0}"),
    (re.compile(r"^MoveToHardLimit\.Axis (\d+)$"), "Move to hard limit, axis {0}"),
    (re.compile(r"^Delay\.Ch (\w+)$"), "Trigger delay, channel {0}"),
    (re.compile(r"^Amplitude\.Ch (\w+)$"), "Trigger output amplitude, channel {0}"),
    (re.compile(r"^Linked\.Ch (\w+)$"), "Channel {0} linked-delay setting"),
    (re.compile(r"^Current\.Ch(\d+)$"), "Output current, channel {0}"),
    (re.compile(r"^Current_Limit\.Ch(\d+)$"), "Current limit, channel {0}"),
    (re.compile(r"^Enable_Output\.Ch(\d+)$"), "Output enable, channel {0}"),
    (re.compile(r"^Degauss\.Ch(\d+)$"), "Degauss cycle, channel {0}"),
    (re.compile(r"^OVP\.Ch(\d+)$"), "Over-voltage protection setpoint, channel {0}"),
    (re.compile(r"^Power\.Ch(\d+)$"), "Output power, channel {0}"),
    (re.compile(r"^Continuous_trigger\.Ch(\d+)$"), "Continuous trigger enable, channel {0}"),
    (re.compile(r"^(?:DO|DigitalOutput)\.Ch(?:annel)? ?(\d+)$"), "Digital output, channel {0}"),
    (re.compile(r"^AI_mean\.Channel (\d+)$"), "Mean analog input reading, channel {0}"),
    (re.compile(r"^AnalogOutput\.Channel (\d+)$"), "Analog output, channel {0}"),
    (re.compile(r"^enable\.Channel (\d+)$"), "Channel {0} enable"),
    (re.compile(r"^Enable\.Ch([A-D])$"), "Scope channel {0} enable"),
    (re.compile(r"^Range\.Ch([A-D])$"), "Scope input range, channel {0}"),
    (re.compile(r"^Python Results\.Ch([A-D])$"), "Python analysis result, channel {0}"),
    (re.compile(r"^Crosshair\.(.+)$"), "Display crosshair: {0}"),
]


def var_desc(v: dict) -> str:
    name = v["geecs_var"]
    base = _EXACT_VARS.get(name)
    if base is None:
        for pat, tmpl in _VAR_PATTERNS:
            m = pat.match(name)
            if m:
                base = tmpl.format(*m.groups())
                break
    if base is None:
        base = f"GEECS variable '{name}'"
    extras = []
    if v.get("egu"):
        extras.append(v["egu"])
    lo, hi = v.get("lo"), v.get("hi")
    if lo is not None and hi is not None:
        extras.append(f"range {lo:g} to {hi:g}")
    if v.get("choices"):
        extras.append("options: " + ", ".join(v["choices"]))
    if extras:
        base += f" ({'; '.join(extras)})"
    if v.get("description"):  # the rare DB-provided .DESC wins as a prefix
        base = f"{v['description']} — {base}"
    return base


# --- Device description resolution ------------------------------------------

_STEER = re.compile(r"^U_(V?)S(\d)([HV])$")
_VISA_CAM = re.compile(r"^UC_VisaEBeam(\d)$")
_MAGSPEC_CAM = re.compile(r"^UC_BCaveMagSpecCam(\d)$")
_ALINE_CAM = re.compile(r"^UC_ALineEBeam|^UC_ALineEbeam")


def device_desc(name: str, devtype: str) -> str:
    if name in DEVICE_DESC and DEVICE_DESC[name]:
        return DEVICE_DESC[name]
    m = _STEER.match(name)
    if m:
        visa, n, plane = m.groups()
        line = "VISA undulator" if visa else "ALine transport"
        pl = "horizontal" if plane == "H" else "vertical"
        return f"{line} steering corrector {n}, {pl} plane (CAEN Easy-Driver supply)."
    m = _VISA_CAM.match(name)
    if m:
        return f"E-beam profile camera at VISA undulator section {m.group(1)}."
    m = _MAGSPEC_CAM.match(name)
    if m:
        return f"BCave magnetic-spectrometer screen camera {m.group(1)} (one segment of the dispersed energy spectrum)."
    if _ALINE_CAM.match(name):
        n = name[-1]
        return f"E-beam profile camera {n} on the ALine transport line."
    m = _AMP_CAM.match(name)
    if m:
        subject = _AMP_SUBJECT[m.group(2)].format(n=m.group(1))
        return f"Camera viewing {subject} (drive-laser chain)."
    # Honest name-derived fallback: instrument class + the GEECS name.
    subject = name[3:] if name.startswith("UC_") else name[2:]
    if devtype == "Point Grey Camera":
        return f"Camera '{subject}' (subject inferred from name — laser/beam view named {subject})."
    return f"{devtype} device '{subject}'."


# --- Build the tree ----------------------------------------------------------

data = json.loads(EXTRACT.read_text())
experiment = data["experiment"]

# Tree keys ARE the normalized PV components (gateway naming contract). The
# runtime finder builds channel names from the *selected keys* (not
# _channel_part), so keys must already be CA-safe; the original GEECS names
# live in the descriptions for semantic search.
tree_devtypes: dict = {}
for dev in sorted(data["devices"], key=lambda d: (d["devicetype"], d["device"])):
    dt = dev["devicetype"]
    dt_node = tree_devtypes.setdefault(
        dt,
        {"_description": DEVTYPE_DESC.get(dt, f"GEECS device type '{dt}'.")},
    )
    dev_key = norm(dev["pv_prefix"])
    dev_node: dict = {
        "_description": f"{dev['device']} — {device_desc(dev['device'], dt)}",
    }
    for v in dev["variables"]:
        v_key = norm(v["geecs_var"])
        desc = var_desc(v)
        if v_key != v["geecs_var"]:
            desc = f"GEECS name '{v['geecs_var']}'. {desc}"
        v_node: dict = {"_description": desc}
        if v["settable"]:
            v_node["_is_leaf"] = True
            v_node["SP"] = {
                "_description": f"Setpoint (write) PV for {v['geecs_var']} — CA puts are forwarded to the device.",
            }
        if v_key in dev_node:
            raise SystemExit(
                f"normalized-name collision in {dev['device']}: {v['geecs_var']} -> {v_key}"
            )
        dev_node[v_key] = v_node
    # Per-device gateway status PV (always served by the CA gateway).
    dev_node["connected"] = {
        "_description": "Gateway TCP-subscription status for this device (enum: Disconnected/Connected; MAJOR alarm while down).",
    }
    if dev_key in dt_node:
        raise SystemExit(f"normalized device-name collision: {dev['device']} -> {dev_key}")
    dt_node[dev_key] = dev_node

# Gateway self-diagnostics (PV_CONTRACT.md §"reserved CAGateway namespace").
# Not in the GEECS DB — served unconditionally by the gateway itself. These
# are the liveness signals the system-health panel should watch.
tree_devtypes["CAGateway"] = {
    "_description": (
        "GeecsCAGateway self-diagnostics (devIocStats-style, updated every "
        "5 s). heartbeat/devices_connected are the liveness signals to watch: "
        "if heartbeat stops ticking the gateway is down and every other "
        "channel here is stale."
    ),
    "cagateway": {
        "_description": "The CA gateway service itself (reserved device namespace).",
        "heartbeat": {
            "_description": "Gateway heartbeat — ticks every 5 s while the gateway is alive. Primary liveness signal.",
        },
        "devices_connected": {
            "_description": "Number of GEECS devices with a live TCP subscription. Compare against the expected device count to spot dropouts.",
        },
        "uptime": {
            "_description": "Gateway uptime in seconds since last (re)start.",
        },
        "version": {
            "_description": "Installed GeecsCAGateway package version string.",
        },
        "restart": {
            "_description": (
                "The one client-writable gateway PV (enum: Idle/Restart; written "
                "directly, no :SP). Writing 'Restart' cleanly restarts the gateway "
                "and re-syncs the served set from the GEECS DB — expect a few "
                "seconds of CA disconnect. Only write on operator request."
            ),
        },
    },
}

doc = {
    "_comment": (
        "HTU / Undulator experiment channel database. Generated by "
        "build-profile/tools/generate_hierarchical.py from a GEECS DB snapshot "
        "extracted via GeecsCAGateway's own config builder; PV names follow "
        "the gateway naming contract (GeecsCAGateway/PV_CONTRACT.md). "
        "Branch descriptions were curated in the 2026-07-23 build interview. "
        "Do not hand-edit: rerun the generator."
    ),
    "hierarchy": {
        "levels": [
            {"name": "experiment", "type": "tree"},
            {"name": "devicetype", "type": "tree"},
            {"name": "device", "type": "tree"},
            {"name": "variable", "type": "tree"},
            {"name": "access", "type": "tree", "optional": True},
        ],
        "naming_pattern": "{experiment}:{device}:{variable}:{access}",
        "_description": (
            "Navigation: experiment -> GEECS device type -> device -> variable "
            "[-> SP]. The devicetype level is navigation-only; channel names "
            "are undulator:<device>:<variable> with an :SP suffix on settable "
            "variables."
        ),
    },
    "tree": {
        norm(experiment): {
            "_description": f"{experiment} experiment — {ROOT_DESC}",
            **tree_devtypes,
        }
    },
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(doc, indent=1))

n_dev = sum(len([k for k in v if not k.startswith("_")]) for v in tree_devtypes.values())
n_var = sum(
    len([k for k in dev if not k.startswith("_")])
    for dt in tree_devtypes.values()
    for name, dev in dt.items()
    if not name.startswith("_")
)
print(f"wrote {OUT}")
print(f"device types: {len(tree_devtypes)}  devices: {n_dev}  variable nodes: {n_var}")

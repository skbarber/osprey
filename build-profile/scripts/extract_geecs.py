"""Extract the Undulator experiment's served PV set via GeecsCAGateway code.

Uses the gateway's own config builder so names, dtypes, units, limits,
settability, and descriptions match exactly what the gateway serves.
Writes one JSON with everything OSPREY's channel-database needs.
"""

import json
import sys

from geecs_ca_gateway.config import GatewayConfig
from geecs_ca_gateway.db.geecs_db import GeecsDb

EXPERIMENT = sys.argv[1] if len(sys.argv) > 1 else "Undulator"

cfg = GatewayConfig.from_geecs_experiment(EXPERIMENT)

# Device types give us the natural grouping level for the hierarchy.
devtypes = {}
for dev in cfg.devices:
    try:
        devtypes[dev.name] = GeecsDb.get_device_type(dev.name)
    except Exception as exc:  # noqa: BLE001
        devtypes[dev.name] = f"<error: {exc}>"

# Image-typed variables are skipped by the CA config builder (not scalar CA
# data) but are now served as PVA NTNDArray PVs by GeecsPvaGateway — capture
# them separately so the channel database can list them.
from geecs_ca_gateway.config import effective_vartype
from geecs_ca_gateway.pv_naming import pv_name

image_map: dict[str, list[str]] = {}
var_map = GeecsDb.get_experiment_device_variables(EXPERIMENT)
for dev_name, rows in var_map.items():
    for meta in rows:
        if effective_vartype(meta.get("variabletype"), meta.get("choices")) == "image":
            image_map.setdefault(dev_name, []).append(meta["name"])

out = []
for dev in cfg.devices:
    out.append(
        {
            "device": dev.name,
            "devicetype": devtypes.get(dev.name),
            "pv_prefix": dev.pv_prefix,
            "image_variables": [
                {"geecs_var": v, "pv": pv_name(EXPERIMENT, dev.pv_prefix, v)}
                for v in sorted(set(image_map.get(dev.name, [])))
            ],
            "variables": [
                {
                    "geecs_var": v.geecs_var,
                    "pv": dev.pv_name_for(v),
                    "dtype": v.dtype,
                    "settable": v.settable,
                    "egu": v.egu,
                    "lo": v.lo,
                    "hi": v.hi,
                    "choices": v.choices,
                    "description": v.description,
                }
                for v in dev.variables
            ],
        }
    )

with open("undulator_extract.json", "w") as f:
    json.dump({"experiment": EXPERIMENT, "devices": out}, f, indent=1)

n_vars = sum(len(d["variables"]) for d in out)
n_desc = sum(1 for d in out for v in d["variables"] if v["description"])
print(f"devices: {len(out)}  variables: {n_vars}  with description: {n_desc}")
print("device types:", sorted({d['devicetype'] for d in out}))

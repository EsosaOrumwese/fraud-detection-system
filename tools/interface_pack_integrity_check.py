import json
from collections import Counter
from pathlib import Path

import yaml


def _tuple_list(value):
    if not value:
        return ()
    return tuple(value)


def main():
    root = Path("docs/model_spec/data-engine/interface_pack")
    harvest = json.loads((root / "_harvest/dataset_outputs.json").read_text(encoding="utf-8"))
    outputs = yaml.safe_load((root / "engine_outputs.catalogue.yaml").read_text(encoding="utf-8"))
    gates = yaml.safe_load((root / "engine_gates.map.yaml").read_text(encoding="utf-8"))

    harvest_keys = Counter()
    for item in harvest:
        hid = item.get("id")
        if not hid:
            continue
        dictionary_ref = f"{item.get('source')}#{hid}"
        key = (
            hid,
            dictionary_ref,
            item.get("path"),
            item.get("schema_ref"),
            _tuple_list(item.get("partitioning")),
        )
        harvest_keys[key] += 1

    output_keys = Counter()
    for item in (outputs.get("outputs") or []):
        if not isinstance(item, dict):
            continue
        oid = item.get("output_id")
        if not oid:
            continue
        key = (
            oid,
            item.get("dictionary_ref"),
            item.get("path_template"),
            item.get("schema_ref"),
            _tuple_list(item.get("partitions")),
        )
        output_keys[key] += 1

    missing = harvest_keys - output_keys
    extra = output_keys - harvest_keys

    # Gate integrity: each output requiring gates must be authorized by those gates.
    gate_outputs = {}
    for gate in (gates.get("gates") or []):
        if not isinstance(gate, dict):
            continue
        gate_outputs[gate.get("gate_id")] = set(gate.get("authorizes_outputs") or [])

    missing_gate_ids = []
    missing_authorizations = []
    for item in (outputs.get("outputs") or []):
        if not isinstance(item, dict):
            continue
        oid = item.get("output_id")
        if not oid:
            continue
        for gid in item.get("read_requires_gates") or []:
            if gid not in gate_outputs:
                missing_gate_ids.append((oid, gid))
            elif oid not in gate_outputs[gid]:
                missing_authorizations.append((oid, gid))

    print(f"Harvest entries: {sum(harvest_keys.values())}")
    print(f"Outputs entries: {sum(output_keys.values())}")
    print(f"Missing entries (harvest -> outputs): {sum(missing.values())}")
    print(f"Extra entries (outputs not in harvest): {sum(extra.values())}")
    print(f"Outputs missing gate IDs: {len(missing_gate_ids)}")
    print(f"Outputs missing gate authorizations: {len(missing_authorizations)}")

    if missing:
        print("\nMissing entries (harvest -> outputs):")
        for key, count in missing.most_common(20):
            print(f" - {count}x {key}")
        if len(missing) > 20:
            print(f" ... {len(missing) - 20} more")
    if extra:
        print("\nExtra entries (outputs not in harvest):")
        for key, count in extra.most_common(20):
            print(f" - {count}x {key}")
        if len(extra) > 20:
            print(f" ... {len(extra) - 20} more")
    if missing_gate_ids:
        print("\nMissing gate IDs:")
        for oid, gid in missing_gate_ids[:20]:
            print(f" - {oid}: gate_id={gid} not in gates map")
        if len(missing_gate_ids) > 20:
            print(f" ... {len(missing_gate_ids) - 20} more")
    if missing_authorizations:
        print("\nMissing authorizations in gate map:")
        for oid, gid in missing_authorizations[:20]:
            print(f" - {oid}: not in authorizes_outputs for {gid}")
        if len(missing_authorizations) > 20:
            print(f" ... {len(missing_authorizations) - 20} more")


if __name__ == "__main__":
    main()

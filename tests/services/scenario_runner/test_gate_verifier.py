import pathlib
import pytest

from fraud_detection.scenario_runner.evidence import GateMap, GateVerifier, GateStatus

RUN_ROOT = pathlib.Path(r"c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92")
MANIFEST = "c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8"

GATE_MAP = pathlib.Path(r"c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\model_spec\data-engine\interface_pack\engine_gates.map.yaml")


@pytest.mark.skipif(not RUN_ROOT.exists(), reason="local_full_run-5 not available")
def test_gate_verify_6b_pass() -> None:
    gate_map = GateMap(GATE_MAP)
    verifier = GateVerifier(RUN_ROOT, gate_map)
    result = verifier.verify("gate.layer3.6B.validation", {"manifest_fingerprint": MANIFEST})
    assert result.receipt is not None
    assert result.receipt.status == GateStatus.PASS


@pytest.mark.skipif(not RUN_ROOT.exists(), reason="local_full_run-5 not available")
def test_gate_verify_3a_pass() -> None:
    gate_map = GateMap(GATE_MAP)
    verifier = GateVerifier(RUN_ROOT, gate_map)
    result = verifier.verify("gate.layer1.3A.validation", {"manifest_fingerprint": MANIFEST})
    assert result.receipt is not None
    assert result.receipt.status == GateStatus.PASS

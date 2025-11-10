import json
from pathlib import Path

from engine.layers.l1.seg_2B.s7_audit import S7AuditRunner
from engine.layers.l1.seg_2B.s8_validation import S8ValidationInputs, S8ValidationRunner

from tests.engine.test_seg_2b_s7_audit import (
    MANIFEST,
    _build_inputs,
)


def _prepare_environment(tmp_path: Path) -> tuple[S8ValidationInputs, Path]:
    s7_inputs, context = _build_inputs(tmp_path)
    S7AuditRunner().run(s7_inputs)
    base = context["base"]
    s8_inputs = S8ValidationInputs(
        data_root=base,
        manifest_fingerprint=MANIFEST,
        dictionary_path=s7_inputs.dictionary_path,
        emit_summary_stdout=False,
    )
    return s8_inputs, base


def test_s8_builds_validation_bundle(tmp_path: Path) -> None:
    runner = S8ValidationRunner()
    inputs, base = _prepare_environment(tmp_path)
    result = runner.run(inputs)

    assert result.bundle_path.is_dir()
    index_payload = json.loads(result.index_path.read_text(encoding="utf-8"))
    assert any(
        entry["path"] == f"reports/seed=2025110601/{runner.REPORT_FILENAME}"
        for entry in index_payload
    )
    flag_text = result.flag_path.read_text(encoding="utf-8").strip()
    assert flag_text.startswith("sha256_hex = ")
    assert result.bundle_digest in flag_text


def test_s8_republish_is_idempotent(tmp_path: Path) -> None:
    runner = S8ValidationRunner()
    inputs, _ = _prepare_environment(tmp_path)
    first = runner.run(inputs)
    second = runner.run(inputs)

    assert first.bundle_path == second.bundle_path
    assert first.bundle_digest == second.bundle_digest


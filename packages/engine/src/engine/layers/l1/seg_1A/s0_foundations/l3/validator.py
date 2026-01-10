"""Read-only validation harness for S0 outputs (L3)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

import polars as pl
from jsonschema import Draft202012Validator, ValidationError

from ..exceptions import err
from ..l0.artifacts import hash_artifact
from ..l1.hashing import compute_manifest_fingerprint, compute_parameter_hash
from ..l2.output import S0Outputs
from ..l2.runner import SealedFoundations
from ...shared.dictionary import load_dictionary, resolve_dataset_path
from ...shared.passed_flag import parse_passed_flag


def _load_parquet(path: Path) -> pl.DataFrame:
    if not path.exists():
        raise err("E_VALIDATION_MISMATCH", f"missing parquet dataset '{path.name}'")
    return pl.read_parquet(path)


def _sort_frame(frame: pl.DataFrame, keys: Iterable[str]) -> pl.DataFrame:
    return frame.sort(keys).select(frame.columns)


def _assert_frame_equal(
    expected: pl.DataFrame, observed: pl.DataFrame, *, dataset: str
) -> None:
    if expected.shape != observed.shape:
        raise err(
            "E_VALIDATION_MISMATCH",
            f"{dataset} shape mismatch expected {expected.shape} got {observed.shape}",
        )
    if expected.columns != observed.columns:
        raise err(
            "E_VALIDATION_MISMATCH",
            f"{dataset} column mismatch expected {expected.columns} got {observed.columns}",
        )
    if expected.to_dicts() != observed.to_dicts():
        raise err("E_VALIDATION_MISMATCH", f"{dataset} content mismatch")


def _assert_schema(frame: pl.DataFrame, ref, *, dataset: str) -> None:
    schema = ref.load()
    validator = Draft202012Validator(schema)
    data = frame.to_dicts()
    try:
        validator.validate(data)
    except ValidationError as exc:  # pragma: no cover - exercised via corruption tests
        raise err(
            "E_VALIDATION_SCHEMA",
            f"{dataset} schema violation: {exc.message}",
        ) from exc


def _verify_pass_flag(bundle_dir: Path) -> None:
    files = sorted(p for p in bundle_dir.iterdir() if p.name != "_passed.flag")
    files.sort(key=lambda p: p.name)
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.read_bytes())
    flag_path = bundle_dir / "_passed.flag"
    if not flag_path.exists():
        raise err("E_VALIDATION_DIGEST", "missing _passed.flag")
    expected = digest.hexdigest()
    try:
        flag_digest = parse_passed_flag(flag_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise err("E_VALIDATION_DIGEST", "validation bundle digest malformed") from exc
    if flag_digest != expected:
        raise err("E_VALIDATION_DIGEST", "validation bundle digest mismatch")


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise err("E_VALIDATION_MISMATCH", f"missing JSON artefact '{path.name}'")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise err("E_VALIDATION_MISMATCH", f"missing JSONL artefact '{path.name}'")
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    return records


def _rehash_param_artifacts(records: list[dict], sealed: SealedFoundations) -> list:
    digests = []
    by_name = {
        digest.basename: digest.path for digest in sealed.parameter_hash.artefacts
    }
    for record in records:
        name = record.get("filename")
        if not isinstance(name, str):
            raise err("E_VALIDATION_DIGEST", "param_digest_log missing filename")
        path = by_name.get(name)
        if path is None:
            raise err(
                "E_VALIDATION_DIGEST",
                f"param_digest_log references unknown file '{name}'",
            )
        digest = hash_artifact(path, error_prefix="E_VALIDATION_DIGEST")
        if digest.sha256_hex != record.get("sha256_hex"):
            raise err(
                "E_VALIDATION_DIGEST",
                f"param digest mismatch for '{path}'",
            )
        digests.append(digest)
    return digests


def _rehash_fingerprint_artifacts(records: list[dict]) -> list:
    digests = []
    for record in records:
        path = Path(record["path"])
        digest = hash_artifact(path, error_prefix="E_VALIDATION_DIGEST")
        if digest.sha256_hex != record.get("sha256"):
            raise err(
                "E_VALIDATION_DIGEST",
                f"artefact '{path}' digest mismatch",
            )
        digests.append(digest)
    return digests


def _verify_lineage(bundle_dir: Path, sealed: SealedFoundations) -> None:
    param_records = _load_jsonl(bundle_dir / "param_digest_log.jsonl")
    param_digests = _rehash_param_artifacts(param_records, sealed)
    recomputed_param = compute_parameter_hash(param_digests)
    if recomputed_param.parameter_hash != sealed.parameter_hash.parameter_hash:
        raise err("E_VALIDATION_DIGEST", "parameter_hash mismatch")

    manifest_records = _load_jsonl(bundle_dir / "fingerprint_artifacts.jsonl")
    manifest_digests = _rehash_fingerprint_artifacts(manifest_records)
    manifest_result = compute_manifest_fingerprint(
        manifest_digests,
        git_commit_raw=bytes.fromhex(sealed.manifest_fingerprint.git_commit_hex),
        parameter_hash_bytes=bytes.fromhex(recomputed_param.parameter_hash),
    )
    if (
        manifest_result.manifest_fingerprint
        != sealed.manifest_fingerprint.manifest_fingerprint
    ):
        raise err("E_VALIDATION_DIGEST", "manifest_fingerprint mismatch")


def _verify_numeric_attest(bundle_dir: Path) -> None:
    attest = _load_json(bundle_dir / "numeric_policy_attest.json")
    tests = attest.get("self_tests", {})
    for name, result in tests.items():
        if result != "pass":
            raise err(
                "E_VALIDATION_NUMERIC",
                f"numeric self-test '{name}' reported {result}",
            )


def validate_outputs(
    *,
    base_path: Path,
    sealed: SealedFoundations,
    outputs: S0Outputs,
    seed: int,
    run_id: str,
) -> None:
    """Re-open persisted artefacts and ensure they match deterministic expectations."""

    parameter_hash = sealed.parameter_hash.parameter_hash
    manifest_fingerprint = sealed.manifest_fingerprint.manifest_fingerprint
    dictionary = load_dictionary()

    observed_flags = _load_parquet(
        resolve_dataset_path(
            "crossborder_eligibility_flags",
            base_path=base_path,
            template_args={"parameter_hash": parameter_hash},
            dictionary=dictionary,
        )
    )
    observed_design = _load_parquet(
        resolve_dataset_path(
            "hurdle_design_matrix",
            base_path=base_path,
            template_args={"parameter_hash": parameter_hash},
            dictionary=dictionary,
        )
    )

    authority = sealed.context.schema_authority
    _assert_schema(
        observed_flags,
        authority.segment_schema("/prep/crossborder_eligibility_flags"),
        dataset="crossborder_eligibility_flags",
    )
    _assert_schema(
        observed_design,
        authority.segment_schema("/model/hurdle_design_matrix"),
        dataset="hurdle_design_matrix",
    )

    expected_flags = _sort_frame(outputs.crossborder_flags, ["merchant_id"])
    expected_design = _sort_frame(outputs.design_matrix, ["merchant_id"])
    _assert_frame_equal(
        expected_flags,
        _sort_frame(observed_flags, ["merchant_id"]),
        dataset="crossborder_eligibility_flags",
    )
    _assert_frame_equal(
        expected_design,
        _sort_frame(observed_design, ["merchant_id"]),
        dataset="hurdle_design_matrix",
    )

    diag_path = resolve_dataset_path(
        "hurdle_pi_probs",
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    if outputs.diagnostics is not None:
        observed_diag = _load_parquet(diag_path)
        _assert_schema(
            observed_diag,
            authority.segment_schema("/model/hurdle_pi_probs"),
            dataset="hurdle_pi_probs",
        )
        expected_diag = _sort_frame(outputs.diagnostics, ["merchant_id"])
        _assert_frame_equal(
            expected_diag,
            _sort_frame(observed_diag, ["merchant_id"]),
            dataset="hurdle_pi_probs",
        )
    elif diag_path.exists():
        raise err("E_VALIDATION_MISMATCH", "unexpected diagnostics parquet present")

    bundle_dir = resolve_dataset_path(
        "validation_bundle_1A",
        base_path=base_path,
        template_args={"manifest_fingerprint": manifest_fingerprint},
        dictionary=dictionary,
    )
    if not bundle_dir.exists():
        raise err("E_VALIDATION_MISMATCH", "validation bundle missing")
    summary = _load_json(bundle_dir / "validation_summary.json")
    if summary.get("run_id") != run_id:
        raise err("E_VALIDATION_MISMATCH", "validation summary run_id mismatch")
    if summary.get("parameter_hash") != parameter_hash:
        raise err("E_VALIDATION_MISMATCH", "validation summary parameter_hash mismatch")
    if summary.get("manifest_fingerprint") != manifest_fingerprint:
        raise err("E_VALIDATION_MISMATCH", "validation summary manifest mismatch")
    _verify_pass_flag(bundle_dir)
    _verify_lineage(bundle_dir, sealed)
    _verify_numeric_attest(bundle_dir)

    audit_path = resolve_dataset_path(
        "rng_audit_log",
        base_path=base_path,
        template_args={
            "seed": seed,
            "parameter_hash": parameter_hash,
            "run_id": run_id,
        },
        dictionary=dictionary,
    )
    audit_rows = _load_jsonl(audit_path)
    if len(audit_rows) != 1:
        raise err(
            "E_VALIDATION_MISMATCH", "rng_audit_log must contain exactly one record"
        )
    audit = audit_rows[0]
    if (
        audit.get("parameter_hash") != parameter_hash
        or audit.get("manifest_fingerprint") != manifest_fingerprint
    ):
        raise err("E_VALIDATION_MISMATCH", "rng audit lineage mismatch")

    events_root = base_path / "logs" / "layer1" / "1A" / "rng" / "events"
    event_exists = any(events_root.rglob("part-00000.jsonl"))
    if not event_exists:
        raise err("E_VALIDATION_MISMATCH", "rng event logs missing")


__all__ = ["validate_outputs"]

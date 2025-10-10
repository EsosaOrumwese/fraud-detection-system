import hashlib
from pathlib import Path

import pytest
import yaml

from engine.layers.l1.seg_1A.s1_hurdle.l2.runner import HurdleDecision
from engine.layers.l1.seg_1A.s2_nb_outlets.l2.runner import NBFinalRecord
from engine.layers.l1.seg_1A.s3_crossborder_universe.l2.deterministic import (
    ArtefactSpec,
    MerchantProfile,
    build_deterministic_context,
)
from engine.layers.l1.seg_1A.s0_foundations.exceptions import S0Error


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_dummy_file(path: Path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8")


def test_build_deterministic_context_success(tmp_path: Path) -> None:
    rule_ladder_path = tmp_path / "policy.s3.rule_ladder.yaml"
    _write_yaml(
        rule_ladder_path,
        {
            "semver": "1.0.0",
            "version": "2025-10-10",
            "reason_codes": ["ALLOW_DEFAULT"],
            "filter_tags": ["ADMISSIBLE"],
            "rules": [],
        },
    )
    iso_path = tmp_path / "iso_canonical.parquet"
    _write_dummy_file(iso_path, "dummy iso bytes")

    merchant_profiles = [
        MerchantProfile(merchant_id=1, home_country_iso="GB", mcc="5411", channel="CP"),
        MerchantProfile(merchant_id=2, home_country_iso="US", mcc="5732", channel="CNP"),
    ]
    decisions = [
        HurdleDecision(
            merchant_id=1,
            eta=0.0,
            pi=0.9,
            deterministic=False,
            is_multi=True,
            u=0.1,
            rng_counter_before=(0, 0),
            rng_counter_after=(0, 1),
            draws=1,
            blocks=1,
        ),
        HurdleDecision(
            merchant_id=2,
            eta=0.0,
            pi=0.8,
            deterministic=False,
            is_multi=True,
            u=0.2,
            rng_counter_before=(0, 0),
            rng_counter_after=(0, 1),
            draws=1,
            blocks=1,
        ),
    ]
    finals = [
        NBFinalRecord(
            merchant_id=1,
            mu=1.0,
            phi=1.0,
            n_outlets=3,
            nb_rejections=0,
            attempts=1,
        ),
        NBFinalRecord(
            merchant_id=2,
            mu=1.0,
            phi=1.0,
            n_outlets=4,
            nb_rejections=1,
            attempts=2,
        ),
    ]
    context = build_deterministic_context(
        parameter_hash="a" * 64,
        manifest_fingerprint="b" * 64,
        run_id="c" * 32,
        seed=123456789,
        merchant_profiles=merchant_profiles,
        decisions=decisions,
        nb_finals=finals,
        iso_countries={"GB", "US"},
        rule_ladder_spec=ArtefactSpec(
            artefact_id="policy.s3.rule_ladder.yaml",
            path=rule_ladder_path,
        ),
        iso_countries_spec=ArtefactSpec(
            artefact_id="iso3166_canonical_2024",
            path=iso_path,
            semver="2025-10-08",
        ),
    )

    assert context.parameter_hash == "a" * 64
    assert context.seed == 123456789
    assert context.iso_countries == frozenset({"GB", "US"})

    merchants = context.by_merchant()
    assert merchants[1].n_outlets == 3
    assert merchants[2].n_outlets == 4
    assert merchants[1].channel == "CP"
    assert merchants[2].channel == "CNP"

    rule_digest = hashlib.sha256(rule_ladder_path.read_bytes()).hexdigest()
    assert context.artefacts.rule_ladder.sha256 == rule_digest
    assert context.artefacts.rule_ladder.semver == "1.0.0"
    assert context.artefacts.iso_countries.sha256 == hashlib.sha256(
        iso_path.read_bytes()
    ).hexdigest()
    assert context.artefacts.iso_countries.semver == "2025-10-08"
    assert context.artefacts.currency_to_country is None


def test_build_deterministic_context_requires_multi(tmp_path: Path) -> None:
    rule_ladder_path = tmp_path / "policy.yaml"
    _write_yaml(rule_ladder_path, {"semver": "1.0.0", "version": "v"})
    iso_path = tmp_path / "iso.parquet"
    _write_dummy_file(iso_path, "iso")

    merchant_profiles = [MerchantProfile(merchant_id=1, home_country_iso="GB", mcc="5411", channel="CP")]
    decisions = [
        HurdleDecision(
            merchant_id=1,
            eta=0.0,
            pi=0.9,
            deterministic=False,
            is_multi=False,
            u=0.1,
            rng_counter_before=(0, 0),
            rng_counter_after=(0, 1),
            draws=1,
            blocks=1,
        )
    ]
    finals = [
        NBFinalRecord(
            merchant_id=1,
            mu=1.0,
            phi=1.0,
            n_outlets=3,
            nb_rejections=0,
            attempts=1,
        )
    ]

    with pytest.raises(S0Error) as exc:
        build_deterministic_context(
            parameter_hash="a" * 64,
            manifest_fingerprint="b" * 64,
            run_id="c" * 32,
            seed=0,
            merchant_profiles=merchant_profiles,
            decisions=decisions,
            nb_finals=finals,
            iso_countries={"GB"},
            rule_ladder_spec=ArtefactSpec(
                artefact_id="policy.s3.rule_ladder.yaml",
                path=rule_ladder_path,
            ),
            iso_countries_spec=ArtefactSpec(
                artefact_id="iso3166_canonical_2024",
                path=iso_path,
            ),
        )
    assert exc.value.context.code == "ERR_S3_PRECONDITION"


def test_build_deterministic_context_invalid_channel(tmp_path: Path) -> None:
    rule_ladder_path = tmp_path / "policy.yaml"
    _write_yaml(rule_ladder_path, {"semver": "1.0.0"})
    iso_path = tmp_path / "iso.parquet"
    _write_dummy_file(iso_path, "iso")

    merchant_profiles = [
        MerchantProfile(
            merchant_id=1,
            home_country_iso="GB",
            mcc="5411",
            channel="MOBILE",
        )
    ]
    decisions = [
        HurdleDecision(
            merchant_id=1,
            eta=0.0,
            pi=0.9,
            deterministic=False,
            is_multi=True,
            u=0.1,
            rng_counter_before=(0, 0),
            rng_counter_after=(0, 1),
            draws=1,
            blocks=1,
        )
    ]
    finals = [
        NBFinalRecord(
            merchant_id=1,
            mu=1.0,
            phi=1.0,
            n_outlets=3,
            nb_rejections=0,
            attempts=1,
        )
    ]

    with pytest.raises(S0Error) as exc:
        build_deterministic_context(
            parameter_hash="a" * 64,
            manifest_fingerprint="b" * 64,
            run_id="c" * 32,
            seed=0,
            merchant_profiles=merchant_profiles,
            decisions=decisions,
            nb_finals=finals,
            iso_countries={"GB"},
            rule_ladder_spec=ArtefactSpec(
                artefact_id="policy.s3.rule_ladder.yaml",
                path=rule_ladder_path,
            ),
            iso_countries_spec=ArtefactSpec(
                artefact_id="iso3166_canonical_2024",
                path=iso_path,
            ),
        )
    assert exc.value.context.code == "ERR_S3_VOCAB_INVALID"


def test_build_deterministic_context_missing_policy(tmp_path: Path) -> None:
    iso_path = tmp_path / "iso.parquet"
    _write_dummy_file(iso_path, "iso")

    merchant_profiles = [
        MerchantProfile(merchant_id=1, home_country_iso="GB", mcc="5411", channel="CP")
    ]
    decisions = [
        HurdleDecision(
            merchant_id=1,
            eta=0.0,
            pi=0.9,
            deterministic=False,
            is_multi=True,
            u=0.1,
            rng_counter_before=(0, 0),
            rng_counter_after=(0, 1),
            draws=1,
            blocks=1,
        )
    ]
    finals = [
        NBFinalRecord(
            merchant_id=1,
            mu=1.0,
            phi=1.0,
            n_outlets=3,
            nb_rejections=0,
            attempts=1,
        )
    ]

    with pytest.raises(S0Error) as exc:
        build_deterministic_context(
            parameter_hash="a" * 64,
            manifest_fingerprint="b" * 64,
            run_id="c" * 32,
            seed=0,
            merchant_profiles=merchant_profiles,
            decisions=decisions,
            nb_finals=finals,
            iso_countries={"GB"},
            rule_ladder_spec=ArtefactSpec(
                artefact_id="policy.s3.rule_ladder.yaml",
                path=tmp_path / "missing.yaml",
            ),
            iso_countries_spec=ArtefactSpec(
                artefact_id="iso3166_canonical_2024",
                path=iso_path,
            ),
        )
    assert exc.value.context.code == "ERR_S3_AUTHORITY_MISSING"

import polars as pl
import pytest

from engine.layers.l1.seg_1A.s1_hurdle.l2.runner import HurdleDecision
from engine.layers.l1.seg_1A.s2_nb_outlets.l2.runner import NBFinalRecord
from engine.layers.l1.seg_1A.s3_crossborder_universe import (
    ArtefactSpec,
    MerchantProfile,
    S3CrossBorderRunner,
    S3FeatureToggles,
    build_deterministic_context,
)
from engine.layers.l1.seg_1A.s0_foundations.exceptions import S0Error
from engine.layers.l1.seg_1A.s3_crossborder_universe.l0.policy import (
    load_base_weight_policy,
    load_thresholds_policy,
)
from engine.layers.l1.seg_1A.s3_crossborder_universe.l3.validator import (
    validate_s3_outputs,
)


def _write_policy(path):
    path.write_text(
        "\n".join(
            [
                'semver: "1.0.0"',
                'version: "2025-10-10"',
                "reason_codes:",
                "  - DENY_SANCTIONED",
                "  - ALLOW_DEFAULT",
                "  - DEFAULT_DENY",
                "filter_tags:",
                "  - HOME",
                "  - SANCTIONED",
                "  - ADMISSIBLE",
                "  - CROSS_BORDER_ELIGIBLE",
                "named_sets:",
                "  SANCTIONED:",
                "    countries: ['RU', 'IR', 'KP']",
                "  PREFERRED_FOREIGN:",
                "    countries: ['GB', 'DE', 'FR', 'CA', 'US', 'IE', 'NL', 'AU', 'JP']",
                "precedence_order:",
                "  - DENY",
                "  - ALLOW",
                "  - CLASS",
                "  - LEGAL",
                "  - THRESHOLD",
                "  - DEFAULT",
                "rules:",
                "  - rule_id: RL_DENY_SANCTIONED_HOME",
                "    precedence: DENY",
                "    priority: 10",
                "    is_decision_bearing: true",
                '    predicate: "home_country_iso in SANCTIONED"',
                "    outcome:",
                "      reason_code: DENY_SANCTIONED",
                "      tags: ['SANCTIONED']",
                "      crossborder: false",
                "      deny_named_sets: ['SANCTIONED']",
                "  - rule_id: RL_ALLOW_BASE",
                "    precedence: ALLOW",
                "    priority: 100",
                "    is_decision_bearing: true",
                '    predicate: "channel == \\"CP\\""',
                "    outcome:",
                "      reason_code: ALLOW_DEFAULT",
                "      tags: ['ADMISSIBLE', 'CROSS_BORDER_ELIGIBLE']",
                "      crossborder: true",
                "      admit_named_sets: ['PREFERRED_FOREIGN']",
                "  - rule_id: RL_DEFAULT_FALLBACK",
                "    precedence: DEFAULT",
                "    priority: 1000",
                "    is_decision_bearing: true",
                '    predicate: "true"',
                "    outcome:",
                "      reason_code: DEFAULT_DENY",
                "      tags: []",
                "      crossborder: false",
            ]
        ),
        encoding="utf-8",
    )


def _write_base_weight_policy(path):
    path.write_text(
        "\n".join(
            [
                'semver: "1.0.0"',
                'version: "2025-10-10"',
                "dp: 4",
                "constants:",
                "  base: 1.0000",
                "  grocery_bonus: 0.2500",
                "  eea_bonus: 0.1000",
                "sets:",
                "  EEA12: [\"GB\",\"DE\",\"FR\",\"IE\",\"NL\",\"US\",\"CA\",\"AU\",\"JP\"]",
                "  SANCTIONED: [\"JP\"]",
                "selection_rules:",
                "  - id: \"DENY_SANCTIONED\"",
                "    predicate: 'country_iso in SANCTIONED'",
                "    score_components: []",
                "  - id: \"GROCERY_CNP_EEA\"",
                "    predicate: 'channel == \"CNP\" && mcc == 5411 && country_iso in EEA12'",
                "    score_components: [\"base\",\"grocery_bonus\",\"eea_bonus\"]",
                "  - id: \"BASELINE_REGION\"",
                "    predicate: 'country_iso in EEA12'",
                "    score_components: [\"base\"]",
                "  - id: \"DEFAULT\"",
                "    predicate: 'true'",
                "    score_components: [\"base\"]",
            ]
        ),
        encoding="utf-8",
    )


def _write_thresholds_policy(path):
    path.write_text(
        "\n".join(
            [
                'semver: "1.0.0"',
                'version: "2025-10-10"',
                "dp_resid: 8",
                "floors:",
                "  GB: 1",
                "  US: 1",
                "ceilings:",
                "  GB: 999999",
                "  US: 999999",
            ]
        ),
        encoding="utf-8",
    )


def _build_optional_run(tmp_path):
    policy_path = tmp_path / "policy.s3.rule_ladder.yaml"
    _write_policy(policy_path)
    base_weight_path = tmp_path / "policy.s3.base_weight.yaml"
    _write_base_weight_policy(base_weight_path)
    thresholds_path = tmp_path / "policy.s3.thresholds.yaml"
    _write_thresholds_policy(thresholds_path)
    iso_path = tmp_path / "iso.parquet"
    iso_path.write_text("iso", encoding="utf-8")

    merchant_profiles = [
        MerchantProfile(
            merchant_id=1,
            home_country_iso="GB",
            mcc="5411",
            channel="CP",
        )
    ]
    decisions = [
        HurdleDecision(
            merchant_id=1,
            eta=0.0,
            pi=0.95,
            deterministic=False,
            is_multi=True,
            u=0.05,
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
            n_outlets=6,
            nb_rejections=0,
            attempts=1,
        )
    ]

    deterministic = build_deterministic_context(
        parameter_hash="d" * 64,
        manifest_fingerprint="e" * 64,
        run_id="f" * 32,
        seed=9876,
        merchant_profiles=merchant_profiles,
        decisions=decisions,
        nb_finals=finals,
        iso_countries={"GB", "DE", "FR", "CA", "US", "IE", "NL", "AU", "JP"},
        rule_ladder_spec=ArtefactSpec(
            artefact_id="policy.s3.rule_ladder.yaml",
            path=policy_path,
        ),
        iso_countries_spec=ArtefactSpec(
            artefact_id="iso3166_canonical_2024",
            path=iso_path,
        ),
        base_weight_spec=ArtefactSpec(
            artefact_id="policy.s3.base_weight.yaml",
            path=base_weight_path,
        ),
        thresholds_spec=ArtefactSpec(
            artefact_id="policy.s3.thresholds.yaml",
            path=thresholds_path,
        ),
    )

    toggles = S3FeatureToggles(
        priors_enabled=True,
        integerisation_enabled=True,
        sequencing_enabled=True,
    )
    base_weight_policy = load_base_weight_policy(
        base_weight_path, iso_countries=deterministic.iso_countries
    )
    thresholds_policy = load_thresholds_policy(
        thresholds_path, iso_countries=deterministic.iso_countries
    )

    runner = S3CrossBorderRunner()
    result = runner.run(
        base_path=tmp_path,
        deterministic=deterministic,
        rule_ladder_path=policy_path,
        toggles=toggles,
        base_weight_policy=base_weight_policy,
        thresholds_policy=thresholds_policy,
    )

    return (
        deterministic,
        result,
        policy_path,
        toggles,
        base_weight_policy,
        thresholds_policy,
    )


def test_s3_runner_and_validator(tmp_path):
    policy_path = tmp_path / "policy.s3.rule_ladder.yaml"
    _write_policy(policy_path)
    iso_path = tmp_path / "iso.parquet"
    iso_path.write_text("iso", encoding="utf-8")

    merchant_profiles = [
        MerchantProfile(
            merchant_id=1,
            home_country_iso="GB",
            mcc="5411",
            channel="CP",
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

    deterministic = build_deterministic_context(
        parameter_hash="a" * 64,
        manifest_fingerprint="b" * 64,
        run_id="c" * 32,
        seed=1234,
        merchant_profiles=merchant_profiles,
        decisions=decisions,
        nb_finals=finals,
        iso_countries={"GB", "DE", "FR", "CA", "US", "IE", "NL", "AU", "JP"},
        rule_ladder_spec=ArtefactSpec(
            artefact_id="policy.s3.rule_ladder.yaml",
            path=policy_path,
        ),
        iso_countries_spec=ArtefactSpec(
            artefact_id="iso3166_canonical_2024",
            path=iso_path,
        ),
    )

    runner = S3CrossBorderRunner()
    result = runner.run(
        base_path=tmp_path,
        deterministic=deterministic,
        rule_ladder_path=policy_path,
        toggles=S3FeatureToggles(),
    )

    assert result.candidate_set_path.exists()
    data = pl.read_parquet(result.candidate_set_path).sort(
        ["merchant_id", "candidate_rank"]
    )
    assert data.height == 9
    first_row = data.row(0, named=True)
    assert first_row["is_home"] is True
    assert first_row["country_iso"] == "GB"
    assert first_row["candidate_rank"] == 0
    assert "ALLOW_DEFAULT" in first_row["reason_codes"]
    assert "HOME" in first_row["filter_tags"]

    validate_s3_outputs(
        deterministic=deterministic,
        candidate_set_path=result.candidate_set_path,
        rule_ladder_path=policy_path,
        toggles=S3FeatureToggles(),
    )

def test_s3_optional_lanes(tmp_path):
    deterministic, result, policy_path, toggles, base_weight_policy, thresholds_policy = _build_optional_run(tmp_path)

    assert result.base_weight_priors_path is not None
    assert result.integerised_counts_path is not None
    assert result.site_sequence_path is not None

    priors_df = pl.read_parquet(result.base_weight_priors_path)
    assert priors_df.get_column("dp").unique().to_list() == [4]

    counts_df = pl.read_parquet(result.integerised_counts_path)
    total_counts = counts_df.get_column("count").sum()
    assert total_counts == deterministic.merchants[0].n_outlets

    sequence_df = pl.read_parquet(result.site_sequence_path)
    assert sequence_df.height == total_counts

    validation = validate_s3_outputs(
        deterministic=deterministic,
        candidate_set_path=result.candidate_set_path,
        rule_ladder_path=policy_path,
        toggles=toggles,
        base_weight_policy=base_weight_policy,
        thresholds_policy=thresholds_policy,
        base_weight_priors_path=result.base_weight_priors_path,
        integerised_counts_path=result.integerised_counts_path,
        site_sequence_path=result.site_sequence_path,
    )
    metrics = dict(validation.metrics)
    assert metrics["priors_rows"] > 0
    assert metrics["integerised_rows"] > 0
    assert metrics["sequence_rows"] > 0


def test_s3_validator_detects_count_breach(tmp_path):
    deterministic, result, policy_path, toggles, base_weight_policy, thresholds_policy = _build_optional_run(tmp_path)

    counts_path = result.integerised_counts_path
    assert counts_path is not None
    assert result.base_weight_priors_path is not None
    assert result.site_sequence_path is not None
    rows = pl.read_parquet(counts_path).to_dicts()
    rows[0]["count"] += 1
    pl.DataFrame(rows).write_parquet(counts_path, compression="zstd")

    with pytest.raises(S0Error) as exc:
        validate_s3_outputs(
            deterministic=deterministic,
            candidate_set_path=result.candidate_set_path,
            rule_ladder_path=policy_path,
            toggles=toggles,
            base_weight_policy=base_weight_policy,
            thresholds_policy=thresholds_policy,
            base_weight_priors_path=result.base_weight_priors_path,
            integerised_counts_path=counts_path,
            site_sequence_path=result.site_sequence_path,
        )
    assert exc.value.context.code == "ERR_S3_INTEGER_SUM_MISMATCH"


def test_s3_feature_toggles_validation():
    toggles = S3FeatureToggles(sequencing_enabled=True)
    with pytest.raises(S0Error) as exc:
        toggles.validate()
    assert exc.value.context.code == "ERR_S3_PRECONDITION"


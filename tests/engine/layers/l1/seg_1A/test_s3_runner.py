import polars as pl
import pytest
from decimal import Decimal

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
    load_bounds_policy,
    load_thresholds_policy,
)
from engine.layers.l1.seg_1A.s3_crossborder_universe.l3.validator import (
    validate_s3_outputs,
)
from engine.layers.l1.seg_1A.s3_crossborder_universe.l1.kernels import (
    _compute_integerised_counts,
    _compute_priors,
)
from engine.layers.l1.seg_1A.s3_crossborder_universe.l0.types import RankedCandidateRow
from engine.layers.l1.seg_1A.s3_crossborder_universe.l2.deterministic import (
    MerchantContext,
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


def _write_bounds_policy(path):
    path.write_text(
        "\n".join(
            [
                'semver: "1.0.0"',
                'version: "2025-10-10"',
                "default_upper: 999999",
                "overrides:",
                "  GB: 6",
                "  US: 4",
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
    bounds_path = tmp_path / "policy.s3.bounds.yaml"
    _write_bounds_policy(bounds_path)
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
        bounds_spec=ArtefactSpec(
            artefact_id="policy.s3.bounds.yaml",
            path=bounds_path,
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
    bounds_policy = load_bounds_policy(
        bounds_path, iso_countries=deterministic.iso_countries
    )

    runner = S3CrossBorderRunner()
    result = runner.run(
        base_path=tmp_path,
        deterministic=deterministic,
        rule_ladder_path=policy_path,
        toggles=toggles,
        base_weight_policy=base_weight_policy,
        thresholds_policy=thresholds_policy,
        bounds_policy=bounds_policy,
    )

    return (
        deterministic,
        result,
        policy_path,
        toggles,
        base_weight_policy,
        thresholds_policy,
        bounds_policy,
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
    (
        deterministic,
        result,
        policy_path,
        toggles,
        base_weight_policy,
        thresholds_policy,
        bounds_policy,
    ) = _build_optional_run(tmp_path)

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
    assert metrics["schema_validated"] == 1.0
    assert metrics["diagnostic_rows"] == float(len(validation.diagnostics))
    assert len(validation.diagnostics) == 1
    diag = validation.diagnostics[0]
    assert diag["merchant_id"] == deterministic.merchants[0].merchant_id
    assert diag["integerised_count_rows"] > 0
    assert isinstance(diag["prior_weight_sum"], str)


def test_s3_validator_detects_count_breach(tmp_path):
    (
        deterministic,
        result,
        policy_path,
        toggles,
        base_weight_policy,
        thresholds_policy,
        bounds_policy,
    ) = _build_optional_run(tmp_path)

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






def test_compute_priors_exclusion(tmp_path):
    policy_path = tmp_path / "policy.s3.base_weight.yaml"
    _write_base_weight_policy(policy_path)
    policy = load_base_weight_policy(
        policy_path, iso_countries={"GB", "FR", "JP", "US", "CA", "NL", "IE", "DE", "AU"}
    )
    merchant = MerchantContext(
        merchant_id=1,
        home_country_iso="GB",
        mcc="5411",
        channel="CNP",
        n_outlets=6,
    )
    ranked = [
        RankedCandidateRow(
            merchant_id=1,
            country_iso="GB",
            is_home=True,
            candidate_rank=0,
            filter_tags=("HOME",),
            reason_codes=(),
            admitting_rules=(),
        ),
        RankedCandidateRow(
            merchant_id=1,
            country_iso="FR",
            is_home=False,
            candidate_rank=1,
            filter_tags=("ADMISSIBLE",),
            reason_codes=(),
            admitting_rules=(),
        ),
        RankedCandidateRow(
            merchant_id=1,
            country_iso="JP",
            is_home=False,
            candidate_rank=2,
            filter_tags=("ADMISSIBLE",),
            reason_codes=(),
            admitting_rules=(),
        ),
    ]
    priors, weights = _compute_priors(
        ranked,
        merchant=merchant,
        policy=policy,
        merchant_tags=("ADMISSIBLE",),
    )
    assert {row.country_iso for row in priors} == {"GB", "FR"}
    assert weights[2] == Decimal("0")
    assert weights[0] == Decimal("1.3500")
    assert weights[1] == Decimal("1.3500")


def test_compute_priors_no_scores(tmp_path):
    policy_path = tmp_path / "policy.none.yaml"
    policy_path.write_text(
        "\n".join(
            [
                'semver: "1.0.0"',
                'version: "2025-10-10"',
                "dp: 4",
                "constants:",
                "  base: 1.0000",
                "selection_rules:",
                "  - id: \"DENY_ALL\"",
                "    predicate: 'true'",
                "    score_components: []",
            ]
        ),
        encoding="utf-8",
    )
    policy = load_base_weight_policy(policy_path, iso_countries={"GB", "US"})
    merchant = MerchantContext(
        merchant_id=1,
        home_country_iso="GB",
        mcc="5411",
        channel="CP",
        n_outlets=4,
    )
    ranked = [
        RankedCandidateRow(
            merchant_id=1,
            country_iso="GB",
            is_home=True,
            candidate_rank=0,
            filter_tags=("HOME",),
            reason_codes=(),
            admitting_rules=(),
        ),
        RankedCandidateRow(
            merchant_id=1,
            country_iso="US",
            is_home=False,
            candidate_rank=1,
            filter_tags=("ADMISSIBLE",),
            reason_codes=(),
            admitting_rules=(),
        ),
    ]
    priors, weights = _compute_priors(
        ranked,
        merchant=merchant,
        policy=policy,
        merchant_tags=(),
    )
    assert priors == []
    assert weights is None


def test_s3_validator_schema_violation(tmp_path):
    (
        deterministic,
        result,
        policy_path,
        toggles,
        base_weight_policy,
        thresholds_policy,
        bounds_policy,
    ) = _build_optional_run(tmp_path)

    candidate_rows = pl.read_parquet(result.candidate_set_path).to_dicts()
    candidate_rows[0]["country_iso"] = "g1"  # violates ISO schema pattern
    pl.DataFrame(candidate_rows).write_parquet(result.candidate_set_path, compression="zstd")

    with pytest.raises(S0Error) as exc:
        validate_s3_outputs(
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
    assert exc.value.context.code == "ERR_S3_SCHEMA_VALIDATION"


def test_integerisation_reallocates_under_bounds(tmp_path):
    bounds_path = tmp_path / "policy.s3.bounds.yaml"
    bounds_path.write_text(
        "\n".join(
            [
                'semver: "1.0.0"',
                'version: "2025-10-10"',
                "default_upper: 6",
                "overrides:",
                "  GB: 4",
                "  US: 2",
            ]
        ),
        encoding="utf-8",
    )
    bounds_policy = load_bounds_policy(bounds_path, iso_countries={"GB", "US", "FR"})
    ranked = [
        RankedCandidateRow(
            merchant_id=1,
            country_iso="GB",
            is_home=True,
            candidate_rank=0,
            filter_tags=("HOME",),
            reason_codes=(),
            admitting_rules=(),
        ),
        RankedCandidateRow(
            merchant_id=1,
            country_iso="US",
            is_home=False,
            candidate_rank=1,
            filter_tags=("ADMISSIBLE",),
            reason_codes=(),
            admitting_rules=(),
        ),
        RankedCandidateRow(
            merchant_id=1,
            country_iso="FR",
            is_home=False,
            candidate_rank=2,
            filter_tags=("ADMISSIBLE",),
            reason_codes=(),
            admitting_rules=(),
        ),
    ]
    count_rows, counts = _compute_integerised_counts(
        ranked,
        n_outlets=10,
        weights=None,
        policy=None,
        bounds_policy=bounds_policy,
    )
    assert sum(counts) == 10
    gb = next(row for row in count_rows if row.country_iso == "GB")
    us = next(row for row in count_rows if row.country_iso == "US")
    fr = next(row for row in count_rows if row.country_iso == "FR")
    assert gb.count <= 4
    assert us.count <= 2
    assert fr.count >= 4


def test_base_weight_score_value(tmp_path):
    policy_path = tmp_path / "policy.score_value.yaml"
    policy_path.write_text(
        "\n".join(
            [
                'semver: "1.0.0"',
                'version: "2025-10-10"',
                "dp: 2",
                "constants:",
                "  base: 1.00",
                "selection_rules:",
                "  - id: HOME_RULE",
                "    predicate: 'is_home'",
                "    score_value: 2.50",
                "  - id: DEFAULT",
                "    predicate: 'true'",
                "    score_components: ['base']",
            ]
        ),
        encoding="utf-8",
    )
    policy = load_base_weight_policy(policy_path)
    merchant = MerchantContext(
        merchant_id=42,
        home_country_iso="GB",
        mcc="5411",
        channel="CP",
        n_outlets=3,
    )
    ranked = [
        RankedCandidateRow(
            merchant_id=42,
            country_iso="GB",
            is_home=True,
            candidate_rank=0,
            filter_tags=("HOME",),
            reason_codes=(),
            admitting_rules=(),
        ),
        RankedCandidateRow(
            merchant_id=42,
            country_iso="US",
            is_home=False,
            candidate_rank=1,
            filter_tags=("ADMISSIBLE",),
            reason_codes=(),
            admitting_rules=(),
        ),
    ]
    priors, weights = _compute_priors(
        ranked,
        merchant=merchant,
        policy=policy,
        merchant_tags=("HOME",),
    )
    assert [row.base_weight_dp for row in priors] == ["2.50", "1.00"]
    assert weights == [Decimal("2.50"), Decimal("1.00")]


def test_base_weight_normalisation(tmp_path):
    policy_path = tmp_path / "policy.normalisation.yaml"
    policy_path.write_text(
        "\n".join(
            [
                'semver: "1.0.0"',
                'version: "2025-10-10"',
                "dp: 2",
                "constants:",
                "  base: 1.00",
                "normalisation:",
                "  method: sum_to_target",
                "  target: 4.00",
                "selection_rules:",
                "  - id: HOME_RULE",
                "    predicate: 'is_home'",
                "    score_components: ['base']",
                "  - id: FOREIGN_RULE",
                "    predicate: 'true'",
                "    score_components: ['base']",
            ]
        ),
        encoding="utf-8",
    )
    policy = load_base_weight_policy(policy_path)
    merchant = MerchantContext(
        merchant_id=7,
        home_country_iso="GB",
        mcc="5411",
        channel="CP",
        n_outlets=2,
    )
    ranked = [
        RankedCandidateRow(
            merchant_id=7,
            country_iso="GB",
            is_home=True,
            candidate_rank=0,
            filter_tags=("HOME",),
            reason_codes=(),
            admitting_rules=(),
        ),
        RankedCandidateRow(
            merchant_id=7,
            country_iso="US",
            is_home=False,
            candidate_rank=1,
            filter_tags=("ADMISSIBLE",),
            reason_codes=(),
            admitting_rules=(),
        ),
    ]
    priors, weights = _compute_priors(
        ranked,
        merchant=merchant,
        policy=policy,
        merchant_tags=(),
    )
    assert [row.base_weight_dp for row in priors] == ["2.00", "2.00"]
    assert weights == [Decimal("2.00"), Decimal("2.00")]

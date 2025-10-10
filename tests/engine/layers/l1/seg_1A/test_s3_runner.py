import polars as pl

from engine.layers.l1.seg_1A.s1_hurdle.l2.runner import HurdleDecision
from engine.layers.l1.seg_1A.s2_nb_outlets.l2.runner import NBFinalRecord
from engine.layers.l1.seg_1A.s3_crossborder_universe import (
    ArtefactSpec,
    MerchantProfile,
    S3CrossBorderRunner,
    S3FeatureToggles,
    build_deterministic_context,
)
from engine.layers.l1.seg_1A.s3_crossborder_universe.l3.validator import (
    validate_s3_candidate_set,
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

    validate_s3_candidate_set(
        deterministic=deterministic,
        candidate_set_path=result.candidate_set_path,
        rule_ladder_path=policy_path,
    )

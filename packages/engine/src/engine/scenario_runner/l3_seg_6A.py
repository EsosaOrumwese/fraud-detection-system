"""Scenario runner for Segment 6A (S0 gate through S5 validation)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from engine.layers.l3.seg_6A import (
    AccountInputs,
    AccountRunner,
    InstrumentInputs,
    InstrumentRunner,
    NetworkInputs,
    NetworkRunner,
    PartyInputs,
    PartyRunner,
    PostureInputs,
    PostureRunner,
    S0GateRunner,
    S0Inputs,
    S0Outputs,
)
from engine.layers.l3.seg_6A.shared.dictionary import load_dictionary

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Segment6AConfig:
    """User configuration for running Segment 6A."""

    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str
    dictionary_path: Optional[Path] = None
    validation_bundle_1a: Optional[Path] = None
    validation_bundle_1b: Optional[Path] = None
    validation_bundle_2a: Optional[Path] = None
    validation_bundle_2b: Optional[Path] = None
    validation_bundle_3a: Optional[Path] = None
    validation_bundle_3b: Optional[Path] = None
    validation_bundle_5a: Optional[Path] = None
    validation_bundle_5b: Optional[Path] = None
    run_s1: bool = True
    run_s2: bool = True
    run_s3: bool = True
    run_s4: bool = True
    run_s5: bool = True


@dataclass(frozen=True)
class Segment6AResult:
    manifest_fingerprint: str
    parameter_hash: str
    receipt_path: Path
    sealed_inputs_path: Path
    sealed_inputs_digest: str
    s1_party_base_path: Path | None
    s1_party_summary_path: Path | None
    s2_account_base_path: Path | None
    s2_holdings_path: Path | None
    s2_merchant_account_path: Path | None
    s2_account_summary_path: Path | None
    s3_instrument_base_path: Path | None
    s3_account_links_path: Path | None
    s3_party_holdings_path: Path | None
    s3_instrument_summary_path: Path | None
    s4_device_base_path: Path | None
    s4_ip_base_path: Path | None
    s4_device_links_path: Path | None
    s4_ip_links_path: Path | None
    s4_neighbourhoods_path: Path | None
    s4_network_summary_path: Path | None
    s5_report_path: Path | None
    s5_issue_table_path: Path | None
    s5_bundle_index_path: Path | None
    s5_passed_flag_path: Path | None


class Segment6AOrchestrator:
    """Runs Segment 6A S0-S5."""

    def __init__(self) -> None:
        self._s0_runner = S0GateRunner()

    def run(self, config: Segment6AConfig) -> Segment6AResult:
        load_dictionary(config.dictionary_path)
        data_root = config.data_root.expanduser().absolute()

        logger.info(
            "Segment6A S0 orchestrator invoked (manifest=%s, parameter_hash=%s)",
            config.manifest_fingerprint,
            config.parameter_hash,
        )
        s0_inputs = S0Inputs(
            base_path=data_root,
            output_base_path=data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            parameter_hash=config.parameter_hash,
            seed=config.seed,
            run_id=config.run_id,
            dictionary_path=config.dictionary_path,
            validation_bundle_1a=config.validation_bundle_1a,
            validation_bundle_1b=config.validation_bundle_1b,
            validation_bundle_2a=config.validation_bundle_2a,
            validation_bundle_2b=config.validation_bundle_2b,
            validation_bundle_3a=config.validation_bundle_3a,
            validation_bundle_3b=config.validation_bundle_3b,
            validation_bundle_5a=config.validation_bundle_5a,
            validation_bundle_5b=config.validation_bundle_5b,
        )
        logger.info("Segment6A S0 starting (manifest=%s)", config.manifest_fingerprint)
        s0_outputs: S0Outputs = self._s0_runner.run(s0_inputs)
        logger.info("Segment6A S0 completed (manifest=%s)", s0_outputs.manifest_fingerprint)

        s1_party_base_path = None
        s1_party_summary_path = None
        if config.run_s1:
            logger.info("Segment6A S1 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            s1_inputs = PartyInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                parameter_hash=s0_outputs.parameter_hash,
                seed=config.seed,
                run_id=config.run_id,
                dictionary_path=config.dictionary_path,
            )
            s1_result = PartyRunner().run(s1_inputs)
            s1_party_base_path = s1_result.party_base_path
            s1_party_summary_path = s1_result.party_summary_path

        s2_account_base_path = None
        s2_holdings_path = None
        s2_merchant_account_path = None
        s2_account_summary_path = None
        if config.run_s2 and config.run_s1:
            logger.info("Segment6A S2 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            s2_inputs = AccountInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                parameter_hash=s0_outputs.parameter_hash,
                seed=config.seed,
                run_id=config.run_id,
                dictionary_path=config.dictionary_path,
            )
            s2_result = AccountRunner().run(s2_inputs)
            s2_account_base_path = s2_result.account_base_path
            s2_holdings_path = s2_result.holdings_path
            s2_merchant_account_path = s2_result.merchant_account_path
            s2_account_summary_path = s2_result.account_summary_path

        s3_instrument_base_path = None
        s3_account_links_path = None
        s3_party_holdings_path = None
        s3_instrument_summary_path = None
        if config.run_s3 and config.run_s2:
            logger.info("Segment6A S3 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            s3_inputs = InstrumentInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                parameter_hash=s0_outputs.parameter_hash,
                seed=config.seed,
                run_id=config.run_id,
                dictionary_path=config.dictionary_path,
            )
            s3_result = InstrumentRunner().run(s3_inputs)
            s3_instrument_base_path = s3_result.instrument_base_path
            s3_account_links_path = s3_result.account_links_path
            s3_party_holdings_path = s3_result.party_holdings_path
            s3_instrument_summary_path = s3_result.instrument_summary_path

        s4_device_base_path = None
        s4_ip_base_path = None
        s4_device_links_path = None
        s4_ip_links_path = None
        s4_neighbourhoods_path = None
        s4_network_summary_path = None
        if config.run_s4 and config.run_s3:
            logger.info("Segment6A S4 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            s4_inputs = NetworkInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                parameter_hash=s0_outputs.parameter_hash,
                seed=config.seed,
                run_id=config.run_id,
                dictionary_path=config.dictionary_path,
            )
            s4_result = NetworkRunner().run(s4_inputs)
            s4_device_base_path = s4_result.device_base_path
            s4_ip_base_path = s4_result.ip_base_path
            s4_device_links_path = s4_result.device_links_path
            s4_ip_links_path = s4_result.ip_links_path
            s4_neighbourhoods_path = s4_result.neighbourhoods_path
            s4_network_summary_path = s4_result.network_summary_path

        s5_report_path = None
        s5_issue_table_path = None
        s5_bundle_index_path = None
        s5_passed_flag_path = None
        if config.run_s5 and config.run_s4:
            logger.info("Segment6A S5 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            s5_inputs = PostureInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                parameter_hash=s0_outputs.parameter_hash,
                seed=config.seed,
                run_id=config.run_id,
                dictionary_path=config.dictionary_path,
            )
            s5_result = PostureRunner().run(s5_inputs)
            s5_report_path = s5_result.report_path
            s5_issue_table_path = s5_result.issue_table_path
            s5_bundle_index_path = s5_result.bundle_index_path
            s5_passed_flag_path = s5_result.passed_flag_path

        return Segment6AResult(
            manifest_fingerprint=s0_outputs.manifest_fingerprint,
            parameter_hash=s0_outputs.parameter_hash,
            receipt_path=s0_outputs.receipt_path,
            sealed_inputs_path=s0_outputs.sealed_inputs_path,
            sealed_inputs_digest=s0_outputs.sealed_inputs_digest,
            s1_party_base_path=s1_party_base_path,
            s1_party_summary_path=s1_party_summary_path,
            s2_account_base_path=s2_account_base_path,
            s2_holdings_path=s2_holdings_path,
            s2_merchant_account_path=s2_merchant_account_path,
            s2_account_summary_path=s2_account_summary_path,
            s3_instrument_base_path=s3_instrument_base_path,
            s3_account_links_path=s3_account_links_path,
            s3_party_holdings_path=s3_party_holdings_path,
            s3_instrument_summary_path=s3_instrument_summary_path,
            s4_device_base_path=s4_device_base_path,
            s4_ip_base_path=s4_ip_base_path,
            s4_device_links_path=s4_device_links_path,
            s4_ip_links_path=s4_ip_links_path,
            s4_neighbourhoods_path=s4_neighbourhoods_path,
            s4_network_summary_path=s4_network_summary_path,
            s5_report_path=s5_report_path,
            s5_issue_table_path=s5_issue_table_path,
            s5_bundle_index_path=s5_bundle_index_path,
            s5_passed_flag_path=s5_passed_flag_path,
        )


__all__ = ["Segment6AConfig", "Segment6AResult", "Segment6AOrchestrator"]

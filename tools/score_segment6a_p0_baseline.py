#!/usr/bin/env python3
"""Emit Segment 6A P0 baseline realism gateboard (T1..T10)."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import yaml

BOOTSTRAP_REPS_DEFAULT = 1000
BASELINE_REPORT_RUN_ID = "c25a2675fbfbacd952b13bb594880e92"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def scan(run_root: Path, dataset: str) -> str:
    ds = (run_root / "data/layer3/6A" / dataset).as_posix()
    return f"parquet_scan('{ds}/**/*.parquet', hive_partitioning=true, union_by_name=true)"


def jsd(p: np.ndarray, q: np.ndarray) -> float:
    eps = 1e-12
    p = p.astype(np.float64)
    q = q.astype(np.float64)
    p = p / max(float(p.sum()), eps)
    q = q / max(float(q.sum()), eps)
    m = 0.5 * (p + q)
    p = np.clip(p, eps, 1.0)
    q = np.clip(q, eps, 1.0)
    m = np.clip(m, eps, 1.0)
    return 0.5 * float(np.sum(p * np.log(p / m)) + np.sum(q * np.log(q / m)))


def or_with_smoothing(a: int, b: int, c: int, d: int) -> float:
    return ((a + 0.5) / (b + 0.5)) / ((c + 0.5) / (d + 0.5))


def bootstrap_or_ci(a: int, b: int, c: int, d: int, reps: int, rng: np.random.Generator) -> tuple[float, float]:
    n = a + b + c + d
    if n <= 0:
        return float("nan"), float("nan")
    probs = np.array([a, b, c, d], dtype=np.float64) / float(n)
    draws = rng.multinomial(n, probs, size=reps)
    vals = np.array([or_with_smoothing(int(x[0]), int(x[1]), int(x[2]), int(x[3])) for x in draws], dtype=np.float64)
    return float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))


def bootstrap_binomial_ci(n_total: int, n_success: int, reps: int, rng: np.random.Generator) -> tuple[float, float]:
    if n_total <= 0:
        return float("nan"), float("nan")
    p = float(n_success) / float(n_total)
    draws = rng.binomial(n_total, p, size=reps).astype(np.float64) / float(n_total)
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def parse_kmax(priors: dict[str, Any]) -> list[tuple[str, str, int]]:
    rows: list[tuple[str, str, int]] = []
    for rule in priors.get("rules", []):
        rows.append(
            (
                str(rule.get("party_type")),
                str(rule.get("account_type")),
                int((rule.get("params") or {}).get("K_max")),
            )
        )
    return rows


def parse_ip_targets(ip_priors: dict[str, Any]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    rows = (((ip_priors.get("ip_type_mix_model") or {}).get("pi_ip_type_by_region")) or [])
    for row in rows:
        region = str(row.get("region_id"))
        shares: dict[str, float] = {}
        for item in (row.get("pi_ip_type") or []):
            shares[str(item.get("ip_type"))] = float(item.get("share") or 0.0)
        s = sum(shares.values())
        out[region] = {k: (v / s if s > 0 else 0.0) for k, v in shares.items()}
    return out


def role_sets_from_taxonomy(tax: dict[str, Any]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for row in tax.get("role_sets", []):
        out[str(row.get("entity_type"))] = {str(x.get("id")) for x in (row.get("roles") or [])}
    return out


def score_t1_t2(con: duckdb.DuckDBPyConnection, run_root: Path, kmax_rows: list[tuple[str, str, int]]) -> tuple[dict[str, Any], dict[str, Any]]:
    con.execute("drop table if exists kmax_map")
    con.execute("create temp table kmax_map(party_type varchar, account_type varchar, k_max integer)")
    con.executemany("insert into kmax_map values (?, ?, ?)", kmax_rows)
    s2 = scan(run_root, "s2_account_base_6A")

    max_over, sum_over, missing_cells = con.execute(
        f"""
        with cnt as (
          select owner_party_id, party_type, account_type, count(*)::bigint as n
          from {s2}
          group by 1,2,3
        ),
        joined as (
          select c.n, k.k_max
          from cnt c
          left join kmax_map k
            on c.party_type = k.party_type and c.account_type = k.account_type
        )
        select
          max(greatest(n - coalesce(k_max,0),0))::bigint,
          sum(greatest(n - coalesce(k_max,0),0))::bigint,
          sum(case when k_max is null then 1 else 0 end)::bigint
        from joined
        """
    ).fetchone()
    t1_pass = int(max_over or 0) == 0 and int(sum_over or 0) == 0 and int(missing_cells or 0) == 0
    t1 = {
        "gate": "T1_KMAX_HARD_INVARIANT",
        "value": int(max_over or 0),
        "threshold_B": "= 0",
        "threshold_Bplus": "= 0",
        "pass_B": bool(t1_pass),
        "pass_Bplus": bool(t1_pass),
        "status": "PASS" if t1_pass else "FAIL",
        "details": {
            "max_overflow": int(max_over or 0),
            "total_overflow": int(sum_over or 0),
            "missing_rule_cells": int(missing_cells or 0),
        },
    }

    rows = con.execute(
        f"""
        with cnt as (
          select owner_party_id, party_type, account_type, count(*)::bigint as n
          from {s2}
          group by 1,2,3
        )
        select
          c.party_type,
          c.account_type,
          max(c.n)::bigint as max_n,
          quantile_cont(c.n, 0.99)::double as p99_n,
          k.k_max::integer as k_max
        from cnt c
        left join kmax_map k
          on c.party_type = k.party_type and c.account_type = k.account_type
        group by 1,2,5
        order by 1,2
        """
    ).fetchall()
    per_type: list[dict[str, Any]] = []
    max_p99_over = 0.0
    max_max_over = 0.0
    missing_types = 0
    for party_type, account_type, max_n, p99_n, k_max in rows:
        if k_max is None:
            missing_types += 1
            per_type.append(
                {
                    "party_type": str(party_type),
                    "account_type": str(account_type),
                    "k_max": None,
                    "max_accounts_per_party": int(max_n or 0),
                    "p99_accounts_per_party": float(p99_n or 0.0),
                    "pass_tail": False,
                }
            )
            continue
        p99_over = max(float(p99_n or 0.0) - float(k_max), 0.0)
        max_over_type = max(float(max_n or 0.0) - float(k_max), 0.0)
        max_p99_over = max(max_p99_over, p99_over)
        max_max_over = max(max_max_over, max_over_type)
        per_type.append(
            {
                "party_type": str(party_type),
                "account_type": str(account_type),
                "k_max": int(k_max),
                "max_accounts_per_party": int(max_n or 0),
                "p99_accounts_per_party": float(p99_n or 0.0),
                "pass_tail": bool(p99_over <= 1e-12 and max_over_type <= 1e-12),
            }
        )
    t2_pass = missing_types == 0 and max_p99_over <= 1e-12 and max_max_over <= 1e-12
    t2 = {
        "gate": "T2_KMAX_TAIL_SANITY",
        "value": max(max_p99_over, max_max_over),
        "threshold_B": "p99<=Kmax and max<=Kmax",
        "threshold_Bplus": "p99<=Kmax and max<=Kmax",
        "pass_B": bool(t2_pass),
        "pass_Bplus": bool(t2_pass),
        "status": "PASS" if t2_pass else "FAIL",
        "details": {
            "max_p99_over_kmax": max_p99_over,
            "max_max_over_kmax": max_max_over,
            "missing_rule_types": missing_types,
            "per_type": per_type,
        },
    }
    return t1, t2


def score_t3_t4_t5(
    con: duckdb.DuckDBPyConnection,
    run_root: Path,
    ip_targets: dict[str, dict[str, float]],
    reps: int,
    rng: np.random.Generator,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    s_ip_links = scan(run_root, "s4_ip_links_6A")
    s_ip_base = scan(run_root, "s4_ip_base_6A")
    s_dev = scan(run_root, "s4_device_base_6A")

    rows = con.execute(
        f"""
        select d.home_region_id, b.ip_type, count(*)::bigint as n
        from {s_ip_links} l
        join {s_ip_base} b on b.ip_id = l.ip_id
        join {s_dev} d on d.device_id = l.device_id
        group by 1,2
        """
    ).fetchall()
    obs_by_region: dict[str, dict[str, int]] = {}
    for region, ip_type, n in rows:
        r = str(region)
        obs_by_region.setdefault(r, {})
        obs_by_region[r][str(ip_type)] = int(n or 0)
    regions = sorted(set(obs_by_region.keys()) | set(ip_targets.keys()))
    ip_types = sorted({k for m in obs_by_region.values() for k in m.keys()} | {k for m in ip_targets.values() for k in m.keys()})

    max_abs_error_pp = 0.0
    boot_vals: list[float] = []
    per_region: list[dict[str, Any]] = []
    for region in regions:
        obs = obs_by_region.get(region, {})
        n_region = int(sum(obs.values()))
        if n_region <= 0:
            continue
        obs_dist = np.array([float(obs.get(ip, 0)) / float(n_region) for ip in ip_types], dtype=np.float64)
        tgt_dist = np.array([float(ip_targets.get(region, {}).get(ip, 0.0)) for ip in ip_types], dtype=np.float64)
        errs = np.abs(obs_dist - tgt_dist) * 100.0
        max_abs_error_pp = max(max_abs_error_pp, float(np.max(errs)))
        per_region.append({"region_id": region, "n_links": n_region, "max_abs_error_pp": float(np.max(errs))})
        draws = rng.multinomial(n_region, obs_dist / max(float(obs_dist.sum()), 1e-12), size=reps)
        for draw in draws:
            d = draw.astype(np.float64) / float(n_region)
            boot_vals.append(float(np.max(np.abs(d - tgt_dist) * 100.0)))
    ci_low = float(np.quantile(boot_vals, 0.025)) if boot_vals else float("nan")
    ci_high = float(np.quantile(boot_vals, 0.975)) if boot_vals else float("nan")
    t3 = {
        "gate": "T3_IP_PRIOR_ALIGNMENT",
        "value": max_abs_error_pp,
        "threshold_B": "<= 15",
        "threshold_Bplus": "<= 8",
        "pass_B": bool(max_abs_error_pp <= 15.0),
        "pass_Bplus": bool(max_abs_error_pp <= 8.0),
        "status": "PASS" if max_abs_error_pp <= 15.0 else "FAIL",
        "ci_low": (None if not math.isfinite(ci_low) else ci_low),
        "ci_high": (None if not math.isfinite(ci_high) else ci_high),
        "details": {"regions_evaluated": len(per_region), "per_region": per_region},
    }

    linked_devices, total_devices = con.execute(
        f"""
        with a as (select count(distinct device_id)::bigint as n from {s_dev}),
             b as (select count(distinct device_id)::bigint as n from {s_ip_links})
        select b.n, a.n from a,b
        """
    ).fetchone()
    linked_i = int(linked_devices or 0)
    total_i = int(total_devices or 0)
    coverage = float(linked_i) / float(total_i) if total_i > 0 else 0.0
    cov_low, cov_high = bootstrap_binomial_ci(total_i, linked_i, reps, rng)
    t4 = {
        "gate": "T4_DEVICE_IP_COVERAGE",
        "value": coverage,
        "threshold_B": ">= 0.25",
        "threshold_Bplus": ">= 0.35",
        "pass_B": bool(coverage >= 0.25),
        "pass_Bplus": bool(coverage >= 0.35),
        "status": "PASS" if coverage >= 0.25 else "FAIL",
        "ci_low": (None if not math.isfinite(cov_low) else cov_low),
        "ci_high": (None if not math.isfinite(cov_high) else cov_high),
        "details": {"linked_devices": linked_i, "total_devices": total_i},
    }

    p99_v, max_v = con.execute(
        f"""
        with d as (
          select ip_id, count(distinct device_id)::bigint as n
          from {s_ip_links}
          group by 1
        )
        select quantile_cont(n, 0.99)::double, max(n)::bigint from d
        """
    ).fetchone()
    p99_f = float(p99_v or 0.0)
    max_i = int(max_v or 0)
    t5 = {
        "gate": "T5_IP_REUSE_TAIL_BOUNDS",
        "value": {"p99_devices_per_ip": p99_f, "max_devices_per_ip": max_i},
        "threshold_B": "p99<=120 and max<=600",
        "threshold_Bplus": "p99<=80 and max<=350",
        "pass_B": bool(p99_f <= 120.0 and max_i <= 600),
        "pass_Bplus": bool(p99_f <= 80.0 and max_i <= 350),
        "status": "PASS" if (p99_f <= 120.0 and max_i <= 600) else "FAIL",
        "details": {},
    }
    return t3, t4, t5


def score_t6(con: duckdb.DuckDBPyConnection, run_root: Path, role_sets: dict[str, set[str]]) -> dict[str, Any]:
    rows_total = 0
    rows_mapped = 0
    rows_unmapped = 0
    per_entity: list[dict[str, Any]] = []
    datasets = [
        ("PARTY", "s5_party_fraud_roles_6A", "fraud_role_party"),
        ("ACCOUNT", "s5_account_fraud_roles_6A", "fraud_role_account"),
        ("MERCHANT", "s5_merchant_fraud_roles_6A", "fraud_role_merchant"),
        ("DEVICE", "s5_device_fraud_roles_6A", "fraud_role_device"),
        ("IP", "s5_ip_fraud_roles_6A", "fraud_role_ip"),
    ]
    for entity, ds, col in datasets:
        allowed = role_sets.get(entity, set())
        cnts = con.execute(f"select {col}, count(*)::bigint from {scan(run_root, ds)} group by 1").fetchall()
        ent_total = 0
        ent_mapped = 0
        unmapped_values: list[str] = []
        for role, n in cnts:
            ent_total += int(n or 0)
            if str(role) in allowed:
                ent_mapped += int(n or 0)
            else:
                unmapped_values.append(str(role))
        ent_unmapped = ent_total - ent_mapped
        rows_total += ent_total
        rows_mapped += ent_mapped
        rows_unmapped += ent_unmapped
        per_entity.append(
            {
                "entity_type": entity,
                "rows_total": ent_total,
                "rows_mapped": ent_mapped,
                "rows_unmapped": ent_unmapped,
                "unmapped_roles": sorted(unmapped_values),
                "allowed_roles": sorted(allowed),
            }
        )
    coverage = float(rows_mapped) / float(rows_total) if rows_total > 0 else 0.0
    ok = abs(coverage - 1.0) <= 1e-12 and rows_unmapped == 0
    return {
        "gate": "T6_ROLE_MAPPING_COVERAGE",
        "value": {"mapped_runtime_roles_fraction": coverage, "unmapped_count": rows_unmapped},
        "threshold_B": "coverage=1 and unmapped=0",
        "threshold_Bplus": "coverage=1 and unmapped=0",
        "pass_B": bool(ok),
        "pass_Bplus": bool(ok),
        "status": "PASS" if ok else "FAIL",
        "details": {"rows_total": rows_total, "rows_mapped": rows_mapped, "rows_unmapped": rows_unmapped, "per_entity": per_entity},
    }


def score_t7(con: duckdb.DuckDBPyConnection, run_root: Path, reps: int, rng: np.random.Generator) -> dict[str, Any]:
    s_party = scan(run_root, "s5_party_fraud_roles_6A")
    s_account = scan(run_root, "s5_account_fraud_roles_6A")
    s_device = scan(run_root, "s5_device_fraud_roles_6A")
    s_acc_base = scan(run_root, "s2_account_base_6A")
    s_dev_base = scan(run_root, "s4_device_base_6A")

    a11, a10, a01, a00 = con.execute(
        f"""
        with p as (
          select party_id, case when upper(fraud_role_party) in ('SYNTHETIC_ID','MULE','ASSOCIATE','ORGANISER') then 1 else 0 end as rp
          from {s_party}
        ),
        a as (
          select b.owner_party_id as party_id,
                 case when upper(r.fraud_role_account) in ('DORMANT_RISKY','HIGH_RISK_ACCOUNT','MULE_ACCOUNT') then 1 else 0 end as ra
          from {s_acc_base} b
          join {s_account} r on r.account_id=b.account_id
        )
        select
          sum(case when p.rp=1 and a.ra=1 then 1 else 0 end)::bigint,
          sum(case when p.rp=1 and a.ra=0 then 1 else 0 end)::bigint,
          sum(case when p.rp=0 and a.ra=1 then 1 else 0 end)::bigint,
          sum(case when p.rp=0 and a.ra=0 then 1 else 0 end)::bigint
        from a join p on p.party_id=a.party_id
        """
    ).fetchone()
    d11, d10, d01, d00 = con.execute(
        f"""
        with p as (
          select party_id, case when upper(fraud_role_party) in ('SYNTHETIC_ID','MULE','ASSOCIATE','ORGANISER') then 1 else 0 end as rp
          from {s_party}
        ),
        d as (
          select b.primary_party_id as party_id,
                 case when upper(r.fraud_role_device) in ('REUSED_DEVICE','HIGH_RISK_DEVICE') then 1 else 0 end as rd
          from {s_dev_base} b
          join {s_device} r on r.device_id=b.device_id
        )
        select
          sum(case when p.rp=1 and d.rd=1 then 1 else 0 end)::bigint,
          sum(case when p.rp=1 and d.rd=0 then 1 else 0 end)::bigint,
          sum(case when p.rp=0 and d.rd=1 then 1 else 0 end)::bigint,
          sum(case when p.rp=0 and d.rd=0 then 1 else 0 end)::bigint
        from d join p on p.party_id=d.party_id
        """
    ).fetchone()
    a11_i, a10_i, a01_i, a00_i = int(a11 or 0), int(a10 or 0), int(a01 or 0), int(a00 or 0)
    d11_i, d10_i, d01_i, d00_i = int(d11 or 0), int(d10 or 0), int(d01 or 0), int(d00 or 0)
    or_acc = or_with_smoothing(a11_i, a10_i, a01_i, a00_i)
    or_dev = or_with_smoothing(d11_i, d10_i, d01_i, d00_i)
    acc_low, acc_high = bootstrap_or_ci(a11_i, a10_i, a01_i, a00_i, reps, rng)
    dev_low, dev_high = bootstrap_or_ci(d11_i, d10_i, d01_i, d00_i, reps, rng)
    pass_b = or_acc >= 1.5 and or_dev >= 1.5 and acc_low > 1.0 and dev_low > 1.0
    pass_bp = or_acc >= 2.0 and or_dev >= 2.0 and acc_low > 1.0 and dev_low > 1.0
    return {
        "gate": "T7_RISK_PROPAGATION_EFFECT",
        "value": {"or_account": or_acc, "or_device": or_dev},
        "threshold_B": "OR_account>=1.5 and OR_device>=1.5 and ci_low>1.0",
        "threshold_Bplus": "OR_account>=2.0 and OR_device>=2.0 and ci_low>1.0",
        "pass_B": bool(pass_b),
        "pass_Bplus": bool(pass_bp),
        "status": "PASS" if pass_b else "FAIL",
        "details": {
            "or_account_ci95": {"low": acc_low, "high": acc_high},
            "or_device_ci95": {"low": dev_low, "high": dev_high},
            "account_contingency": {"11": a11_i, "10": a10_i, "01": a01_i, "00": a00_i},
            "device_contingency": {"11": d11_i, "10": d10_i, "01": d01_i, "00": d00_i},
        },
    }


def score_t8(
    con: duckdb.DuckDBPyConnection,
    run_root: Path,
    ip_targets: dict[str, dict[str, float]],
    device_priors: dict[str, Any],
    ip_priors: dict[str, Any],
    fraud_role_taxonomy: dict[str, Any],
    validation_policy: dict[str, Any],
) -> dict[str, Any]:
    s_ip_links = scan(run_root, "s4_ip_links_6A")
    s_ip_base = scan(run_root, "s4_ip_base_6A")
    s_dev_base = scan(run_root, "s4_device_base_6A")
    s_dev_role = scan(run_root, "s5_device_fraud_roles_6A")
    s_ip_role = scan(run_root, "s5_ip_fraud_roles_6A")

    reg_rows = con.execute(
        f"""
        select d.home_region_id, b.ip_type, count(*)::bigint as n
        from {s_ip_links} l
        join {s_ip_base} b on b.ip_id=l.ip_id
        join {s_dev_base} d on d.device_id=l.device_id
        group by 1,2
        """
    ).fetchall()
    reg_counts: dict[str, dict[str, int]] = {}
    reg_totals: dict[str, int] = {}
    for region, ip_type, n in reg_rows:
        r = str(region)
        reg_counts.setdefault(r, {})
        reg_counts[r][str(ip_type)] = int(n or 0)
        reg_totals[r] = reg_totals.get(r, 0) + int(n or 0)
    ip_types = sorted({k for m in reg_counts.values() for k in m.keys()} | {k for m in ip_targets.values() for k in m.keys()})
    obs = np.zeros(len(ip_types), dtype=np.float64)
    tgt = np.zeros(len(ip_types), dtype=np.float64)
    total_links = float(sum(reg_totals.values()))
    if total_links > 0:
        for i, ip in enumerate(ip_types):
            obs[i] = sum(float(m.get(ip, 0)) for m in reg_counts.values()) / total_links
        for region, n in reg_totals.items():
            w = float(n) / total_links
            for i, ip in enumerate(ip_types):
                tgt[i] += w * float(ip_targets.get(region, {}).get(ip, 0.0))
    ip_jsd = jsd(obs, tgt) if total_links > 0 else float("nan")

    role_sets = role_sets_from_taxonomy(fraud_role_taxonomy)
    role_mapping_contract = validation_policy.get("role_mapping_contract", {}) or {}

    def _normalize_map(raw_map: dict[str, Any]) -> dict[str, str]:
        return {str(k): str(v) for k, v in (raw_map or {}).items()}

    device_canonical_roles = set(role_sets.get("DEVICE", set())) or {"CLEAN_DEVICE", "REUSED_DEVICE", "HIGH_RISK_DEVICE"}
    ip_canonical_roles = set(role_sets.get("IP", set())) or {"CLEAN_IP", "SHARED_IP", "HIGH_RISK_IP"}
    device_map = _normalize_map(
        role_mapping_contract.get("device_raw_to_taxonomy")
        or {
            "NORMAL_DEVICE": "CLEAN_DEVICE",
            "RISKY_DEVICE": "HIGH_RISK_DEVICE",
            "BOT_LIKE_DEVICE": "HIGH_RISK_DEVICE",
            "SHARED_SUSPICIOUS_DEVICE": "REUSED_DEVICE",
        }
    )
    ip_map = _normalize_map(
        role_mapping_contract.get("ip_raw_to_taxonomy")
        or {
            "NORMAL_IP": "CLEAN_IP",
            "CORPORATE_NAT_IP": "SHARED_IP",
            "MOBILE_CARRIER_IP": "SHARED_IP",
            "PUBLIC_SHARED_IP": "SHARED_IP",
            "DATACENTRE_IP": "HIGH_RISK_IP",
            "PROXY_IP": "HIGH_RISK_IP",
            "HIGH_RISK_IP": "HIGH_RISK_IP",
        }
    )
    ip_group_match_mode = str(role_mapping_contract.get("ip_group_match_mode") or "by_ip_or_asn")

    dev_group_map = {str(k): str(v) for k, v in ((((device_priors.get("device_groups") or {}).get("device_type_to_group")) or {}).items())}
    dev_probs: dict[tuple[str, str], dict[str, float]] = {}
    for g, tiers in ((((device_priors.get("role_probability_model") or {}).get("pi_role_by_group_and_tier")) or {}).items()):
        for t, rows in (tiers or {}).items():
            probs = {str(x.get("role_id")): float(x.get("prob") or 0.0) for x in (rows or [])}
            s = sum(probs.values())
            dev_probs[(str(g), str(t))] = {k: (v / s if s > 0 else 0.0) for k, v in probs.items()}
    dev_rows = con.execute(
        f"""
        select d.device_type, r.risk_tier, r.fraud_role_device, count(*)::bigint as n
        from {s_dev_role} r
        join {s_dev_base} d on d.device_id=r.device_id
        group by 1,2,3
        """
    ).fetchall()
    dev_roles = sorted(device_canonical_roles)
    dev_obs = {k: 0.0 for k in dev_roles}
    dev_exp = {k: 0.0 for k in dev_roles}
    for dtyp, tier, raw_role, n in dev_rows:
        n_f = float(int(n or 0))
        mapped = device_map.get(str(raw_role), str(raw_role))
        if mapped in dev_obs:
            dev_obs[mapped] += n_f
        probs = dev_probs.get((dev_group_map.get(str(dtyp), ""), str(tier)), {})
        for raw_expected_role, raw_prob in probs.items():
            mapped_expected = device_map.get(str(raw_expected_role), str(raw_expected_role))
            if mapped_expected in dev_exp:
                dev_exp[mapped_expected] += n_f * float(raw_prob)
    dev_jsd = jsd(np.array([dev_obs[k] for k in dev_roles]), np.array([dev_exp[k] for k in dev_roles]))

    ip_group_rules: list[tuple[int, str, set[str], set[str]]] = []
    for row in ((((ip_priors.get("ip_groups") or {}).get("groups")) or [])):
        ip_group_rules.append((int(row.get("group_priority") or 999), str(row.get("group_id")), {str(x) for x in (row.get("ip_types") or [])}, {str(x) for x in (row.get("asn_classes") or [])}))
    ip_group_rules.sort(key=lambda x: x[0])
    ip_probs: dict[tuple[str, str], dict[str, float]] = {}
    for g, tiers in ((((ip_priors.get("role_probability_model") or {}).get("pi_role_by_group_and_tier")) or {}).items()):
        for t, rows in (tiers or {}).items():
            probs = {str(x.get("role_id")): float(x.get("prob") or 0.0) for x in (rows or [])}
            s = sum(probs.values())
            ip_probs[(str(g), str(t))] = {k: (v / s if s > 0 else 0.0) for k, v in probs.items()}
    ip_rows = con.execute(
        f"""
        select b.ip_type, b.asn_class, r.risk_tier, r.fraud_role_ip, count(*)::bigint as n
        from {s_ip_role} r
        join {s_ip_base} b on b.ip_id=r.ip_id
        group by 1,2,3,4
        """
    ).fetchall()
    ip_roles = sorted(ip_canonical_roles)
    ip_obs = {k: 0.0 for k in ip_roles}
    ip_exp = {k: 0.0 for k in ip_roles}
    unresolved_rows = 0
    for ip_type, asn_class, tier, raw_role, n in ip_rows:
        n_f = float(int(n or 0))
        mapped = ip_map.get(str(raw_role), str(raw_role))
        if mapped in ip_obs:
            ip_obs[mapped] += n_f
        group_id = None
        for _, gid, ip_set, asn_set in ip_group_rules:
            if ip_group_match_mode == "by_ip_and_asn":
                matched = str(ip_type) in ip_set and str(asn_class) in asn_set
            else:
                matched = str(ip_type) in ip_set or str(asn_class) in asn_set
            if matched:
                group_id = gid
                break
        if group_id is None:
            unresolved_rows += int(n_f)
            continue
        probs = ip_probs.get((group_id, str(tier)), {})
        for raw_expected_role, raw_prob in probs.items():
            mapped_expected = ip_map.get(str(raw_expected_role), str(raw_expected_role))
            if mapped_expected in ip_exp:
                ip_exp[mapped_expected] += n_f * float(raw_prob)
    ip_role_jsd = jsd(np.array([ip_obs[k] for k in ip_roles]), np.array([ip_exp[k] for k in ip_roles]))

    components = {"ip_type_jsd": ip_jsd, "device_role_jsd": dev_jsd, "ip_role_jsd": ip_role_jsd}
    worst = max(float(v) for v in components.values())
    return {
        "gate": "T8_DISTRIBUTION_ALIGNMENT_JSD",
        "value": worst,
        "threshold_B": "<= 0.08",
        "threshold_Bplus": "<= 0.05",
        "pass_B": bool(worst <= 0.08),
        "pass_Bplus": bool(worst <= 0.05),
        "status": "PASS" if worst <= 0.08 else "FAIL",
        "details": {
            "components": components,
            "ip_unresolved_group_rows": unresolved_rows,
            "ip_group_match_mode": ip_group_match_mode,
            "t8_compare_space": "canonical_taxonomy",
        },
    }


def score_t9_insufficient() -> dict[str, Any]:
    return {
        "gate": "T9_CROSS_SEED_STABILITY",
        "value": None,
        "threshold_B": "<= 0.25",
        "threshold_Bplus": "<= 0.15",
        "pass_B": False,
        "pass_Bplus": False,
        "status": "INSUFFICIENT_EVIDENCE",
        "details": {"reason": "single-seed lane only; required seeds {42,7,101,202} not present"},
    }


def score_t10(run_root: Path, manifest_fingerprint: str) -> dict[str, Any]:
    report_path = (
        run_root
        / "data/layer3/6B/validation"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "s5_validation_report_6B.json"
    )
    if not report_path.exists():
        return {
            "gate": "T10_DOWNSTREAM_COMPAT_6B",
            "value": None,
            "threshold_B": "must pass",
            "threshold_Bplus": "must pass",
            "pass_B": False,
            "pass_Bplus": False,
            "status": "INSUFFICIENT_EVIDENCE",
            "details": {"reason": "6B validation artifact missing under same run-id", "expected_path": str(report_path)},
        }
    payload = load_json(report_path)
    ok = str(payload.get("overall_status", "")).upper() == "PASS"
    return {
        "gate": "T10_DOWNSTREAM_COMPAT_6B",
        "value": {"overall_status_6B": str(payload.get("overall_status"))},
        "threshold_B": "must pass",
        "threshold_Bplus": "must pass",
        "pass_B": bool(ok),
        "pass_Bplus": bool(ok),
        "status": "PASS" if ok else "FAIL",
        "details": {"validation_report_6B": str(report_path)},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 6A P0 baseline realism gateboard.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_6A")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_6A/reports")
    parser.add_argument("--bootstrap-reps", type=int, default=BOOTSTRAP_REPS_DEFAULT)
    parser.add_argument("--bootstrap-seed", type=int, default=42)
    args = parser.parse_args()

    run_root = Path(args.runs_root) / str(args.run_id).strip()
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")
    receipt = load_json(run_root / "run_receipt.json")
    manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
    parameter_hash = str(receipt.get("parameter_hash") or "")
    seed = int(receipt.get("seed") or 0)
    if not manifest_fingerprint or not parameter_hash:
        raise ValueError("run_receipt missing manifest_fingerprint/parameter_hash")

    kmax_priors = load_yaml(Path("config/layer3/6A/priors/account_per_party_priors_6A.v1.yaml"))
    ip_count_priors = load_yaml(Path("config/layer3/6A/priors/ip_count_priors_6A.v1.yaml"))
    device_role_priors = load_yaml(Path("config/layer3/6A/priors/device_role_priors_6A.v1.yaml"))
    ip_role_priors = load_yaml(Path("config/layer3/6A/priors/ip_role_priors_6A.v1.yaml"))
    fraud_role_taxonomy = load_yaml(Path("config/layer3/6A/taxonomy/fraud_role_taxonomy_6A.v1.yaml"))
    validation_policy = load_yaml(Path("config/layer3/6A/policy/validation_policy_6A.v1.yaml"))

    kmax_rows = parse_kmax(kmax_priors)
    ip_targets = parse_ip_targets(ip_count_priors)
    if not kmax_rows:
        raise ValueError("No Kmax rules loaded from account_per_party_priors_6A.v1.yaml")
    if not ip_targets:
        raise ValueError("No ip_type targets loaded from ip_count_priors_6A.v1.yaml")

    rng = np.random.default_rng(int(args.bootstrap_seed))
    con = duckdb.connect()
    try:
        t1, t2 = score_t1_t2(con, run_root, kmax_rows)
        t3, t4, t5 = score_t3_t4_t5(con, run_root, ip_targets, int(args.bootstrap_reps), rng)
        t6 = score_t6(con, run_root, role_sets_from_taxonomy(fraud_role_taxonomy))
        t7 = score_t7(con, run_root, int(args.bootstrap_reps), rng)
        t8 = score_t8(
            con,
            run_root,
            ip_targets,
            device_role_priors,
            ip_role_priors,
            fraud_role_taxonomy,
            validation_policy,
        )
    finally:
        con.close()
    t9 = score_t9_insufficient()
    t10 = score_t10(run_root, manifest_fingerprint)

    gates_list = [t1, t2, t3, t4, t5, t6, t7, t8, t9, t10]
    gates = {g["gate"]: g for g in gates_list}
    failed_b = [g["gate"] for g in gates_list if not bool(g.get("pass_B"))]
    failed_bp = [g["gate"] for g in gates_list if not bool(g.get("pass_Bplus"))]
    eligible_grade = "B_plus" if not failed_bp else ("B" if not failed_b else "below_B")
    decision = "UNLOCK_P1" if not failed_b else "HOLD_REMEDIATE"

    payload = {
        "generated_at_utc": now_utc(),
        "segment": "6A",
        "phase": "P0",
        "run_context": {
            "runs_root": str(Path(args.runs_root)),
            "run_id": str(args.run_id),
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
        },
        "authority_sources": {
            "published_report": "docs/reports/eda/segment_6A/segment_6A_published_report.md",
            "remediation_report": "docs/reports/eda/segment_6A/segment_6A_remediation_report.md",
            "published_baseline_run_id": BASELINE_REPORT_RUN_ID,
        },
        "gates": gates,
        "summary": {
            "phase_gate": "P0",
            "eligible_grade": eligible_grade,
            "pass_B": len(failed_b) == 0,
            "pass_Bplus": len(failed_bp) == 0,
            "failed_gates_for_B": failed_b,
            "failed_gates_for_Bplus": failed_bp,
            "decision": decision,
        },
    }

    out_path = Path(args.out_root) / f"segment6a_p0_realism_gateboard_{args.run_id}.json"
    write_json(out_path, payload)
    print(str(out_path))
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()

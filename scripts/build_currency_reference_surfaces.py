#!/usr/bin/env python3
"""Build ISO legal tender and currency share reference surfaces for 2024Q4."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import polars as pl


ROOT = Path(__file__).resolve().parents[1]


SIX_XLS_URL = "https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xls"
SIX_XML_URL = "https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml"
WDI_GDP_URL = "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD?format=json&per_page=20000"
BIS_D11_2_URL = "https://data.bis.org/api/v0/publication_tables/BIS,DER_D11_2,1.0"
BIS_D11_3_URL = "https://data.bis.org/api/v0/publication_tables/BIS,DER_D11_3,1.0"


NON_TENDER_CODES = {
    "XXX",
    "XTS",
    "XDR",
    "XAU",
    "XAG",
    "XPT",
    "XPD",
    "XBA",
    "XBB",
    "XBC",
    "XBD",
    "XSU",
    "XUA",
    "XFU",
    "BOV",
    "CHE",
    "CHW",
    "CLF",
    "COU",
    "MXV",
    "USN",
    "UYI",
}


ALIAS_MAP = {
    "BOLIVIA PLURINATIONAL STATE OF": "BOLIVIA",
    "BRUNEI DARUSSALAM": "BRUNEI",
    "CONGO DEMOCRATIC REPUBLIC OF": "DEMOCRATIC REPUBLIC OF THE CONGO",
    "CONGO": "REPUBLIC OF THE CONGO",
    "COTE D IVOIRE": "IVORY COAST",
    "IRAN ISLAMIC REPUBLIC OF": "IRAN",
    "KOREA REPUBLIC OF": "SOUTH KOREA",
    "KOREA DEMOCRATIC PEOPLE S REPUBLIC OF": "NORTH KOREA",
    "LAO PEOPLE S DEMOCRATIC REPUBLIC": "LAOS",
    "MICRONESIA FEDERATED STATES OF": "MICRONESIA",
    "MOLDOVA REPUBLIC OF": "MOLDOVA",
    "PALESTINE STATE OF": "PALESTINIAN TERRITORY",
    "RUSSIAN FEDERATION": "RUSSIA",
    "SINT MAARTEN DUTCH PART": "SINT MAARTEN",
    "TANZANIA UNITED REPUBLIC OF": "TANZANIA",
    "TURKIYE": "TURKEY",
    "VENEZUELA BOLIVARIAN REPUBLIC OF": "VENEZUELA",
    "VIET NAM": "VIETNAM",
    "UNITED STATES OF AMERICA": "UNITED STATES",
    "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND": "UNITED KINGDOM",
    "BONAIRE SINT EUSTATIUS AND SABA": "BONAIRE SAINT EUSTATIUS AND SABA",
}


def _sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, target: Path) -> Tuple[str, str]:
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = urllib.request.urlopen(url).read()
    target.write_bytes(raw)
    ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return _sha256_bytes(raw), ts


def _normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.upper()
    text = text.replace("&", "AND")
    text = re.sub(r"[\'\.,()\ -]", " ", text)
    text = re.sub(r"\bTHE\b", " ", text)
    text = re.sub(r"\\s+", " ", text).strip()
    return text


def _build_iso_map(iso_table: pl.DataFrame) -> Tuple[Dict[str, str], Dict[str, str]]:
    normalized = {}
    alpha3_map = {}
    for row in iso_table.iter_rows(named=True):
        iso2 = row["country_iso"]
        name = row["name"]
        alpha3 = row["alpha3"]
        if name is None or iso2 is None:
            continue
        norm = _normalize_name(str(name))
        if norm in normalized and normalized[norm] != iso2:
            raise RuntimeError(f"ISO normalization collision for {norm}")
        normalized[norm] = iso2
        if alpha3:
            alpha3_map[str(alpha3)] = iso2
    return normalized, alpha3_map


def _apply_alias(norm: str) -> str:
    return _normalize_name(ALIAS_MAP.get(norm, norm))


def _parse_six_list_one(xml_path: Path) -> Tuple[str, List[dict]]:
    root = ET.fromstring(xml_path.read_bytes())
    published = root.attrib.get("Pblshd", "")
    rows = []
    ccy_tbl = root.find("CcyTbl")
    if ccy_tbl is None:
        raise RuntimeError("SIX XML missing CcyTbl node")
    for entry in ccy_tbl.findall("CcyNtry"):
        entity = entry.findtext("CtryNm")
        currency = entry.findtext("Ccy")
        currency_num = entry.findtext("CcyNbr")
        minor_units = entry.findtext("CcyMnrUnts")
        if entity is None or currency is None:
            continue
        rows.append(
            {
                "entity": entity.strip(),
                "currency": currency.strip(),
                "currency_numeric": currency_num.strip() if currency_num else None,
                "minor_units": minor_units.strip() if minor_units else None,
            }
        )
    return published, rows


def _load_wdi_gdp(source_path: Path, iso3_map: Dict[str, str]) -> Dict[str, float]:
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or len(payload) < 2:
        raise RuntimeError("Unexpected WDI payload")
    data = payload[1]
    gdp_by_iso2: Dict[str, float] = {}
    for row in data:
        if row.get("date") != "2024":
            continue
        iso3 = row.get("countryiso3code")
        value = row.get("value")
        if not iso3 or value is None:
            continue
        iso2 = iso3_map.get(iso3)
        if iso2 is None:
            continue
        try:
            gdp_val = float(value)
        except (TypeError, ValueError):
            continue
        if gdp_val > 0:
            gdp_by_iso2[iso2] = gdp_val
    return gdp_by_iso2


def _parse_bis_table(source_path: Path) -> dict:
    return json.loads(source_path.read_text(encoding="utf-8"))


def _find_bis_column(columns: list, year: str, child_name: str | None = None) -> str:
    for col in columns:
        if col.get("header_name") == year:
            if child_name is None:
                return str(col["field"])
            for child in col.get("children", []):
                if child.get("header_name") == child_name:
                    return str(child["field"])
    raise RuntimeError(f"BIS column not found for year={year} child={child_name}")


def _parse_bis_values(items: list, field_id: str) -> Dict[str, float]:
    values: Dict[str, float] = {}
    for item in items:
        label = item.get("level_1") or item.get("level1")
        if not label:
            continue
        cell = item.get(field_id, {})
        value = cell.get("value") if isinstance(cell, dict) else None
        if value is None:
            continue
        text = str(value).replace(",", "").strip()
        if text in {"", "..."}:
            continue
        try:
            values[label] = float(text)
        except ValueError:
            continue
    return values


def _largest_remainder_allocation(
    total: int, shares: List[Tuple[str, float]]
) -> Dict[str, int]:
    raw = [(iso, total * share) for iso, share in shares]
    floors = {iso: int(math.floor(val)) for iso, val in raw}
    residuals = [(iso, val - floors[iso]) for iso, val in raw]
    remaining = total - sum(floors.values())
    residuals.sort(key=lambda x: (-x[1], x[0]))
    for iso, _ in residuals[:remaining]:
        floors[iso] += 1
    return floors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iso-path", default="reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet")
    args = parser.parse_args()

    iso_table = pl.read_parquet(ROOT / args.iso_path)
    iso_name_map, iso3_map = _build_iso_map(iso_table)

    iso_legal_dir = ROOT / "reference" / "iso" / "iso_legal_tender" / "2024"
    iso_legal_source = iso_legal_dir / "source"
    iso_legal_source.mkdir(parents=True, exist_ok=True)

    ccy_dir = ROOT / "reference" / "network" / "ccy_country_shares" / "2024Q4"
    ccy_source = ccy_dir / "source"
    ccy_source.mkdir(parents=True, exist_ok=True)

    settlement_dir = ROOT / "reference" / "network" / "settlement_shares" / "2024Q4"
    settlement_source = settlement_dir / "source"
    settlement_source.mkdir(parents=True, exist_ok=True)

    six_xml_path = iso_legal_source / "list-one.xml"
    six_sha, six_ts = _download(SIX_XML_URL, six_xml_path)
    ccy_xml_path = ccy_source / "list-one.xml"
    if not ccy_xml_path.exists():
        ccy_xml_path.write_bytes(six_xml_path.read_bytes())

    published_date, six_rows = _parse_six_list_one(six_xml_path)
    published_year = int(published_date.split("-")[0]) if published_date else None
    iso_legal_exact = published_year == 2024
    ccy_exact = published_year == 2024 and int(published_date.split("-")[1]) >= 10 if published_date else False

    unmapped_entities: List[str] = []
    entity_map: Dict[str, str] = {}
    for row in six_rows:
        norm = _normalize_name(row["entity"])
        norm = _apply_alias(norm)
        iso2 = iso_name_map.get(norm)
        if iso2 is None:
            unmapped_entities.append(row["entity"])
            continue
        entity_map[row["entity"]] = iso2

    records: Dict[str, List[dict]] = {}
    for row in six_rows:
        iso2 = entity_map.get(row["entity"])
        if iso2 is None:
            continue
        currency = row["currency"]
        if currency in NON_TENDER_CODES:
            continue
        records.setdefault(iso2, []).append(row)

    dropped_no_tender: List[str] = []
    tender_rows: List[dict] = []
    for iso2, entries in sorted(records.items()):
        candidates = []
        for entry in entries:
            currency = entry["currency"]
            if not re.fullmatch(r"[A-Z]{3}", currency or ""):
                continue
            minor = entry["minor_units"]
            minor_val = None
            if minor is not None and minor.isdigit():
                minor_val = int(minor)
            candidates.append((currency, entry, minor_val))
        if not candidates:
            dropped_no_tender.append(iso2)
            continue
        candidates.sort(
            key=lambda x: (
                0 if x[2] in {0, 1, 2, 3} else 1,
                x[0],
            )
        )
        currency, entry, minor_val = candidates[0]
        numeric_val = None
        if entry["currency_numeric"] and entry["currency_numeric"].isdigit():
            numeric_val = int(entry["currency_numeric"])
        tender_rows.append(
            {
                "country_iso": iso2,
                "currency": currency,
                "currency_numeric": numeric_val,
                "minor_units": minor_val,
                "source_vintage": f"SIX_List_One_{published_date}" if published_date else "SIX_List_One",
                "is_exact_vintage": iso_legal_exact,
            }
        )

    tender_df = pl.DataFrame(tender_rows).sort("country_iso")
    iso_legal_path = iso_legal_dir / "iso_legal_tender.parquet"
    tender_df.write_parquet(iso_legal_path)

    iso_legal_prov = {
        "source_urls": [SIX_XML_URL],
        "downloaded_at_utc": six_ts,
        "published_date": published_date,
        "raw_sha256": six_sha,
        "output_sha256": _sha256_file(iso_legal_path),
        "unmapped_entities": sorted(set(unmapped_entities)),
        "dropped_no_tender": dropped_no_tender,
        "is_exact_vintage": iso_legal_exact,
    }
    (iso_legal_dir / "iso_legal_tender.provenance.json").write_text(
        json.dumps(iso_legal_prov, indent=2, sort_keys=True), encoding="utf-8"
    )

    gdp_json_path = ccy_source / "NY.GDP.MKTP.CD_2024.json"
    gdp_sha, gdp_ts = _download(WDI_GDP_URL, gdp_json_path)
    gdp_weights = _load_wdi_gdp(gdp_json_path, iso3_map)

    bis_d11_3_path = ccy_source / "BIS_DER_D11_3_2022.json"
    bis3_sha, bis3_ts = _download(BIS_D11_3_URL, bis_d11_3_path)
    bis3 = _parse_bis_table(bis_d11_3_path)
    bis3_field_pct = _find_bis_column(bis3["columns"], "2022", "%")
    bis3_values = _parse_bis_values(bis3["items"], bis3_field_pct)

    membership: Dict[str, List[str]] = {}
    for row in six_rows:
        iso2 = entity_map.get(row["entity"])
        if iso2 is None:
            continue
        currency = row["currency"]
        if currency in NON_TENDER_CODES:
            continue
        if not re.fullmatch(r"[A-Z]{3}", currency or ""):
            continue
        membership.setdefault(currency, [])
        if iso2 not in membership[currency]:
            membership[currency].append(iso2)

    ccy_rows: List[dict] = []
    for currency, members in sorted(membership.items()):
        members = sorted(members)
        weights = []
        for iso2 in members:
            weight = gdp_weights.get(iso2, 1.0e9)
            weights.append(weight)
        total = sum(weights)
        shares = [w / total for w in weights]
        if len(members) == 1:
            shares = [1.0]

        share_rows = list(zip(members, shares))
        obs_count_total = 5000
        if currency in bis3_values and bis3_values[currency] > 0:
            bis_total = sum(v for v in bis3_values.values() if v > 0)
            share = bis3_values[currency] / bis_total
            obs_count_total = int(round(2_000_000 * share))
            obs_count_total = max(5000, min(250_000, obs_count_total))
        alloc = _largest_remainder_allocation(obs_count_total, share_rows)
        for iso2, share in share_rows:
            ccy_rows.append(
                {
                    "currency": currency,
                    "country_iso": iso2,
                    "share": float(share),
                    "obs_count": int(alloc[iso2]),
                }
            )

    ccy_df = pl.DataFrame(ccy_rows).sort(["currency", "country_iso"])
    ccy_path = ccy_dir / "ccy_country_shares.parquet"
    ccy_df.write_parquet(ccy_path)

    ccy_prov = {
        "source_urls": [SIX_XML_URL, WDI_GDP_URL, BIS_D11_3_URL],
        "downloaded_at_utc": {
            "six": six_ts,
            "wdi_gdp": gdp_ts,
            "bis_d11_3": bis3_ts,
        },
        "published_date": published_date,
        "raw_sha256": {
            "six": six_sha,
            "wdi_gdp": gdp_sha,
            "bis_d11_3": bis3_sha,
        },
        "indicator": "NY.GDP.MKTP.CD",
        "indicator_year": 2024,
        "w_floor": 1.0e9,
        "obs_count_policy": {
            "source": "BIS D11.3 2022",
            "N_total_ccy": 2_000_000,
            "N_min": 5000,
            "N_max": 250_000,
        },
        "unmapped_entities": sorted(set(unmapped_entities)),
        "output_sha256": _sha256_file(ccy_path),
        "is_exact_vintage": ccy_exact,
    }
    (ccy_dir / "ccy_country_shares.provenance.json").write_text(
        json.dumps(ccy_prov, indent=2, sort_keys=True), encoding="utf-8"
    )

    bis_d11_2_path = settlement_source / "BIS_DER_D11_2_2022.json"
    bis2_sha, bis2_ts = _download(BIS_D11_2_URL, bis_d11_2_path)
    bis2 = _parse_bis_table(bis_d11_2_path)
    bis2_field = _find_bis_column(bis2["columns"], "2022")
    bis2_values = _parse_bis_values(bis2["items"], bis2_field)

    hub_values: List[Tuple[str, float]] = []
    unmapped_hubs: List[str] = []
    for name, value in bis2_values.items():
        norm = _normalize_name(name)
        norm = _apply_alias(norm)
        iso2 = iso_name_map.get(norm)
        if iso2 is None:
            unmapped_hubs.append(name)
            continue
        hub_values.append((iso2, value))
    hub_values.sort(key=lambda x: x[1], reverse=True)
    hub_values = hub_values[:20]
    hub_total = sum(v for _, v in hub_values)
    hub_weights = {iso2: v / hub_total for iso2, v in hub_values if hub_total > 0}

    bis3_path = settlement_source / "BIS_DER_D11_3_2022.json"
    if not bis3_path.exists():
        bis3_path.write_bytes(bis_d11_3_path.read_bytes())
    bis3_sha_settle = _sha256_file(bis3_path)

    settlement_rows: List[dict] = []
    for currency in sorted(ccy_df["currency"].unique().to_list()):
        cur_rows = ccy_df.filter(pl.col("currency") == currency).sort("country_iso")
        base = cur_rows["share"].to_list()
        members = cur_rows["country_iso"].to_list()
        base_map = {iso2: float(share) for iso2, share in zip(members, base)}
        max_base = max(base)

        hub_mass = 0.70 if max_base < 0.90 else 0.40
        hub_members = [iso2 for iso2 in members if iso2 in hub_weights]
        if hub_members:
            hub_norm_total = sum(hub_weights[iso2] for iso2 in hub_members)
            hub_map = {iso2: hub_weights[iso2] / hub_norm_total for iso2 in hub_members}
            blended = {}
            for iso2 in members:
                hub_val = hub_map.get(iso2, 0.0)
                blended[iso2] = hub_mass * hub_val + (1.0 - hub_mass) * base_map[iso2]
            total = sum(blended.values())
            blended = {iso2: val / total for iso2, val in blended.items()}
        else:
            blended = base_map

        bis_total = sum(v for v in bis3_values.values() if v > 0)
        obs_total = 25_000
        if currency in bis3_values and bis3_values[currency] > 0:
            share = bis3_values[currency] / bis_total
            obs_total = int(round(10_000_000 * share))
            obs_total = max(25_000, min(2_000_000, obs_total))

        share_rows = [(iso2, blended[iso2]) for iso2 in members]
        alloc = _largest_remainder_allocation(obs_total, share_rows)
        for iso2, share in share_rows:
            settlement_rows.append(
                {
                    "currency": currency,
                    "country_iso": iso2,
                    "share": float(share),
                    "obs_count": int(alloc[iso2]),
                }
            )

    settlement_df = pl.DataFrame(settlement_rows).sort(["currency", "country_iso"])
    settlement_path = settlement_dir / "settlement_shares.parquet"
    settlement_df.write_parquet(settlement_path)

    settlement_prov = {
        "route": "B",
        "time_window": "2024Q4",
        "currency_universe_source": str(ccy_path.as_posix()),
        "currency_universe_sha256": _sha256_file(ccy_path),
        "hub_source": "BIS D11.2 2022",
        "hub_top_n": 20,
        "hub_mass_default": 0.70,
        "hub_mass_if_concentrated": 0.40,
        "hub_countries": [iso2 for iso2, _ in hub_values],
        "evidence_policy": {
            "source": "BIS D11.3 2022",
            "N_total": 10_000_000,
            "N_min": 25_000,
            "N_max": 2_000_000,
        },
        "downloaded_at_utc": {
            "bis_d11_2": bis2_ts,
            "bis_d11_3": bis3_ts,
        },
        "raw_sha256": {
            "bis_d11_2": bis2_sha,
            "bis_d11_3": bis3_sha_settle,
        },
        "unmapped_hub_entities": sorted(set(unmapped_hubs)),
        "output_sha256": _sha256_file(settlement_path),
    }
    (settlement_dir / "settlement_shares.provenance.json").write_text(
        json.dumps(settlement_prov, indent=2, sort_keys=True), encoding="utf-8"
    )


if __name__ == "__main__":
    main()

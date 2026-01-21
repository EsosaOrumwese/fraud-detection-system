"""Numba kernel for 5B.S4 arrival expansion."""

from __future__ import annotations

import numpy as np

try:  # pragma: no cover - optional accel
    import numba as nb

    NUMBA_AVAILABLE = True
except Exception:  # pragma: no cover - numba not installed
    nb = None
    NUMBA_AVAILABLE = False


UINT64_MASK = np.uint64(0xFFFFFFFFFFFFFFFF)
PHILOX_M0 = np.uint64(0xD2B74407B1CE6E93)
PHILOX_W0 = np.uint64(0x9E3779B97F4A7C15)
INV_TWO_POW_64 = 1.0 / 18446744073709551616.0
MICROS_PER_SECOND = 1_000_000
MICROS_PER_MINUTE = 60 * MICROS_PER_SECOND


if NUMBA_AVAILABLE:

    @nb.njit(cache=True)
    def _mul_hi_lo(a: np.uint64, b: np.uint64) -> tuple[np.uint64, np.uint64]:
        product = a * b
        lo = product & UINT64_MASK
        hi = (product >> np.uint64(64)) & UINT64_MASK
        return hi, lo

    @nb.njit(cache=True)
    def philox2x64_10(counter_hi: np.uint64, counter_lo: np.uint64, key: np.uint64) -> tuple[np.uint64, np.uint64]:
        c0 = counter_lo & UINT64_MASK
        c1 = counter_hi & UINT64_MASK
        k0 = key & UINT64_MASK
        for _ in range(10):
            hi, lo = _mul_hi_lo(PHILOX_M0, c0)
            c0 = (hi ^ k0 ^ c1) & UINT64_MASK
            c1 = lo
            k0 = (k0 + PHILOX_W0) & UINT64_MASK
        return c0, c1

    @nb.njit(cache=True)
    def add_u128(counter_hi: np.uint64, counter_lo: np.uint64, increment: np.uint64) -> tuple[np.uint64, np.uint64]:
        total_lo = counter_lo + increment
        new_lo = total_lo & UINT64_MASK
        carry = total_lo >> np.uint64(64)
        new_hi = (counter_hi + carry) & UINT64_MASK
        return new_hi, new_lo

    @nb.njit(cache=True)
    def u01_from_u64(value: np.uint64) -> float:
        return (float(value) + 0.5) * INV_TWO_POW_64

    @nb.njit(cache=True)
    def _alias_pick(prob: np.ndarray, alias: np.ndarray, u: float, offset: int, length: int) -> int:
        if length <= 1:
            return 0
        scaled = u * float(length)
        j = int(scaled)
        if j >= length:
            j = length - 1
        threshold = scaled - float(j)
        if threshold < prob[offset + j]:
            return j
        return int(alias[offset + j])

    @nb.njit(cache=True)
    def _tz_offset_minutes(
        tz_index_start: np.ndarray,
        tz_index_count: np.ndarray,
        tz_transitions_utc: np.ndarray,
        tz_offsets_minutes: np.ndarray,
        tzid_idx: int,
        ts_utc_seconds: int,
    ) -> int:
        start = int(tz_index_start[tzid_idx])
        count = int(tz_index_count[tzid_idx])
        if count <= 0:
            return 0
        lo = 0
        hi = count - 1
        pos = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            value = int(tz_transitions_utc[start + mid])
            if value <= ts_utc_seconds:
                pos = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return int(tz_offsets_minutes[start + pos])

    @nb.njit(cache=True)
    def _lookup_site_table(
        merchant_idx: int,
        tzid_idx: int,
        site_map_start: np.ndarray,
        site_map_count: np.ndarray,
        site_map_tzid: np.ndarray,
        site_map_table_index: np.ndarray,
    ) -> int:
        start = int(site_map_start[merchant_idx])
        count = int(site_map_count[merchant_idx])
        if count <= 0:
            return -1
        lo = 0
        hi = count - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            value = int(site_map_tzid[start + mid])
            if value == tzid_idx:
                return int(site_map_table_index[start + mid])
            if value < tzid_idx:
                lo = mid + 1
            else:
                hi = mid - 1
        return -1

    @nb.njit(parallel=True, nogil=True, cache=True)
    def expand_arrivals(
        row_offsets: np.ndarray,
        counts: np.ndarray,
        bucket_start_us: np.ndarray,
        bucket_duration_us: np.ndarray,
        merchant_ids: np.ndarray,
        merchant_indices: np.ndarray,
        zone_rep_indices: np.ndarray,
        bucket_indices: np.ndarray,
        row_seq_start: np.ndarray,
        time_keys: np.ndarray,
        time_ctr_hi: np.ndarray,
        time_ctr_lo: np.ndarray,
        site_keys: np.ndarray,
        site_ctr_hi: np.ndarray,
        site_ctr_lo: np.ndarray,
        edge_keys: np.ndarray,
        edge_ctr_hi: np.ndarray,
        edge_ctr_lo: np.ndarray,
        group_table_index: np.ndarray,
        group_table_offsets: np.ndarray,
        group_table_lengths: np.ndarray,
        group_prob: np.ndarray,
        group_alias: np.ndarray,
        group_tzid: np.ndarray,
        site_map_start: np.ndarray,
        site_map_count: np.ndarray,
        site_map_tzid: np.ndarray,
        site_map_table_index: np.ndarray,
        site_table_offsets: np.ndarray,
        site_table_lengths: np.ndarray,
        site_prob: np.ndarray,
        site_alias: np.ndarray,
        site_ids: np.ndarray,
        site_tzids: np.ndarray,
        edge_table_index: np.ndarray,
        edge_table_offsets: np.ndarray,
        edge_table_lengths: np.ndarray,
        edge_prob: np.ndarray,
        edge_alias: np.ndarray,
        edge_edge_index: np.ndarray,
        edge_tzids: np.ndarray,
        merchant_virtual_mode: np.ndarray,
        merchant_settlement_tzid: np.ndarray,
        tz_index_start: np.ndarray,
        tz_index_count: np.ndarray,
        tz_transitions_utc: np.ndarray,
        tz_offsets_minutes: np.ndarray,
        p_virtual_hybrid: float,
        out_ts_utc_us: np.ndarray,
        out_arrival_seq: np.ndarray,
        out_is_virtual: np.ndarray,
        out_site_id: np.ndarray,
        out_edge_index: np.ndarray,
        out_tzid_primary: np.ndarray,
        out_tzid_operational: np.ndarray,
        out_tzid_settlement: np.ndarray,
        out_ts_local_primary_us: np.ndarray,
        out_ts_local_operational_us: np.ndarray,
        out_ts_local_settlement_us: np.ndarray,
        out_merchant_id: np.ndarray,
        out_bucket_index: np.ndarray,
        out_zone_rep_index: np.ndarray,
        out_lambda_realised: np.ndarray,
        row_virtual_counts: np.ndarray,
        row_errors: np.ndarray,
        lambda_realised_rows: np.ndarray,
    ) -> None:
        rows = counts.shape[0]
        for row_idx in nb.prange(rows):
            count = int(counts[row_idx])
            if count <= 0:
                continue
            out_offset = int(row_offsets[row_idx])
            base_start = int(bucket_start_us[row_idx])
            duration_us = int(bucket_duration_us[row_idx])
            merchant_id = merchant_ids[row_idx]
            merchant_idx = int(merchant_indices[row_idx])
            zone_rep_idx = int(zone_rep_indices[row_idx])
            bucket_index = int(bucket_indices[row_idx])
            seq_start = int(row_seq_start[row_idx])
            time_key = np.uint64(time_keys[row_idx])
            time_hi = np.uint64(time_ctr_hi[row_idx])
            time_lo = np.uint64(time_ctr_lo[row_idx])
            site_key = np.uint64(site_keys[row_idx])
            site_hi = np.uint64(site_ctr_hi[row_idx])
            site_lo = np.uint64(site_ctr_lo[row_idx])
            edge_key = np.uint64(edge_keys[row_idx])
            edge_hi = np.uint64(edge_ctr_hi[row_idx])
            edge_lo = np.uint64(edge_ctr_lo[row_idx])
            group_idx = int(group_table_index[row_idx])
            group_offset = 0
            group_length = 0
            if group_idx >= 0:
                group_offset = int(group_table_offsets[group_idx])
                group_length = int(group_table_lengths[group_idx])
            virtual_mode = int(merchant_virtual_mode[merchant_idx])
            settlement_tzid = int(merchant_settlement_tzid[merchant_idx])
            edge_table_idx = int(edge_table_index[merchant_idx])
            site_start = int(site_map_start[merchant_idx])
            site_count = int(site_map_count[merchant_idx])
            default_site_table_idx = -1
            if site_count > 0:
                default_site_table_idx = int(site_map_table_index[site_start])
            edge_offset = 0
            virtual_seen = 0
            row_error = 0
            for j in range(count):
                out_idx = out_offset + j
                t_hi, t_lo = add_u128(time_hi, time_lo, np.uint64(j))
                t0, _t1 = philox2x64_10(t_hi, t_lo, time_key)
                u_time = u01_from_u64(t0)
                jitter_us = int(u_time * float(duration_us))
                if jitter_us >= duration_us:
                    jitter_us = duration_us - 1
                ts_utc_us = base_start + jitter_us

                out_ts_utc_us[out_idx] = ts_utc_us
                out_arrival_seq[out_idx] = seq_start + j + 1
                out_merchant_id[out_idx] = merchant_id
                out_bucket_index[out_idx] = bucket_index
                out_zone_rep_index[out_idx] = zone_rep_idx
                out_lambda_realised[out_idx] = lambda_realised_rows[row_idx]

                s_hi, s_lo = add_u128(site_hi, site_lo, np.uint64(j))
                s0, s1 = philox2x64_10(s_hi, s_lo, site_key)
                u0 = u01_from_u64(s0)
                u1 = u01_from_u64(s1)

                is_virtual = False
                if virtual_mode == 2:
                    is_virtual = True
                elif virtual_mode == 1:
                    is_virtual = u0 < p_virtual_hybrid

                out_is_virtual[out_idx] = is_virtual
                if is_virtual:
                    if edge_table_idx < 0:
                        if default_site_table_idx >= 0:
                            is_virtual = False
                            out_is_virtual[out_idx] = False
                        else:
                            row_error = 2
                            out_site_id[out_idx] = 0
                            out_edge_index[out_idx] = -1
                            out_tzid_primary[out_idx] = -1
                            out_tzid_operational[out_idx] = -1
                            out_tzid_settlement[out_idx] = -1
                            out_ts_local_primary_us[out_idx] = -1
                            out_ts_local_operational_us[out_idx] = -1
                            out_ts_local_settlement_us[out_idx] = -1
                            continue
                if is_virtual:
                    e_hi, e_lo = add_u128(edge_hi, edge_lo, np.uint64(edge_offset))
                    e0, _e1 = philox2x64_10(e_hi, e_lo, edge_key)
                    u_edge = u01_from_u64(e0)
                    edge_offset += 1
                    table_offset = int(edge_table_offsets[edge_table_idx])
                    table_length = int(edge_table_lengths[edge_table_idx])
                    edge_pick = _alias_pick(edge_prob, edge_alias, u_edge, table_offset, table_length)
                    edge_idx = int(edge_edge_index[table_offset + edge_pick])
                    tzid_operational = int(edge_tzids[edge_idx])
                    out_edge_index[out_idx] = edge_idx
                    out_site_id[out_idx] = 0
                    out_tzid_primary[out_idx] = tzid_operational
                    out_tzid_operational[out_idx] = tzid_operational
                    ts_utc_sec = int(ts_utc_us // MICROS_PER_SECOND)
                    offset_minutes = _tz_offset_minutes(
                        tz_index_start,
                        tz_index_count,
                        tz_transitions_utc,
                        tz_offsets_minutes,
                        tzid_operational,
                        ts_utc_sec,
                    )
                    out_ts_local_primary_us[out_idx] = ts_utc_us + offset_minutes * MICROS_PER_MINUTE
                    out_ts_local_operational_us[out_idx] = ts_utc_us + offset_minutes * MICROS_PER_MINUTE
                    if settlement_tzid >= 0:
                        out_tzid_settlement[out_idx] = settlement_tzid
                        offset_settle = _tz_offset_minutes(
                            tz_index_start,
                            tz_index_count,
                            tz_transitions_utc,
                            tz_offsets_minutes,
                            settlement_tzid,
                            ts_utc_sec,
                        )
                        out_ts_local_settlement_us[out_idx] = ts_utc_us + offset_settle * MICROS_PER_MINUTE
                    else:
                        out_tzid_settlement[out_idx] = tzid_operational
                        out_ts_local_settlement_us[out_idx] = out_ts_local_operational_us[out_idx]
                    virtual_seen += 1
                else:
                    tzid_choice = zone_rep_idx
                    if group_length > 0:
                        pick = _alias_pick(group_prob, group_alias, u0, group_offset, group_length)
                        tzid_choice = int(group_tzid[group_offset + pick])
                    site_table_idx = _lookup_site_table(
                        merchant_idx,
                        tzid_choice,
                        site_map_start,
                        site_map_count,
                        site_map_tzid,
                        site_map_table_index,
                    )
                    if site_table_idx < 0:
                        if default_site_table_idx >= 0:
                            site_table_idx = default_site_table_idx
                        else:
                            row_error = 1
                            out_site_id[out_idx] = 0
                            out_edge_index[out_idx] = -1
                            out_tzid_primary[out_idx] = -1
                            out_tzid_operational[out_idx] = -1
                            out_tzid_settlement[out_idx] = -1
                            out_ts_local_primary_us[out_idx] = -1
                            out_ts_local_operational_us[out_idx] = -1
                            out_ts_local_settlement_us[out_idx] = -1
                            continue
                    site_offset = int(site_table_offsets[site_table_idx])
                    site_length = int(site_table_lengths[site_table_idx])
                    site_pick = _alias_pick(site_prob, site_alias, u1, site_offset, site_length)
                    site_id = site_ids[site_offset + site_pick]
                    site_tzid = int(site_tzids[site_offset + site_pick])
                    out_site_id[out_idx] = site_id
                    out_edge_index[out_idx] = -1
                    out_tzid_primary[out_idx] = site_tzid
                    ts_utc_sec = int(ts_utc_us // MICROS_PER_SECOND)
                    offset_minutes = _tz_offset_minutes(
                        tz_index_start,
                        tz_index_count,
                        tz_transitions_utc,
                        tz_offsets_minutes,
                        site_tzid,
                        ts_utc_sec,
                    )
                    out_ts_local_primary_us[out_idx] = ts_utc_us + offset_minutes * MICROS_PER_MINUTE
                    out_tzid_operational[out_idx] = site_tzid
                    out_tzid_settlement[out_idx] = site_tzid
                    out_ts_local_operational_us[out_idx] = out_ts_local_primary_us[out_idx]
                    out_ts_local_settlement_us[out_idx] = out_ts_local_primary_us[out_idx]
            row_virtual_counts[row_idx] = virtual_seen
            row_errors[row_idx] = row_error

else:

    def expand_arrivals(*_args, **_kwargs) -> None:  # pragma: no cover
        raise RuntimeError("numba is not available")


__all__ = ["NUMBA_AVAILABLE", "expand_arrivals"]

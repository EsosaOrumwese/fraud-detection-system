from __future__ import annotations

from typing import Tuple

import numpy as np

try:
    import numba as nb

    _NUMBA_AVAILABLE = True
except Exception:  # pragma: no cover - runtime availability guard
    nb = None
    _NUMBA_AVAILABLE = False


def numba_available() -> bool:
    return _NUMBA_AVAILABLE


def build_tz_cache_arrays(
    tzid_list: list[str],
    tz_cache: dict[str, tuple[list[int], list[int]]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    instants_flat: list[int] = []
    offsets_flat: list[int] = []
    offsets: list[int] = []
    counts: list[int] = []
    cursor = 0
    for tzid in tzid_list:
        entry = tz_cache.get(tzid)
        if entry is None:
            instants = []
            offsets_values = []
        else:
            instants, offsets_values = entry
        offsets.append(cursor)
        counts.append(len(instants))
        instants_flat.extend(int(v) for v in instants)
        offsets_flat.extend(int(v) for v in offsets_values)
        cursor += len(instants)
    return (
        np.asarray(instants_flat, dtype=np.int64),
        np.asarray(offsets_flat, dtype=np.int32),
        np.asarray(offsets, dtype=np.int64),
        np.asarray(counts, dtype=np.int32),
    )


def build_tzid_bytes(
    tzid_list: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    bytes_flat: list[int] = []
    offsets: list[int] = []
    lengths: list[int] = []
    cursor = 0
    for tzid in tzid_list:
        encoded = tzid.encode("utf-8")
        offsets.append(cursor)
        lengths.append(len(encoded))
        bytes_flat.extend(encoded)
        cursor += len(encoded)
    return (
        np.asarray(bytes_flat, dtype=np.uint8),
        np.asarray(offsets, dtype=np.int64),
        np.asarray(lengths, dtype=np.int32),
    )


def build_edge_alias_arrays(
    edge_keys: np.ndarray,
    edge_alias_meta: dict[int, dict[str, object]],
    blob_view: object,
    alias_endianness: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    prob_flat: list[float] = []
    alias_flat: list[int] = []
    offsets: list[int] = []
    counts: list[int] = []
    cursor = 0
    fmt = "<" if alias_endianness == "little" else ">"
    for merchant_id in edge_keys.tolist():
        meta = edge_alias_meta.get(int(merchant_id))
        if meta is None:
            offsets.append(cursor)
            counts.append(0)
            continue
        offset = int(meta["offset"])
        length = int(meta["length"])
        view = blob_view.slice(offset, length)
        if len(view) < 16:
            raise ValueError("alias slice header incomplete")
        n_items = int(np.frombuffer(view[0:4], dtype=f"{fmt}u4")[0])
        prob_qbits = int(np.frombuffer(view[4:8], dtype=f"{fmt}u4")[0])
        payload_offset = 16
        expected_len = payload_offset + (n_items * 8)
        if len(view) < expected_len:
            raise ValueError("alias slice payload incomplete")
        scale = float(1 << prob_qbits)
        offsets.append(cursor)
        counts.append(n_items)
        for idx in range(n_items):
            base = payload_offset + idx * 8
            prob_raw = int(np.frombuffer(view[base : base + 4], dtype=f"{fmt}u4")[0])
            alias_idx = int(np.frombuffer(view[base + 4 : base + 8], dtype=f"{fmt}u4")[0])
            prob_flat.append(float(prob_raw) / scale)
            alias_flat.append(alias_idx)
            cursor += 1
    return (
        np.asarray(prob_flat, dtype=np.float64),
        np.asarray(alias_flat, dtype=np.int64),
        np.asarray(offsets, dtype=np.int64),
        np.asarray(counts, dtype=np.int32),
    )


def warmup_compiled_kernel() -> None:
    if not _NUMBA_AVAILABLE:
        return
    merchants = np.zeros(1, dtype=np.uint64)
    zone_idx = np.zeros(1, dtype=np.int32)
    bucket_index = np.zeros(1, dtype=np.int64)
    count_n = np.zeros(1, dtype=np.int64)
    arrival_seq_start = np.zeros(1, dtype=np.int64)
    bucket_start_micros = np.zeros(1, dtype=np.int64)
    bucket_duration_micros = np.ones(1, dtype=np.int64)
    bucket_duration_seconds = np.ones(1, dtype=np.float64)
    class_keys = np.zeros(1, dtype=np.uint64)
    class_modes = np.zeros(1, dtype=np.int8)
    settlement_keys = np.zeros(1, dtype=np.uint64)
    settlement_tz_index = np.zeros(1, dtype=np.int32)
    edge_keys = np.zeros(1, dtype=np.uint64)
    edge_offsets = np.zeros(1, dtype=np.int64)
    edge_counts = np.zeros(1, dtype=np.int32)
    edge_ids = np.zeros(1, dtype=np.int64)
    edge_tz_index = np.zeros(1, dtype=np.int32)
    edge_alias_prob = np.zeros(1, dtype=np.float64)
    edge_alias_alias = np.zeros(1, dtype=np.int64)
    edge_alias_offsets = np.zeros(1, dtype=np.int64)
    edge_alias_counts = np.zeros(1, dtype=np.int32)
    site_keys = np.zeros((1, 2), dtype=np.int64)
    site_offsets = np.zeros(1, dtype=np.int64)
    site_counts = np.zeros(1, dtype=np.int32)
    site_prob = np.zeros(1, dtype=np.float64)
    site_alias = np.zeros(1, dtype=np.int64)
    site_site_orders = np.zeros(1, dtype=np.int64)
    fallback_keys = np.zeros(1, dtype=np.uint64)
    fallback_offsets = np.zeros(1, dtype=np.int64)
    fallback_counts = np.zeros(1, dtype=np.int32)
    fallback_prob = np.zeros(1, dtype=np.float64)
    fallback_alias = np.zeros(1, dtype=np.int64)
    fallback_site_orders = np.zeros(1, dtype=np.int64)
    site_tz_keys = np.zeros((1, 2), dtype=np.int64)
    site_tz_values = np.zeros(1, dtype=np.int32)
    tz_instants_flat = np.zeros(1, dtype=np.int64)
    tz_offsets_flat = np.zeros(1, dtype=np.int32)
    tz_offset_offsets = np.zeros(1, dtype=np.int64)
    tz_offset_counts = np.zeros(1, dtype=np.int32)
    tzid_bytes = np.zeros(1, dtype=np.uint8)
    tzid_offsets = np.zeros(1, dtype=np.int64)
    tzid_lengths = np.zeros(1, dtype=np.int32)
    time_prefix = np.zeros(1, dtype=np.uint8)
    site_prefix = np.zeros(1, dtype=np.uint8)
    edge_prefix = np.zeros(1, dtype=np.uint8)
    max_arrivals_per_bucket = 1
    p_virtual_hybrid = 0.0
    draws_per_arrival = 1
    out_arrival_seq = np.zeros(1, dtype=np.int64)
    out_ts_utc_micros = np.zeros(1, dtype=np.int64)
    out_tzid_primary_idx = np.zeros(1, dtype=np.int32)
    out_ts_local_primary_micros = np.zeros(1, dtype=np.int64)
    out_tzid_operational_idx = np.zeros(1, dtype=np.int32)
    out_ts_local_operational_micros = np.zeros(1, dtype=np.int64)
    out_tzid_settlement_idx = np.zeros(1, dtype=np.int32)
    out_ts_local_settlement_micros = np.zeros(1, dtype=np.int64)
    out_site_id = np.zeros(1, dtype=np.int64)
    out_edge_id = np.zeros(1, dtype=np.int64)
    out_is_virtual = np.zeros(1, dtype=np.uint8)
    summary_physical = np.zeros(1, dtype=np.int64)
    summary_virtual = np.zeros(1, dtype=np.int64)
    missing_alias_flags = np.zeros(1, dtype=np.uint8)
    rng_last = np.zeros((3, 2), dtype=np.int64)
    error_state = np.zeros(2, dtype=np.int64)
    progress = np.zeros(2, dtype=np.int64)
    progress_stride = np.int64(1)

    expand_batch_kernel(
        merchants,
        zone_idx,
        bucket_index,
        count_n,
        arrival_seq_start,
        bucket_start_micros,
        bucket_duration_micros,
        bucket_duration_seconds,
        class_keys,
        class_modes,
        settlement_keys,
        settlement_tz_index,
        edge_keys,
        edge_offsets,
        edge_counts,
        edge_ids,
        edge_tz_index,
        edge_alias_prob,
        edge_alias_alias,
        edge_alias_offsets,
        edge_alias_counts,
        site_keys,
        site_offsets,
        site_counts,
        site_prob,
        site_alias,
        site_site_orders,
        fallback_keys,
        fallback_offsets,
        fallback_counts,
        fallback_prob,
        fallback_alias,
        fallback_site_orders,
        site_tz_keys,
        site_tz_values,
        tz_instants_flat,
        tz_offsets_flat,
        tz_offset_offsets,
        tz_offset_counts,
        tzid_bytes,
        tzid_offsets,
        tzid_lengths,
        time_prefix,
        site_prefix,
        edge_prefix,
        max_arrivals_per_bucket,
        p_virtual_hybrid,
        draws_per_arrival,
        out_arrival_seq,
        out_ts_utc_micros,
        out_tzid_primary_idx,
        out_ts_local_primary_micros,
        out_tzid_operational_idx,
        out_ts_local_operational_micros,
        out_tzid_settlement_idx,
        out_ts_local_settlement_micros,
        out_site_id,
        out_edge_id,
        out_is_virtual,
        summary_physical,
        summary_virtual,
        missing_alias_flags,
        rng_last,
        error_state,
        progress,
        progress_stride,
    )


_PREFIX_MERCHANT = np.frombuffer(b"merchant_id=", dtype=np.uint8)
_PREFIX_ZONE = np.frombuffer(b"|zone=", dtype=np.uint8)
_PREFIX_BUCKET = np.frombuffer(b"|bucket_index=", dtype=np.uint8)
_PREFIX_ARRIVAL = np.frombuffer(b"|arrival_seq=", dtype=np.uint8)

if _NUMBA_AVAILABLE:
    _K = np.array(
        [
            0x428A2F98,
            0x71374491,
            0xB5C0FBCF,
            0xE9B5DBA5,
            0x3956C25B,
            0x59F111F1,
            0x923F82A4,
            0xAB1C5ED5,
            0xD807AA98,
            0x12835B01,
            0x243185BE,
            0x550C7DC3,
            0x72BE5D74,
            0x80DEB1FE,
            0x9BDC06A7,
            0xC19BF174,
            0xE49B69C1,
            0xEFBE4786,
            0x0FC19DC6,
            0x240CA1CC,
            0x2DE92C6F,
            0x4A7484AA,
            0x5CB0A9DC,
            0x76F988DA,
            0x983E5152,
            0xA831C66D,
            0xB00327C8,
            0xBF597FC7,
            0xC6E00BF3,
            0xD5A79147,
            0x06CA6351,
            0x14292967,
            0x27B70A85,
            0x2E1B2138,
            0x4D2C6DFC,
            0x53380D13,
            0x650A7354,
            0x766A0ABB,
            0x81C2C92E,
            0x92722C85,
            0xA2BFE8A1,
            0xA81A664B,
            0xC24B8B70,
            0xC76C51A3,
            0xD192E819,
            0xD6990624,
            0xF40E3585,
            0x106AA070,
            0x19A4C116,
            0x1E376C08,
            0x2748774C,
            0x34B0BCB5,
            0x391C0CB3,
            0x4ED8AA4A,
            0x5B9CCA4F,
            0x682E6FF3,
            0x748F82EE,
            0x78A5636F,
            0x84C87814,
            0x8CC70208,
            0x90BEFFFA,
            0xA4506CEB,
            0xBEF9A3F7,
            0xC67178F2,
        ],
        dtype=np.uint32,
    )

    _H0 = np.array(
        [
            0x6A09E667,
            0xBB67AE85,
            0x3C6EF372,
            0xA54FF53A,
            0x510E527F,
            0x9B05688C,
            0x1F83D9AB,
            0x5BE0CD19,
        ],
        dtype=np.uint32,
    )

    @nb.njit(cache=True, nogil=True)
    def _rotr(value: np.uint32, shift: int) -> np.uint32:
        return ((value >> shift) | (value << (32 - shift))) & np.uint32(0xFFFFFFFF)

    @nb.njit(cache=True, nogil=True)
    def _sha256_compress(state: np.ndarray, block: np.ndarray) -> None:
        w = np.empty(64, dtype=np.uint32)
        for i in range(16):
            j = i * 4
            w[i] = (
                (np.uint32(block[j]) << 24)
                | (np.uint32(block[j + 1]) << 16)
                | (np.uint32(block[j + 2]) << 8)
                | np.uint32(block[j + 3])
            )
        for i in range(16, 64):
            s0 = _rotr(w[i - 15], 7) ^ _rotr(w[i - 15], 18) ^ (w[i - 15] >> 3)
            s1 = _rotr(w[i - 2], 17) ^ _rotr(w[i - 2], 19) ^ (w[i - 2] >> 10)
            w[i] = (w[i - 16] + s0 + w[i - 7] + s1) & np.uint32(0xFFFFFFFF)
        a = state[0]
        b = state[1]
        c = state[2]
        d = state[3]
        e = state[4]
        f = state[5]
        g = state[6]
        h = state[7]
        for i in range(64):
            s1 = _rotr(e, 6) ^ _rotr(e, 11) ^ _rotr(e, 25)
            ch = (e & f) ^ ((~e) & g)
            temp1 = (h + s1 + ch + _K[i] + w[i]) & np.uint32(0xFFFFFFFF)
            s0 = _rotr(a, 2) ^ _rotr(a, 13) ^ _rotr(a, 22)
            maj = (a & b) ^ (a & c) ^ (b & c)
            temp2 = (s0 + maj) & np.uint32(0xFFFFFFFF)
            h = g
            g = f
            f = e
            e = (d + temp1) & np.uint32(0xFFFFFFFF)
            d = c
            c = b
            b = a
            a = (temp1 + temp2) & np.uint32(0xFFFFFFFF)
        state[0] = (state[0] + a) & np.uint32(0xFFFFFFFF)
        state[1] = (state[1] + b) & np.uint32(0xFFFFFFFF)
        state[2] = (state[2] + c) & np.uint32(0xFFFFFFFF)
        state[3] = (state[3] + d) & np.uint32(0xFFFFFFFF)
        state[4] = (state[4] + e) & np.uint32(0xFFFFFFFF)
        state[5] = (state[5] + f) & np.uint32(0xFFFFFFFF)
        state[6] = (state[6] + g) & np.uint32(0xFFFFFFFF)
        state[7] = (state[7] + h) & np.uint32(0xFFFFFFFF)

    @nb.njit(cache=True, nogil=True)
    def _sha256_update(state, buffer, buffer_len, data, data_len, total_len):
        for i in range(data_len):
            buffer[buffer_len] = data[i]
            buffer_len += 1
            if buffer_len == 64:
                _sha256_compress(state, buffer)
                buffer_len = 0
        total_len += data_len
        return buffer_len, total_len

    @nb.njit(cache=True, nogil=True)
    def sha256_digest(prefix_bytes, prefix_len, msg_bytes, msg_len, digest_out):
        state = _H0.copy()
        buffer = np.zeros(64, dtype=np.uint8)
        buffer_len = 0
        total_len = 0
        buffer_len, total_len = _sha256_update(
            state, buffer, buffer_len, prefix_bytes, prefix_len, total_len
        )
        buffer_len, total_len = _sha256_update(
            state, buffer, buffer_len, msg_bytes, msg_len, total_len
        )
        buffer[buffer_len] = 0x80
        buffer_len += 1
        if buffer_len > 56:
            while buffer_len < 64:
                buffer[buffer_len] = 0
                buffer_len += 1
            _sha256_compress(state, buffer)
            buffer_len = 0
        while buffer_len < 56:
            buffer[buffer_len] = 0
            buffer_len += 1
        bit_len = np.uint64(total_len) * np.uint64(8)
        for i in range(8):
            buffer[63 - i] = np.uint8((bit_len >> (np.uint64(i) * 8)) & np.uint64(0xFF))
        _sha256_compress(state, buffer)
        for i in range(8):
            val = state[i]
            digest_out[i * 4] = np.uint8((val >> 24) & np.uint32(0xFF))
            digest_out[i * 4 + 1] = np.uint8((val >> 16) & np.uint32(0xFF))
            digest_out[i * 4 + 2] = np.uint8((val >> 8) & np.uint32(0xFF))
            digest_out[i * 4 + 3] = np.uint8(val & np.uint32(0xFF))

    @nb.njit(cache=True, nogil=True)
    def _u64_from_digest_be(digest, start):
        val = np.uint64(0)
        for i in range(8):
            val = (val << np.uint64(8)) | np.uint64(digest[start + i])
        return val

    @nb.njit(cache=True, nogil=True)
    def _mul_hi_lo(a: np.uint64, b: np.uint64) -> Tuple[np.uint64, np.uint64]:
        product = a * b
        lo = product & np.uint64(0xFFFFFFFFFFFFFFFF)
        hi = (product >> np.uint64(64)) & np.uint64(0xFFFFFFFFFFFFFFFF)
        return hi, lo

    @nb.njit(cache=True, nogil=True)
    def philox2x64_10(counter_hi, counter_lo, key):
        c0 = counter_lo & np.uint64(0xFFFFFFFFFFFFFFFF)
        c1 = counter_hi & np.uint64(0xFFFFFFFFFFFFFFFF)
        k0 = key & np.uint64(0xFFFFFFFFFFFFFFFF)
        for _ in range(10):
            hi, lo = _mul_hi_lo(np.uint64(0xD2B74407B1CE6E93), c0)
            c0 = (hi ^ k0 ^ c1) & np.uint64(0xFFFFFFFFFFFFFFFF)
            c1 = lo
            k0 = (k0 + np.uint64(0x9E3779B97F4A7C15)) & np.uint64(0xFFFFFFFFFFFFFFFF)
        return c0, c1

    @nb.njit(cache=True, nogil=True)
    def add_u128(counter_hi, counter_lo, increment):
        total_lo = counter_lo + increment
        new_lo = total_lo & np.uint64(0xFFFFFFFFFFFFFFFF)
        carry = total_lo >> np.uint64(64)
        new_hi = (counter_hi + carry) & np.uint64(0xFFFFFFFFFFFFFFFF)
        return new_hi, new_lo

    _INV_TWO_POW_64 = 1.0 / 18446744073709551616.0

    @nb.njit(cache=True, nogil=True)
    def u01_from_u64(value):
        return (float(value) + 0.5) * _INV_TWO_POW_64

    @nb.njit(cache=True, nogil=True)
    def alias_pick(prob, alias, u):
        n = prob.shape[0]
        if n == 0:
            return -1
        idx = int(u * n)
        if idx >= n:
            idx = n - 1
        frac = u * n - idx
        if frac < prob[idx]:
            return idx
        return int(alias[idx])

    @nb.njit(cache=True, nogil=True)
    def write_uint_decimal(value, buf, pos):
        if value == 0:
            buf[pos] = 48
            return pos + 1
        tmp = np.empty(20, dtype=np.uint8)
        count = 0
        v = value
        while v > 0:
            tmp[count] = np.uint8(48 + (v % 10))
            v //= 10
            count += 1
        for i in range(count - 1, -1, -1):
            buf[pos] = tmp[i]
            pos += 1
        return pos

    @nb.njit(cache=True, nogil=True)
    def build_domain_key(
        merchant_id,
        zone_bytes,
        zone_start,
        zone_len,
        bucket_index,
        arrival_seq,
        out_buf,
    ):
        pos = 0
        # merchant_id=
        for i in range(_PREFIX_MERCHANT.shape[0]):
            out_buf[pos] = _PREFIX_MERCHANT[i]
            pos += 1
        pos = write_uint_decimal(merchant_id, out_buf, pos)
        for i in range(_PREFIX_ZONE.shape[0]):
            out_buf[pos] = _PREFIX_ZONE[i]
            pos += 1
        for i in range(zone_len):
            out_buf[pos] = zone_bytes[zone_start + i]
            pos += 1
        for i in range(_PREFIX_BUCKET.shape[0]):
            out_buf[pos] = _PREFIX_BUCKET[i]
            pos += 1
        pos = write_uint_decimal(bucket_index, out_buf, pos)
        for i in range(_PREFIX_ARRIVAL.shape[0]):
            out_buf[pos] = _PREFIX_ARRIVAL[i]
            pos += 1
        pos = write_uint_decimal(arrival_seq, out_buf, pos)
        return pos

    @nb.njit(cache=True, nogil=True)
    def lookup_sorted_key(keys, key):
        lo = 0
        hi = keys.shape[0] - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            val = keys[mid]
            if val == key:
                return mid
            if val < key:
                lo = mid + 1
            else:
                hi = mid - 1
        return -1

    @nb.njit(cache=True, nogil=True)
    def lookup_structured_key(keys, key1, key2):
        lo = 0
        hi = keys.shape[0] - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            v1 = keys[mid, 0]
            v2 = keys[mid, 1]
            if v1 == key1 and v2 == key2:
                return mid
            if v1 < key1 or (v1 == key1 and v2 < key2):
                lo = mid + 1
            else:
                hi = mid - 1
        return -1

    @nb.njit(cache=True, nogil=True)
    def tz_offset_minutes(
        instants_flat,
        offsets_flat,
        offsets,
        counts,
        tz_idx,
        instant_seconds,
    ):
        start = offsets[tz_idx]
        count = counts[tz_idx]
        if count <= 0:
            return 0
        lo = 0
        hi = count - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            val = instants_flat[start + mid]
            if val <= instant_seconds:
                lo = mid + 1
            else:
                hi = mid - 1
        idx = hi
        if idx < 0:
            idx = 0
        return int(offsets_flat[start + idx])

    @nb.njit(cache=True, nogil=True)
    def expand_batch_kernel(
        merchants,
        zone_idx,
        bucket_index,
        count_n,
        arrival_seq_start,
        bucket_start_micros,
        bucket_duration_micros,
        bucket_duration_seconds,
        class_keys,
        class_modes,
        settlement_keys,
        settlement_tz_index,
        edge_keys,
        edge_offsets,
        edge_counts,
        edge_ids,
        edge_tz_index,
        edge_alias_prob,
        edge_alias_alias,
        edge_alias_offsets,
        edge_alias_counts,
        site_keys,
        site_offsets,
        site_counts,
        site_prob,
        site_alias,
        site_site_orders,
        fallback_keys,
        fallback_offsets,
        fallback_counts,
        fallback_prob,
        fallback_alias,
        fallback_site_orders,
        site_tz_keys,
        site_tz_values,
        tz_instants_flat,
        tz_offsets_flat,
        tz_offset_offsets,
        tz_offset_counts,
        tzid_bytes,
        tzid_offsets,
        tzid_lengths,
        time_prefix,
        site_prefix,
        edge_prefix,
        max_arrivals_per_bucket,
        p_virtual_hybrid,
        draws_per_arrival,
        out_arrival_seq,
        out_ts_utc_micros,
        out_tzid_primary_idx,
        out_ts_local_primary_micros,
        out_tzid_operational_idx,
        out_ts_local_operational_micros,
        out_tzid_settlement_idx,
        out_ts_local_settlement_micros,
        out_site_id,
        out_edge_id,
        out_is_virtual,
        summary_physical,
        summary_virtual,
        missing_alias_flags,
        rng_last,
        error_state,
        progress,
        progress_stride,
    ):
        pos = 0
        rng_time_events = 0
        rng_site_events = 0
        rng_edge_events = 0
        for i in range(merchants.shape[0]):
            m_id = merchants[i]
            tz_idx = zone_idx[i]
            b_idx = bucket_index[i]
            n = count_n[i]
            if n <= 0:
                continue
            if n > max_arrivals_per_bucket:
                error_state[0] = 1
                error_state[1] = i
                return 0
            class_idx = lookup_sorted_key(class_keys, m_id)
            if class_idx < 0:
                error_state[0] = 2
                error_state[1] = i
                return 0
            vmode = class_modes[class_idx]
            domain_key_buf = np.empty(256, dtype=np.uint8)
            msg_buf = np.empty(260, dtype=np.uint8)
            digest = np.empty(32, dtype=np.uint8)
            for offset in range(n):
                arrival_seq = arrival_seq_start[i] + offset
                dk_len = build_domain_key(
                    m_id,
                    tzid_bytes,
                    tzid_offsets[tz_idx],
                    tzid_lengths[tz_idx],
                    b_idx,
                    arrival_seq,
                    domain_key_buf,
                )
                if dk_len > 252:
                    error_state[0] = 9
                    error_state[1] = i
                    return 0
                msg_len = dk_len + 4
                msg_buf[0] = np.uint8((dk_len >> 24) & 0xFF)
                msg_buf[1] = np.uint8((dk_len >> 16) & 0xFF)
                msg_buf[2] = np.uint8((dk_len >> 8) & 0xFF)
                msg_buf[3] = np.uint8(dk_len & 0xFF)
                for j in range(dk_len):
                    msg_buf[4 + j] = domain_key_buf[j]
                sha256_digest(time_prefix, time_prefix.shape[0], msg_buf, msg_len, digest)
                time_key = _u64_from_digest_be(digest, 0)
                time_hi = _u64_from_digest_be(digest, 8)
                time_lo = _u64_from_digest_be(digest, 16)
                out0, out1 = philox2x64_10(time_hi, time_lo, time_key)
                u_time = u01_from_u64(out0)
                offset_micros = int(u_time * bucket_duration_seconds[b_idx] * 1_000_000.0)
                max_offset = int(bucket_duration_micros[b_idx]) - 1
                if offset_micros > max_offset:
                    offset_micros = max_offset if max_offset > 0 else 0
                ts_utc_micros = bucket_start_micros[b_idx] + offset_micros
                rng_time_events += 1

                use_site_pick = vmode != 2
                u_site_primary = 0.0
                u_site_secondary = 0.0
                if use_site_pick:
                    sha256_digest(site_prefix, site_prefix.shape[0], msg_buf, msg_len, digest)
                    site_key = _u64_from_digest_be(digest, 0)
                    site_hi = _u64_from_digest_be(digest, 8)
                    site_lo = _u64_from_digest_be(digest, 16)
                    s0, s1 = philox2x64_10(site_hi, site_lo, site_key)
                    u_site_primary = u01_from_u64(s0)
                    u_site_secondary = u01_from_u64(s1)
                    rng_site_events += 1

                is_virtual = vmode == 2
                if vmode == 1:
                    is_virtual = u_site_primary < p_virtual_hybrid

                tzid_primary_idx = -1
                tzid_operational_idx = -1
                tzid_settlement_idx = -1
                ts_local_primary = 0
                ts_local_operational = 0
                ts_local_settlement = 0
                site_id = -1
                edge_id = -1

                if is_virtual:
                    edge_idx = lookup_sorted_key(edge_keys, m_id)
                    if edge_idx < 0:
                        error_state[0] = 3
                        error_state[1] = i
                        return 0
                    offset = edge_offsets[edge_idx]
                    count = edge_counts[edge_idx]
                    prob_offset = edge_alias_offsets[edge_idx]
                    prob_count = edge_alias_counts[edge_idx]
                    if count <= 0 or prob_count <= 0:
                        error_state[0] = 4
                        error_state[1] = i
                        return 0
                    sha256_digest(edge_prefix, edge_prefix.shape[0], msg_buf, msg_len, digest)
                    edge_key = _u64_from_digest_be(digest, 0)
                    edge_hi = _u64_from_digest_be(digest, 8)
                    edge_lo = _u64_from_digest_be(digest, 16)
                    e0, _ = philox2x64_10(edge_hi, edge_lo, edge_key)
                    u_edge = u01_from_u64(e0)
                    rng_edge_events += 1
                    edge_index = alias_pick(
                        edge_alias_prob[prob_offset : prob_offset + prob_count],
                        edge_alias_alias[prob_offset : prob_offset + prob_count],
                        u_edge,
                    )
                    if edge_index < 0 or edge_index >= count:
                        error_state[0] = 5
                        error_state[1] = i
                        return 0
                    edge_id = int(edge_ids[offset + edge_index])
                    tzid_operational_idx = int(edge_tz_index[offset + edge_index])
                    tzid_primary_idx = tzid_operational_idx
                    settlement_idx = lookup_sorted_key(settlement_keys, m_id)
                    if settlement_idx >= 0:
                        tzid_settlement_idx = int(settlement_tz_index[settlement_idx])
                    offset_min = tz_offset_minutes(
                        tz_instants_flat,
                        tz_offsets_flat,
                        tz_offset_offsets,
                        tz_offset_counts,
                        tzid_primary_idx,
                        ts_utc_micros // 1_000_000,
                    )
                    ts_local_primary = ts_utc_micros + offset_min * 60 * 1_000_000
                    ts_local_operational = ts_local_primary
                    if tzid_settlement_idx >= 0:
                        settle_min = tz_offset_minutes(
                            tz_instants_flat,
                            tz_offsets_flat,
                            tz_offset_offsets,
                            tz_offset_counts,
                            tzid_settlement_idx,
                            ts_utc_micros // 1_000_000,
                        )
                        ts_local_settlement = ts_utc_micros + settle_min * 60 * 1_000_000
                    summary_virtual[i] += 1
                else:
                    alias_idx = lookup_structured_key(site_keys, m_id, tz_idx)
                    prob_offset = 0
                    prob_count = 0
                    if alias_idx >= 0:
                        prob_offset = site_offsets[alias_idx]
                        prob_count = site_counts[alias_idx]
                    else:
                        missing_alias_flags[i] = 1
                        fb_idx = lookup_sorted_key(fallback_keys, m_id)
                        if fb_idx >= 0:
                            prob_offset = fallback_offsets[fb_idx]
                            prob_count = fallback_counts[fb_idx]
                    if prob_count <= 0:
                        error_state[0] = 6
                        error_state[1] = i
                        return 0
                    u_site = u_site_secondary if vmode == 1 else u_site_primary
                    if alias_idx >= 0:
                        site_index = alias_pick(
                            site_prob[prob_offset : prob_offset + prob_count],
                            site_alias[prob_offset : prob_offset + prob_count],
                            u_site,
                        )
                        site_orders = site_site_orders
                    else:
                        site_index = alias_pick(
                            fallback_prob[prob_offset : prob_offset + prob_count],
                            fallback_alias[prob_offset : prob_offset + prob_count],
                            u_site,
                        )
                        site_orders = fallback_site_orders
                    if site_index < 0 or site_index >= prob_count:
                        error_state[0] = 7
                        error_state[1] = i
                        return 0
                    site_id = int(
                        site_orders[prob_offset + site_index]
                    )
                    tz_lookup_idx = lookup_structured_key(site_tz_keys, m_id, site_id)
                    if tz_lookup_idx < 0:
                        error_state[0] = 8
                        error_state[1] = i
                        return 0
                    tzid_primary_idx = int(site_tz_values[tz_lookup_idx])
                    offset_min = tz_offset_minutes(
                        tz_instants_flat,
                        tz_offsets_flat,
                        tz_offset_offsets,
                        tz_offset_counts,
                        tzid_primary_idx,
                        ts_utc_micros // 1_000_000,
                    )
                    ts_local_primary = ts_utc_micros + offset_min * 60 * 1_000_000
                    summary_physical[i] += 1

                out_arrival_seq[pos] = arrival_seq
                out_ts_utc_micros[pos] = ts_utc_micros
                out_tzid_primary_idx[pos] = tzid_primary_idx
                out_ts_local_primary_micros[pos] = ts_local_primary
                out_tzid_operational_idx[pos] = tzid_operational_idx
                out_ts_local_operational_micros[pos] = ts_local_operational
                out_tzid_settlement_idx[pos] = tzid_settlement_idx
                out_ts_local_settlement_micros[pos] = ts_local_settlement
                out_site_id[pos] = site_id
                out_edge_id[pos] = edge_id
                out_is_virtual[pos] = 1 if is_virtual else 0
                pos += 1
            if progress_stride > 0 and (i % progress_stride) == 0:
                progress[0] = i + 1
                progress[1] = pos

        progress[0] = merchants.shape[0]
        progress[1] = pos

        rng_last[0, 0] = rng_time_events
        rng_last[1, 0] = rng_site_events
        rng_last[2, 0] = rng_edge_events
        return pos

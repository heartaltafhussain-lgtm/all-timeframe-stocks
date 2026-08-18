#!/usr/bin/env python3
"""
GTF v2 zone detector — course-faithful (Episodes 3-9 rules):
  - Zone = Leg-in + Base (1+ candles) + Leg-out (explosive)
  - Demand: base ke baad green explosive leg-out; Supply: red explosive
  - Proximal = highest body of base candles (demand) / lowest body (supply)
  - Distal   = lowest wick (demand) / highest wick (supply), PLUS
               exceptional marking: leg-in/leg-out ki extreme wick bhi
  - Track: n_base (1-3 strong / 4-5 medium / >5 garbage), n_legout,
           has_gap, body/ATR strength
  - Freshness: tests counter (Ep 6)
"""
import numpy as np
import pandas as pd

IMPULSE_ATR = 0.35
BODY_PCT_MIN = 50.0
BASE_MAX_ATR = 0.60        # base candle body <= 0.6*ATR (fight zone)
MAX_ZONES = 8
LOOKBACK_BARS = 220
MIN_ZONE_ATR = 0.05
MAX_ZONE_ATR = 1.80
NEAR_PCT = 0.02


def wilder_atr(high, low, close, n=14):
    high = np.asarray(high, float); low = np.asarray(low, float); close = np.asarray(close, float)
    prev = np.roll(close, 1)
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))
    tr[0] = high[0] - low[0]
    atr = np.full(len(tr), np.nan)
    if len(tr) < n:
        return atr
    atr[n - 1] = tr[:n].mean()
    alpha = 1.0 / n
    for i in range(n, len(tr)):
        atr[i] = atr[i - 1] * (1 - alpha) + tr[i] * alpha
    return atr


def _overlap(zones, prox, dist):
    for z in zones:
        lo1, hi1 = min(z["prox"], z["dist"]), max(z["prox"], z["dist"])
        lo2, hi2 = min(prox, dist), max(prox, dist)
        ov = min(hi1, hi2) - max(lo1, lo2)
        sz = max(hi2 - lo2, 1e-9)
        if ov > 0 and ov / sz > 0.50:
            return True
    return False


def grade_of(s):
    return "A+" if s >= 9 else "A" if s >= 7 else "B" if s >= 5.5 else "C"


def trade_score(fresh_tests, n_base, n_legout, has_gap, body_atr_ratio):
    """Ep 8: Trade Score max 7 -> freshness(3) + strength(2) + time at base(2)."""
    f = 3.0 if fresh_tests == 0 else 1.5 if fresh_tests == 1 else 0.0
    if n_legout >= 2 or (n_legout == 1 and has_gap):
        s = 2.0
    elif n_legout == 1:
        s = 1.0
    else:
        s = 0.5
    if 1 <= n_base <= 3:
        b = 2.0
    elif 4 <= n_base <= 5:
        b = 1.0
    else:
        b = 0.0
    return round(f + s + b, 1)


def detect_zones_v2(o, h, l, c, snapshot_idx=None, start_win=220):
    """
    Course-faithful zone engine.
    Returns (demand_snaps, supply_snaps): {bar_idx: [(born, prox, dist, tests,
                                                      score, n_base, n_legout, has_gap, body_ratio), ...]}
    """
    n = len(c)
    atr = wilder_atr(h, l, c)
    start = max(n - start_win, 16)

    demands = []   # mutable dicts
    supplies = []
    d_snap, s_snap = {}, {}
    want = set(snapshot_idx) if snapshot_idx is not None else None

    for i in range(start, n):
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        body = abs(c[i] - o[i])
        rng = max(h[i] - l[i], 1e-9)
        body_pct = body / rng * 100.0
        explosive_up = c[i] > o[i] and body >= a * IMPULSE_ATR and body_pct >= BODY_PCT_MIN
        explosive_dn = c[i] < o[i] and body >= a * IMPULSE_ATR and body_pct >= BODY_PCT_MIN
        base_candle = body <= a * BASE_MAX_ATR

        # ---------- demand zone: base cluster ends at i-1, leg-out = bar i ----------
        if explosive_up:
            # walk back over base candles
            b_start = i - 1
            while b_start > start and abs(c[b_start] - o[b_start]) <= a * BASE_MAX_ATR:
                b_start -= 1
            n_base = (i - 1) - b_start
            if n_base >= 1:
                leg_in_idx = b_start
                leg_out_count = 1
                j = i + 1
                while j < n and c[j] > o[j] and abs(c[j] - o[j]) >= a * IMPULSE_ATR and abs(c[j] - o[j]) / max(h[j] - l[j], 1e-9) * 100 >= BODY_PCT_MIN:
                    leg_out_count += 1
                    j += 1
                has_gap = (o[i] - h[i - 1]) >= c[i] * 0.003
                # proximal: highest body of base candles
                prox = max(max(o[k], c[k]) for k in range(b_start + 1, i))
                # distal: lowest wick of base + exceptional leg-in/leg-out wicks
                wicks = [l[k] for k in range(b_start + 1, i)]
                if leg_in_idx >= 0 and l[leg_in_idx] < prox:
                    wicks.append(l[leg_in_idx])
                for k in range(i, min(j, n)):
                    wicks.append(l[k])
                dist = min(wicks)
                height = prox - dist
                if a * MIN_ZONE_ATR <= height <= a * MAX_ZONE_ATR and not _overlap(demands, prox, dist):
                    ts = trade_score(0, n_base, leg_out_count, has_gap, body / a)
                    demands.append({
                        "prox": round(prox, 2), "dist": round(dist, 2), "born": i,
                        "tests": 0, "score": ts, "grade": grade_of(ts),
                        "n_base": n_base, "n_legout": leg_out_count,
                        "has_gap": has_gap, "body_ratio": round(body / a, 2),
                        "side": "DEMAND",
                    })
                    if len(demands) > MAX_ZONES:
                        demands.pop(0)

        # ---------- supply zone ----------
        if explosive_dn:
            b_start = i - 1
            while b_start > start and abs(c[b_start] - o[b_start]) <= a * BASE_MAX_ATR:
                b_start -= 1
            n_base = (i - 1) - b_start
            if n_base >= 1:
                leg_in_idx = b_start
                leg_out_count = 1
                j = i + 1
                while j < n and c[j] < o[j] and abs(c[j] - o[j]) >= a * IMPULSE_ATR and abs(c[j] - o[j]) / max(h[j] - l[j], 1e-9) * 100 >= BODY_PCT_MIN:
                    leg_out_count += 1
                    j += 1
                has_gap = (l[i - 1] - o[i]) >= c[i] * 0.003
                prox = min(min(o[k], c[k]) for k in range(b_start + 1, i))
                wicks = [h[k] for k in range(b_start + 1, i)]
                if leg_in_idx >= 0 and h[leg_in_idx] > prox:
                    wicks.append(h[leg_in_idx])
                for k in range(i, min(j, n)):
                    wicks.append(h[k])
                dist = max(wicks)
                height = dist - prox
                if a * MIN_ZONE_ATR <= height <= a * MAX_ZONE_ATR and not _overlap(supplies, prox, dist):
                    ts = trade_score(0, n_base, leg_out_count, has_gap, body / a)
                    supplies.append({
                        "prox": round(prox, 2), "dist": round(dist, 2), "born": i,
                        "tests": 0, "score": ts, "grade": grade_of(ts),
                        "n_base": n_base, "n_legout": leg_out_count,
                        "has_gap": has_gap, "body_ratio": round(body / a, 2),
                        "side": "SUPPLY",
                    })
                    if len(supplies) > MAX_ZONES:
                        supplies.pop(0)

        # ---------- tests + invalidation ----------
        keep_d = []
        for z in demands:
            if i <= z["born"]:
                keep_d.append(z)
                continue
            touch_now = l[i] <= z["prox"] and l[i] >= z["dist"]
            touch_prev = (l[i - 1] <= z["prox"] and l[i - 1] >= z["dist"]) if i - 1 > z["born"] else False
            if touch_now and not touch_prev:
                z["tests"] += 1
                z["score"] = trade_score(z["tests"], z["n_base"], z["n_legout"], z["has_gap"], z["body_ratio"])
                z["grade"] = grade_of(z["score"])
            if c[i] < z["dist"]:
                continue
            keep_d.append(z)
        demands = keep_d[-MAX_ZONES:]

        keep_s = []
        for z in supplies:
            if i <= z["born"]:
                keep_s.append(z)
                continue
            touch_now = h[i] >= z["prox"] and h[i] <= z["dist"]
            touch_prev = (h[i - 1] >= z["prox"] and h[i - 1] <= z["dist"]) if i - 1 > z["born"] else False
            if touch_now and not touch_prev:
                z["tests"] += 1
                z["score"] = trade_score(z["tests"], z["n_base"], z["n_legout"], z["has_gap"], z["body_ratio"])
                z["grade"] = grade_of(z["score"])
            if c[i] > z["dist"]:
                continue
            keep_s.append(z)
        supplies = keep_s[-MAX_ZONES:]

        if want is not None and i in want:
            win_lo = i - start_win
            d_snap[i] = tuple(
                (z["born"], z["prox"], z["dist"], z["tests"], z["score"], z["n_base"],
                 z["n_legout"], z["has_gap"], z["body_ratio"])
                for z in demands if z["born"] >= win_lo
            )
            s_snap[i] = tuple(
                (z["born"], z["prox"], z["dist"], z["tests"], z["score"], z["n_base"],
                 z["n_legout"], z["has_gap"], z["body_ratio"])
                for z in supplies if z["born"] >= win_lo
            )
    return d_snap, s_snap


def zone_relation(ltp, prox, dist, side):
    lo, hi = min(prox, dist), max(prox, dist)
    if lo <= ltp <= hi:
        return "IN", 0.0
    if side == "DEMAND":
        if hi < ltp <= hi * (1 + NEAR_PCT):
            return "NEAR", (ltp - hi) / hi * 100.0
        if ltp < lo:
            return "BROKEN", (lo - ltp) / lo * 100.0
        return "AWAY", (ltp - hi) / hi * 100.0
    if lo * (1 - NEAR_PCT) <= ltp < lo:
        return "NEAR", (lo - ltp) / lo * 100.0
    if ltp > hi:
        return "BROKEN", (ltp - hi) / hi * 100.0
    return "AWAY", (lo - ltp) / lo * 100.0


def pick_best_demand(ltp, d_snaps):
    """Best fresh demand zone IN/NEAR, preferring fresh & higher score."""
    cands = []
    for z in d_snaps:
        rel, d = zone_relation(ltp, z[1], z[2], "DEMAND")
        if rel in ("IN", "NEAR"):
            cands.append((z, rel, d))
    if not cands:
        return None
    cands.sort(key=lambda t: (0 if t[1] == "IN" else 1, t[0][3], -t[0][4]))
    return cands[0][0]

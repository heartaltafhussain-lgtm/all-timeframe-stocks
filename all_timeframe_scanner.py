#!/usr/bin/env python3
"""
ALL TIMEFRAME STOCKS — NSE 500 GTF MULTI-TIMEFRAME SCANNER  v5.0
=========================================================
Pehle wala scanner sab combo bands ke picks dikhata tha. Backtest
(Jan 2024 - Aug 2026, 783 filled trades) ke baad ye changes kiye gaye:

  BEFORE (v3.19):  win 36% | avg +0.02R | max DD -81R  -> break-even
  AFTER  (v4.0):   win 42% | avg +0.31R | max DD -16R  (strict filter, tested)

STRICT TOP-3 FILTER (backtest-tested):
  1. Sirf SUPER combo (>= 11.0)
  2. Sirf FRESH zones (0 tests)
  3. Sector whitelist (OIL, FMCG, BANK, HEALTHCARE, INFRA, AUTO, FINSERVICE, IT)
  4. 1D zone score >= 8.0 (optional, default ON)
  5. Picks na ho to "NO STRICT PICKS TODAY - WAIT" (empty top3, weak picks nahi)

  ⚠ Backtest me ye filters ulta nuksan karte hain, isliye REMOVED/included nahi:
     - "sirf IN-zone (BUY READY)" picks  -> win 19%, SL hit 74%
     - high-volume (2x+) picks           -> SL hit 84%
     - dual-zone compulsory filter       -> negative edge (v5.1 me FIXED:
       TRADE STOCKS section ab strict quality gate ke saath hai — strict_trade_excl())

v5.2 (TV-ZONE ALIGN + NO-VANISH FIX — Aug 2026):
  BUG-1 FIX (FACT missing): zone ab impulse (leg-out) candle ke FULL RANGE [Low-High]
     pe banta hai — bilkul TradingView "GTF Demand Supply Pro v4.0" ki tarah.
     Pehle drop-candle ke prox/dist se patla sliver banta tha (FACT: 738-749),
     jabki TV wahi zone 765-797 pe dikhata tha -> price "IN zone" hone ke bawajood
     scanner "AWAY" bol ke stock poore dashboard se hata deta tha.
  BUG-2 FIX (vanishing stocks): pehle sirf IN/NEAR (2%) wale stocks dikhte the.
     Ab WATCH band (8%) ke andar active zone wala stock "PULLBACK WATCH" ke saath
     list me rehta hai — signal dene wala stock aise kabhi gayab nahi hoga.
  + Har stock ka full zone ladder (last + next 1D/1M support) aur NEW strength
    score (freshness/base/departure/volume/age/HTF) popup ke liye JSON me.

v5.1 (STRICT TRADE FIX): dual-zone (TRADE STOCKS) stocks ab strict gate se filter hote
hain — DEMAND + whitelist + FRESH + 1D/1M >= 7 + normal vol. Backtest (May-Aug 2026):
RAW win 41% / +0.36R / PF 1.62 / DD -8.0R  ->  STRICT win 50% / +0.50R / PF 2.0 / DD -3.0R

GitHub Actions: Mon-Fri 15:45 IST
Password ref: 7004602
"""

from __future__ import annotations

import csv
import datetime as dt
import html as htmllib
import json
import math
import os
import re
import sys
import time
import urllib.request
from collections import defaultdict

import numpy as np
import pandas as pd
import yfinance as yf

VERSION = "v5.3 All Timeframe Stocks (TV-ZONE ALIGN + NO-VANISH + SWING 4-5D)"
PASSWORD_REF = "7004602"

# ---------------- v5.2 NO-VANISH WATCH BAND ----------------
# IN/NEAR (2%) ke bahar magar active zone ke itne paas wala stock poore dashboard
# se GAYAB na ho — "PULLBACK WATCH" flag ke saath list me rehta hai.
WATCH_PCT = 0.08        # 8% doori tak watch (1D aur 1M dono ke liye)

# ---------------- STRICT TOP-3 FILTER CONFIG (backtest-tested) ----------------
STRICT_MIN_COMBO = 11.0        # sirf SUPER combo picks
STRICT_FRESH_ONLY = True       # sirf 0-test (fresh) zones
STRICT_MIN_1D_SCORE = 8.0      # 1D zone score >= 8.0 (0.0 = disable)
STRICT_SECTORS = {
    "OIL", "FMCG", "BANK", "HEALTHCARE", "INFRA", "AUTO", "FINSERVICE", "IT",
}
# Backtest me ye sectors negative the (avgR): PSUBANK -0.46, CONSUMPTION -0.63,
# PVTBANK -0.53, CPSE -0.17, REALTY -0.11, METAL -0.11  -> whitelist me NAHI hain.

# ---------------- COURSE MODE (Ep 5/6/8 vetoes — backtest-validated) ----------------
# GTF course ke 2 rules jo data pe confirm hue:
#   Ep 5/6: >5 base candles = GARBAGE zone (win sirf 15%, SL-hit 60%)
#   Ep 8:   trade score <5.5 = WEAK zone (avgR negative)
# Veto lagane se backtest: +0.32R -> +0.61R, win 42% -> 50%, PF 2.29
# (trade-off: signals ~74% kam — quality over quantity, course philosophy)
COURSE_MODE_ENABLED = True      # False karne se purana behavior (veto off)
GARBAGE_BASE_LIMIT = 5          # >5 base candles = garbage
MIN_ZONE_SCORE = 5.5            # course 7-pt trade score minimum

try:
    from gtf_v2 import detect_zones_v2, pick_best_demand as pick_best_demand_v2
    _COURSE_VETO_AVAILABLE = True
except ImportError:  # gtf_v2.py missing -> veto silently off
    _COURSE_VETO_AVAILABLE = False

IMPULSE_ATR = 0.35
IMPULSE_BODY_PCT = 75.0
MIN_ZONE_ATR = 0.05
MAX_ZONE_ATR = 1.80
NEAR_PCT = 0.02
ATR_LEN = 14
LOOKBACK_BARS = 220
MAX_ZONES = 6
BATCH_SIZE = 60
OHLC_PERIOD = "3y"

PSU_BANKS = {
    "SBIN", "PNB", "BANKBARODA", "CANBK", "UNIONBANK", "INDIANB",
    "BANKINDIA", "MAHABANK", "CENTRALBK", "IOB", "UCOBANK", "PSB",
    "J&KBANK", "UCOBANK", "MAHABANK",
}
NIFTY_BANK_MAJORS = {
    "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "INDUSINDBK",
    "IDFCFIRSTB", "FEDERALBNK", "AUBANK", "BANDHANBNK", "YESBANK",
}
CPSE_SYMS = {
    "NTPC", "POWERGRID", "COALINDIA", "ONGC", "BEL", "BHEL", "NHPC",
    "GAIL", "OIL", "CONCOR", "NBCC", "IRCTC", "IRFC", "RVNL", "HAL",
    "BEML", "HUDCO", "NLCINDIA", "SJVN", "NMDC",
}

SECTOR_FROM_INDUSTRY = {
    "financial services": "FINSERVICE",
    "information technology": "IT",
    "automobile and auto components": "AUTO",
    "healthcare": "HEALTHCARE",
    "fast moving consumer goods": "FMCG",
    "metals & mining": "METAL",
    "oil gas & consumable fuels": "OIL",
    "power": "CPSE",
    "realty": "REALTY",
    "construction": "INFRA",
    "construction materials": "INFRA",
    "capital goods": "INFRA",
    "consumer services": "CONSUMPTION",
    "consumer durables": "CONSUMPTION",
    "telecommunication": "CONSUMPTION",
    "services": "CONSUMPTION",
    "chemicals": "FMCG",
    "textiles": "CONSUMPTION",
    "media entertainment & publication": "CONSUMPTION",
    "diversified": "CONSUMPTION",
}

INDEX_TICKERS = {
    "BANK": "^NSEBANK",
    "IT": "^CNXIT",
    "AUTO": "^CNXAUTO",
    "METAL": "^CNXMETAL",
    "PHARMA": "^CNXPHARMA",
    "FMCG": "^CNXFMCG",
    "OIL": "^CNXENERGY",
    "REALTY": "^CNXREALTY",
    "INFRA": "^CNXINFRA",
    "PSUBANK": "^CNXPSUBANK",
    "FINSERVICE": "NIFTY_FIN_SERVICE.NS",
    "CONSUMPTION": "^CNXCONSUM",
    "PVTBANK": "^NSEBANK",
    "HEALTHCARE": "^CNXPHARMA",
}

SECTOR_NAMES = {
    "BANK": "NIFTY BANK", "OIL": "NIFTY ENERGY", "IT": "NIFTY IT", "AUTO": "NIFTY AUTO",
    "METAL": "NIFTY METAL", "PHARMA": "NIFTY PHARMA", "FMCG": "NIFTY FMCG", "REALTY": "NIFTY REALTY",
    "INFRA": "NIFTY INFRA", "PSE": "NIFTY PSE", "FINSERVICE": "NIFTY FIN SERVICE",
    "PSUBANK": "NIFTY PSU BANK", "PVTBANK": "NIFTY PVT BANK", "CONSUMPTION": "NIFTY CONSUMPTION",
    "HEALTHCARE": "NIFTY HEALTHCARE", "CPSE": "NIFTY CPSE",
}


def today_ist():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).replace(tzinfo=None)


def log(msg):
    print(msg, flush=True)


def send_telegram_alert(message):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not (bot_token and chat_id):
        return
    try:
        import urllib.parse
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        ).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=8)
    except Exception as exc:
        log(f"  [TELEGRAM ERROR] {exc}")


def _clean_html(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    text = htmllib.unescape(text).replace("\xa0", " ").strip()
    return re.sub(r"\s+", " ", text)


def fetch_nifty500_universe():
    """Live Wikipedia constituents, else local CSV baked into the repo."""
    rows = []
    try:
        req = urllib.request.Request(
            "https://en.wikipedia.org/wiki/NIFTY_500",
            headers={"User-Agent": "Mozilla/5.0 GTFScanner/3.19"},
        )
        html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
        idx = html.lower().find('id="constituents"')
        section = html[idx: idx + 300000] if idx >= 0 else html
        nxt = section.lower().find("<h2", 20)
        if nxt > 0:
            section = section[:nxt]
        found = re.findall(
            r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>",
            section,
            re.S | re.I,
        )
        for rec in found:
            comp, industry, sym, series, isin = map(_clean_html, rec)
            if sym and sym.upper() != "SYMBOL":
                rows.append(
                    {
                        "symbol": sym.replace(" ", ""),
                        "company": comp,
                        "industry": industry,
                        "series": series,
                        "isin": isin,
                    }
                )
        if len(rows) >= 400:
            log(f"[*] Wikipedia Nifty 500 universe: {len(rows)} symbols")
            return rows
        log(f"[!] Wikipedia parsed only {len(rows)} rows — falling back to local CSV")
    except Exception as exc:
        log(f"[!] Wikipedia fetch failed ({exc}) — using local CSV")

    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nifty500_universe.csv")
    if os.path.exists(csv_path):
        with open(csv_path, newline="", encoding="utf-8") as fh:
            for rec in csv.DictReader(fh):
                if rec.get("symbol"):
                    rows.append(
                        {
                            "symbol": rec["symbol"].replace(" ", ""),
                            "company": rec.get("company") or rec["symbol"],
                            "industry": rec.get("industry") or "",
                            "series": rec.get("series") or "EQ",
                            "isin": rec.get("isin") or "",
                        }
                    )
        log(f"[*] Local Nifty 500 CSV universe: {len(rows)} symbols")
        return rows
    raise RuntimeError("Nifty 500 universe not available (wiki + local CSV both failed)")


def map_sector(symbol, company, industry):
    ind = (industry or "").strip().lower()
    if symbol in CPSE_SYMS:
        return "CPSE"
    if "pharma" in ind or "pharma" in (company or "").lower():
        return "PHARMA"
    if "bank" in ind or "bank" in (company or "").lower() or symbol in PSU_BANKS or symbol in NIFTY_BANK_MAJORS:
        if symbol in PSU_BANKS or "psu" in (company or "").lower():
            return "PSUBANK"
        if symbol in NIFTY_BANK_MAJORS:
            return "BANK"
        return "PVTBANK"
    if "public sector" in ind or symbol.endswith("PSU"):
        return "PSE"
    return SECTOR_FROM_INDUSTRY.get(ind, "CONSUMPTION")


def yahoo_symbol(nse_sym):
    return f"{nse_sym}.NS"


def extract_ohlcv(raw, ticker):
    if raw is None or getattr(raw, "empty", True):
        return None
    df = None
    if isinstance(raw.columns, pd.MultiIndex):
        lvl0 = set(map(str, raw.columns.get_level_values(0)))
        lvl1 = set(map(str, raw.columns.get_level_values(1)))
        if ticker in lvl0:
            df = raw[ticker].copy()
        elif ticker in lvl1:
            df = raw.xs(ticker, axis=1, level=1).copy()
        else:
            return None
    else:
        df = raw.copy()
    rename = {str(c).strip().title(): str(c).strip().title() for c in df.columns}
    df = df.rename(columns=rename)
    # yfinance sometimes uses lowercase
    colmap = {c.lower(): c for c in df.columns}
    need = {}
    for key in ("open", "high", "low", "close", "volume"):
        if key in colmap:
            need[key.capitalize()] = colmap[key]
        else:
            return None
    out = pd.DataFrame({k: pd.to_numeric(df[v], errors="coerce") for k, v in need.items()})
    out.index = pd.to_datetime(df.index, utc=True, errors="coerce").tz_localize(None)
    out = out.dropna(subset=["Open", "High", "Low", "Close"])
    if len(out) < 40:
        return None
    return out.sort_index()


def resample_ohlc(df, rule):
    res = (
        df.resample(rule, label="right", closed="right")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
        .dropna(subset=["Open", "High", "Low", "Close"])
    )
    return res if len(res) >= 20 else None


def wilder_atr(high, low, close, n=ATR_LEN):
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    prev = np.roll(close, 1)
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))
    tr[0] = high[0] - low[0]
    atr = np.full(len(tr), np.nan, dtype=float)
    if len(tr) < n:
        return atr
    atr[n - 1] = tr[:n].mean()
    alpha = 1.0 / n
    for i in range(n, len(tr)):
        atr[i] = atr[i - 1] * (1 - alpha) + tr[i] * alpha
    return atr


def ema(values, n=20):
    values = np.asarray(values, dtype=float)
    out = np.full(len(values), np.nan)
    if len(values) < n:
        return out
    out[n - 1] = values[:n].mean()
    k = 2.0 / (n + 1.0)
    for i in range(n, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


def grade_of(score):
    if score >= 9.0:
        return "A+"
    if score >= 7.0:
        return "A"
    if score >= 5.5:
        return "B"
    return "C"


def calc_score(tests, body, atr, is_no_base, has_gap, aligned_ema, body_pct):
    f_score = 3.0 if tests == 0 else 1.5 if tests == 1 else 0.0
    if (atr and body >= atr * 1.5) or has_gap:
        s_score = 2.0
    elif atr and body >= atr * 0.45:
        s_score = 1.5
    else:
        s_score = 1.0
    b_score = 1.5 if is_no_base else 2.0
    fsb7 = f_score + s_score + b_score
    bonus = 0.0
    if aligned_ema:
        bonus += 1.0
    if has_gap:
        bonus += 1.0
    if atr and body >= atr * 1.2:
        bonus += 1.0
    if body_pct >= IMPULSE_BODY_PCT:
        bonus += 0.5
    tot = min(fsb7 + min(bonus, 3.0), 10.0)
    return round(tot, 1), grade_of(tot)


def detect_active_zones(df, impulse_body_pct=55.0):
    """
    Indicator 3.15 strict 1-bar turn + v5.2 TV zone align:
      Demand = previous red impulsive + current green impulsive + close > prev close
      Supply = previous green impulsive + current red impulsive + close < prev close
    v5.2: Zone = impulse (leg-out) candle ka FULL range [Low-High] — bilkul
    TradingView "GTF Demand Supply Pro v4.0" boxes jaisa (FACT 1-Apr: 765-797 ✓).
    Birth metadata (n_base, legout xATR, vol_ratio, born_date) bhi capture hota hai
    — popup ke strength score ke liye.
    """
    if df is None or len(df) < ATR_LEN + 5:
        return [], []
    o = df["Open"].to_numpy(float)
    h = df["High"].to_numpy(float)
    l = df["Low"].to_numpy(float)
    c = df["Close"].to_numpy(float)
    vol = df["Volume"].to_numpy(float) if "Volume" in df.columns else None
    atr = wilder_atr(h, l, c)
    ema20 = ema(c, 20)
    start = max(len(df) - LOOKBACK_BARS, ATR_LEN + 1)

    demands = []
    supplies = []

    def n_base_candles(i, a):
        """Leg-out se pehle kitni base (chhoti body) candles thi (cap 12)."""
        n = 0
        j = i - 2  # i-1 impulse drop/rally candle hai, usse pehle base
        while j >= 0 and n < 12:
            b = abs(c[j] - o[j])
            aj = atr[j] if np.isfinite(atr[j]) and atr[j] > 0 else a
            if b < aj * 0.35:
                n += 1
                j -= 1
            else:
                break
        return n

    def vol_ratio_at(i):
        if vol is None or i >= len(vol) or not np.isfinite(vol[i]) or vol[i] <= 0:
            return None
        win = vol[max(0, i - 20):i]
        avg = np.nanmean(win) if len(win) else np.nan
        if not np.isfinite(avg) or avg <= 0:
            return None
        return round(float(vol[i] / avg), 2)

    def overlap(zones, prox, dist):
        for z in zones:
            lo1, hi1 = min(z["prox"], z["dist"]), max(z["prox"], z["dist"])
            lo2, hi2 = min(prox, dist), max(prox, dist)
            ov = min(hi1, hi2) - max(lo1, lo2)
            sz = max(hi2 - lo2, 1e-9)
            if ov > 0 and ov / sz > 0.50:
                return True
        return False

    for i in range(start, len(df)):
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        body = abs(c[i] - o[i])
        body1 = abs(c[i - 1] - o[i - 1])
        rng = max(h[i] - l[i], 1e-9)
        body_pct = body / rng * 100.0
        is_green0 = c[i] > o[i]
        is_red0 = c[i] < o[i]
        is_green1 = c[i - 1] > o[i - 1]
        is_red1 = c[i - 1] < o[i - 1]
        has_gap_up = (o[i] - h[i - 1]) >= c[i] * 0.003
        has_gap_dn = (l[i - 1] - o[i]) >= c[i] * 0.003
        aligned_up = np.isfinite(ema20[i]) and c[i] > ema20[i]
        aligned_dn = np.isfinite(ema20[i]) and c[i] < ema20[i]
        impulse_ok = (
            body >= a * IMPULSE_ATR
            and body1 >= a * IMPULSE_ATR
            and body_pct >= impulse_body_pct
        )

        if impulse_ok and is_red1 and is_green0 and c[i] > c[i - 1]:
            # v5.2 TV-ALIGN: zone = impulse (leg-out) candle ka FULL range [Low-High]
            # (TradingView GTF Demand Supply Pro jaisa — e.g. FACT 1-Apr-26: 765-797)
            prox = float(h[i])
            dist = float(l[i])
            height = prox - dist
            if a * MIN_ZONE_ATR <= height <= a * MAX_ZONE_ATR and not overlap(demands, prox, dist):
                score, grade = calc_score(0, body, a, True, has_gap_up, aligned_up, body_pct)
                demands.append(
                    {
                        "side": "DEMAND",
                        "pat": "DR DEMAND",
                        "prox": round(prox, 2),
                        "dist": round(dist, 2),
                        "born": i,
                        "born_date": str(df.index[i].date()),
                        "tests": 0,
                        "score": score,
                        "grade": grade,
                        "birth_score": score,
                        "birth_grade": grade,
                        "body_pct": round(body_pct, 1),
                        "n_base": n_base_candles(i, a),
                        "legout": round(body / a, 2),
                        "vol_ratio": vol_ratio_at(i),
                    }
                )
                if len(demands) > MAX_ZONES:
                    demands.pop(0)

        if impulse_ok and is_green1 and is_red0 and c[i] < c[i - 1]:
            # v5.2 TV-ALIGN: supply zone = impulse (drop) candle ka FULL range [Low-High]
            prox = float(l[i])
            dist = float(h[i])
            height = dist - prox
            if a * MIN_ZONE_ATR <= height <= a * MAX_ZONE_ATR and not overlap(supplies, prox, dist):
                score, grade = calc_score(0, body, a, True, has_gap_dn, aligned_dn, body_pct)
                supplies.append(
                    {
                        "side": "SUPPLY",
                        "pat": "RD SUPPLY",
                        "prox": round(prox, 2),
                        "dist": round(dist, 2),
                        "born": i,
                        "born_date": str(df.index[i].date()),
                        "tests": 0,
                        "score": score,
                        "grade": grade,
                        "birth_score": score,
                        "birth_grade": grade,
                        "body_pct": round(body_pct, 1),
                        "n_base": n_base_candles(i, a),
                        "legout": round(body / a, 2),
                        "vol_ratio": vol_ratio_at(i),
                    }
                )
                if len(supplies) > MAX_ZONES:
                    supplies.pop(0)

        # tests + invalidation on later bars
        last = i == len(df) - 1
        # we apply tests/invalid only using the current bar against already born zones
        keep_d = []
        for z in demands:
            if i <= z["born"]:
                keep_d.append(z)
                continue
            touch_now = l[i] <= z["prox"] and l[i] >= z["dist"]
            touch_prev = l[i - 1] <= z["prox"] and l[i - 1] >= z["dist"] if i - 1 > z["born"] else False
            if touch_now and not touch_prev:
                z["tests"] += 1
                z["score"], z["grade"] = calc_score(
                    z["tests"], body, a, True, False, aligned_up, z.get("body_pct", 0)
                )
            if c[i] < z["dist"]:
                continue  # invalidated, drop
            keep_d.append(z)
        demands = keep_d[-MAX_ZONES:]

        keep_s = []
        for z in supplies:
            if i <= z["born"]:
                keep_s.append(z)
                continue
            touch_now = h[i] >= z["prox"] and h[i] <= z["dist"]
            touch_prev = h[i - 1] >= z["prox"] and h[i - 1] <= z["dist"] if i - 1 > z["born"] else False
            if touch_now and not touch_prev:
                z["tests"] += 1
                z["score"], z["grade"] = calc_score(
                    z["tests"], body, a, True, False, aligned_dn, z.get("body_pct", 0)
                )
            if c[i] > z["dist"]:
                continue
            keep_s.append(z)
        supplies = keep_s[-MAX_ZONES:]

        _ = last  # reserved

    return demands, supplies


def zone_relation(ltp, zone):
    if not zone:
        return "NONE", 999.0
    prox, dist = zone["prox"], zone["dist"]
    lo, hi = (min(prox, dist), max(prox, dist))
    if lo <= ltp <= hi:
        return "IN", 0.0
    if zone["side"] == "DEMAND":
        # just above proximal = approaching demand
        if hi < ltp <= hi * (1 + NEAR_PCT):
            return "NEAR", (ltp - hi) / hi * 100.0
        if ltp < lo:
            return "BROKEN", (lo - ltp) / lo * 100.0
        return "AWAY", (ltp - hi) / hi * 100.0
    # supply
    if lo * (1 - NEAR_PCT) <= ltp < lo:
        return "NEAR", (lo - ltp) / lo * 100.0
    if ltp > hi:
        return "BROKEN", (ltp - hi) / hi * 100.0
    return "AWAY", (lo - ltp) / lo * 100.0


def fmt_zone(zone):
    if not zone:
        return "— NO ACTIVE ZONE —"
    lo, hi = sorted((zone["dist"], zone["prox"]))
    return f"{lo} - {hi} {zone['pat']}"


def fmt_score(zone):
    if not zone:
        return "—"
    return f"{zone['score']:.1f} {zone['grade']}"


def freshness(tests):
    if tests <= 0:
        return "🟢 0 TESTS (FRESH)"
    if tests == 1:
        return "🟡 1 TEST (TESTED)"
    return f"🔴 {tests} TESTS (WEAK)"


def weekly_trend(wdf):
    if wdf is None or len(wdf) < 25:
        return "1W DATA THIN"
    c = wdf["Close"].to_numpy(float)
    e = ema(c, 20)
    last_c, last_e = c[-1], e[-1]
    prev_e = e[-2] if np.isfinite(e[-2]) else last_e
    if not np.isfinite(last_e):
        return "1W EMA FLAT"
    if last_c > last_e and last_e >= prev_e:
        return "1W UP • 20 EMA BULLISH"
    if last_c < last_e and last_e <= prev_e:
        return "1W DOWN • 20 EMA BEARISH"
    return "1W SIDEWAYS • 20 EMA FLAT"


def volume_status(df):
    if df is None or "Volume" not in df.columns or len(df) < 21:
        return "NORMAL VOL", 1.0
    vol = df["Volume"].to_numpy(float)
    avg = np.nanmean(vol[-21:-1]) if np.nanmean(vol[-21:-1]) > 0 else 1.0
    ratio = float(vol[-1] / avg)
    if ratio >= 2.5:
        return "🔥 2.5x VOL EXPLOSION", round(ratio, 2)
    if ratio >= 1.8:
        return "🔥 1.8x HIGH VOL", round(ratio, 2)
    return "NORMAL VOL", round(ratio, 2)


def pick_best_side(ltp, demands, supplies):
    """Choose the most relevant active zone for TODAY's filter."""
    candidates = []
    for z in demands[-3:]:
        rel, dist_pct = zone_relation(ltp, z)
        if rel in ("IN", "NEAR"):
            candidates.append((z, rel, dist_pct))
    for z in supplies[-3:]:
        rel, dist_pct = zone_relation(ltp, z)
        if rel in ("IN", "NEAR"):
            candidates.append((z, rel, dist_pct))
    if not candidates:
        return None, "NONE", 999.0
    # prefer IN over NEAR, then higher score, then closer
    candidates.sort(key=lambda t: (0 if t[1] == "IN" else 1, -t[0]["score"], t[2]))
    z, rel, dist_pct = candidates[0]
    return z, rel, dist_pct


# ---------------- v5.2 NO-VANISH WATCH + ANALYSIS HELPERS ----------------
def watch_relation(ltp, zone):
    """IN/NEAR se AWAY magar WATCH_PCT (8%) ke andar active zone -> PULLBACK WATCH."""
    if not zone:
        return False
    rel, _ = zone_relation(ltp, zone)
    if rel in ("IN", "NEAR"):
        return False
    lo, hi = sorted((zone["dist"], zone["prox"]))
    if zone["side"] == "DEMAND":
        gap = (ltp - hi) / hi if ltp > hi else (lo - ltp) / lo
    else:
        gap = (lo - ltp) / lo if ltp < lo else (ltp - hi) / hi
    return 0 <= gap <= WATCH_PCT


def best_active_zone(ltp, demands, supplies):
    """v5.2: IN/NEAR pehle (pick_best_side); warna sabse PAAS wala active zone
    (WATCH band check ke liye) — warna 8% ke andar wale stocks miss ho jaate the."""
    z, rel, _ = pick_best_side(ltp, demands, supplies)
    if z is not None:
        return z, rel
    best, best_gap = None, 1e9
    for zz in list(demands[-3:]) + list(supplies[-3:]):
        lo, hi = sorted((zz["dist"], zz["prox"]))
        if zz["side"] == "DEMAND":
            g = (ltp - hi) / hi if ltp > hi else (lo - ltp) / lo
        else:
            g = (lo - ltp) / lo if ltp < lo else (ltp - hi) / hi
        if 0 <= g < best_gap:
            best, best_gap = zz, g
    if best is None:
        return None, "NONE"
    return best, ("WATCH" if best_gap <= WATCH_PCT else "AWAY")


def zone_public(ltp, z, htf_demands=None, w_trend_up=False, age_bars=None):
    """Popup ke liye zone ka public dict — existing grade + NEW strength score (dono)."""
    lo, hi = sorted((z["dist"], z["prox"]))
    tests = int(z.get("tests", 0))
    n_base = z.get("n_base")
    legout = z.get("legout")
    vol_ratio = z.get("vol_ratio")

    parts = {}
    # 1) freshness / retests (25%)
    parts["freshness"] = 10.0 if tests == 0 else 7.0 if tests == 1 else 4.0 if tests == 2 else 2.0
    # 2) base candles (15%) — course Ep5/6: >5 base = garbage
    parts["base"] = (10.0 if n_base <= 2 else 8.0 if n_base <= 5 else 3.0) if n_base is not None else 6.0
    # 3) departure strength (20%) — leg-out body xATR
    parts["departure"] = (10.0 if legout >= 1.5 else 8.0 if legout >= 1.0 else 6.0 if legout >= 0.6 else 4.0) if legout is not None else 6.0
    # 4) volume confirmation (15%)
    parts["volume"] = (10.0 if vol_ratio >= 2.5 else 8.0 if vol_ratio >= 1.8 else 6.0 if vol_ratio >= 1.2 else 4.0 if vol_ratio >= 0.8 else 3.0) if vol_ratio is not None else 5.0
    # 5) zone age (10%) — fresh zone > purana zone
    if age_bars is None:
        parts_age = 6.0
    else:
        parts_age = 10.0 if age_bars <= 5 else 7.0 if age_bars <= 15 else 4.0 if age_bars <= 40 else 2.0
    # 6) HTF confluence (15%)
    htf = 3.0
    if htf_demands:
        for m in htf_demands:
            mlo, mhi = sorted((m["dist"], m["prox"]))
            if mlo <= hi * 1.05 and mhi >= lo * 0.95:
                htf = 10.0
                break
        else:
            htf = 6.0 if w_trend_up else 3.0
    elif w_trend_up:
        htf = 6.0
    parts["htf"] = htf

    weights = {"freshness": 0.25, "base": 0.15, "departure": 0.20, "volume": 0.15, "age": 0.10, "htf": 0.15}
    parts["age"] = parts_age
    total = round(sum(parts[k] * weights[k] for k in weights), 1)
    verdict = "STRONG" if total >= 7.5 else "MEDIUM" if total >= 5.5 else "WEAK"

    return {
        "lo": lo,
        "hi": hi,
        "pat": z.get("pat", ""),
        "score": z.get("score"),
        "grade": z.get("grade", ""),
        "birth_score": z.get("birth_score"),
        "birth_grade": z.get("birth_grade", ""),
        "tests": tests,
        "born": z.get("born_date"),
        "n_base": n_base,
        "legout": legout,
        "vol_ratio": vol_ratio,
        "strength": {
            "total": total,
            "verdict": verdict,
            "parts": {k: round(v, 1) for k, v in parts.items()},
        },
    }


def support_ladder(ltp, demands, htf_demands=None, w_trend_up=False, last_idx=None):
    """Support ladder (sirf DEMAND zones): last = current/nearest support
    (price ke sabse paas wala at/below), next = uske neeche wala upcoming support."""
    zs = sorted(demands, key=lambda z: -max(z["dist"], z["prox"]))  # highest first
    pubs = [
        zone_public(ltp, z, htf_demands, w_trend_up,
                    (last_idx - z["born"]) if (last_idx is not None and isinstance(z.get("born"), int)) else None)
        for z in zs
    ]
    cur = None
    for idx, z in enumerate(zs):
        if max(z["dist"], z["prox"]) <= ltp * 1.001:
            cur = idx
            break
    if cur is None and zs:
        cur = 0  # price sabhi zones ke neeche (rare) — highest zone hi "last"
    last = pubs[cur] if cur is not None else None
    nxt = pubs[cur + 1] if cur is not None and cur + 1 < len(pubs) else None
    return last, nxt, pubs[:4]


def download_batches(tickers):
    frames = {}
    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i : i + BATCH_SIZE]
        log(f"[*] Downloading batch {i // BATCH_SIZE + 1}/{(len(tickers) - 1) // BATCH_SIZE + 1} ({len(batch)} tickers)")
        try:
            raw = yf.download(
                tickers=batch,
                period=OHLC_PERIOD,
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
                timeout=60,
            )
        except Exception as exc:
            log(f"    batch error: {exc}")
            raw = None
        if raw is None or getattr(raw, "empty", True):
            time.sleep(1.0)
            continue
        for tkr in batch:
            df = extract_ohlcv(raw, tkr)
            if df is None:
                # v5.2.1: batch me chhoot gaye (rate-limit drop) — individually retry
                try:
                    time.sleep(0.25)
                    solo = yf.download(
                        tickers=tkr, period=OHLC_PERIOD, interval="1d",
                        group_by="ticker", auto_adjust=True, progress=False, timeout=30,
                    )
                    df = extract_ohlcv(solo, tkr)
                except Exception:
                    df = None
                if df is None:
                    # v8 chart API fallback — batch endpoint se zyada reliable
                    try:
                        time.sleep(0.5)
                        h = yf.Ticker(tkr).history(period=OHLC_PERIOD, auto_adjust=True, timeout=30)
                        df = extract_ohlcv(h, tkr)
                    except Exception:
                        df = None
            if df is not None:
                frames[tkr] = df
        time.sleep(0.4)
    return frames


def build_sector_cards(stock_rows, index_ltps):
    by_sec = defaultdict(list)
    for row in stock_rows:
        by_sec[row["sector"]].append(row["type"])

    def card(sec_id, name, desc_default):
        types = by_sec.get(sec_id, [])
        dem = sum(1 for t in types if t == "DEMAND")
        sup = sum(1 for t in types if t == "SUPPLY")
        if dem > sup and dem > 0:
            status, typ, score, bonus = "IN DEMAND", "DEMAND", "9.0 A+", "+2.0 PTS DEMAND"
        elif sup > dem and sup > 0:
            status, typ, score, bonus = "NEAR SUPPLY", "SUPPLY", "8.5 A", "0.0 PTS (Supply Near)"
        else:
            status, typ, score, bonus = "EQUILIBRIUM", "NEUTRAL", "8.0 A", "+1.0 PT TREND"
        ltp = index_ltps.get(sec_id)
        ltp_txt = f"{ltp:,.2f}" if isinstance(ltp, (int, float)) else "—"
        desc = (
            f"{name}: {dem} demand / {sup} supply zone stocks in today's auto-filter. {desc_default}"
        )
        return {
            "id": sec_id,
            "name": name,
            "status": status,
            "type": typ,
            "score": score,
            "ltp": ltp_txt,
            "desc": desc,
            "bonus": bonus,
        }

    cards = [
        {
            "id": "ALL",
            "name": "ALL SECTORS",
            "status": "AUTO FILTER",
            "type": "NEUTRAL",
            "score": "LIVE",
            "ltp": "NSE 500",
            "desc": f"Only stocks sitting IN/NEAR a valid unmitigated 1D or 1M GTF zone on {today_ist().strftime('%Y-%m-%d')}.",
            "bonus": "AUTO",
        },
        card("BANK", "NIFTY BANK", "Banking heavyweights."),
        card("OIL", "NIFTY ENERGY", "Oil & energy names."),
        card("IT", "NIFTY IT", "IT / tech names."),
        card("AUTO", "NIFTY AUTO", "Auto & auto-ancillary."),
        card("METAL", "NIFTY METAL", "Metals & mining."),
        card("PHARMA", "NIFTY PHARMA", "Pharma names."),
        card("FMCG", "NIFTY FMCG", "FMCG / staples."),
        card("REALTY", "NIFTY REALTY", "Realty names."),
        card("INFRA", "NIFTY INFRA", "Infra / capital goods."),
        card("PSE", "NIFTY PSE", "Public sector enterprises."),
        card("FINSERVICE", "NIFTY FIN SERVICE", "NBFCs & financials."),
        card("PSUBANK", "NIFTY PSU BANK", "PSU banks."),
        card("PVTBANK", "NIFTY PVT BANK", "Private banks."),
        card("CONSUMPTION", "NIFTY CONSUMPTION", "Consumption theme."),
        card("HEALTHCARE", "NIFTY HEALTHCARE", "Hospitals & healthcare."),
        card("CPSE", "NIFTY CPSE", "Central PSUs."),
    ]
    return cards


def course_zone_check(df, ltp):
    """Course veto (Ep 5/6/8) — backtest-validated.
    Returns (pass, info):
      - garbage base (>GARBAGE_BASE_LIMIT candles) -> reject
      - weak course trade score (<MIN_ZONE_SCORE)    -> reject
      - course detector ko zone nahi mila           -> pass (veto nahi lagta)
    """
    info = {"hasZone": False, "note": "course zone nahi mila - pass"}
    if df is None or len(df) < 40:
        return True, info
    d = df.tail(220)
    o = d["Open"].to_numpy(float)
    h = d["High"].to_numpy(float)
    l = d["Low"].to_numpy(float)
    c = d["Close"].to_numpy(float)
    ds, _ = detect_zones_v2(o, h, l, c, snapshot_idx=[len(c) - 1], start_win=220)
    z = pick_best_demand_v2(ltp, ds.get(len(c) - 1, ()))
    if z is None:
        return True, info
    _born, _prox, _dist, _tests, score, n_base, n_legout, has_gap, body_ratio = z
    if n_base > GARBAGE_BASE_LIMIT:
        verdict = "GARBAGE"
    elif score < MIN_ZONE_SCORE:
        verdict = "WEAK"
    else:
        verdict = "PASS"
    info = {
        "hasZone": True,
        "nBase": int(n_base),
        "nLegout": int(n_legout),
        "gap": bool(has_gap),
        "score": float(score),
        "grade": grade_of(score),
        "bodyRatio": float(body_ratio),
        "verdict": verdict,
    }
    return (verdict == "PASS"), info


def build_sector_zones(index_frames, index_ltps, stock_rows):
    """Sector INDEX ka apna 1M zone status (demand/supply) + stock counts."""
    by_sec = defaultdict(list)
    for row in stock_rows:
        by_sec[row["sector"]].append(row["type"])
    out = []
    for sec_id in SECTOR_NAMES:
        name = SECTOR_NAMES[sec_id]
        df = index_frames.get(sec_id)
        status, zone_txt, score_txt, side = "NO INDEX DATA", "—", "—", "NEUTRAL"
        if df is not None and len(df) >= 40:
            mdf = resample_ohlc(df, "ME")
            if mdf is not None and len(mdf) >= 12:
                month_d, month_s = detect_active_zones(mdf, impulse_body_pct=50.0)
                ltp = float(df["Close"].iloc[-1])
                z, rel, _ = pick_best_side(ltp, month_d, month_s)
                if z is not None and rel in ("IN", "NEAR"):
                    side = z["side"]
                    status = f"IN {side} ZONE" if rel == "IN" else f"NEAR {side} ZONE"
                    zone_txt = fmt_zone(z)
                    score_txt = fmt_score(z)
                else:
                    status = "NO ACTIVE 1M ZONE"
        dem = sum(1 for t in by_sec.get(sec_id, []) if t == "DEMAND")
        sup = sum(1 for t in by_sec.get(sec_id, []) if t == "SUPPLY")
        ltp = index_ltps.get(sec_id)
        out.append({
            "id": sec_id,
            "name": name,
            "status": status,
            "side": side,
            "zone": zone_txt,
            "score": score_txt,
            "ltp": round(float(ltp), 2) if isinstance(ltp, (int, float)) else None,
            "demCount": dem,
            "supCount": sup,
        })
    return out


def make_top3(stock_rows, frames=None):
    """STRICT v4.0 + COURSE MODE veto: sirf backtest-tested quality picks,
    warna empty list (dashboard 'NO STRICT PICKS TODAY - WAIT' dikhayega)."""
    picks = [
        r
        for r in stock_rows
        if r["type"] == "DEMAND"
        and r.get("rel") in ("IN", "NEAR")
        and "UP" in (r.get("w_trend") or "")
        and r.get("tests_count", 99) == 0              # FRESH only (v3.19: <=1)
        and _combo_num(r.get("combo")) >= STRICT_MIN_COMBO      # SUPER only
        and r.get("sector") in STRICT_SECTORS          # sector whitelist
        and _score_num(r.get("s1d")) >= STRICT_MIN_1D_SCORE     # 1D quality
    ]
    if not picks:
        return []
    picks.sort(key=lambda r: (-_combo_num(r.get("combo")), -_score_num(r.get("s1d")), r.get("sym")))
    top = []
    n_course_rejected = 0
    for r in picks:
        course_info = {"note": "course mode off"}
        if COURSE_MODE_ENABLED and _COURSE_VETO_AVAILABLE and frames is not None:
            df = frames.get(f"{r['sym']}.NS")
            ok, course_info = course_zone_check(df, float(r["ltp"]))
            if not ok:
                n_course_rejected += 1
                log(
                    f"  [COURSE VETO] {r['sym']} reject ({course_info['verdict']}: "
                    f"base={course_info.get('nBase')} score={course_info.get('score')})"
                )
                continue
        ltp = float(r["ltp"])
        # recover daily demand proximal/distal from z1d text
        nums = re.findall(r"(\d+(?:\.\d+)?)", r.get("z1d") or "")
        if len(nums) >= 2:
            lo, hi = float(nums[0]), float(nums[1])
        else:
            lo, hi = round(ltp * 0.97, 2), round(ltp * 0.995, 2)
        entry_hi = hi
        entry_lo = round((lo + hi) / 2.0, 2)
        sl = round(lo * 0.997, 2)
        risk = max(entry_hi - sl, 0.1)
        qty = max(int(round(1000.0 / risk)), 1)
        t1 = round(entry_hi + 2 * risk, 2)
        t2 = round(entry_hi + 3 * risk, 2)
        move = max(int(round(3000.0 / max(qty, 1))), 1)
        note = (
            "⚠ IN-ZONE: chase mat karo — sirf limit order pe entry (backtest: "
            "IN picks win 19% SL 74%)."
            if r.get("rel") == "IN"
            else "NEAR/APPROACHING: entry zone ke limit order pe hi entry."
        )
        top.append(
            {
                "sym": r["sym"],
                "comp": r["comp"],
                "sector": r["sector"],
                "ltp": ltp,
                "combo": r["combo"],
                "z1d": r["z1d"],
                "z1m": r["z1m"],
                "s1d": r["s1d"],
                "s1m": r["s1m"],
                "rel": r.get("rel"),
                "w_trend": r.get("w_trend"),
                "entryLo": entry_lo,
                "entryHi": entry_hi,
                "sl": sl,
                "t1": t1,
                "t2": t2,
                "qty": qty,
                "moveFor3k": move,
                "note": note,
                "course": course_info,
                "secBonus": r.get("secBonus", ""),
            }
        )
        if len(top) >= 3:
            break
    return top


def _combo_num(txt):
    m = re.search(r"(\d+(?:\.\d+)?)\s*/\s*10", str(txt or ""))
    return float(m.group(1)) if m else 0.0


def _score_num(txt):
    m = re.search(r"(\d+(?:\.\d+)?)", str(txt or ""))
    return float(m.group(1)) if m else 0.0


# ---------------- v5.1 STRICT TRADE STOCKS (dual-zone negative-edge FIX) ----------------
# Pehle TRADE STOCKS = har dual-zone stock dikhata tha (tested zones, weak scores,
# negative sectors sab) — backtest me negative edge. Fix: ab dual-zone stocks pe
# strict engine wale hi quality filters lagte hain. Backtest (May-Aug 2026,
# 102 dual-zone demand signals, dedup 5-din):
#   RAW    win 41% | avg +0.31R | PF 1.54 | DD -7.8R | SL 55%
#   STRICT win 50% | avg +0.50R | PF 2.00 | DD -3.0R | SL 50%
STRICT_TRADE_MIN_SCORE = 7.0   # 1D AUR 1M dono scores >= 7 (A grade)


def _zone_parts(z):
    """'5672.2 - 5700.0 DR DEMAND' -> (lo, hi, side) ya None."""
    if not z or "NO ACTIVE" in str(z) or "\u2014" in str(z):
        return None
    nums = re.findall(r"(\d+(?:\.\d+)?)", str(z))
    if len(nums) < 2:
        return None
    a, b = float(nums[0]), float(nums[1])
    side = "SUPPLY" if "SUPPLY" in str(z) else "DEMAND"
    return min(a, b), max(a, b), side


def _near_rel(ltp, parts):
    if parts is None or not ltp:
        return None
    lo, hi, side = parts
    if lo <= ltp <= hi:
        return "IN"
    if side == "DEMAND" and hi < ltp <= hi * 1.02:
        return "NEAR"
    if side == "SUPPLY" and lo * 0.98 <= ltp < lo:
        return "NEAR"
    return None


def _is_dual_zone(r):
    """Server flag pehle; purani history rows ke liye zones se derive."""
    if isinstance(r.get("inDaily"), bool) and isinstance(r.get("inMonthly"), bool):
        return bool(r.get("inDaily") and r.get("inMonthly"))
    z1 = _zone_parts(r.get("z1d"))
    zm = _zone_parts(r.get("z1m"))
    if z1 is None or zm is None:
        return False
    return _near_rel(r.get("ltp"), z1) is not None and _near_rel(r.get("ltp"), zm) is not None


def strict_trade_excl(r):
    """v5.1: dual-zone stock ka quality gate. Empty list = STRICT TRADE candidate."""
    reasons = []
    if r.get("type") != "DEMAND":
        reasons.append("SUPPLY/EQ - long system me nahi")
    if (r.get("tests_count") or 0) > 0:
        reasons.append("TESTED ZONE (%d tests)" % r.get("tests_count"))
    if _score_num(r.get("s1m")) < STRICT_TRADE_MIN_SCORE:
        reasons.append("1M SCORE <7")
    if _score_num(r.get("s1d")) < STRICT_TRADE_MIN_SCORE:
        reasons.append("1D SCORE <7")
    if r.get("sector") not in STRICT_SECTORS:
        reasons.append("SECTOR %s (backtest -ve)" % r.get("sector"))
    if "2x" in (r.get("vol_expl") or "") or "HIGH" in (r.get("vol_expl") or ""):
        reasons.append("HIGH VOLUME (backtest: SL 84%)")
    return reasons


def strict_trade_plan(r):
    """Strict dual-zone candidate ka 1:3 plan (top3 jaisa hi math)."""
    parts = _zone_parts(r.get("z1d"))
    if not parts or parts[2] != "DEMAND":
        return None
    lo, hi, _ = parts
    entry_hi = hi
    entry_lo = round((lo + hi) / 2.0, 2)
    sl = round(lo * 0.997, 2)
    risk = max(entry_hi - sl, 0.1)
    qty = max(int(round(1000.0 / risk)), 1)
    t1 = round(entry_hi + 2 * risk, 2)
    t2 = round(entry_hi + 3 * risk, 2)
    move = max(int(round(3000.0 / max(qty, 1))), 1)
    return {
        "entryLo": entry_lo,
        "entryHi": entry_hi,
        "sl": sl,
        "t1": t1,
        "t2": t2,
        "qty": qty,
        "moveFor3k": move,
    }


def update_history(payload):
    """Roz ka scan history/all.json me append karo (date-wise history filter ke liye).
    Latest scan gtf_live_data.json me rehta hai; history me pura payload copy hota hai."""
    try:
        hist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history")
        os.makedirs(hist_dir, exist_ok=True)
        hist_path = os.path.join(hist_dir, "all.json")
        hist = {"updated": "", "dates": [], "scans": {}}
        if os.path.exists(hist_path):
            try:
                with open(hist_path, "r", encoding="utf-8") as fh:
                    hist = json.load(fh)
            except Exception:
                hist = {"updated": "", "dates": [], "scans": {}}
        elif os.path.exists(os.path.join(os.path.dirname(hist_path), "..", "all.json")):
            # SELF-HEAL: purani seed root me hai (upload mistake) -> wahi se shuru karo,
            # agli scan history/all.json me sahi jagah ban jayegi
            legacy = os.path.join(os.path.dirname(hist_path), "..", "all.json")
            try:
                with open(legacy, "r", encoding="utf-8") as fh:
                    legacy_hist = json.load(fh)
                if isinstance(legacy_hist, dict) and "scans" in legacy_hist:
                    hist = legacy_hist
                    log(f"[✓] History self-heal: root all.json se seed liya "
                        f"({len(hist.get('scans', {}))} scans)")
            except Exception as exc:
                log(f"[!] Legacy history load failed: {exc}")
        d = payload.get("date")
        if not d:
            return
        # v5.2.1: analysisBySym history me store NAHI karte (file bloat rokne ke liye) —
        # popup ko ye sirf LIVE gtf_live_data.json se chahiye
        hist_entry = {k: v for k, v in payload.items() if k != "analysisBySym"}
        hist.setdefault("scans", {})[d] = hist_entry
        dates = [x for x in hist.get("dates", []) if x != d]
        dates.append(d)
        dates.sort(reverse=True)
        # history cap (safety): last 250 scans
        if len(dates) > 250:
            for old in dates[250:]:
                hist.get("scans", {}).pop(old, None)
            dates = dates[:250]
        hist["dates"] = dates
        hist["updated"] = payload.get("timestamp", "")
        with open(hist_path, "w", encoding="utf-8") as fh:
            json.dump(hist, fh, ensure_ascii=False, separators=(",", ":"))
        log(f"[✓] History updated: {len(dates)} dates (latest {dates[0] if dates else '-'})")
    except Exception as exc:
        log(f"[!] History update failed (non-fatal): {exc}")


def load_first_top3_dates():
    """history/all.json se sym -> 'pehli baar strict top-3 me aane ki date' ka map."""
    try:
        hist_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history", "all.json")
        if not os.path.exists(hist_path):
            return {}
        with open(hist_path, "r", encoding="utf-8") as fh:
            hist = json.load(fh)
        out = {}
        scans = hist.get("scans", {}) or {}
        for d in sorted(scans.keys()):
            for t in scans[d].get("top3", []) or []:
                sym = t.get("sym") if isinstance(t, dict) else None
                if sym and sym not in out:
                    out[sym] = d
        return out
    except Exception as exc:
        log(f"[!] first-top3 map load failed (non-fatal): {exc}")
        return {}


INSTI_DATA_URL = "https://raw.githubusercontent.com/heartaltafhussain-lgtm/insti-tracker/main/insti_live_data.json"


def load_extra_symbols(universe_syms):
    """v5.2.1: NIFTY-500 ke BAHAR ke insti-active stocks bhi track karo.
    Bulk/block deals chhote caps me hote hain jo Nifty500 index me nahi hote —
    unka GTF zone analysis bhi popup me dikhna chahiye.
    Sources (priority): 1) sibling insti-tracker repo file  2) raw GitHub URL
    3) local extra_symbols.csv backup."""
    syms = set()
    candidates = []
    sibling = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "insti-tracker", "insti_live_data.json")
    try:
        if os.path.exists(sibling):
            with open(sibling, encoding="utf-8") as fh:
                candidates.append(("sibling insti repo", json.load(fh)))
    except Exception:
        pass
    try:
        req = urllib.request.Request(INSTI_DATA_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            candidates.append(("github raw", json.loads(resp.read().decode("utf-8"))))
    except Exception:
        pass
    for src_name, j in candidates:
        try:
            for r in j.get("accumulation", []) or []:
                syms.add((r.get("sym") or "").strip().upper())
            for k in ("weeklyTop5", "fortnightlyTop5", "monthlyTop5"):
                for r in (j.get(k) or {}).get("rows", []) or []:
                    syms.add((r.get("sym") or "").strip().upper())
            for r in (j.get("triplePositive") or {}).get("rows", []) or []:
                syms.add((r.get("sym") or "").strip().upper())
            for d in j.get("dealsToday", []) or []:
                syms.add((d.get("sym") or "").strip().upper())
        except Exception:
            continue
        if syms:
            log(f"[*] Extra symbols source: {src_name} ({len(syms)} syms)")
            break
    csv_extra = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extra_symbols.csv")
    try:
        if os.path.exists(csv_extra):
            with open(csv_extra, encoding="utf-8") as fh:
                for row in csv.reader(fh):
                    if row and row[0].strip() and row[0].strip().upper() != "SYMBOL":
                        syms.add(row[0].strip().upper())
    except Exception:
        pass
    extras = sorted(s for s in syms if s and s not in universe_syms)
    log(f"[*] Extra scan symbols (NIFTY500 ke bahar): {len(extras)}")
    return extras


def scan():
    now = today_ist()
    today_str = now.strftime("%Y-%m-%d")
    log("=" * 88)
    log(f"  GTF NSE 500 AUTO-FILTER SCANNER  {VERSION}")
    log(f"  Date: {today_str} IST | Password ref: {PASSWORD_REF}")
    log("=" * 88)

    universe = fetch_nifty500_universe()
    # persist latest universe so next run / Actions has it offline
    uni_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nifty500_universe.csv")
    with open(uni_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["symbol", "company", "industry", "series", "isin"])
        w.writeheader()
        w.writerows(universe)

    meta = {r["symbol"]: r for r in universe}
    # v5.2.1: insti-active extra symbols (Nifty500 ke bahar) — sirf popup data ke liye,
    # ye dashboard tables me nahi aayenge
    extra_syms = load_extra_symbols(set(meta.keys()))
    extra_set = set(extra_syms)
    for es in extra_syms:
        meta[es] = {"symbol": es, "company": es, "industry": "", "series": "EQ", "isin": ""}
    tickers = [yahoo_symbol(r["symbol"]) for r in universe] + [yahoo_symbol(e) for e in extra_syms]
    log(f"[*] Fetching 3Y daily OHLC for {len(tickers)} Yahoo symbols...")
    frames = download_batches(tickers)
    log(f"[*] OHLC received for {len(frames)} / {len(tickers)} symbols")

    # index OHLC (3y) — LTP + monthly sector zones ke liye
    index_ltps = {}
    index_frames = {}
    try:
        idx_raw = yf.download(
            tickers=list(INDEX_TICKERS.values()),
            period="3y",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
            timeout=40,
        )
        for sec, tkr in INDEX_TICKERS.items():
            df = extract_ohlcv(idx_raw, tkr)
            if df is not None:
                index_frames[sec] = df
                index_ltps[sec] = float(df["Close"].iloc[-1])
    except Exception as exc:
        log(f"[!] Index LTP fetch skipped: {exc}")

    scanned = 0
    failed = 0
    extra_scanned = 0
    stock_rows = []
    analysis_by_sym = {}

    for nse_sym, info in meta.items():
        ysym = yahoo_symbol(nse_sym)
        df = frames.get(ysym)
        if df is None:
            failed += 1
            continue
        if nse_sym in extra_set:
            extra_scanned += 1
        else:
            scanned += 1
        ltp = float(df["Close"].iloc[-1])
        if not math.isfinite(ltp) or ltp <= 0:
            failed += 1
            continue

        daily_d, daily_s = detect_active_zones(df, impulse_body_pct=60.0)
        wdf = resample_ohlc(df, "W-FRI")
        mdf = resample_ohlc(df, "ME")
        # monthly candles are fatter — slightly looser body% so 1M zones still form
        month_d, month_s = detect_active_zones(mdf, impulse_body_pct=50.0) if mdf is not None else ([], [])
        week_d, week_s = detect_active_zones(wdf, impulse_body_pct=55.0) if wdf is not None else ([], [])

        # v5.2: IN/NEAR zone ya WATCH band (8%) ke andar active zone — dono me stock dikhega
        z1d, rel_d = best_active_zone(ltp, daily_d, daily_s)
        z1m, rel_m = best_active_zone(ltp, month_d, month_s)
        rel_d_ok = rel_d in ("IN", "NEAR")
        rel_m_ok = rel_m in ("IN", "NEAR")
        watch_d = rel_d == "WATCH"
        watch_m = rel_m == "WATCH"

        # v5.2.1: HAR scanned stock ka analysis save (insti popup ke liye) —
        # AWAY stocks aur Nifty500 ke bahar wale extras bhi cover
        try:
            w_tr_all = weekly_trend(wdf)
            w_up_all = "UP" in w_tr_all
            a_l1d, a_n1d, a_zl1d = support_ladder(ltp, daily_d, month_d, w_up_all, len(df) - 1)
            a_l1m, a_n1m, a_zl1m = support_ladder(ltp, month_d, None, w_up_all, (len(mdf) - 1) if mdf is not None else None)
            if rel_d_ok or rel_m_ok:
                rel_all = "IN" if (rel_d == "IN" or rel_m == "IN") else "NEAR"
            elif watch_d or watch_m:
                rel_all = "WATCH"
            else:
                rel_all = "AWAY"
            sig_all = {
                "AWAY": "AWAY — koi active zone 8% band me nahi",
                "WATCH": "PULLBACK WATCH (AWAY — retest ka wait)",
            }.get(rel_all, "ZONE KE PAAS")
            analysis_by_sym[nse_sym] = {
                "sym": nse_sym,
                "comp": info.get("company") or nse_sym,
                "sector": map_sector(nse_sym, info.get("company"), info.get("industry")),
                "ltp": round(ltp, 2),
                "rel": rel_all,
                "sig": sig_all,
                "z1d": fmt_zone(z1d or (daily_d[-1] if daily_d else None) or (daily_s[-1] if daily_s else None)),
                "z1m": fmt_zone(z1m or (month_d[-1] if month_d else None) or (month_s[-1] if month_s else None)),
                "analysis": {
                    "d1": {"last": a_l1d, "next": a_n1d, "zones": a_zl1d},
                    "m1": {"last": a_l1m, "next": a_n1m, "zones": a_zl1m},
                },
            }
        except Exception as _ana_exc:
            analysis_by_sym[nse_sym] = {
                "sym": nse_sym, "comp": info.get("company") or nse_sym, "sector": "—",
                "ltp": round(ltp, 2), "rel": "AWAY", "sig": "ANALYSIS DATA KAM",
                "z1d": "—", "z1m": "—",
                "analysis": {"d1": {"last": None, "next": None, "zones": []},
                             "m1": {"last": None, "next": None, "zones": []}},
            }
        if nse_sym in extra_set:
            continue

        if not rel_d_ok and not rel_m_ok and not watch_d and not watch_m:
            continue

        # decide displayed type from the tighter / more relevant zone
        chosen = None
        chosen_rel = "NONE"
        if rel_d_ok and rel_m_ok:
            if z1d["side"] == z1m["side"]:
                chosen, chosen_rel = z1d, rel_d
            else:
                # conflict — equilibrium / wait
                chosen, chosen_rel = (z1d if rel_d == "IN" else z1m), "CONFLICT"
        elif rel_d_ok:
            chosen, chosen_rel = z1d, rel_d
        elif rel_m_ok:
            chosen, chosen_rel = z1m, rel_m
        elif watch_d:
            chosen, chosen_rel = z1d, "WATCH"
        else:
            chosen, chosen_rel = z1m, "WATCH"

        if chosen_rel == "CONFLICT":
            zone_type = "EQUILIBRIUM"
        else:
            zone_type = chosen["side"]

        sector = map_sector(nse_sym, info.get("company"), info.get("industry"))
        w_tr = weekly_trend(wdf)
        vol_txt, _vol_r = volume_status(df)

        tests = int(chosen["tests"]) if chosen else 0
        s1d = z1d["score"] if z1d else 0.0
        s1m = z1m["score"] if z1m else 0.0
        combo = max(s1d, s1m)
        if z1d and z1m and z1d["side"] == z1m["side"] and rel_d in ("IN", "NEAR") and rel_m in ("IN", "NEAR"):
            combo = min(combo + 1.5, 11.5)
        if zone_type == "DEMAND" and "UP" in w_tr:
            combo = min(combo + 1.0, 11.5)
        if zone_type == "SUPPLY" and "DOWN" in w_tr:
            combo = min(combo + 1.0, 11.5)
        sec_bonus = "+0.0 PTS"
        if zone_type == "DEMAND" and sector in {
            "BANK", "OIL", "AUTO", "METAL", "REALTY", "INFRA", "FINSERVICE",
            "PSUBANK", "PVTBANK", "CPSE", "FMCG",
        }:
            combo = min(combo + 2.0, 11.5)
            sec_bonus = "+2.0 PTS"
        elif zone_type == "DEMAND":
            combo = min(combo + 1.0, 11.5)
            sec_bonus = "+1.0 PT"

        if zone_type == "DEMAND" and chosen_rel == "IN" and combo >= 9.0:
            sig = "BUY READY"
        elif zone_type == "DEMAND" and chosen_rel == "NEAR":
            sig = "APPROACHING DEMAND"
        elif zone_type == "SUPPLY" and chosen_rel == "IN":
            sig = "SUPPLY TEST"
        elif zone_type == "SUPPLY":
            sig = "NEAR SUPPLY"
        else:
            sig = "WAIT FOR PULLBACK"
        if chosen_rel == "WATCH":
            sig = "PULLBACK WATCH (AWAY — retest ka wait)"

        if combo >= 11:
            combo_txt = f"{combo:.1f} / 10 SUPER COMBO"
        elif combo >= 9.5:
            combo_txt = f"{combo:.1f} / 10 HIGH COMBO"
        elif zone_type == "SUPPLY":
            combo_txt = f"{combo:.1f} / 10 SUPPLY"
        else:
            combo_txt = f"{combo:.1f} / 10 SOLID"

        # show most recent 1D / 1M zone even if the qualifier was the other TF
        show_d = z1d or (daily_d[-1] if daily_d else None)
        show_m = z1m or (month_d[-1] if month_d else None)
        # if chosen is supply, prefer that side's leftover zone for the empty TF
        if not show_d and daily_s:
            show_d = daily_s[-1]
        if not show_m and month_s:
            show_m = month_s[-1]

        stock_rows.append(
            {
                "sym": nse_sym,
                "comp": info.get("company") or nse_sym,
                "sector": sector,
                "type": zone_type,
                "ltp": round(ltp, 2),
                "z1d": fmt_zone(show_d),
                "s1d": fmt_score(show_d),
                "z1m": fmt_zone(show_m),
                "s1m": fmt_score(show_m),
                "w_trend": w_tr,
                "tests_count": tests,
                "fresh_badge": freshness(tests),
                "vol_expl": vol_txt,
                "secBonus": sec_bonus,
                "combo": combo_txt,
                "sig": sig,
                "inDaily": rel_d_ok or watch_d,
                "inMonthly": rel_m_ok or watch_m,
                "tradeStock": (rel_d in ("IN", "NEAR")) and (rel_m in ("IN", "NEAR")),
                "watch": True,
                "rel": chosen_rel,
                "industry": info.get("industry") or "",
            }
        )
        # v5.2.1: analysis upar hi ban chuka (analysis_by_sym) — wahi reuse
        stock_rows[-1]["analysis"] = analysis_by_sym[nse_sym]["analysis"]

        # v5.3: SWING 4-5 DIN filter — swing holding ke liye quality gate
        try:
            a_d1 = analysis_by_sym[nse_sym]["analysis"]["d1"]["last"] or {}
            st_tot = (a_d1.get("strength") or {}).get("total")
            m1_last = analysis_by_sym[nse_sym]["analysis"]["m1"]["last"]
            zone_top = max(float(chosen["prox"]), float(chosen["dist"])) if chosen else ltp
            room = 15.0  # upar khali maidan % (supply tak)
            for zc in (list(daily_s) + list(month_s) + list(week_s or [])):
                if zc.get("side") == "SUPPLY":
                    zlo = min(float(zc["prox"]), float(zc["dist"]))
                    if zlo > ltp:
                        room = min(room, (zlo - ltp) / ltp * 100.0)
            notes = []
            ok = True
            if chosen is None or chosen.get("side") != "DEMAND":
                ok = False; notes.append("DEMAND zone nahi")
            if ltp < 30:
                ok = False; notes.append("penny <30")
            if chosen_rel not in ("IN", "NEAR"):
                ok = False; notes.append("zone IN/NEAR nahi")
            if tests >= 2:
                ok = False; notes.append(f"{tests} tests")
            if "UP" not in w_tr:
                ok = False; notes.append("1W DOWN")
            if st_tot is None or st_tot < 6.5:
                ok = False; notes.append(f"strength {st_tot}")
            if ltp > zone_top * 1.03:
                ok = False; notes.append("extended >3%")
            fresh = 10.0 if tests == 0 else 6.0
            wtr = 10.0 if "UP" in w_tr else 0.0
            m1c = 10.0 if m1_last else 4.0
            roomc = max(0.0, min(10.0, room / 0.9))
            sw_score = round(0.40 * (st_tot or 0) + 0.25 * fresh + 0.15 * wtr + 0.10 * m1c + 0.10 * roomc, 1)
            if ok and sw_score >= 8.0:
                verdict = "A+"
            elif ok and sw_score >= 7.0:
                verdict = "A"
            elif ok and sw_score >= 6.0:
                verdict = "B"
            else:
                verdict = "—"
                if ok:
                    notes.append(f"score {sw_score}")
            stock_rows[-1]["swing"] = {
                "ok": bool(ok and verdict != "—"),
                "score": sw_score, "verdict": verdict,
                "room": round(room, 1), "notes": notes,
                "zlo": min(float(chosen["prox"]), float(chosen["dist"])) if chosen else None,
                "zhi": zone_top if chosen else None,
                "pat": (chosen.get("pat") if chosen else "") or "",
            }
        except Exception:
            stock_rows[-1]["swing"] = {"ok": False, "score": 0.0, "verdict": "—", "room": 0.0, "notes": ["data kam"]}

    # sort: BUY READY first, then combo
    rank = {"BUY READY": 0, "APPROACHING DEMAND": 1, "WAIT FOR PULLBACK": 2, "NEAR SUPPLY": 3, "SUPPLY TEST": 4, "PULLBACK WATCH (AWAY — retest ka wait)": 5}
    stock_rows.sort(key=lambda r: (rank.get(r["sig"], 9), -_combo_num(r["combo"]), r["sym"]))

    # v5.0: timeframe subsets (DAILY / MONTHLY / TRADE = dono me same stock)
    daily_stock_rows = [r for r in stock_rows if r["inDaily"]]
    monthly_stock_rows = [r for r in stock_rows if r["inMonthly"]]
    trade_stock_rows = [r for r in stock_rows if r["tradeStock"]]
    for subset in (daily_stock_rows, monthly_stock_rows, trade_stock_rows):
        subset.sort(key=lambda r: (-_combo_num(r["combo"]), r["sym"]))

    # v5.1 STRICT TRADE FIX: dual-zone stocks pe quality gate (negative-edge fix)
    # strict = gate pass (trade candidates), watch = fail (research only)
    for r in stock_rows:
        if r["tradeStock"]:
            r["exclReasons"] = strict_trade_excl(r)
            r["qualityGrade"] = "STRICT" if not r["exclReasons"] else "WATCH"
            r["plan"] = strict_trade_plan(r) if r["qualityGrade"] == "STRICT" else None
        else:
            r["exclReasons"] = []
            r["qualityGrade"] = None
            r["plan"] = None
    strict_trade_rows = [r for r in trade_stock_rows if r["qualityGrade"] == "STRICT"]
    watch_trade_rows = [r for r in trade_stock_rows if r["qualityGrade"] == "WATCH"]
    for subset in (strict_trade_rows, watch_trade_rows):
        subset.sort(key=lambda r: (-_combo_num(r["combo"]), r["sym"]))

    # v5.3: SWING 4-5 DIN picks (max 6, swing score se)
    swing_rows = [r for r in stock_rows if r.get("swing", {}).get("ok")]
    swing_rows.sort(key=lambda r: (-r["swing"]["score"], r["sym"]))
    swing_rows = swing_rows[:6]

    top3 = make_top3(stock_rows, frames)
    if not top3:
        send_telegram_alert(
            "GTF STRICT v4: aaj koi strict pick nahi — WAIT. "
            "(Filters: SUPER combo + FRESH + sector whitelist + COURSE veto)"
        )
    for p in top3:
        send_telegram_alert(
            f"GTF STRICT PICK: {p['sym']} @ ₹{p['ltp']} | {p['combo']} | "
            f"{p['z1d']} | Entry {p['entryLo']}-{p['entryHi']} | SL {p['sl']} | "
            f"T1 {p['t1']} T2 {p['t2']}"
        )

    sector_cards = build_sector_cards(stock_rows, index_ltps)
    sector_zones = build_sector_zones(index_frames, index_ltps, stock_rows)
    stats = {
        "universe": len(universe),
        "ohlcOk": len(frames),
        "scanned": scanned,
        "failed": failed,
        "inZone": len(stock_rows),
        "demand": sum(1 for r in stock_rows if r["type"] == "DEMAND"),
        "supply": sum(1 for r in stock_rows if r["type"] == "SUPPLY"),
        "equilibrium": sum(1 for r in stock_rows if r["type"] == "EQUILIBRIUM"),
        "buyReady": sum(1 for r in stock_rows if r["sig"] == "BUY READY"),
        "extraScanned": extra_scanned,
        "analysisTracked": len(analysis_by_sym),
    }

    # strip helper keys before JSON
    def public(r):
        return {k: v for k, v in r.items() if k != "industry"}

    public_rows = [public(r) for r in stock_rows]

    payload = {
        "date": today_str,
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S IST"),
        "passwordRef": PASSWORD_REF,
        "version": VERSION,
        "strictFilter": {
            "name": "STRICT v4 (backtest-tested)",
            "minCombo": STRICT_MIN_COMBO,
            "freshOnly": STRICT_FRESH_ONLY,
            "min1dScore": STRICT_MIN_1D_SCORE,
            "sectors": sorted(STRICT_SECTORS),
            "note": (
                "Backtest: win 42%, avg +0.31R, T1-hit 41%, max DD -16R. "
                "Picks na hone par WAIT — weak picks nahi dikhaye jaate."
            ),
        },
        "strictTradeFix": {
            "name": "STRICT TRADE v5.1 (dual-zone negative-edge fix)",
            "minScore": STRICT_TRADE_MIN_SCORE,
            "note": (
                "TRADE STOCKS section ab sirf quality-gated dual-zone stocks dikhata hai: "
                "DEMAND + whitelist sector + FRESH zone + 1D/1M score >= 7 + normal volume. "
                "Backtest (May-Aug 2026, 102 dual-zone demand signals): RAW win 41% avg "
                "+0.36R PF 1.62 DD -8.0R SL 59% -> STRICT win 50% avg +0.50R PF 2.0 "
                "DD -3.0R SL 50%. Baaki dual-zone stocks WATCH-ONLY (exclReasons ke saath)."
            ),
        },
        "courseMode": {
            "enabled": bool(COURSE_MODE_ENABLED and _COURSE_VETO_AVAILABLE),
            "available": bool(_COURSE_VETO_AVAILABLE),
            "garbageBaseLimit": GARBAGE_BASE_LIMIT,
            "minZoneScore": MIN_ZONE_SCORE,
            "note": (
                "GTF course Ep 5/6/8 vetoes (data-validated): >5 base = garbage, "
                "course trade score < 5.5 = weak. Backtest: avgR +0.32R -> +0.61R, "
                "win 42% -> 50%. Signals kam, quality zyada."
            ),
        },
        "scanStats": stats,
        "top3": top3,
        "sectorIndices": sector_cards,
        "sectorZones": sector_zones,
        "dailyStocks": [public(r) for r in daily_stock_rows],
        "monthlyStocks": [public(r) for r in monthly_stock_rows],
        "tradeStocks": [public(r) for r in trade_stock_rows],
        "tradeStocksStrict": [public(r) for r in strict_trade_rows],
        "tradeStocksWatch": [public(r) for r in watch_trade_rows],
        "stockData": public_rows,
        "swingPicks": [public(r) for r in swing_rows],
        "analysisBySym": analysis_by_sym,
    }

    # date-wise history pehle update karo (firstTop3Date ke liye aaj ka din bhi map me chahiye)
    update_history(payload)

    # 📅 first time in strict top-3 — har pick/stock ke liye pehli appearance date
    first_map = load_first_top3_dates()
    for p in payload.get("top3", []):
        p["firstTop3Date"] = first_map.get(p.get("sym"))
    for r in payload.get("stockData", []):
        r["firstTop3Date"] = first_map.get(r.get("sym"))

    with open("gtf_live_data.json", "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    export_rows = []
    for r in stock_rows:
        export_rows.append(
            {
                "Symbol": r["sym"],
                "Company": r["comp"],
                "Sector": r["sector"],
                "Type": r["type"],
                "CMP (INR)": r["ltp"],
                "1D Execution Zone": r["z1d"],
                "1D Score": r["s1d"],
                "1M Supporting Zone": r["z1m"],
                "1M Score": r["s1m"],
                "1W Intermediate Trend": r["w_trend"],
                "Zone Freshness": r["fresh_badge"],
                "Volume Status": r["vol_expl"],
                "Sector Bonus (Ep 16)": r["secBonus"],
                "GTF Combo Score": r["combo"],
                "Setup Status": r["sig"],
                "Relation": r.get("rel", ""),
                "In Daily TF": "YES" if r.get("inDaily") else "NO",
                "In Monthly TF": "YES" if r.get("inMonthly") else "NO",
                "Trade Stock (1D+1M)": "YES" if r.get("tradeStock") else "NO",
                "Strict Trade Grade": r.get("qualityGrade") or "",
                "Exclude Reasons": " | ".join(r.get("exclReasons") or []),
                "Entry": (r.get("plan") or {}).get("entryHi", ""),
                "SL": (r.get("plan") or {}).get("sl", ""),
                "T1 (+2R)": (r.get("plan") or {}).get("t1", ""),
                "T2 (+3R)": (r.get("plan") or {}).get("t2", ""),
                "Qty (₹1k risk)": (r.get("plan") or {}).get("qty", ""),
            }
        )
    df_out = pd.DataFrame(export_rows)
    df_out.to_excel("NIFTY500_GTF_Dashboard.xlsx", index=False)
    df_out.to_csv("NIFTY500_GTF_Dashboard.csv", index=False)

    log("")
    log("=" * 88)
    log(
        f"  SCAN DONE  universe={stats['universe']}  ohlc={stats['ohlcOk']}  "
        f"IN/NEAR zone={stats['inZone']}  DEMAND={stats['demand']}  "
        f"SUPPLY={stats['supply']}  BUY READY={stats['buyReady']}  "
        f"DAILY={len(daily_stock_rows)}  MONTHLY={len(monthly_stock_rows)}  "
        f"TRADE(1D+1M)={len(trade_stock_rows)}  "
        f"STRICT TRADE={len(strict_trade_rows)}  WATCH={len(watch_trade_rows)}  "
        f"STRICT TOP3={len(top3)}  "
        f"COURSE_MODE={'ON' if (COURSE_MODE_ENABLED and _COURSE_VETO_AVAILABLE) else 'OFF'}"
    )
    log("=" * 88)
    if not strict_trade_rows:
        log("  [STRICT TRADE v5.1] No strict dual-zone trade stocks today — WAIT.")
    else:
        for r in strict_trade_rows:
            pl = r.get("plan") or {}
            log(
                f"  [STRICT TRADE] {r['sym']} | {r['combo']} | entry "
                f"{pl.get('entryLo')}-{pl.get('entryHi')} | SL {pl.get('sl')} | "
                f"T1 {pl.get('t1')} T2 {pl.get('t2')}"
            )
    if not stock_rows:
        log("  No stock is currently sitting inside a valid GTF zone.")
    else:
        show = df_out.head(15)
        log(show.to_string(index=False))
    if not top3:
        log("  [STRICT v4] No strict picks today — WAIT (weak picks hidden).")
    else:
        for p in top3:
            cinfo = p.get("course") or {}
            c_txt = ""
            if cinfo.get("hasZone"):
                c_txt = (f" | course: {cinfo['verdict']} "
                         f"(base={cinfo.get('nBase')} score={cinfo.get('score')})")
            log(
                f"  [STRICT PICK] {p['sym']} | {p['combo']} | entry "
                f"{p['entryLo']}-{p['entryHi']} | SL {p['sl']} | T1 {p['t1']} T2 {p['t2']}"
                f"{c_txt}"
            )
    log("[✓] Wrote gtf_live_data.json, NIFTY500_GTF_Dashboard.xlsx, NIFTY500_GTF_Dashboard.csv")
    return payload


if __name__ == "__main__":
    try:
        scan()
    except Exception as exc:
        log(f"[FATAL] {exc}")
        raise

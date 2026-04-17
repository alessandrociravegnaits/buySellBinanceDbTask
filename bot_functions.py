"""Trading bot functions grounded on hardcoded technical-analysis rules.

Core entrypoint:
    richiedi_supporti_resistenze(...)

The level detection is deterministic and rule-based.
The PDF knowledge base, if provided, is used only for optional notes/citations
and never for the numeric decisions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
import pandas as pd

from indicators import TechnicalIndicators


@dataclass
class Candle:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


TIMEFRAME_PROFILES: dict[str, dict[str, object]] = {
    "1m": {"base_window": 2, "tolerance_pct": 0.25, "analysis_windows": (2, 4, 6)},
    "5m": {"base_window": 2, "tolerance_pct": 0.30, "analysis_windows": (2, 4, 6)},
    "15m": {"base_window": 3, "tolerance_pct": 0.35, "analysis_windows": (3, 6, 9)},
    "1h": {"base_window": 3, "tolerance_pct": 0.40, "analysis_windows": (3, 6, 10)},
    "4h": {"base_window": 4, "tolerance_pct": 0.50, "analysis_windows": (4, 8, 12)},
    "1d": {"base_window": 5, "tolerance_pct": 0.60, "analysis_windows": (5, 10, 15)},
    "4d": {"base_window": 5, "tolerance_pct": 0.65, "analysis_windows": (5, 10, 15)},
    "1w": {"base_window": 6, "tolerance_pct": 0.80, "analysis_windows": (6, 12, 18)},
}


BOOK_RULES: dict[str, dict[str, object]] = {
    "touches_min": {"1m": 3, "5m": 3, "15m": 3, "1h": 2, "4h": 2, "1d": 2, "4d": 2, "1w": 2},
    "secure_threshold": {"1m": 0.80, "5m": 0.78, "15m": 0.76, "1h": 0.74, "4h": 0.72, "1d": 0.70, "4d": 0.69, "1w": 0.68},
    "retest_lookahead": {"1m": 2, "5m": 2, "15m": 3, "1h": 3, "4h": 4, "1d": 5, "4d": 5, "1w": 6},
    "reaction_buffer_pct": {"1m": 0.05, "5m": 0.06, "15m": 0.08, "1h": 0.10, "4h": 0.15, "1d": 0.20, "4d": 0.22, "1w": 0.30},
    "volume_bonus_min_ratio": {"1m": 1.20, "5m": 1.20, "15m": 1.15, "1h": 1.12, "4h": 1.10, "1d": 1.08, "4d": 1.06, "1w": 1.05},
    "touch_band_pct": {"1m": 0.08, "5m": 0.10, "15m": 0.12, "1h": 0.15, "4h": 0.20, "1d": 0.30, "4d": 0.35, "1w": 0.45},
    "timeframe_weight": {"1m": 0.92, "5m": 0.94, "15m": 0.96, "1h": 0.98, "4h": 1.00, "1d": 1.03, "4d": 1.06, "1w": 1.10},
    "multi_tf_bonus": 0.10,
    "touch_weight": 0.22,
    "multi_tf_weight": 0.16,
    "reaction_weight": 0.14,
    "recency_weight": 0.08,
    "volume_weight": 0.08,
    "distance_weight": 0.05,
    "cluster_weight": 0.09,
    "close_confirmation_weight": 0.08,
    "role_reversal_weight": 0.06,
    "round_number_weight": 0.04,
}


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2.0)


def _mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _book_value(profile_key: str, timeframe: str, default: float | int) -> float | int:
    tf = timeframe.lower()
    table = BOOK_RULES.get(profile_key, {})
    return table.get(tf, default)  # type: ignore[return-value]


def _average_true_range_like(candles: list[Candle], lookback: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    ranges: list[float] = []
    start = max(1, len(candles) - lookback)
    for idx in range(start, len(candles)):
        current = candles[idx]
        prev_close = candles[idx - 1].close
        tr = max(
            current.high - current.low,
            abs(current.high - prev_close),
            abs(current.low - prev_close),
        )
        ranges.append(tr)
    return _mean(ranges)


def _volume_ratio_at_touches(candles: list[Candle], touch_indices: list[int], lookback: int = 20) -> float:
    volumes = [c.volume for c in candles if c.volume is not None]
    if not volumes or not touch_indices:
        return 0.0

    baseline = _median(volumes[-lookback:]) if len(volumes) >= 3 else _median(volumes)
    if baseline <= 0:
        return 0.0

    touch_volumes = [candles[i].volume for i in touch_indices if 0 <= i < len(candles) and candles[i].volume is not None]
    if not touch_volumes:
        return 0.0

    return round(_mean([float(v) / baseline for v in touch_volumes]), 4)


def _touch_reaction_score(
    candles: list[Candle],
    level: float,
    level_type: str,
    touch_indices: list[int],
    lookahead: int,
    buffer_pct: float,
) -> float:
    if not touch_indices:
        return 0.0

    successful = 0
    total = 0
    buffer = buffer_pct / 100.0

    for idx in touch_indices:
        if idx >= len(candles) - 1:
            continue
        total += 1
        future = candles[idx + 1 : min(len(candles), idx + 1 + lookahead)]
        if not future:
            continue

        if level_type == "support":
            bounced = any(c.close >= level * (1.0 + buffer) for c in future)
        else:
            bounced = any(c.close <= level * (1.0 - buffer) for c in future)

        if bounced:
            successful += 1

    return round(successful / max(total, 1), 4)


def _price_distance_score(last_close: float, level: float, level_type: str, atr_like: float) -> float:
    if last_close <= 0:
        return 0.0
    distance_pct = abs(level - last_close) / last_close * 100.0
    baseline = max(atr_like / max(last_close, 1e-9) * 100.0, 0.1)
    score = 1.0 - min(distance_pct / max(baseline * 3.0, 0.1), 1.0)
    if level_type == "support" and level > last_close:
        score *= 0.2
    if level_type == "resistance" and level < last_close:
        score *= 0.2
    return round(max(score, 0.0), 4)


def _cluster_quality_score(touches: int, span: int, series_len: int) -> float:
    touches_score = min(touches / 5.0, 1.0)
    span_score = min(span / max(series_len, 1), 1.0)
    return round((0.7 * touches_score) + (0.3 * span_score), 4)


def _round_number_step(level: float) -> float:
    abs_level = abs(level)
    if abs_level >= 1000:
        return 100.0
    if abs_level >= 100:
        return 10.0
    if abs_level >= 10:
        return 1.0
    if abs_level >= 1:
        return 0.1
    if abs_level >= 0.1:
        return 0.01
    return 0.001


def _round_number_score(level: float) -> tuple[float, float, float]:
    step = _round_number_step(level)
    nearest = round(level / step) * step
    distance_pct = abs(level - nearest) / max(abs(level), 1e-9) * 100.0
    score = max(0.0, 1.0 - min(distance_pct / 0.25, 1.0))
    return round(score, 4), round(nearest, 6), round(distance_pct, 4)


def _close_breakout_score(
    candles: list[Candle],
    level: float,
    level_type: str,
    lookahead: int,
    buffer_pct: float,
) -> float:
    closes = [c.close for c in candles]
    if len(closes) < 2:
        return 0.0

    buffer = buffer_pct / 100.0
    min_follow = max(2, min(lookahead, 3))

    if level_type == "support":
        threshold = level * (1.0 + buffer)
        for idx in range(1, len(closes)):
            if closes[idx - 1] <= level and closes[idx] > threshold:
                future = closes[idx : min(len(closes), idx + min_follow)]
                if not future:
                    return 0.0
                confirmed = sum(close > threshold for close in future)
                return round(confirmed / len(future), 4)
    else:
        threshold = level * (1.0 - buffer)
        for idx in range(1, len(closes)):
            if closes[idx - 1] >= level and closes[idx] < threshold:
                future = closes[idx : min(len(closes), idx + min_follow)]
                if not future:
                    return 0.0
                confirmed = sum(close < threshold for close in future)
                return round(confirmed / len(future), 4)

    return 0.0


def _role_reversal_score(
    candles: list[Candle],
    level: float,
    level_type: str,
    lookahead: int,
    buffer_pct: float,
) -> float:
    closes = [c.close for c in candles]
    if len(closes) < 3:
        return 0.0

    buffer = buffer_pct / 100.0
    retest_limit = max(2, lookahead)

    if level_type == "support":
        breakout_threshold = level * (1.0 + buffer)
        breakout_idx = None
        for idx in range(1, len(closes)):
            if closes[idx - 1] <= level and closes[idx] > breakout_threshold:
                breakout_idx = idx
                break
        if breakout_idx is None:
            return 0.0

        end_idx = min(len(candles), breakout_idx + 1 + retest_limit)
        for idx in range(breakout_idx + 1, end_idx):
            candle = candles[idx]
            if candle.low <= level * (1.0 + buffer) and candle.close >= breakout_threshold:
                post = closes[idx + 1 : min(len(closes), idx + 3)]
                hold_ratio = 1.0 if not post else sum(close >= breakout_threshold for close in post) / len(post)
                return round(min(1.0, 0.7 + 0.3 * hold_ratio), 4)
    else:
        breakout_threshold = level * (1.0 - buffer)
        breakout_idx = None
        for idx in range(1, len(closes)):
            if closes[idx - 1] >= level and closes[idx] < breakout_threshold:
                breakout_idx = idx
                break
        if breakout_idx is None:
            return 0.0

        end_idx = min(len(candles), breakout_idx + 1 + retest_limit)
        for idx in range(breakout_idx + 1, end_idx):
            candle = candles[idx]
            if candle.high >= level * (1.0 - buffer) and candle.close <= breakout_threshold:
                post = closes[idx + 1 : min(len(closes), idx + 3)]
                hold_ratio = 1.0 if not post else sum(close <= breakout_threshold for close in post) / len(post)
                return round(min(1.0, 0.7 + 0.3 * hold_ratio), 4)

    return 0.0


def _pivot_highs_lows(candles: list[Candle], window: int) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []

    if len(candles) < (2 * window + 1):
        return highs, lows

    for i in range(window, len(candles) - window):
        center = candles[i]
        neigh = candles[i - window : i + window + 1]
        max_h = max(c.high for c in neigh)
        min_l = min(c.low for c in neigh)
        if center.high >= max_h:
            highs.append((i, center.high))
        if center.low <= min_l:
            lows.append((i, center.low))
    return highs, lows


def _cluster_levels(points: list[tuple[int, float]], tolerance_pct: float) -> list[dict]:
    if not points:
        return []

    points = sorted(points, key=lambda p: p[1])
    tol = max(tolerance_pct, 0.01) / 100.0

    clusters: list[dict] = []
    for idx, price in points:
        if not clusters:
            clusters.append({"prices": [price], "indices": [idx]})
            continue

        last = clusters[-1]
        center = sum(last["prices"]) / len(last["prices"])
        rel_diff = abs(price - center) / max(center, 1e-9)
        if rel_diff <= tol:
            last["prices"].append(price)
            last["indices"].append(idx)
        else:
            clusters.append({"prices": [price], "indices": [idx]})

    out: list[dict] = []
    for cl in clusters:
        level = sum(cl["prices"]) / len(cl["prices"])
        touches = len(cl["prices"])
        recency = max(cl["indices"]) if cl["indices"] else 0
        out.append(
            {
                "level": round(level, 6),
                "touches": touches,
                "last_touch_index": recency,
                "score": (touches * 2.0) + (recency / 1000.0),
            }
        )

    out.sort(key=lambda x: x["score"], reverse=True)
    return out


def _resolve_timeframe_profile(timeframe: str) -> dict[str, object]:
    return TIMEFRAME_PROFILES.get(timeframe.lower(), TIMEFRAME_PROFILES["1d"])


def _analysis_windows(base_window: int, profile_windows: Iterable[int] | None = None) -> list[int]:
    if profile_windows is not None:
        windows = [max(int(w), 1) for w in profile_windows]
    else:
        windows = [base_window, base_window * 2, base_window * 3]
    return sorted(set(max(w, 1) for w in windows))


def _match_level(level: float, candidates: list[dict], tolerance_pct: float) -> dict | None:
    best: dict | None = None
    best_diff = float("inf")
    tol = max(tolerance_pct, 0.01) / 100.0
    for cand in candidates:
        cand_level = float(cand.get("level", 0.0))
        diff = abs(cand_level - level) / max(level, 1e-9)
        if diff <= tol and diff < best_diff:
            best = cand
            best_diff = diff
    return best


def _confidence_from_components(
    *,
    touches: int,
    confirmations: int,
    windows_total: int,
    recency_index: int,
    series_len: int,
    proximity_pct: float,
) -> float:
    touches_score = min(touches / 4.0, 1.0)
    confirmations_score = confirmations / max(windows_total, 1)
    recency_score = min(max(recency_index / max(series_len, 1), 0.0), 1.0)
    proximity_score = max(0.0, 1.0 - min(abs(proximity_pct) / 3.0, 1.0))
    confidence = (
        0.30 * touches_score
        + 0.30 * confirmations_score
        + 0.20 * recency_score
        + 0.20 * proximity_score
    )
    return round(min(max(confidence, 0.0), 1.0), 4)


def _secure_level_summary(
    candles: list[Candle],
    base_levels: list[dict],
    confirmation_sets: list[list[dict]],
    last_close: float,
    level_type: str,
    series_len: int,
    tolerance_pct: float,
    timeframe: str,
) -> dict | None:
    if not base_levels:
        return None

    enriched: list[dict] = []
    windows_total = len(confirmation_sets)
    touch_threshold = int(_book_value("touches_min", timeframe, 2))
    lookahead = int(_book_value("retest_lookahead", timeframe, 3))
    reaction_buffer_pct = float(_book_value("reaction_buffer_pct", timeframe, 0.1))
    volume_bonus_ratio = float(_book_value("volume_bonus_min_ratio", timeframe, 1.1))
    touch_band_pct = float(_book_value("touch_band_pct", timeframe, 0.2))
    timeframe_weight = float(_book_value("timeframe_weight", timeframe, 1.0))
    atr_like = _average_true_range_like(candles)

    for base in base_levels:
        level = float(base["level"])
        confirmations = 1
        matched_levels: list[dict] = [base]
        for window_levels in confirmation_sets:
            match = _match_level(level, window_levels, tolerance_pct=tolerance_pct)
            if match is not None:
                confirmations += 1
                matched_levels.append(match)

        combined_touches = sum(int(x.get("touches", 0)) for x in matched_levels)
        recency_index = max(int(x.get("last_touch_index", 0)) for x in matched_levels)
        proximity_pct = ((level - last_close) / max(last_close, 1e-9)) * 100.0
        touch_indices = sorted({int(x.get("last_touch_index", 0)) for x in matched_levels})
        reaction_score = _touch_reaction_score(
            candles,
            level=level,
            level_type=level_type,
            touch_indices=touch_indices,
            lookahead=lookahead,
            buffer_pct=reaction_buffer_pct,
        )
        close_confirmation_score = _close_breakout_score(
            candles,
            level=level,
            level_type=level_type,
            lookahead=lookahead,
            buffer_pct=reaction_buffer_pct,
        )
        role_reversal_score = _role_reversal_score(
            candles,
            level=level,
            level_type=level_type,
            lookahead=lookahead,
            buffer_pct=reaction_buffer_pct,
        )
        round_number_score, nearest_round_number, round_number_distance_pct = _round_number_score(level)
        volume_ratio = _volume_ratio_at_touches(candles, touch_indices)
        volume_score = min(volume_ratio / max(volume_bonus_ratio, 1e-9), 1.0)
        distance_score = _price_distance_score(last_close, level, level_type, atr_like)
        cluster_quality = _cluster_quality_score(
            touches=combined_touches,
            span=recency_index - min(touch_indices) if touch_indices else recency_index,
            series_len=series_len,
        )

        touches_score = min(combined_touches / max(touch_threshold, 1), 1.0)
        multi_tf_score = min(confirmations / max(windows_total + 1, 1), 1.0)
        recency_score = min(max(recency_index / max(series_len, 1), 0.0), 1.0)
        reaction_component = max(reaction_score, min(cluster_quality, 1.0))

        confidence = round(
            min(
                max(
                    (
                        BOOK_RULES["touch_weight"] * touches_score
                        + BOOK_RULES["multi_tf_weight"] * multi_tf_score
                        + BOOK_RULES["reaction_weight"] * reaction_component
                        + BOOK_RULES["recency_weight"] * recency_score
                        + BOOK_RULES["volume_weight"] * volume_score
                        + BOOK_RULES["distance_weight"] * distance_score
                        + BOOK_RULES["cluster_weight"] * cluster_quality
                        + float(BOOK_RULES["close_confirmation_weight"]) * close_confirmation_score
                        + float(BOOK_RULES["role_reversal_weight"]) * role_reversal_score
                        + float(BOOK_RULES["round_number_weight"]) * round_number_score
                    )
                    * timeframe_weight,
                    0.0,
                ),
                1.0,
            ),
            4,
        )

        enriched.append(
            {
                "level": round(level, 6),
                "touches": combined_touches,
                "confirmations": confirmations,
                "confirmation_ratio": round(confirmations / max(windows_total + 1, 1), 4),
                "last_touch_index": recency_index,
                "distance_pct_from_last_close": round(proximity_pct, 4),
                "reaction_score": reaction_score,
                "close_confirmation_score": close_confirmation_score,
                "role_reversal_score": role_reversal_score,
                "round_number_score": round_number_score,
                "nearest_round_number": nearest_round_number,
                "round_number_distance_pct": round_number_distance_pct,
                "volume_ratio": volume_ratio,
                "volume_score": volume_score,
                "distance_score": distance_score,
                "cluster_quality": cluster_quality,
                "touch_threshold": touch_threshold,
                "touch_band_pct": touch_band_pct,
                "confidence": confidence,
                "source": "hardcoded_book_rules",
                "rule_flags": {
                    "touches_ok": combined_touches >= touch_threshold,
                    "multi_tf_ok": confirmations >= 2,
                    "reaction_ok": reaction_score >= 0.5,
                    "close_confirmation_ok": close_confirmation_score >= 0.5,
                    "role_reversal_ok": role_reversal_score >= 0.5,
                    "round_number_ok": round_number_score >= 0.5,
                    "volume_ok": volume_ratio >= volume_bonus_ratio,
                    "distance_ok": distance_score >= 0.25,
                },
            }
        )

    if level_type == "support":
        valid = [x for x in enriched if x["level"] <= last_close]
        valid.sort(key=lambda x: (x["confidence"], x["level"]), reverse=True)
    else:
        valid = [x for x in enriched if x["level"] >= last_close]
        valid.sort(key=lambda x: (x["confidence"], -x["level"]))

    return valid[0] if valid else None


def _filter_by_last_close(levels: list[dict], last_close: float, level_type: str, max_levels: int) -> list[dict]:
    if level_type == "support":
        filtered = [l for l in levels if l["level"] <= last_close]
        filtered.sort(key=lambda x: x["level"], reverse=True)
    else:
        filtered = [l for l in levels if l["level"] >= last_close]
        filtered.sort(key=lambda x: x["level"])

    return filtered[: max(max_levels, 1)]


def _enrich_with_distance(levels: list[dict], last_close: float) -> list[dict]:
    out: list[dict] = []
    for item in levels:
        distance_pct = ((item["level"] - last_close) / max(last_close, 1e-9)) * 100.0
        new_item = dict(item)
        new_item["distance_pct_from_last_close"] = round(distance_pct, 4)
        out.append(new_item)
    return out


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def richiedi_supporti_resistenze(
    candles: Iterable[Candle | dict],
    *,
    symbol: str = "UNKNOWN",
    timeframe: str = "1d",
    max_levels: int = 3,
    pivot_window: int = 2,
    tolerance_pct: float = 0.4,
    secure_threshold: float | None = None,
    apply_trend_filter: bool = False,
) -> dict:
    """Hardcoded support/resistance function, knowledge-augmented.

    - Detection logic is deterministic (pivot + clustering).
    - Book knowledge is used for rationale/explanations, not for numeric levels.
    """

    normalized: list[Candle] = []
    for row in candles:
        if isinstance(row, Candle):
            normalized.append(row)
            continue
        normalized.append(
            Candle(
                timestamp=str(row.get("timestamp") or row.get("date") or ""),
                open=_to_float(row.get("open")),
                high=_to_float(row.get("high")),
                low=_to_float(row.get("low")),
                close=_to_float(row.get("close")),
                volume=_to_float(row.get("volume")) if row.get("volume") is not None else None,
            )
        )

    tf_profile = _resolve_timeframe_profile(timeframe)
    effective_window = max(int(tf_profile.get("base_window", pivot_window)), max(pivot_window, 1))
    # initial tolerance (may be adapted later using ATR)
    effective_tolerance = float(tf_profile.get("tolerance_pct", tolerance_pct)) if tolerance_pct is None else tolerance_pct
    window_profile = _analysis_windows(effective_window, tf_profile.get("analysis_windows"))

    if len(normalized) < (2 * effective_window + 1):
        raise ValueError(
            "Serie OHLC troppo corta: servono almeno 2*pivot_window+1 candele "
            f"(ricevute: {len(normalized)}, pivot_window={effective_window})."
        )

    default_secure_threshold = float(_book_value("secure_threshold", timeframe, 0.72))
    effective_secure_threshold = default_secure_threshold if secure_threshold is None else float(secure_threshold)

    highs, lows = _pivot_highs_lows(normalized, window=effective_window)

    # Build a small DataFrame for indicators to compute EMA/ATR when needed
    df = pd.DataFrame(
        [
            {
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume if c.volume is not None else 0.0,
            }
            for c in normalized
        ]
    )

    # compute ATR-like baseline and optionally EMA(20) for trend filtering
    atr_like = _average_true_range_like(normalized)
    last_close = normalized[-1].close

    # adaptive tolerance: enlarge tolerance proportionally to recent ATR to account for volatility
    atr_pct = (atr_like / max(last_close, 1e-9)) * 100.0 if last_close > 0 else 0.0
    adaptive_tol = max(effective_tolerance, min(atr_pct * 1.5, 10.0))
    effective_tolerance_adaptive = adaptive_tol

    resistance_raw = _cluster_levels(highs, tolerance_pct=effective_tolerance_adaptive)
    support_raw = _cluster_levels(lows, tolerance_pct=effective_tolerance_adaptive)

    confirmation_sets_support: list[list[dict]] = []
    confirmation_sets_resistance: list[list[dict]] = []
    for window in window_profile[1:]:
        if len(normalized) < (2 * window + 1):
            continue
        win_highs, win_lows = _pivot_highs_lows(normalized, window=window)
        confirmation_sets_support.append(_cluster_levels(win_lows, tolerance_pct=effective_tolerance_adaptive))
        confirmation_sets_resistance.append(_cluster_levels(win_highs, tolerance_pct=effective_tolerance_adaptive))

    # last_close already computed above
    supports = _filter_by_last_close(support_raw, last_close, "support", max_levels=max_levels)
    resistances = _filter_by_last_close(resistance_raw, last_close, "resistance", max_levels=max_levels)
    supports = _enrich_with_distance(supports, last_close)
    resistances = _enrich_with_distance(resistances, last_close)

    secure_support = _secure_level_summary(
        candles=normalized,
        base_levels=supports,
        confirmation_sets=confirmation_sets_support,
        last_close=last_close,
        level_type="support",
        series_len=len(normalized),
        tolerance_pct=effective_tolerance_adaptive,
        timeframe=timeframe,
    )
    secure_resistance = _secure_level_summary(
        candles=normalized,
        base_levels=resistances,
        confirmation_sets=confirmation_sets_resistance,
        last_close=last_close,
        level_type="resistance",
        series_len=len(normalized),
        tolerance_pct=effective_tolerance_adaptive,
        timeframe=timeframe,
    )

    secure_support_ok = bool(secure_support and float(secure_support.get("confidence", 0.0)) >= effective_secure_threshold)
    secure_resistance_ok = bool(secure_resistance and float(secure_resistance.get("confidence", 0.0)) >= effective_secure_threshold)

    # optional trend filter: prefer supports in uptrend and resistances in downtrend
    trend_up = None
    try:
        ti = TechnicalIndicators.from_ohlcv(df)
        ema20 = ti.ema(length=20)
        ema20_last = float(ema20.iloc[-1]) if not ema20.empty else None
        trend_up = None if ema20_last is None else (last_close >= ema20_last)
    except Exception:
        ema20_last = None
        trend_up = None

    if apply_trend_filter and trend_up is not None:
        # require trend direction to match role: supports only in uptrend, resistances only in downtrend
        if secure_support_ok and trend_up is False:
            secure_support_ok = False
        if secure_resistance_ok and trend_up is True:
            secure_resistance_ok = False

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "generated_at": _now_iso(),
        "last_close": round(last_close, 6),
        "supports": supports,
        "resistances": resistances,
        "secure_support": secure_support,
        "secure_resistance": secure_resistance,
        "secure_support_ok": secure_support_ok,
        "secure_resistance_ok": secure_resistance_ok,
        "secure_threshold": effective_secure_threshold,
        "method": {
            "name": "hardcoded_pivot_cluster",
            "pivot_window": effective_window,
            "base_tolerance_pct": effective_tolerance,
            "tolerance_pct": effective_tolerance_adaptive,
            "adaptive_tolerance": effective_tolerance_adaptive,
            "applied_trend_filter": apply_trend_filter,
            "ema_20": ema20_last if 'ema20_last' in locals() else None,
            "max_levels": max_levels,
            "series_len": len(normalized),
            "pivot_high_count": len(highs),
            "pivot_low_count": len(lows),
            "analysis_windows": window_profile,
            "rulebook": {
                "touch_threshold": _book_value("touches_min", timeframe, 2),
                "secure_threshold_default": default_secure_threshold,
                "retest_lookahead": _book_value("retest_lookahead", timeframe, 3),
                "reaction_buffer_pct": _book_value("reaction_buffer_pct", timeframe, 0.1),
                "volume_bonus_min_ratio": _book_value("volume_bonus_min_ratio", timeframe, 1.1),
                "touch_band_pct": _book_value("touch_band_pct", timeframe, 0.2),
                "timeframe_weight": _book_value("timeframe_weight", timeframe, 1.0),
                "close_confirmation_weight": BOOK_RULES["close_confirmation_weight"],
                "role_reversal_weight": BOOK_RULES["role_reversal_weight"],
                "round_number_weight": BOOK_RULES["round_number_weight"],
            },
        },
        "knowledge_notes": [],
        "integration_hint": (
            "Il motore è hardcoded secondo regole tecniche; usa secure_support/"
            "secure_resistance per la logica principale quando secure_*_ok è True. "
            "Le knowledge_notes sono opzionali e servono solo a spiegare o auditare."
        ),
    }


def spiega_supporti_resistenze(analysis: dict) -> str:
    """Convert a technical-analysis result into a readable operational explanation."""

    symbol = analysis.get("symbol", "UNKNOWN")
    timeframe = analysis.get("timeframe", "1d")
    last_close = analysis.get("last_close", "?")
    secure_threshold = analysis.get("secure_threshold", "?")
    secure_support = analysis.get("secure_support") or {}
    secure_resistance = analysis.get("secure_resistance") or {}
    support_ok = bool(analysis.get("secure_support_ok"))
    resistance_ok = bool(analysis.get("secure_resistance_ok"))

    lines: list[str] = []
    lines.append(f"Analisi {symbol} su timeframe {timeframe}")
    lines.append(f"Prezzo ultimo close: {last_close}")
    lines.append(f"Soglia di sicurezza: {secure_threshold}")
    lines.append("")

    if secure_support:
        lines.append("Supporto sicuro candidato:")
        lines.append(f"- livello: {secure_support.get('level')}")
        lines.append(f"- confidence: {secure_support.get('confidence')}")
        lines.append(f"- conferme: {secure_support.get('confirmations')}")
        lines.append(f"- tocchi: {secure_support.get('touches')}")
        lines.append(f"- valido: {'si' if support_ok else 'no'}")
        flags = secure_support.get("rule_flags") or {}
        lines.append(f"- regole rispettate: {flags}")
        lines.append("")
    else:
        lines.append("Nessun supporto sicuro trovato.")
        lines.append("")

    if secure_resistance:
        lines.append("Resistenza sicura candidata:")
        lines.append(f"- livello: {secure_resistance.get('level')}")
        lines.append(f"- confidence: {secure_resistance.get('confidence')}")
        lines.append(f"- conferme: {secure_resistance.get('confirmations')}")
        lines.append(f"- tocchi: {secure_resistance.get('touches')}")
        lines.append(f"- valido: {'si' if resistance_ok else 'no'}")
        flags = secure_resistance.get("rule_flags") or {}
        lines.append(f"- regole rispettate: {flags}")
        lines.append("")
    else:
        lines.append("Nessuna resistenza sicura trovata.")
        lines.append("")

    method = analysis.get("method") or {}
    if method:
        lines.append("Motore usato:")
        lines.append(f"- pivot window: {method.get('pivot_window')}")
        lines.append(f"- tolleranza: {method.get('tolerance_pct')}")
        lines.append(f"- finestre di conferma: {method.get('analysis_windows')}")
        rulebook = method.get("rulebook") or {}
        if rulebook:
            lines.append(f"- rulebook: {rulebook}")

    return "\n".join(lines).strip()

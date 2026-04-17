from bot_functions import (
    Candle,
    _close_breakout_score,
    _role_reversal_score,
    _round_number_score,
    richiedi_supporti_resistenze,
)


def _candles(rows):
    return [Candle(timestamp=str(i), open=o, high=h, low=l, close=c, volume=1000.0) for i, (o, h, l, c) in enumerate(rows)]


def test_round_number_score_prefers_clean_levels():
    round_score, nearest, distance_pct = _round_number_score(100.0)
    off_score, off_nearest, off_distance_pct = _round_number_score(103.0)

    assert nearest == 100.0
    assert distance_pct == 0.0
    assert round_score > off_score
    assert off_nearest == 100.0
    assert off_distance_pct > 0.0


def test_support_breakout_close_and_role_reversal_scores():
    candles = _candles(
        [
            (99.8, 100.0, 99.4, 99.6),
            (99.6, 99.9, 99.1, 99.3),
            (99.3, 99.8, 99.0, 99.2),
            (99.2, 100.2, 99.1, 100.25),
            (100.25, 100.35, 99.95, 100.18),
            (100.18, 100.40, 99.97, 100.28),
        ]
    )

    close_score = _close_breakout_score(candles, 100.0, "support", lookahead=3, buffer_pct=0.1)
    role_score = _role_reversal_score(candles, 100.0, "support", lookahead=3, buffer_pct=0.1)

    assert close_score > 0.5
    assert role_score > 0.5


def test_resistance_breakout_close_and_role_reversal_scores():
    candles = _candles(
        [
            (100.2, 100.8, 100.0, 100.6),
            (100.6, 100.9, 100.2, 100.4),
            (100.4, 100.7, 100.1, 100.3),
            (100.3, 100.35, 99.6, 99.85),
            (99.85, 100.05, 99.5, 99.72),
            (99.72, 99.95, 99.4, 99.65),
        ]
    )

    close_score = _close_breakout_score(candles, 100.0, "resistance", lookahead=3, buffer_pct=0.1)
    role_score = _role_reversal_score(candles, 100.0, "resistance", lookahead=3, buffer_pct=0.1)

    assert close_score > 0.5
    assert role_score > 0.5


def test_timeframe_weight_is_exposed_in_metadata():
    candles = _candles(
        [
            (99.6, 99.9, 99.3, 99.5),
            (99.5, 99.8, 99.2, 99.4),
            (99.4, 99.7, 99.1, 99.3),
            (99.3, 99.6, 99.0, 99.2),
            (99.2, 99.5, 98.9, 99.1),
            (99.1, 99.4, 98.8, 99.0),
            (99.0, 99.3, 98.7, 98.9),
            (98.9, 99.2, 98.6, 98.8),
            (98.8, 99.1, 98.5, 98.7),
            (98.7, 99.0, 98.4, 98.6),
            (98.6, 99.1, 98.3, 98.9),
            (98.9, 99.5, 98.8, 99.2),
            (99.2, 99.8, 99.0, 99.5),
            (99.5, 100.2, 99.4, 99.9),
            (99.9, 100.5, 99.8, 100.3),
            (100.3, 100.8, 100.1, 100.6),
            (100.6, 101.0, 100.4, 100.85),
            (100.85, 101.2, 100.7, 101.0),
            (101.0, 101.4, 100.9, 101.25),
            (101.25, 101.6, 101.1, 101.45),
        ]
    )

    analysis_1m = richiedi_supporti_resistenze(candles, symbol="TEST", timeframe="1m", max_levels=5)
    analysis_1w = richiedi_supporti_resistenze(candles, symbol="TEST", timeframe="1w", max_levels=5)

    assert analysis_1m["method"]["rulebook"]["timeframe_weight"] < analysis_1w["method"]["rulebook"]["timeframe_weight"]
    assert analysis_1m["method"]["rulebook"]["close_confirmation_weight"] > 0
    assert analysis_1w["method"]["rulebook"]["round_number_weight"] > 0

import numpy as np
import pandas as pd

from indicators import TechnicalIndicators


def _build_sample_ohlcv(rows: int = 180) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=rows, freq="15min", tz="UTC")

    trend = np.linspace(100.0, 118.0, rows)
    noise = 0.45 * np.sin(np.arange(rows) / 3.0)
    close = trend + noise
    open_ = close - 0.12
    high = close + 0.75
    low = close - 0.80
    volume = 1000 + np.linspace(0, 250, rows) + (np.arange(rows) % 7) * 9

    return pd.DataFrame(
        {
            "timestamp": idx,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def test_from_ohlcv_normalizes_columns():
    data = _build_sample_ohlcv().rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
            "timestamp": "Date",
        }
    )

    indicators = TechnicalIndicators.from_ohlcv(data)
    assert list(indicators.ohlcv.columns) == ["open", "high", "low", "close", "volume"]
    assert len(indicators.ohlcv) == len(data)


def test_rsi_atr_obv_volume_ma_have_values():
    indicators = TechnicalIndicators.from_ohlcv(_build_sample_ohlcv())

    rsi = indicators.rsi(length=14)
    atr = indicators.atr(length=14)
    obv = indicators.obv()
    vol_ma = indicators.volume_ma(length=20)

    assert pd.notna(rsi.iloc[-1])
    assert 0 <= float(rsi.dropna().iloc[-1]) <= 100
    assert float(atr.dropna().iloc[-1]) > 0
    assert len(obv.dropna()) > 0
    assert float(vol_ma.dropna().iloc[-1]) > 0


def test_adx_output_columns_and_bounds():
    indicators = TechnicalIndicators.from_ohlcv(_build_sample_ohlcv())
    adx = indicators.adx(length=14)

    assert {"plus_di_14", "minus_di_14", "adx_14"}.issubset(set(adx.columns))
    last_adx = float(adx["adx_14"].dropna().iloc[-1])
    assert 0 <= last_adx <= 100


def test_atr_stop_structure_and_ordering():
    indicators = TechnicalIndicators.from_ohlcv(_build_sample_ohlcv())
    stops = indicators.atr_stop(length=14, multiplier=1.5, direction="both")

    assert {"atr_long_stop_14", "atr_short_stop_14"}.issubset(set(stops.columns))

    frame = indicators.ohlcv.join(stops)
    frame = frame.dropna()
    assert (frame["atr_long_stop_14"] < frame["close"]).all()
    assert (frame["atr_short_stop_14"] > frame["close"]).all()


def test_compute_default_set_and_latest_snapshot():
    indicators = TechnicalIndicators.from_ohlcv(_build_sample_ohlcv())

    table = indicators.compute_default_set()
    snapshot = indicators.latest_snapshot()

    expected_columns = {
        "rsi_14",
        "atr_14",
        "obv",
        "volume_ma_20",
        "sma_20",
        "ema_20",
        "plus_di_14",
        "minus_di_14",
        "adx_14",
    }
    assert expected_columns.issubset(set(table.columns))

    assert "rsi_14" in snapshot
    assert "adx_14" in snapshot


def test_from_mcp_price_history_accepts_dict_payload():
    raw = _build_sample_ohlcv(60)
    payload = {"data": raw.to_dict(orient="records")}

    indicators = TechnicalIndicators.from_mcp_price_history(payload)
    rsi = indicators.rsi(length=14)

    assert len(indicators.ohlcv) == 60
    assert len(rsi) == 60


def test_from_mcp_price_history_accepts_markdown_table_payload():
    payload = """
|   Close |    High |     Low |    Open |      Volume |
|--------:|--------:|--------:|--------:|------------:|
| 1.38149 | 1.39246 | 1.29613 | 1.32121 | 2.51393e+09 |
| 1.34237 | 1.38694 | 1.34006 | 1.38149 | 2.59888e+09 |
| 1.34414 | 1.36524 | 1.32356 | 1.34238 | 2.59948e+09 |
"""

    indicators = TechnicalIndicators.from_mcp_price_history(payload)

    assert len(indicators.ohlcv) == 3
    assert indicators.ohlcv["close"].iloc[0] == 1.38149

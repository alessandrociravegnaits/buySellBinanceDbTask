import numpy as np
import pandas as pd

import prevision


def _build_sample_ohlcv(rows: int = 180) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=rows, freq="15min", tz="UTC")
    trend = np.linspace(1.20, 1.42, rows)
    wave = 0.012 * np.sin(np.arange(rows) / 4.0)
    close = trend + wave
    open_ = close - 0.003
    high = close + 0.008
    low = close - 0.010
    volume = 1_000_000 + np.linspace(0, 250_000, rows)

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


def test_normalize_symbol_appends_default_quote():
    assert prevision.normalize_symbol("xrp") == "XRPUSDC"
    assert prevision.normalize_symbol("XRP/USDC") == "XRPUSDC"
    assert prevision.normalize_symbol("BTCUSDT") == "BTCUSDT"


def test_analyze_frame_builds_bot_command(monkeypatch):
    frame = _build_sample_ohlcv()
    monkeypatch.setattr(prevision, "fetch_symbol_step_size", lambda symbol: (0.001, 0.001))

    result = prevision.analyze_frame(
        symbol="XRPUSDC",
        frame=frame,
        tf_minutes=15,
        budget_quote=100.0,
        lookback_bars=90,
    )

    assert result.command.startswith("/B XRPUSDC ")
    assert "tf=15" in result.command
    assert "btc_alert" in result.command
    assert "oco:tp=" in result.command
    assert "sl=trail:" in result.command
    assert result.quantity is not None
    assert result.quantity > 0

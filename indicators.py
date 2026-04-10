"""Technical indicators utilities for OHLCV data.

This module is intentionally dependency-light and uses only pandas/numpy.
It is designed to work with OHLCV frames coming from exchange feeds or
from raw payloads exported by external tools (for example MCP finance).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd


REQUIRED_OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class TechnicalIndicators:
    """Compute technical indicators from a normalized OHLCV DataFrame.

    Expected columns: open, high, low, close, volume.
    Optional index: datetime-like or integer.
    """

    ohlcv: pd.DataFrame

    @classmethod
    def from_ohlcv(cls, data: pd.DataFrame) -> "TechnicalIndicators":
        """Create an instance from any OHLCV-like DataFrame.

        Column names are normalized to lowercase. Common aliases like
        `timestamp`/`date` are accepted.
        """
        normalized = cls._normalize_ohlcv(data)
        return cls(ohlcv=normalized)

    @classmethod
    def from_mcp_price_history(cls, payload: Any) -> "TechnicalIndicators":
        """Create an instance from a raw MCP-like payload.

        Accepted payloads:
        - DataFrame with OHLCV columns
        - list[dict] with OHLCV keys (case-insensitive)
        - dict containing one list field among: data, prices, ohlcv, rows
        - markdown table string as returned by MCP finance price history
        """
        if isinstance(payload, pd.DataFrame):
            return cls.from_ohlcv(payload)

        if isinstance(payload, str):
            records = cls._parse_markdown_ohlcv_table(payload)
            return cls.from_ohlcv(pd.DataFrame(records))

        records: Iterable[Mapping[str, Any]]
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            candidate = None
            for key in ("data", "prices", "ohlcv", "rows"):
                value = payload.get(key)
                if isinstance(value, list):
                    candidate = value
                    break
            if candidate is None:
                raise ValueError("Payload MCP non contiene una lista OHLCV riconoscibile")
            records = candidate
        else:
            raise TypeError("Payload non supportato per from_mcp_price_history")

        return cls.from_ohlcv(pd.DataFrame(records))

    @staticmethod
    def _parse_markdown_ohlcv_table(payload: str) -> list[dict[str, Any]]:
        """Parse a markdown OHLCV table into record dictionaries.

        Expected shape (common from MCP finance):
        | Close | High | Low | Open | Volume |
        |------:|-----:|----:|-----:|-------:|
        |  ...  | ...  | ... | ...  |  ...   |
        """
        lines = [line.strip() for line in payload.splitlines() if line.strip()]
        if len(lines) < 3:
            raise ValueError("Stringa MCP non valida: tabella markdown incompleta")

        header_line = lines[0]
        if "|" not in header_line:
            raise ValueError("Stringa MCP non valida: header tabella mancante")

        headers = [h.strip().lower() for h in header_line.strip("|").split("|")]
        records: list[dict[str, Any]] = []
        for row in lines[2:]:
            cells = [c.strip() for c in row.strip("|").split("|")]
            if len(cells) != len(headers):
                continue

            item: dict[str, Any] = {}
            for key, value in zip(headers, cells):
                try:
                    item[key] = float(value)
                except ValueError:
                    item[key] = value
            records.append(item)

        if not records:
            raise ValueError("Stringa MCP non valida: nessuna riga dati")

        return records

    @staticmethod
    def _normalize_ohlcv(data: pd.DataFrame) -> pd.DataFrame:
        if data is None or data.empty:
            raise ValueError("OHLCV DataFrame vuoto")

        df = data.copy()
        renamed = {str(col): str(col).strip().lower() for col in df.columns}
        df.rename(columns=renamed, inplace=True)

        alias_map = {
            "datetime": "timestamp",
            "time": "timestamp",
            "date": "timestamp",
        }
        for src, dst in alias_map.items():
            if src in df.columns and dst not in df.columns:
                df.rename(columns={src: dst}, inplace=True)

        missing = [col for col in REQUIRED_OHLCV_COLUMNS if col not in df.columns]
        if missing:
            raise ValueError(f"Colonne OHLCV mancanti: {missing}")

        for col in REQUIRED_OHLCV_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        if "timestamp" in df.columns:
            ts = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
            if ts.notna().any():
                df.index = ts

        df = df.sort_index()
        df = df.dropna(subset=["high", "low", "close", "volume"])
        return df[["open", "high", "low", "close", "volume"]]

    def sma(self, length: int = 20, column: str = "close") -> pd.Series:
        if length <= 0:
            raise ValueError("length deve essere > 0")
        return self.ohlcv[column].rolling(window=length, min_periods=length).mean()

    def ema(self, length: int = 20, column: str = "close") -> pd.Series:
        if length <= 0:
            raise ValueError("length deve essere > 0")
        return self.ohlcv[column].ewm(span=length, adjust=False, min_periods=length).mean()

    def volume_ma(self, length: int = 20) -> pd.Series:
        return self.sma(length=length, column="volume")

    def rsi(self, length: int = 14, column: str = "close") -> pd.Series:
        if length <= 0:
            raise ValueError("length deve essere > 0")

        delta = self.ohlcv[column].diff()
        gains = delta.clip(lower=0)
        losses = -delta.clip(upper=0)

        avg_gain = gains.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
        avg_loss = losses.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)

        rsi = 100 - (100 / (1 + rs))
        return rsi.clip(lower=0, upper=100)

    def true_range(self) -> pd.Series:
        high = self.ohlcv["high"]
        low = self.ohlcv["low"]
        prev_close = self.ohlcv["close"].shift(1)

        tr_1 = high - low
        tr_2 = (high - prev_close).abs()
        tr_3 = (low - prev_close).abs()
        return pd.concat([tr_1, tr_2, tr_3], axis=1).max(axis=1)

    def atr(self, length: int = 14) -> pd.Series:
        if length <= 0:
            raise ValueError("length deve essere > 0")
        tr = self.true_range()
        return tr.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()

    def adx(self, length: int = 14) -> pd.DataFrame:
        if length <= 0:
            raise ValueError("length deve essere > 0")

        high = self.ohlcv["high"]
        low = self.ohlcv["low"]

        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = pd.Series(
            np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
            index=self.ohlcv.index,
        )
        minus_dm = pd.Series(
            np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
            index=self.ohlcv.index,
        )

        atr = self.atr(length=length)
        smooth_plus_dm = plus_dm.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
        smooth_minus_dm = minus_dm.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()

        plus_di = 100 * (smooth_plus_dm / atr.replace(0, np.nan))
        minus_di = 100 * (smooth_minus_dm / atr.replace(0, np.nan))

        dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
        adx = dx.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()

        out = pd.DataFrame(
            {
                f"plus_di_{length}": plus_di,
                f"minus_di_{length}": minus_di,
                f"adx_{length}": adx,
            }
        )
        return out

    def obv(self) -> pd.Series:
        close = self.ohlcv["close"]
        vol = self.ohlcv["volume"].fillna(0)
        direction = close.diff().fillna(0)
        signed = np.where(direction > 0, vol, np.where(direction < 0, -vol, 0.0))
        return pd.Series(signed, index=self.ohlcv.index).cumsum()

    def atr_stop(
        self,
        length: int = 14,
        multiplier: float = 1.5,
        direction: str = "both",
        column: str = "close",
    ) -> pd.DataFrame | pd.Series:
        """ATR-based stop levels.

        direction options:
        - "long": stop under price
        - "short": stop above price
        - "both": return DataFrame with both columns
        """
        if multiplier <= 0:
            raise ValueError("multiplier deve essere > 0")

        base = self.ohlcv[column]
        atr = self.atr(length=length)
        long_stop = base - multiplier * atr
        short_stop = base + multiplier * atr

        if direction == "long":
            return long_stop
        if direction == "short":
            return short_stop
        if direction != "both":
            raise ValueError("direction deve essere 'long', 'short' o 'both'")

        return pd.DataFrame(
            {
                f"atr_long_stop_{length}": long_stop,
                f"atr_short_stop_{length}": short_stop,
            }
        )

    def compute_default_set(self) -> pd.DataFrame:
        """Compute the default indicator set used in trading checks.

        Includes:
        - RSI(14)
        - ATR(14)
        - ADX(14) + DI lines
        - OBV
        - Volume MA(20)
        - SMA(20), EMA(20)
        """
        adx = self.adx(length=14)

        out = pd.DataFrame(index=self.ohlcv.index)
        out["rsi_14"] = self.rsi(length=14)
        out["atr_14"] = self.atr(length=14)
        out["obv"] = self.obv()
        out["volume_ma_20"] = self.volume_ma(length=20)
        out["sma_20"] = self.sma(length=20)
        out["ema_20"] = self.ema(length=20)

        for col in adx.columns:
            out[col] = adx[col]

        return out

    def latest_snapshot(self) -> dict[str, float | None]:
        """Return latest values for quick rule checks in the bot."""
        indicators = self.compute_default_set()
        if indicators.empty:
            return {}

        row = indicators.iloc[-1]
        out: dict[str, float | None] = {}
        for key, value in row.to_dict().items():
            if pd.isna(value):
                out[key] = None
            else:
                out[key] = float(value)
        return out
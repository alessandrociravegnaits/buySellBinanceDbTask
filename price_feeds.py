"""
Price Feeds — implementazioni concrete di PriceFeed
Aggiungi qui il feed reale (ccxt, yfinance, ecc.)
"""

import threading
import os
import logging
from core import PriceFeed

log = logging.getLogger(__name__)


class MockPriceFeed(PriceFeed):
    """Prezzo manuale — per test e backtest."""

    def __init__(self, initial_price: float = 100.0):
        self._price = initial_price
        self._lock  = threading.Lock()

    def get_price(self, symbol: str, tf_minutes: int = 1) -> float:
        with self._lock:
            return self._price

    def set_price(self, price: float):
        with self._lock:
            self._price = price


class Binance1mClosePriceFeed(PriceFeed):
    """
    Feed reale Binance ispirato a `lettura1mt` di spunto.py.
    Restituisce il close dell'ultima candela per il timeframe richiesto.
    Usa `python-binance` per recuperare le klines.
    """

    TF_MAP = {
        1: "1m",
        5: "5m",
        15: "15m",
        30: "30m",
        60: "1h",
        120: "2h",
        240: "4h",
        1440: "1d",
    }

    def __init__(self, api_key: str = None, api_secret: str = None, round_digits: int = 8):
        try:
            from binance.client import Client
        except ImportError as exc:
            raise ImportError(
                "python-binance non installato. Installa con: pip install python-binance"
            ) from exc

        self._Client = Client
        self._round_digits = round_digits
        self._client = Client(
            api_key or os.getenv("BINANCE_API_KEY"),
            api_secret or os.getenv("BINANCE_SECRET_KEY"),
        )

    def _period_text_for(self, interval: str) -> str:
        # costruisce una descrizione temporale accettata da get_historical_klines
        if interval.endswith("m"):
            n = int(interval[:-1])
            return f"{n} minute ago UTC"
        if interval.endswith("h"):
            n = int(interval[:-1])
            return f"{n} hour ago UTC"
        if interval.endswith("d"):
            n = int(interval[:-1]) if interval[:-1].isdigit() else 1
            return f"{n} day ago UTC"
        return "1 minute ago UTC"

    def get_price(self, symbol: str, tf_minutes: int = 1) -> float:
        interval = self.TF_MAP.get(int(tf_minutes))
        if interval is None:
            raise ValueError(f"Unsupported tf_minutes: {tf_minutes}")
        try:
            period = self._period_text_for(interval)
            kline = self._client.get_historical_klines(
                symbol,
                interval,
                period,
            )
            close = float(kline[0][4])
            return round(close, self._round_digits)
        except Exception as exc:
            log.error("Errore Binance feed su %s tf=%s: %s", symbol, tf_minutes, exc)
            raise


# class BinancePriceFeed(PriceFeed):
#     """Esempio: feed reale via ccxt."""
#     def __init__(self):
#         import ccxt
#         self._exchange = ccxt.binance()
#
#     def get_price(self, symbol: str) -> float:
#         ticker = self._exchange.fetch_ticker(symbol)
#         return ticker['last']


# class YFinancePriceFeed(PriceFeed):
#     """Esempio: feed reale via yfinance (azioni)."""
#     def get_price(self, symbol: str) -> float:
#         import yfinance as yf
#         ticker = yf.Ticker(symbol)
#         return ticker.fast_info['last_price']

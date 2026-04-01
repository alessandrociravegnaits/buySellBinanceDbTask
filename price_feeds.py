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

    def get_price(self, symbol: str) -> float:
        with self._lock:
            return self._price

    def set_price(self, price: float):
        with self._lock:
            self._price = price


class Binance1mClosePriceFeed(PriceFeed):
    """
    Feed reale Binance ispirato a `lettura1mt` di spunto.py:
    legge il close dell'ultima candela 1m e lo restituisce come float.
    """

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

    def get_price(self, symbol: str) -> float:
        try:
            kline = self._client.get_historical_klines(
                symbol,
                self._Client.KLINE_INTERVAL_1MINUTE,
                "1 minute ago UTC",
            )
            close = float(kline[0][4])
            return round(close, self._round_digits)
        except Exception as exc:
            log.error("Errore Binance feed su %s: %s", symbol, exc)
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

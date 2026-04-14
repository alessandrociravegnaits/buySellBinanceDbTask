"""Market-to-command helper for the trading bot.

This script asks for a symbol/pair, fetches public Binance OHLCV data,
computes a compact technical view, and prints a bot-ready trailing-buy
command.

It is a local helper, not a replacement for the manual mcp finance flow
used during Copilot reasoning.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Any

import pandas as pd
import requests

from indicators import TechnicalIndicators


BINANCE_API_BASE = "https://api.binance.com"
DEFAULT_TF_MINUTES = 15
DEFAULT_LOOKBACK_BARS = 90
DEFAULT_KLINES_LIMIT = 200
SUPPORTED_TF = {
    1: "1m",
    5: "5m",
    15: "15m",
    30: "30m",
    60: "1h",
    120: "2h",
    240: "4h",
    1440: "1d",
}


@dataclass(frozen=True)
class AnalysisResult:
    symbol: str
    tf_minutes: int
    close: float
    swing_high: float
    swing_low: float
    score: int
    bias: str
    support_level: float
    bounce_percent: float
    take_profit_percent: float
    stop_percent: float
    btc_alert: bool
    acquistopulito: bool
    quantity: float | None
    command: str
    summary_lines: list[str]


def normalize_symbol(raw: str, default_quote: str = "USDC") -> str:
    value = (raw or "").strip().upper().replace(" ", "")
    if not value:
        raise ValueError("Simbolo vuoto")
    if "/" in value:
        value = value.replace("/", "")
    if any(value.endswith(suffix) for suffix in ("USDT", "USDC", "FDUSD", "BTC", "ETH", "EUR", "TRY", "BNB")):
        return value
    return f"{value}{default_quote}"


def tf_to_interval(tf_minutes: int) -> str:
    if tf_minutes not in SUPPORTED_TF:
        allowed = ", ".join(str(item) for item in sorted(SUPPORTED_TF))
        raise ValueError(f"Timeframe non supportato: {tf_minutes}. Valori ammessi: {allowed}")
    return SUPPORTED_TF[tf_minutes]


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def trim_float(value: float, digits: int = 8) -> str:
    number = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return number or "0"


def fetch_ohlcv_from_binance(symbol: str, tf_minutes: int, limit: int = DEFAULT_KLINES_LIMIT) -> pd.DataFrame:
    interval = tf_to_interval(tf_minutes)
    response = requests.get(
        f"{BINANCE_API_BASE}/api/v3/klines",
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or not payload:
        raise RuntimeError(f"Nessun dato OHLCV disponibile per {symbol}")

    frame = pd.DataFrame(
        payload,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "number_of_trades",
            "taker_buy_base_asset_volume",
            "taker_buy_quote_asset_volume",
            "ignore",
        ],
    )
    frame["timestamp"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[["timestamp", "open", "high", "low", "close", "volume"]].dropna()
    if frame.empty:
        raise RuntimeError(f"OHLCV vuoto dopo normalizzazione per {symbol}")
    return frame


def fetch_symbol_step_size(symbol: str) -> tuple[float, float]:
    response = requests.get(
        f"{BINANCE_API_BASE}/api/v3/exchangeInfo",
        params={"symbol": symbol},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    symbols = payload.get("symbols") or []
    if not symbols:
        raise RuntimeError(f"Simbolo non trovato su Binance: {symbol}")

    info = symbols[0]
    lot_size = next((item for item in info.get("filters", []) if item.get("filterType") == "LOT_SIZE"), None)
    if not lot_size:
        raise RuntimeError(f"LOT_SIZE non disponibile per {symbol}")

    return float(lot_size["stepSize"]), float(lot_size["minQty"])


def floor_to_step(value: float, step: float) -> float:
    if value <= 0:
        return 0.0
    step_dec = Decimal(str(step))
    if step_dec <= 0:
        return float(value)
    value_dec = Decimal(str(value))
    floored = (value_dec / step_dec).to_integral_value(rounding=ROUND_DOWN) * step_dec
    return float(floored)


def fibonacci_levels(swing_high: float, swing_low: float) -> dict[str, float]:
    spread = swing_high - swing_low
    return {
        "0%": swing_high,
        "23.6%": swing_high - spread * 0.236,
        "38.2%": swing_high - spread * 0.382,
        "50%": swing_high - spread * 0.5,
        "61.8%": swing_high - spread * 0.618,
        "78.6%": swing_high - spread * 0.786,
        "100%": swing_low,
    }


def macd_line(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    line = ema12 - ema26
    signal = line.ewm(span=9, adjust=False, min_periods=9).mean()
    hist = line - signal
    return line, signal, hist


def support_depth_from_score(score: int) -> int:
    if score >= 3:
        return 0
    if score >= 1:
        return 1
    if score >= -1:
        return 2
    return 3


def choose_support_level(levels: dict[str, float], close: float, score: int) -> tuple[str, float]:
    ordered = [item for item in levels.items() if item[1] < close]
    if not ordered:
        ordered = [item for item in levels.items() if item[0] != "0%"]
    ordered = sorted(ordered, key=lambda item: item[1], reverse=True)
    depth = min(support_depth_from_score(score), max(0, len(ordered) - 1))
    return ordered[depth]


def support_score(snapshot: dict[str, Any], close: float, macd_value: float, signal_value: float, volume: float) -> tuple[int, str]:
    score = 0

    ema20 = snapshot.get("ema_20")
    rsi14 = snapshot.get("rsi_14")
    adx14 = snapshot.get("adx_14")
    volume_ma20 = snapshot.get("volume_ma_20")

    if ema20 is not None:
        score += 1 if close > float(ema20) else -1
    if rsi14 is not None:
        rsi = float(rsi14)
        if rsi >= 55:
            score += 1
        elif rsi <= 45:
            score -= 1
    if adx14 is not None:
        adx = float(adx14)
        if adx >= 18:
            score += 1
        elif adx < 12:
            score -= 1
    if macd_value > signal_value:
        score += 1
    else:
        score -= 1
    if volume_ma20 is not None and volume > float(volume_ma20):
        score += 1

    if score >= 3:
        bias = "strong"
    elif score >= 1:
        bias = "moderate"
    else:
        bias = "cautious"

    return score, bias


def derive_buy_parameters(close: float, support: float, atr: float | None, score: int, bias: str) -> tuple[float, float, float]:
    atr_pct = (float(atr) / close * 100.0) if atr and close > 0 else 1.0
    base_bounce = atr_pct * 1.25
    if bias == "strong":
        base_bounce *= 0.9
    elif bias == "cautious":
        base_bounce *= 1.15

    bounce_percent = clamp(round(base_bounce, 2), 0.8, 3.0)
    take_profit_percent = clamp(round(max(2.0, atr_pct * 3.0 + max(0, score) * 0.25), 2), 2.0, 7.0)
    stop_percent = clamp(round(max(1.0, atr_pct * 1.8), 2), 1.0, 3.5)
    return bounce_percent, take_profit_percent, stop_percent


def build_command(
    symbol: str,
    bounce_percent: float,
    quantity: float | None,
    support: float,
    tf_minutes: int,
    tp_percent: float,
    stop_percent: float,
    btc_alert: bool,
    acquistopulito: bool,
) -> str:
    parts = [
        "/B",
        symbol,
        trim_float(bounce_percent, digits=2),
        trim_float(quantity, digits=8) if quantity is not None else "QTY",
        trim_float(support, digits=8),
        f"tf={tf_minutes}",
    ]
    if acquistopulito:
        parts.append("acquistopulito")
    if btc_alert:
        parts.append("btc_alert")
    parts.append(f"oco:tp={trim_float(tp_percent, digits=2)}%,sl=trail:{trim_float(stop_percent, digits=2)}%")
    return " ".join(parts)


def analyze_frame(
    symbol: str,
    frame: pd.DataFrame,
    tf_minutes: int,
    budget_quote: float | None = None,
    lookback_bars: int = DEFAULT_LOOKBACK_BARS,
) -> AnalysisResult:
    indicators = TechnicalIndicators.from_ohlcv(frame)
    snapshot = indicators.latest_snapshot()
    close = float(frame["close"].iloc[-1])

    lookback = min(max(1, lookback_bars), len(frame))
    window = frame.tail(lookback)
    swing_high = float(window["high"].max())
    swing_low = float(window["low"].min())
    levels = fibonacci_levels(swing_high, swing_low)

    macd_series, signal_series, _ = macd_line(frame["close"])
    macd_value = float(macd_series.iloc[-1]) if pd.notna(macd_series.iloc[-1]) else 0.0
    signal_value = float(signal_series.iloc[-1]) if pd.notna(signal_series.iloc[-1]) else 0.0
    score, bias = support_score(snapshot, close, macd_value, signal_value, float(window["volume"].iloc[-1]))

    level_name, support = choose_support_level(levels, close, score)
    bounce_percent, tp_percent, stop_percent = derive_buy_parameters(
        close=close,
        support=support,
        atr=snapshot.get("atr_14"),
        score=score,
        bias=bias,
    )

    btc_alert = True
    acquistopulito = (
        score >= 3
        and snapshot.get("ema_20") is not None
        and close > float(snapshot["ema_20"])
        and snapshot.get("rsi_14") is not None
        and float(snapshot["rsi_14"]) >= 50
        and snapshot.get("adx_14") is not None
        and float(snapshot["adx_14"]) >= 18
    )

    quantity: float | None = None
    if budget_quote is not None and budget_quote > 0:
        raw_quantity = budget_quote / support
        step_size, min_qty = fetch_symbol_step_size(symbol)
        quantity = floor_to_step(raw_quantity, step_size)
        if quantity < min_qty:
            raise RuntimeError(
                f"Quantita' calcolata troppo bassa per {symbol}: {quantity} < minQty {min_qty}"
            )

    command = build_command(
        symbol=symbol,
        bounce_percent=bounce_percent,
        quantity=quantity,
        support=support,
        tf_minutes=tf_minutes,
        tp_percent=tp_percent,
        stop_percent=stop_percent,
        btc_alert=btc_alert,
        acquistopulito=acquistopulito,
    )

    summary_lines = [
        f"Pair: {symbol}",
        f"Timeframe: {tf_minutes}m",
        f"Last close: {trim_float(close, 8)}",
        f"Swing range: {trim_float(swing_low, 8)} -> {trim_float(swing_high, 8)}",
        f"Fib level used: {level_name} = {trim_float(support, 8)}",
        f"Trend bias: {bias} (score {score})",
        f"Bounce percent: {trim_float(bounce_percent, 2)}",
        f"Take profit: {trim_float(tp_percent, 2)}",
        f"Trailing stop: {trim_float(stop_percent, 2)}",
        f"BTC alert: {'on' if btc_alert else 'off'}",
        f"Clean entry: {'on' if acquistopulito else 'off'}",
    ]
    if quantity is not None:
        summary_lines.append(f"Quantity: {trim_float(quantity, 8)}")

    return AnalysisResult(
        symbol=symbol,
        tf_minutes=tf_minutes,
        close=close,
        swing_high=swing_high,
        swing_low=swing_low,
        score=score,
        bias=bias,
        support_level=support,
        bounce_percent=bounce_percent,
        take_profit_percent=tp_percent,
        stop_percent=stop_percent,
        btc_alert=btc_alert,
        acquistopulito=acquistopulito,
        quantity=quantity,
        command=command,
        summary_lines=summary_lines,
    )


def analyze_symbol(
    symbol_input: str,
    tf_minutes: int,
    budget_quote: float | None = None,
    lookback_bars: int = DEFAULT_LOOKBACK_BARS,
) -> AnalysisResult:
    symbol = normalize_symbol(symbol_input)
    frame = fetch_ohlcv_from_binance(symbol, tf_minutes)
    return analyze_frame(
        symbol=symbol,
        frame=frame,
        tf_minutes=tf_minutes,
        budget_quote=budget_quote,
        lookback_bars=lookback_bars,
    )


def prompt_symbol(default: str = "XRPUSDC") -> str:
    raw = input(f"Pair o base asset [{default}]: ").strip()
    return raw or default


def prompt_budget() -> float | None:
    raw = input("Budget nel quote asset (invio per saltare): ").strip()
    if not raw:
        return None
    return float(raw.replace(",", "."))


def prompt_tf(default: int = DEFAULT_TF_MINUTES) -> int:
    raw = input(f"Timeframe minuti [{default}]: ").strip()
    return int(raw or default)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a bot-ready trailing buy command from Binance data.")
    parser.add_argument("symbol", nargs="?", help="Pair or base asset, for example XRPUSDC or XRP")
    parser.add_argument("--budget", type=float, default=None, help="Budget in quote asset used to compute QTY")
    parser.add_argument("--tf", type=int, default=None, help="Timeframe in minutes")
    parser.add_argument("--lookback", type=int, default=DEFAULT_LOOKBACK_BARS, help="Lookback bars for support zone")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    symbol = args.symbol or prompt_symbol()
    tf_minutes = args.tf if args.tf is not None else prompt_tf()
    budget = args.budget if args.budget is not None else prompt_budget()

    try:
        result = analyze_symbol(symbol, tf_minutes=tf_minutes, budget_quote=budget, lookback_bars=args.lookback)
    except Exception as exc:
        print(f"Errore: {exc}")
        return 1

    print("\n=== Analisi ===")
    for line in result.summary_lines:
        print(f"- {line}")

    print("\n=== Comando pronto ===")
    print(result.command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
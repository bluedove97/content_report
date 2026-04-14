"""
주가 데이터 및 기술적 지표 수집 Tool
FinanceDataReader로 OHLCV를 수집하고 pandas-ta로 기술적 지표를 계산합니다.
- RSI(14), MACD(12/26/9), SMA(20/60/120), 볼린저밴드(20,2)
- 1M/3M 수익률, 52주 고저 위치, 거래량 비율
"""

import json
import os
import sys
from datetime import datetime, timedelta

import FinanceDataReader as fdr
import pandas as pd
import pandas_ta as ta


def _safe_float(val) -> float | None:
    try:
        v = float(val)
        return None if (v != v) else v  # NaN check
    except (TypeError, ValueError):
        return None


def _detect_macd_cross(df: pd.DataFrame, macd_col: str, signal_col: str, lookback: int = 5) -> str | None:
    """최근 N일 내 MACD 골든크로스/데드크로스를 감지합니다."""
    if len(df) < lookback + 1:
        return None

    window = df[[macd_col, signal_col]].tail(lookback + 1).dropna()
    if len(window) < 2:
        return None

    for i in range(1, len(window)):
        curr_m = window[macd_col].iloc[i]
        curr_s = window[signal_col].iloc[i]
        prev_m = window[macd_col].iloc[i - 1]
        prev_s = window[signal_col].iloc[i - 1]

        if curr_m > curr_s and prev_m <= prev_s:
            return "golden"
        if curr_m < curr_s and prev_m >= prev_s:
            return "dead"

    return None


def fetch_stock_technicals(ticker: str, name: str) -> dict | None:
    """
    단일 종목의 OHLCV + 기술적 지표를 계산합니다.
    120일선·52주 고저를 위해 약 400일치 데이터를 수집합니다.
    """
    end_date = datetime.today()
    start_date = end_date - timedelta(days=420)

    try:
        df = fdr.DataReader(ticker, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    except Exception as e:
        print(f"  [경고] {name}({ticker}) OHLCV 수집 실패: {e}", file=sys.stderr)
        return None

    if df is None or df.empty or len(df) < 30:
        print(f"  [경고] {name}({ticker}): 데이터 부족 ({len(df) if df is not None else 0}행)", file=sys.stderr)
        return None

    # 컬럼명 통일 (대소문자)
    df.columns = [c.capitalize() for c in df.columns]
    if "Close" not in df.columns:
        print(f"  [경고] {name}({ticker}): Close 컬럼 없음", file=sys.stderr)
        return None

    # --- 기술적 지표 계산 ---
    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.sma(length=20, append=True)
    df.ta.sma(length=60, append=True)
    df.ta.sma(length=120, append=True)
    df.ta.bbands(length=20, std=2.0, append=True)

    latest = df.iloc[-1]
    current_price = float(latest["Close"])

    # --- 수익률 ---
    price_1m = float(df.iloc[-22]["Close"]) if len(df) >= 22 else None
    price_3m = float(df.iloc[-66]["Close"]) if len(df) >= 66 else None
    change_1m = round((current_price - price_1m) / price_1m * 100, 2) if price_1m else None
    change_3m = round((current_price - price_3m) / price_3m * 100, 2) if price_3m else None

    # --- 52주 고저 ---
    df_52w = df.tail(252)
    high_52w = float(df_52w["High"].max())
    low_52w = float(df_52w["Low"].min())
    pos_52w = round((current_price - low_52w) / (high_52w - low_52w) * 100, 1) if (high_52w - low_52w) > 0 else 50.0

    # --- RSI ---
    rsi_col = next((c for c in df.columns if c.startswith("RSI_")), None)
    rsi = _safe_float(latest[rsi_col]) if rsi_col else None

    # --- MACD ---
    macd_col = next((c for c in df.columns if c.startswith("MACD_") and "h" not in c and "s" not in c.lower()[5:]), None)
    signal_col = next((c for c in df.columns if c.startswith("MACDs_")), None)
    hist_col = next((c for c in df.columns if c.startswith("MACDh_")), None)

    macd_val = _safe_float(latest[macd_col]) if macd_col else None
    signal_val = _safe_float(latest[signal_col]) if signal_col else None
    macd_hist = _safe_float(latest[hist_col]) if hist_col else None
    macd_cross = _detect_macd_cross(df, macd_col, signal_col) if (macd_col and signal_col) else None

    # --- 이동평균 ---
    sma20 = _safe_float(latest.get("SMA_20"))
    sma60 = _safe_float(latest.get("SMA_60"))
    sma120 = _safe_float(latest.get("SMA_120"))

    # --- 볼린저밴드 ---
    bb_upper_col = next((c for c in df.columns if c.startswith("BBU_")), None)
    bb_mid_col = next((c for c in df.columns if c.startswith("BBM_")), None)
    bb_lower_col = next((c for c in df.columns if c.startswith("BBL_")), None)

    bb_upper = _safe_float(latest[bb_upper_col]) if bb_upper_col else None
    bb_mid = _safe_float(latest[bb_mid_col]) if bb_mid_col else None
    bb_lower = _safe_float(latest[bb_lower_col]) if bb_lower_col else None
    bb_position = None
    if bb_upper and bb_lower and (bb_upper - bb_lower) > 0:
        bb_position = round((current_price - bb_lower) / (bb_upper - bb_lower) * 100, 1)

    # --- 거래량 비율 ---
    vol_current = int(latest["Volume"]) if "Volume" in df.columns else 0
    vol_20avg = int(df.tail(20)["Volume"].mean()) if "Volume" in df.columns else 0
    vol_ratio = round(vol_current / vol_20avg, 2) if vol_20avg > 0 else 1.0

    # --- 최근 5일 가격 (표시용) ---
    df_recent = df.tail(5)
    recent_prices = [
        {"date": d.strftime("%m/%d"), "close": int(p), "volume": int(v)}
        for d, p, v in zip(df_recent.index, df_recent["Close"], df_recent.get("Volume", [0] * 5))
    ]

    return {
        "ticker": ticker,
        "name": name,
        "current_price": int(current_price),
        "change_1m": change_1m,
        "change_3m": change_3m,
        "high_52w": int(high_52w),
        "low_52w": int(low_52w),
        "position_52w": pos_52w,
        "rsi": round(rsi, 1) if rsi is not None else None,
        "macd": round(macd_val, 2) if macd_val is not None else None,
        "macd_signal": round(signal_val, 2) if signal_val is not None else None,
        "macd_hist": round(macd_hist, 2) if macd_hist is not None else None,
        "macd_cross": macd_cross,
        "sma20": int(sma20) if sma20 else None,
        "sma60": int(sma60) if sma60 else None,
        "sma120": int(sma120) if sma120 else None,
        "bb_upper": int(bb_upper) if bb_upper else None,
        "bb_mid": int(bb_mid) if bb_mid else None,
        "bb_lower": int(bb_lower) if bb_lower else None,
        "bb_position": bb_position,
        "volume": vol_current,
        "volume_ratio": vol_ratio,
        "recent_prices": recent_prices,
    }


def run(config_path: str = "config.json", output_path: str = ".tmp/r02_stock_data.json") -> None:
    import fetch_companies

    companies = fetch_companies.get_companies_with_fallback(config_path)
    results = []
    success, fail = 0, 0

    for company in companies:
        ticker = company["ticker"]
        name = company["name"]
        print(f"  기술 데이터 수집 중: {name}({ticker})")
        data = fetch_stock_technicals(ticker, name)
        if data:
            results.append(data)
            success += 1
        else:
            fail += 1

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"[fetch_stock_data] 완료: 성공 {success}개, 실패 {fail}개 → {output_path}")


if __name__ == "__main__":
    run()

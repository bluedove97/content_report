"""
주간 주가 데이터 수집 Tool
FinanceDataReader를 사용하여 각 종목의 최근 5거래일 데이터를 수집합니다.
"""

import json
import os
import sys
from datetime import datetime, timedelta

import FinanceDataReader as fdr

import fetch_companies


def load_config(config_path: str = "config.json") -> dict:
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def fetch_weekly_data(ticker: str, name: str, weeks: int = 1) -> dict | None:
    end_date = datetime.today()
    start_date = end_date - timedelta(weeks=weeks, days=3)  # 주말 고려해 여유분 포함

    try:
        df = fdr.DataReader(ticker, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    except Exception as e:
        print(f"  [경고] {name}({ticker}) 데이터 수집 실패: {e}", file=sys.stderr)
        return None

    if df is None or df.empty:
        print(f"  [경고] {name}({ticker}): 데이터 없음", file=sys.stderr)
        return None

    # 6일치 확보 후 표시는 최근 5거래일 — 가장 오래된 날의 등락 계산을 위해 1일 여유
    df = df.tail(6)

    close_prices = df["Close"].tolist()
    last_close = close_prices[-1]
    first_close = close_prices[0]
    change_pct = round((last_close - first_close) / first_close * 100, 2) if first_close else 0

    # 표시용 5일치 (마지막 5행)
    df_display = df.tail(5)
    display_closes = [int(p) for p in df_display["Close"].tolist()]
    display_volumes = [int(v) for v in df_display["Volume"].tolist()]

    return {
        "ticker": ticker,
        "name": name,
        "dates": [d.strftime("%m/%d") for d in df_display.index],
        "close": display_closes,
        "close_prev": int(close_prices[0]),  # 6번째 날 종가 — 등락 계산용
        "current_price": int(last_close),
        "change_pct": change_pct,
        "week_high": int(df_display["High"].max()),
        "week_low": int(df_display["Low"].min()),
        "volume": int(df_display["Volume"].iloc[-1]),
        "volumes": display_volumes,
    }


def run(config_path: str = "config.json", output_path: str = ".tmp/stock_data.json") -> None:
    config = load_config(config_path)
    companies = fetch_companies.get_companies_with_fallback(config_path)
    weeks = config["report"].get("weeks_of_data", 1)

    results = []
    success, fail = 0, 0

    for company in companies:
        ticker = company["ticker"]
        name = company["name"]
        print(f"  수집 중: {name}({ticker})")
        data = fetch_weekly_data(ticker, name, weeks)
        if data:
            results.append(data)
            success += 1
        else:
            fail += 1

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"[fetch_stock] 완료: 성공 {success}개, 실패 {fail}개 → {output_path}")


if __name__ == "__main__":
    run()

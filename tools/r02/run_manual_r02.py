"""
r02 종목 분석 리포트 수동 실행
사용법: python run_manual_r02.py --tickers "005380,035420" --emails "a@b.com,c@d.com"
"""

import argparse
import os
import sys
import traceback
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "tools" / "r02"))

import fetch_companies
import fetch_fundamentals
import fetch_stock_data
import generate_report
import send_email


def resolve_companies(tickers_str: str) -> list[dict]:
    tickers = [t.strip() for t in tickers_str.split(",") if t.strip()]
    companies = []
    try:
        from pykrx import stock
        for ticker in tickers:
            name = stock.get_market_ticker_name(ticker) or ticker
            companies.append({"ticker": ticker, "name": name})
    except Exception:
        companies = [{"ticker": t, "name": t} for t in tickers]
    return companies


def main() -> None:
    parser = argparse.ArgumentParser(description="r02 종목 분석 리포트 수동 실행")
    parser.add_argument("--tickers", required=True, help="종목코드 (쉼표 구분, 예: 005380,035420)")
    parser.add_argument("--emails", required=True, help="수신 이메일 (쉼표 구분, 예: a@b.com,c@d.com)")
    args = parser.parse_args()

    load_dotenv()

    companies = resolve_companies(args.tickers)
    print(f"[manual_r02] 대상 종목: {[c['name'] for c in companies]}")
    print(f"[manual_r02] 수신 이메일: {args.emails}")

    # fetch_companies 모듈의 get_companies_with_fallback을 지정 종목으로 교체
    fetch_companies.get_companies_with_fallback = lambda *_: companies

    failures = []

    try:
        fetch_stock_data.run()
    except Exception:
        print(f"[manual_r02] fetch_stock_data 실패:\n{traceback.format_exc()}", file=sys.stderr)
        failures.append("fetch_stock_data")

    try:
        fetch_fundamentals.run()
    except Exception:
        print(f"[manual_r02] fetch_fundamentals 실패:\n{traceback.format_exc()}", file=sys.stderr)
        failures.append("fetch_fundamentals")

    if "fetch_stock_data" in failures and "fetch_fundamentals" in failures:
        print("[manual_r02] 모든 데이터 수집 실패. 중단합니다.", file=sys.stderr)
        sys.exit(1)

    try:
        generate_report.run()
    except Exception:
        print(f"[manual_r02] generate_report 실패:\n{traceback.format_exc()}", file=sys.stderr)
        sys.exit(1)

    try:
        send_email.run(recipient=args.emails)
    except Exception:
        print(f"[manual_r02] send_email 실패:\n{traceback.format_exc()}", file=sys.stderr)
        sys.exit(1)

    if failures:
        print(f"[manual_r02] 완료 (일부 실패: {failures})")
    else:
        print("[manual_r02] 완료 (전체 성공)")


if __name__ == "__main__":
    main()

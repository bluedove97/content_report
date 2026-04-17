"""
재무 지표 수집 Tool — 네이버금융(시장 데이터) + DART(3년 재무제표)
- 네이버금융 API: 종목별 PER, PBR, EPS, BPS, 배당수익률, 시가총액
- DART: 최근 3개년 연간 재무제표 → ROE, 부채비율, 매출/영업이익/순이익 추세
"""

import json
import os
import re
import sys
from datetime import datetime

import OpenDartReader as odr
import pandas as pd
import requests


# ─── 네이버 금융 헬퍼 ──────────────────────────────────────────────────────────

_NAVER_HEADERS = {"User-Agent": "Mozilla/5.0"}

_MARKET_AVG_CACHE: dict = {}
_NAVER_RAW_CACHE: dict = {}


def _parse_num(s: str) -> float | None:
    """숫자 문자열에서 숫자만 추출 (배, 원, % 제거)"""
    if not s:
        return None
    s = re.sub(r"[,배원%조억\s]", "", s).strip()
    try:
        return float(s)
    except ValueError:
        return None


def _parse_market_cap(value_str: str) -> int | None:
    """'1,189조 8,472억' → 원 단위 정수 변환"""
    if not value_str:
        return None
    result = 0
    jo = re.search(r"([\d,]+)조", value_str)
    eok = re.search(r"([\d,]+)억", value_str)
    if jo:
        result += int(jo.group(1).replace(",", "")) * 1_000_000_000_000
    if eok:
        result += int(eok.group(1).replace(",", "")) * 100_000_000
    return result if result > 0 else None


def get_ticker_market(ticker: str) -> str:
    """네이버 API로 종목의 시장 구분(KOSPI/KOSDAQ) 반환"""
    try:
        r = requests.get(
            f"https://m.stock.naver.com/api/stock/{ticker}/basic",
            headers=_NAVER_HEADERS,
            timeout=10,
        )
        if r.status_code == 200:
            exchange = r.json().get("stockExchangeType", {}).get("nameEng", "")
            if "KOSDAQ" in exchange.upper():
                return "KOSDAQ"
    except Exception:
        pass
    return "KOSPI"


def _fetch_naver_raw(ticker: str) -> dict:
    """네이버 integration API 원본 JSON 반환 (캐시 사용)"""
    if ticker in _NAVER_RAW_CACHE:
        return _NAVER_RAW_CACHE[ticker]
    try:
        r = requests.get(
            f"https://m.stock.naver.com/api/stock/{ticker}/integration",
            headers=_NAVER_HEADERS,
            timeout=10,
        )
        data = r.json() if r.status_code == 200 else {}
    except Exception as e:
        print(f"    [경고] 네이버 API 수집 실패 ({ticker}): {e}", file=sys.stderr)
        data = {}
    _NAVER_RAW_CACHE[ticker] = data
    return data


def _get_industry_name(ticker: str) -> str | None:
    """네이버 금융 PC 페이지에서 업종명 파싱"""
    try:
        r = requests.get(
            f"https://finance.naver.com/item/main.nhn?code={ticker}",
            headers=_NAVER_HEADERS,
            timeout=8,
        )
        if r.status_code == 200:
            match = re.search(r"업종.*?<a[^>]+upjong[^>]+>([^<]+)</a>", r.text)
            if match:
                return match.group(1).strip()
    except Exception:
        pass
    return None


def fetch_sector_info(ticker: str) -> dict:
    """업종명 및 동종 업종 평균 PER/PBR 계산 (industryCompareInfo peer 기준)"""
    result = {"sector_name": None, "sector_per": None, "sector_pbr": None}

    result["sector_name"] = _get_industry_name(ticker)

    raw = _fetch_naver_raw(ticker)
    peer_tickers = [
        s.get("itemCode")
        for s in raw.get("industryCompareInfo", [])
        if s.get("itemCode")
    ]

    pers, pbrs = [], []
    for pt in peer_tickers:
        pd = _fetch_naver_integration(pt)
        if pd.get("per"):
            pers.append(pd["per"])
        if pd.get("pbr"):
            pbrs.append(pd["pbr"])

    if pers:
        pers_sorted = sorted(pers)
        result["sector_per"] = round(pers_sorted[len(pers_sorted) // 2], 1)
    if pbrs:
        pbrs_sorted = sorted(pbrs)
        result["sector_pbr"] = round(pbrs_sorted[len(pbrs_sorted) // 2], 2)

    return result


def fetch_market_averages() -> dict:
    """
    시장 평균 PER/PBR — 네이버 대표 종목 샘플로 추정
    KOSPI 대형주 10개, KOSDAQ 대형주 10개의 중앙값 사용
    """
    kospi_samples = ["005930", "000660", "035420", "005380", "051910",
                     "006400", "028260", "003550", "105560", "068270"]
    kosdaq_samples = ["247540", "086520", "091990", "196170", "035760",
                      "263750", "251270", "357780", "326030", "112040"]

    result = {"KOSPI": {"per": None, "pbr": None}, "KOSDAQ": {"per": None, "pbr": None}}

    for market_name, tickers in [("KOSPI", kospi_samples), ("KOSDAQ", kosdaq_samples)]:
        pers, pbrs = [], []
        for t in tickers:
            try:
                data = _fetch_naver_integration(t)
                if data.get("per"):
                    pers.append(data["per"])
                if data.get("pbr"):
                    pbrs.append(data["pbr"])
            except Exception:
                continue
        if pers:
            pers_sorted = sorted(pers)
            result[market_name]["per"] = round(pers_sorted[len(pers_sorted) // 2], 1)
        if pbrs:
            pbrs_sorted = sorted(pbrs)
            result[market_name]["pbr"] = round(pbrs_sorted[len(pbrs_sorted) // 2], 2)

    return result


def _fetch_naver_integration(ticker: str) -> dict:
    """네이버 금융 integration API에서 PER/PBR/EPS/BPS/배당/시가총액 추출"""
    data = _fetch_naver_raw(ticker)
    if not data:
        return {}

    result = {}
    for item in data.get("totalInfos", []):
        code = item.get("code", "")
        val = item.get("value", "")
        if code == "per":
            result["per"] = _parse_num(val)
        elif code == "pbr":
            result["pbr"] = _parse_num(val)
        elif code == "eps":
            v = _parse_num(val)
            result["eps"] = int(v) if v is not None else None
        elif code == "bps":
            v = _parse_num(val)
            result["bps"] = int(v) if v is not None else None
        elif code == "dividendYieldRatio":
            result["div"] = _parse_num(val)
        elif code == "marketValue":
            result["market_cap"] = _parse_market_cap(val)

    return result


def fetch_naver_fundamentals(ticker: str) -> dict:
    """종목의 재무 지표를 네이버 금융에서 수집"""
    data = _fetch_naver_integration(ticker)
    result = {}
    for key in ("per", "pbr", "eps", "bps", "div", "market_cap"):
        v = data.get(key)
        if v is not None:
            if key == "per" and isinstance(v, float):
                result[key] = round(v, 1)
            elif key == "pbr" and isinstance(v, float):
                result[key] = round(v, 2)
            elif key == "div" and isinstance(v, float):
                result[key] = round(v, 2)
            else:
                result[key] = v
    return result


# ─── DART 헬퍼 ─────────────────────────────────────────────────────────────

def _extract_account(df: pd.DataFrame, *account_names: str) -> int | None:
    """재무제표 DataFrame에서 계정명 후보군 중 첫 번째 매칭된 당기 금액을 추출합니다."""
    if df is None or df.empty:
        return None

    nm_col = None
    for c in ["account_nm", "account_name"]:
        if c in df.columns:
            nm_col = c
            break
    if not nm_col:
        return None

    amt_col = None
    for c in ["thstrm_amount", "당기금액", "thstrm_amt"]:
        if c in df.columns:
            amt_col = c
            break
    if not amt_col:
        num_cols = [c for c in df.columns if df[c].dtype in ["int64", "float64", "object"] and c != nm_col]
        if not num_cols:
            return None
        amt_col = num_cols[-1]

    stripped = df[nm_col].str.strip()
    for name in account_names:
        row = df[stripped == name]
        if not row.empty:
            raw = str(row.iloc[0][amt_col]).replace(",", "").replace(" ", "")
            if not raw or raw in ["-", "nan", "None", ""]:
                continue
            try:
                return int(float(raw))
            except ValueError:
                continue
    return None


def _fmt_amount(v: int | None) -> str | None:
    """금액을 억원 단위로 포맷 (Ollama 프롬프트용)"""
    if v is None:
        return None
    억 = v / 100_000_000
    if abs(억) >= 10000:
        return f"{억/10000:.1f}조원"
    return f"{억:.0f}억원"


def fetch_dart_financials(dart: odr, ticker: str, name: str) -> dict:
    """DART에서 최근 3개년 연간 재무제표를 수집하고 주요 지표를 계산합니다."""

    try:
        corp_code = dart.find_corp_code(ticker)
    except Exception as e:
        print(f"    [경고] DART corp_code 조회 실패 ({ticker}): {e}", file=sys.stderr)
        return {}

    if not corp_code:
        print(f"    [경고] DART corp_code 없음 ({ticker} / {name})", file=sys.stderr)
        return {}

    last_year = datetime.today().year - 1
    years = [last_year, last_year - 1, last_year - 2]

    year_data: dict[int, dict] = {}

    for year in years:
        df = None
        for fs_div in ["CFS", "OFS"]:
            try:
                df = dart.finstate_all(corp_code, year, reprt_code="11011", fs_div=fs_div)
                if df is not None and not df.empty:
                    break
            except Exception:
                continue

        if df is None or df.empty:
            continue

        revenue = _extract_account(df, "매출액", "영업수익", "수익(매출액)")
        op_income = _extract_account(df, "영업이익", "영업이익(손실)")
        net_income = _extract_account(df, "당기순이익", "당기순이익(손실)")
        equity = _extract_account(df, "자본총계")
        liabilities = _extract_account(df, "부채총계")

        roe = round(net_income / equity * 100, 1) if (net_income and equity and equity != 0) else None
        debt_ratio = round(liabilities / equity * 100, 1) if (liabilities and equity and equity != 0) else None
        op_margin = round(op_income / revenue * 100, 1) if (op_income and revenue and revenue != 0) else None

        year_data[year] = {
            "revenue_raw": revenue,
            "op_income_raw": op_income,
            "net_income_raw": net_income,
            "revenue": _fmt_amount(revenue),
            "operating_income": _fmt_amount(op_income),
            "net_income": _fmt_amount(net_income),
            "roe": roe,
            "debt_ratio": debt_ratio,
            "op_margin": op_margin,
        }

    if not year_data:
        return {}

    sorted_years = sorted(year_data.keys(), reverse=True)

    rev_growth = []
    for i, yr in enumerate(sorted_years):
        if i + 1 < len(sorted_years):
            curr = year_data[yr].get("revenue_raw")
            prev = year_data[sorted_years[i + 1]].get("revenue_raw")
            if curr and prev and prev != 0:
                rev_growth.append(round((curr - prev) / abs(prev) * 100, 1))
            else:
                rev_growth.append(None)
        else:
            rev_growth.append(None)

    return {
        "years": sorted_years,
        "revenue": [year_data[y].get("revenue") for y in sorted_years],
        "operating_income": [year_data[y].get("operating_income") for y in sorted_years],
        "net_income": [year_data[y].get("net_income") for y in sorted_years],
        "roe": [year_data[y].get("roe") for y in sorted_years],
        "debt_ratio": [year_data[y].get("debt_ratio") for y in sorted_years],
        "op_margin": [year_data[y].get("op_margin") for y in sorted_years],
        "revenue_growth_yoy": rev_growth,
    }


# ─── 진입점 ────────────────────────────────────────────────────────────────

def run(config_path: str = "config.json", output_path: str = ".tmp/r02_fundamentals.json") -> None:
    import fetch_companies

    dart_api_key = os.environ.get("DART_API_KEY", "")
    dart = odr(dart_api_key) if dart_api_key else None
    if not dart:
        print("[fetch_fundamentals] DART_API_KEY 없음 — DART 재무제표 수집을 건너뜁니다.", file=sys.stderr)

    print("[fetch_fundamentals] 시장 평균 수집 중...")
    market_avgs = fetch_market_averages()
    for mkt, avg in market_avgs.items():
        print(f"  {mkt} 평균 PER: {avg['per']}, PBR: {avg['pbr']}")

    companies = fetch_companies.get_companies_with_fallback(config_path)
    results = []
    success, fail = 0, 0

    for company in companies:
        ticker = company["ticker"]
        name = company["name"]
        print(f"  재무 데이터 수집 중: {name}({ticker})")

        mkt = get_ticker_market(ticker)
        naver_data = fetch_naver_fundamentals(ticker)
        sector_info = fetch_sector_info(ticker)  # integration 캐시 재사용
        naver_data["sector_name"] = sector_info["sector_name"]
        naver_data["sector_per"] = sector_info["sector_per"]
        naver_data["sector_pbr"] = sector_info["sector_pbr"]
        if sector_info["sector_name"] or sector_info["sector_per"]:
            print(f"    업종: {sector_info['sector_name']} / 업종 평균 PER: {sector_info['sector_per']}, PBR: {sector_info['sector_pbr']}")

        dart_data = {}
        if dart:
            try:
                dart_data = fetch_dart_financials(dart, ticker, name)
                if dart_data:
                    print(f"    DART 재무제표 수집 완료: {dart_data.get('years', [])}")
                else:
                    print(f"    DART 재무제표 없음 — 네이버 데이터만 사용", file=sys.stderr)
            except Exception as e:
                print(f"    [경고] DART 수집 실패 ({name}): {e}", file=sys.stderr)

        if naver_data or dart_data:
            results.append({
                "ticker": ticker,
                "name": name,
                "market": mkt,
                **naver_data,
                "dart": dart_data if dart_data else None,
            })
            success += 1
        else:
            fail += 1

    output = {"market_averages": market_avgs, "stocks": results}
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[fetch_fundamentals] 완료: 성공 {success}개, 실패 {fail}개 → {output_path}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    run()

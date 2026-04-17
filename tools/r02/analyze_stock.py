"""
종목 분석 엔진 Tool — Claude API (claude-haiku-4-5)
재무 지표 + 기술적 지표 + DART 재무제표를 Claude API에 제공하여
증권사 애널리스트 수준의 6단계 분석 및 매수/매도 추천을 생성합니다.

응답 형식 (JSON):
  {
    "grade": "매수",          // 적극매수|매수|중립|매도|적극매도
    "summary": "한 줄 요약",
    "reasons": ["근거1", ...],
    "risks": ["리스크1", ...]
  }
"""

import json
import os
import re
import sys

VALID_GRADES = ["적극매수", "매수", "중립", "매도", "적극매도"]

GRADE_MAP = {
    "적극매수": ("Strong Buy",  "#1b5e20"),
    "매수":     ("Buy",         "#2e7d32"),
    "중립":     ("Hold",        "#e65100"),
    "매도":     ("Sell",        "#c62828"),
    "적극매도": ("Strong Sell", "#7b1fa2"),
}

SYSTEM_PROMPT = """당신은 한국 주식 전문 증권사 애널리스트입니다.
제공된 데이터를 바탕으로 종목을 심층 분석하고 반드시 JSON 형식으로만 응답하세요.
마크다운, 설명 텍스트, 코드블록(``` 등) 없이 순수 JSON만 출력하세요.
분석은 기업 개요, 재무 분석, 산업 분석, 모멘텀 분석, 리스크 요인, 종합의견 순서로 내부적으로 수행하세요."""


def _build_prompt(stock_data: dict, fundamentals: dict, market_avgs: dict) -> str:
    name = stock_data.get("name", "")
    ticker = stock_data.get("ticker", "")
    market = fundamentals.get("market", "KOSPI")
    mkt_avg = market_avgs.get(market, {})

    def _v(d, *keys, default="N/A"):
        for k in keys:
            v = d.get(k)
            if v is not None:
                return v
        return default

    def _pct(v):
        return f"{v:+.1f}%" if v is not None else "N/A"

    def _price(v):
        return f"{int(v):,}원" if v is not None else "N/A"

    def _cap(v):
        if v is None:
            return "N/A"
        t = v / 1_000_000_000_000
        if t >= 1:
            return f"{t:.1f}조원"
        return f"{v/1_000_000_000:.0f}억원"

    macd_cross = stock_data.get("macd_cross")
    macd_label = {"golden": "골든크로스(5일내)", "dead": "데드크로스(5일내)"}.get(macd_cross, "크로스 없음")

    # ── 기술적 지표 블록 ──
    tech_block = f"""[현재 가격 및 기술적 지표]
현재가: {_price(stock_data.get('current_price'))}
RSI(14일): {_v(stock_data, 'rsi')}
이동평균: 20일={_price(stock_data.get('sma20'))}, 60일={_price(stock_data.get('sma60'))}, 120일={_price(stock_data.get('sma120'))}
MACD: {macd_label} / 볼린저밴드 위치: {_v(stock_data, 'bb_position', default='N/A')}%
1개월 수익률: {_pct(stock_data.get('change_1m'))} / 3개월 수익률: {_pct(stock_data.get('change_3m'))}
52주 고가: {_price(stock_data.get('high_52w'))} / 52주 저가: {_price(stock_data.get('low_52w'))} (현재 위치: {_v(stock_data, 'position_52w', default='N/A')}%)"""

    # ── 재무 평가 지표 블록 (pykrx) ──
    mkt_per_str = f"{mkt_avg.get('per')}배" if mkt_avg.get("per") else "N/A"
    sector_name = fundamentals.get("sector_name", "")
    sector_per = fundamentals.get("sector_per")
    sector_pbr = fundamentals.get("sector_pbr")
    sector_label = f"업종({sector_name})" if sector_name else "업종"
    sector_per_str = f" / {sector_label} 평균: {sector_per}배" if sector_per is not None else ""
    sector_pbr_str = f" ({sector_label} 평균: {sector_pbr}배)" if sector_pbr is not None else ""
    fund_block = f"""[재무 평가 지표 — 현재 시장/업종 기준]
PER: {f"{fundamentals.get('per')}배" if fundamentals.get('per') else "N/A"} ({market} 평균: {mkt_per_str}{sector_per_str})
PBR: {f"{fundamentals.get('pbr')}배" if fundamentals.get('pbr') else "N/A"}{sector_pbr_str}
EPS: {_price(fundamentals.get('eps'))} / BPS: {_price(fundamentals.get('bps'))}
배당수익률: {f"{fundamentals.get('div')}%" if fundamentals.get('div') else "N/A"}"""

    # ── DART 3개년 재무 추세 블록 ──
    dart = fundamentals.get("dart")
    if dart and dart.get("years"):
        years = dart["years"]
        def _dart_row(label, values):
            vals = " / ".join(str(v) if v is not None else "N/A" for v in values)
            return f"{label}: {vals}"

        dart_block = f"""[3개년 재무 추세 — DART 공시 기준 (최신→과거: {' / '.join(str(y) for y in years)})]
{_dart_row('매출액', dart.get('revenue', []))}
{_dart_row('영업이익', dart.get('operating_income', []))}
{_dart_row('당기순이익', dart.get('net_income', []))}
{_dart_row('ROE(%)', dart.get('roe', []))}
{_dart_row('부채비율(%)', dart.get('debt_ratio', []))}
{_dart_row('영업이익률(%)', dart.get('op_margin', []))}
{_dart_row('매출 YoY성장률(%)', dart.get('revenue_growth_yoy', []))}"""
    else:
        dart_block = "[3개년 재무 추세]\n데이터 없음 (DART 공시 미확인)"

    # ── 응답 형식 ──
    format_block = """[응답 형식 — 반드시 이 JSON만 출력하세요]
{
  "grade": "매수",
  "summary": "한 줄 핵심 요약 (50자 이내)",
  "reasons": ["매수/중립/매도 근거1", "근거2", "근거3"],
  "risks": ["리스크1", "리스크2"]
}
grade는 반드시 다음 중 하나: 적극매수, 매수, 중립, 매도, 적극매도"""

    return f"""[종목 정보]
종목명: {name} ({ticker}) / 시장: {market} / 시가총액: {_cap(fundamentals.get('market_cap'))}

{tech_block}

{fund_block}

{dart_block}

{format_block}"""


def _parse_response(raw: str) -> dict:
    """Ollama 응답에서 JSON을 추출합니다."""
    # 코드블록 제거
    text = re.sub(r"```(?:json)?\s*", "", raw, flags=re.IGNORECASE).strip()
    text = text.replace("```", "").strip()

    # JSON 부분 추출 시도
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # 전체 파싱 시도
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _fallback(ticker: str, name: str, market: str, reason: str, fundamentals: dict, market_avgs: dict) -> dict:
    grade_kr = "중립"
    grade_en, color = GRADE_MAP[grade_kr]
    mkt_avg = market_avgs.get(market, {})
    return {
        "ticker": ticker,
        "name": name,
        "market": market,
        "grade_kr": grade_kr,
        "grade_en": grade_en,
        "color": color,
        "score": None,
        "max_score": None,
        "summary": reason,
        "reasons": [],
        "risks": [reason],
        "scores": {},
        "market_avg_per": mkt_avg.get("per"),
        "market_avg_pbr": mkt_avg.get("pbr"),
    }


def analyze(stock_data: dict, fundamentals: dict, market_avgs: dict) -> dict:
    """
    단일 종목을 Claude API (claude-haiku-4-5)로 분석합니다.
    API 호출 실패 또는 파싱 실패 시 중립(fallback)을 반환합니다.
    """
    import anthropic

    ticker = stock_data.get("ticker", "")
    name = stock_data.get("name", "")
    market = fundamentals.get("market", "KOSPI")
    mkt_avg = market_avgs.get(market, {})

    prompt = _build_prompt(stock_data, fundamentals, market_avgs)

    # ── Claude API 호출 ──
    raw_text = ""
    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": prompt},
            ],
        )
        raw_text = response.content[0].text.strip()
    except Exception as e:
        err = f"Claude API 호출 실패: {e}"
        print(f"  [경고] {name}({ticker}) {err}", file=sys.stderr)
        return _fallback(ticker, name, market, err, fundamentals, market_avgs)

    # ── JSON 파싱 ──
    parsed = _parse_response(raw_text)
    if not parsed:
        msg = f"JSON 파싱 실패 — 원본: {raw_text[:120]}..."
        print(f"  [경고] {name}({ticker}) {msg}", file=sys.stderr)
        return _fallback(ticker, name, market, msg, fundamentals, market_avgs)

    # ── grade 검증 ──
    grade_kr = str(parsed.get("grade", "중립")).strip()
    if grade_kr not in VALID_GRADES:
        # 부분 매칭 시도
        for g in VALID_GRADES:
            if g in grade_kr:
                grade_kr = g
                break
        else:
            grade_kr = "중립"

    grade_en, color = GRADE_MAP[grade_kr]

    return {
        "ticker": ticker,
        "name": name,
        "market": market,
        "grade_kr": grade_kr,
        "grade_en": grade_en,
        "color": color,
        "score": None,
        "max_score": None,
        "summary": str(parsed.get("summary", "")).strip()[:100],
        "reasons": [str(r) for r in parsed.get("reasons", []) if r],
        "risks": [str(r) for r in parsed.get("risks", []) if r],
        "scores": {},
        "market_avg_per": mkt_avg.get("per"),
        "market_avg_pbr": mkt_avg.get("pbr"),
    }

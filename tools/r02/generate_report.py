"""
애널리스트 스타일 HTML 리포트 생성 Tool
주가 기술 데이터 + 재무 지표 + DART 재무제표 + Ollama 분석 결과를 합쳐 이메일 리포트를 생성합니다.
"""

import json
import os
from datetime import datetime

import analyze_stock


# ─── 헬퍼 ──────────────────────────────────────────────────────────────────

def _fmt_price(v) -> str:
    return f"{int(v):,}원" if v is not None else "N/A"


def _fmt_cap(v) -> str:
    if v is None:
        return "N/A"
    t = v / 1_000_000_000_000
    if t >= 1:
        return f"{t:.1f}조"
    b = v / 1_000_000_000
    return f"{b:.0f}억"


def _pct_badge(pct, reverse=False) -> str:
    if pct is None:
        return '<span style="color:#999;">N/A</span>'
    color = "#d32f2f" if pct > 0 else ("#1565c0" if pct < 0 else "#555")
    arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "―")
    return f'<span style="color:{color};font-weight:600;">{arrow} {abs(pct):.1f}%</span>'


def _grade_badge(grade_kr: str, color: str) -> str:
    return (
        f'<span style="display:inline-block;background:{color};color:#fff;'
        f'padding:3px 10px;border-radius:12px;font-size:12px;font-weight:700;'
        f'letter-spacing:0.5px;">{grade_kr}</span>'
    )


# ─── 요약 테이블 ────────────────────────────────────────────────────────────

def _build_summary_table(rows: list[dict]) -> str:
    if not rows:
        return '<p style="color:#888;">분석 데이터가 없습니다.</p>'

    _H  = "background:#1a237e;color:#fff;font-size:11px;padding:6px 10px;text-align:center;"
    _BR = "border-right:1px solid #3949ab;"
    _BB = "border-bottom:1px solid #3949ab;"

    header = f"""
    <tr>
      <th style="{_H}{_BR}{_BB}">종합의견</th>
      <th style="{_H}{_BR}vertical-align:middle;" rowspan="4">현재금액</th>
      <th style="{_H}{_BR}{_BB}">1개월</th>
      <th style="{_H}{_BB}">PER</th>
    </tr>
    <tr>
      <th style="{_H}{_BR}{_BB}">종목</th>
      <th style="{_H}{_BR}{_BB}">3개월</th>
      <th style="{_H}{_BB}">PBR</th>
    </tr>
    <tr>
      <th style="{_H}{_BR}{_BB}">코드</th>
      <th style="{_H}{_BR}{_BB}"></th>
      <th style="{_H}{_BB}">RSI</th>
    </tr>
    <tr>
      <th style="{_H}{_BR}">마켓</th>
      <th style="{_H}{_BR}"></th>
      <th style="{_H}"></th>
    </tr>"""

    tbody = ""
    for i, row in enumerate(rows):
        sd = row["stock_data"]
        fd = row["fundamentals"]
        an = row["analysis"]
        bg = "#fafafa" if i % 2 == 0 else "#fff"

        per_str = f"{fd['per']:.1f}x" if fd.get("per") else "N/A"
        pbr_str = f"{fd['pbr']:.2f}x" if fd.get("pbr") else "N/A"
        rsi_val = sd.get("rsi")
        rsi_color = "#d32f2f" if rsi_val and rsi_val > 70 else ("#1565c0" if rsi_val and rsi_val < 30 else "#333")
        rsi_str = f'<span style="color:{rsi_color};">{rsi_val:.0f}</span>' if rsi_val else "N/A"

        _TD  = f"background:{bg};font-size:13px;padding:7px 5px;"
        _BBS = "border-bottom:1px solid #eeeeee;"
        _BTS = "border-top:2px solid #c5cae9;" if i > 0 else ""

        tbody += f"""
        <tr>
          <td style="{_TD}{_BTS}{_BBS}text-align:center;">{_grade_badge(an['grade_kr'], an['color'])}</td>
          <td style="{_TD}{_BTS}text-align:center;font-size:15px;font-weight:700;vertical-align:middle;border-right:1px solid #e0e0e0;border-left:1px solid #e0e0e0;" rowspan="4">{_fmt_price(sd.get('current_price'))}</td>
          <td style="{_TD}{_BTS}{_BBS}text-align:right;border-right:1px solid #e0e0e0;">{_pct_badge(sd.get('change_1m'))}</td>
          <td style="{_TD}{_BTS}{_BBS}text-align:right;">{per_str}</td>
        </tr>
        <tr>
          <td style="{_TD}{_BBS}text-align:center;font-weight:600;">{sd['name']}</td>
          <td style="{_TD}{_BBS}text-align:right;border-right:1px solid #e0e0e0;">{_pct_badge(sd.get('change_3m'))}</td>
          <td style="{_TD}{_BBS}text-align:right;">{pbr_str}</td>
        </tr>
        <tr>
          <td style="{_TD}{_BBS}text-align:center;color:#999;font-size:11px;">{sd['ticker']}</td>
          <td style="{_TD}{_BBS}border-right:1px solid #e0e0e0;"></td>
          <td style="{_TD}{_BBS}text-align:right;">{rsi_str}</td>
        </tr>
        <tr>
          <td style="{_TD}text-align:center;color:#888;font-size:11px;">{fd.get('market', '')}</td>
          <td style="{_TD}border-right:1px solid #e0e0e0;"></td>
          <td style="{_TD}"></td>
        </tr>"""

    return f"""
    <div style="overflow-x:auto;-webkit-overflow-scrolling:touch;">
      <table style="width:100%;border-collapse:collapse;font-family:Arial,sans-serif;border-radius:6px;overflow:hidden;border:1px solid #e0e0e0;">
        <thead>{header}</thead>
        <tbody>{tbody}</tbody>
      </table>
    </div>"""


# ─── 섹션 헬퍼 ──────────────────────────────────────────────────────────────

def _section_header(num: str, title: str) -> str:
    return (
        f'<div style="background:#f5f5f5;padding:6px 12px;margin:12px 0 6px 0;'
        f'border-left:3px solid #1a237e;font-size:12px;font-weight:700;color:#333;">'
        f'{num} {title}</div>'
    )


def _kv_table(pairs: list[tuple]) -> str:
    rows = ""
    for label, value in pairs:
        rows += (
            f'<tr><td style="padding:4px 8px 4px 0;color:#888;font-size:12px;white-space:nowrap;">{label}</td>'
            f'<td style="padding:4px 8px 4px 12px;font-size:13px;font-weight:600;color:#222;">{value}</td></tr>'
        )
    return f'<table style="border-collapse:collapse;width:100%;">{rows}</table>'


# ─── DART 재무 추세 테이블 ────────────────────────────────────────────────────

def _build_dart_section(dart: dict | None) -> str:
    if not dart or not dart.get("years"):
        return ""

    years = dart["years"]
    year_headers = "".join(
        f'<th style="padding:5px 8px;text-align:right;font-size:11px;color:#888;">{y}년</th>'
        for y in years
    )

    def _dart_row(label, values, suffix="", color_fn=None):
        cells = ""
        for v in values:
            val_str = f"{v}{suffix}" if v is not None else "N/A"
            color = ""
            if color_fn and v is not None:
                color = f'color:{color_fn(v)};'
            cells += f'<td style="padding:5px 8px;text-align:right;font-size:12px;{color}">{val_str}</td>'
        return f'<tr><td style="padding:5px 8px;font-size:12px;color:#666;">{label}</td>{cells}</tr>'

    def _growth_color(v):
        return "#2e7d32" if v > 0 else ("#c62828" if v < 0 else "#555")

    rows_html = (
        _dart_row("매출액", dart.get("revenue", []))
        + _dart_row("영업이익", dart.get("operating_income", []))
        + _dart_row("당기순이익", dart.get("net_income", []))
        + _dart_row("ROE", dart.get("roe", []), suffix="%", color_fn=_growth_color)
        + _dart_row("부채비율", dart.get("debt_ratio", []), suffix="%")
        + _dart_row("영업이익률", dart.get("op_margin", []), suffix="%", color_fn=_growth_color)
        + _dart_row("매출 YoY", dart.get("revenue_growth_yoy", []), suffix="%", color_fn=_growth_color)
    )

    return (
        _section_header("②-DART", "3개년 재무 추세 (DART 공시 기준)")
        + f"""<table style="width:100%;border-collapse:collapse;background:#fafafa;border-radius:4px;">
          <thead>
            <tr style="background:#e8eaf6;">
              <th style="padding:5px 8px;text-align:left;font-size:11px;color:#888;">항목</th>
              {year_headers}
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>"""
    )


# ─── 종목 상세 섹션 ──────────────────────────────────────────────────────────

def _build_stock_section(row: dict) -> str:
    sd = row["stock_data"]
    fd = row["fundamentals"]
    an = row["analysis"]

    name = sd["name"]
    ticker = sd["ticker"]
    market = fd.get("market", "")
    summary = an.get("summary", "")

    # ── 헤더 카드 (score bar 제거, summary 표시) ──
    header_html = f"""
    <div style="background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:16px 20px;margin-bottom:16px;">
      <table style="width:100%;border-collapse:collapse;">
        <tr>
          <td style="vertical-align:top;">
            <div style="font-size:16px;font-weight:700;color:#1a237e;">{name}</div>
            <div style="font-size:12px;color:#888;margin-top:2px;">{ticker} · {market} · {_fmt_price(sd.get('current_price'))}</div>
            {"" if not summary else f'<div style="font-size:12px;color:#555;margin-top:6px;font-style:italic;">{summary}</div>'}
          </td>
          <td style="text-align:right;vertical-align:top;">
            {_grade_badge(an['grade_kr'], an['color'])}
            <div style="font-size:11px;color:#888;margin-top:4px;">{an['grade_en']}</div>
          </td>
        </tr>
      </table>"""

    # ── ① 기업 개요 ──
    sec1 = _section_header("①", "기업 개요")
    sec1 += _kv_table([
        ("시장", market),
        ("시가총액", _fmt_cap(fd.get("market_cap"))),
        ("EPS (주당순이익)", _fmt_price(fd.get("eps"))),
        ("BPS (주당순자산)", _fmt_price(fd.get("bps"))),
        ("배당수익률", f"{fd['div']:.1f}%" if fd.get("div") else "N/A"),
    ])

    # ── ② 재무 분석 (시장/업종 기준) ──
    per = fd.get("per")
    pbr = fd.get("pbr")
    mkt_per = an.get("market_avg_per")
    mkt_pbr = an.get("market_avg_pbr")
    sector_name = fd.get("sector_name")
    sector_per = fd.get("sector_per")

    per_str = f"{per:.1f}배" if per else "N/A"
    pbr_str = f"{pbr:.2f}배" if pbr else "N/A"

    per_diff = ""
    if per and mkt_per:
        diff = (per - mkt_per) / mkt_per * 100
        sign = "+" if diff > 0 else ""
        c = "#d32f2f" if diff > 15 else ("#2e7d32" if diff < -15 else "#555")
        per_diff = f' <span style="color:{c};font-size:11px;">({sign}{diff:.0f}% vs 시장)</span>'

    sec_per_diff = ""
    if per and sector_per:
        sdiff = (per - sector_per) / sector_per * 100
        ssign = "+" if sdiff > 0 else ""
        sc = "#d32f2f" if sdiff > 15 else ("#2e7d32" if sdiff < -15 else "#777")
        sec_per_diff = f' <span style="color:{sc};font-size:11px;">({ssign}{sdiff:.0f}% vs 업종)</span>'

    pbr_diff = ""
    if pbr and mkt_pbr:
        diff = (pbr - mkt_pbr) / mkt_pbr * 100
        sign = "+" if diff > 0 else ""
        c = "#d32f2f" if diff > 15 else ("#2e7d32" if diff < -15 else "#555")
        pbr_diff = f' <span style="color:{c};font-size:11px;">({sign}{diff:.0f}% vs 시장)</span>'

    sec2 = _section_header("②", "재무 분석 (시장/업종 기준)")
    sec2_pairs = [
        ("PER", f"{per_str}{per_diff}{sec_per_diff}"),
        ("PBR", f"{pbr_str}{pbr_diff}"),
        (f"{market} 평균 PER", f"{mkt_per:.1f}배" if mkt_per else "N/A"),
        (f"{market} 평균 PBR", f"{mkt_pbr:.2f}배" if mkt_pbr else "N/A"),
    ]
    sector_pbr = fd.get("sector_pbr")
    if sector_name or sector_per:
        sector_label = f"업종 ({sector_name})" if sector_name else "업종"
        per_part = f"평균 PER {sector_per:.1f}배" if sector_per else "평균 PER N/A"
        pbr_part = f" / 평균 PBR {sector_pbr:.2f}배" if sector_pbr else ""
        sec2_pairs.append((sector_label, f"{per_part}{pbr_part}"))
    sec2 += _kv_table(sec2_pairs)

    # ── ②-DART 3개년 재무 추세 ──
    sec2_dart = _build_dart_section(fd.get("dart"))

    # ── ③ 산업 분석 ──
    pos_52w = sd.get("position_52w")
    high_52w = sd.get("high_52w")
    low_52w = sd.get("low_52w")

    pos_bar = ""
    if pos_52w is not None:
        bar_width = min(100, max(0, pos_52w))
        bar_color = "#2e7d32" if pos_52w <= 30 else ("#c62828" if pos_52w >= 90 else "#1a237e")
        pos_bar = (
            f'<div style="background:#e0e0e0;height:8px;border-radius:4px;margin:4px 0 2px 0;">'
            f'<div style="background:{bar_color};width:{bar_width}%;height:100%;border-radius:4px;"></div>'
            f'</div>'
            f'<div style="font-size:11px;color:#888;">'
            f'저가 {_fmt_price(low_52w)} ← <b>{pos_52w:.0f}%</b> → 고가 {_fmt_price(high_52w)}'
            f'</div>'
        )

    per_gap_str = "N/A"
    if per and mkt_per:
        gap = (per - mkt_per) / mkt_per * 100
        sign = "+" if gap > 0 else ""
        per_gap_str = f"{sign}{gap:.0f}%"

    sec3_pairs = []
    if sector_name:
        sec3_pairs.append(("업종", sector_name))
    sec3_pairs.append((f"{market} 평균 PER 대비", per_gap_str))
    if per and sector_per:
        sgap = (per - sector_per) / sector_per * 100
        ssign = "+" if sgap > 0 else ""
        sec3_pairs.append(("업종 평균 PER 대비", f"{ssign}{sgap:.0f}%"))
    sec3_pairs.append(("52주 가격 위치", ""))

    sec3 = _section_header("③", "산업 분석")
    sec3 += _kv_table(sec3_pairs)
    sec3 += pos_bar

    # ── ④ 모멘텀 분석 ──
    rsi = sd.get("rsi")
    sma20, sma60, sma120 = sd.get("sma20"), sd.get("sma60"), sd.get("sma120")
    current = sd.get("current_price")
    macd_cross = sd.get("macd_cross")
    macd_hist = sd.get("macd_hist")
    bb_pos = sd.get("bb_position")

    ma_label = "N/A"
    if current and sma20 and sma60 and sma120:
        if current > sma20 and sma20 > sma60 and sma60 > sma120:
            ma_label = '<span style="color:#2e7d32;font-weight:600;">정배열 (상승 추세)</span>'
        elif current < sma20 and sma20 < sma60 and sma60 < sma120:
            ma_label = '<span style="color:#c62828;font-weight:600;">역배열 (하락 추세)</span>'
        else:
            ma_label = '<span style="color:#888;">혼조 (방향 불명확)</span>'

    macd_label = "크로스 없음 (관망)"
    if macd_cross == "golden":
        macd_label = '<span style="color:#2e7d32;font-weight:600;">골든크로스 발생 ▲</span>'
    elif macd_cross == "dead":
        macd_label = '<span style="color:#c62828;font-weight:600;">데드크로스 발생 ▼</span>'
    elif macd_hist is not None:
        macd_label = (
            '<span style="color:#2e7d32;">매수 추세 유지</span>'
            if macd_hist > 0
            else '<span style="color:#c62828;">매도 추세 유지</span>'
        )

    rsi_label = "N/A"
    if rsi is not None:
        if rsi < 30:
            rsi_label = f'<span style="color:#1565c0;font-weight:600;">{rsi:.1f} — 과매도 구간</span>'
        elif rsi > 70:
            rsi_label = f'<span style="color:#d32f2f;font-weight:600;">{rsi:.1f} — 과매수 구간</span>'
        elif 30 <= rsi <= 50:
            rsi_label = f'<span style="color:#2e7d32;">{rsi:.1f} — 반등 구간</span>'
        else:
            rsi_label = f'<span style="color:#555;">{rsi:.1f} — 중립 구간</span>'

    bb_label = "N/A"
    if bb_pos is not None:
        if bb_pos >= 95:
            bb_label = f'<span style="color:#d32f2f;">{bb_pos:.0f}% (상단 돌파)</span>'
        elif bb_pos >= 70:
            bb_label = f'<span style="color:#e65100;">{bb_pos:.0f}% (밴드 상단 근접)</span>'
        elif bb_pos <= 5:
            bb_label = f'<span style="color:#1565c0;">{bb_pos:.0f}% (하단 돌파)</span>'
        elif bb_pos <= 30:
            bb_label = f'<span style="color:#2e7d32;">{bb_pos:.0f}% (밴드 하단 근접)</span>'
        else:
            bb_label = f'<span style="color:#555;">{bb_pos:.0f}% (밴드 중간)</span>'

    sec4 = _section_header("④", "모멘텀 분석")
    sec4 += _kv_table([
        ("이동평균 배열", ma_label),
        ("20일선", _fmt_price(sma20)),
        ("60일선", _fmt_price(sma60)),
        ("120일선", _fmt_price(sma120)),
        ("MACD", macd_label),
        ("RSI (14일)", rsi_label),
        ("볼린저밴드 위치", bb_label),
        ("1개월 수익률", _pct_badge(sd.get("change_1m"))),
        ("3개월 수익률", _pct_badge(sd.get("change_3m"))),
    ])

    # ── ⑤ 리스크 요인 (Ollama 생성) ──
    risks = an.get("risks", [])
    risk_html = (
        "<ul style='margin:4px 0;padding-left:16px;'>"
        + "".join(f'<li style="padding:3px 0;font-size:13px;color:#c62828;">⚠ {r}</li>' for r in risks)
        + "</ul>"
        if risks
        else '<p style="color:#888;font-size:12px;margin:4px 0;">식별된 주요 리스크 없음</p>'
    )

    sec5 = _section_header("⑤", "리스크 요인")
    sec5 += risk_html

    # ── ⑥ 종합 의견 (Ollama 생성, score bar 없음) ──
    reasons = an.get("reasons", [])
    reason_html = (
        "<ul style='margin:4px 0;padding-left:16px;color:#333;'>"
        + "".join(f'<li style="padding:3px 0;font-size:13px;">✓ {r}</li>' for r in reasons)
        + "</ul>"
        if reasons
        else ""
    )

    sec6 = _section_header("⑥", "종합 의견 (AI 분석)")
    sec6 += f"""
    <div style="background:{an['color']}10;border:1px solid {an['color']}40;border-radius:6px;padding:10px 14px;margin-bottom:8px;">
      <span style="font-size:18px;font-weight:700;color:{an['color']};">{an['grade_kr']}</span>
      <span style="font-size:12px;color:#888;margin-left:6px;">{an['grade_en']}</span>
      {"" if not summary else f'<div style="font-size:12px;color:#555;margin-top:6px;">{summary}</div>'}
    </div>
    {reason_html}
    <p style="font-size:11px;color:#aaa;margin:8px 0 0 0;">※ 본 분석은 Claude(claude-haiku-4-5) AI 생성 참고 자료입니다. 투자 판단의 근거로 사용하지 마세요.</p>"""

    return header_html + sec1 + sec2 + sec2_dart + sec3 + sec4 + sec5 + sec6 + "</div>"


# ─── 전체 리포트 조립 ───────────────────────────────────────────────────────

def build_full_report(rows: list[dict], report_date: str) -> str:
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    today = datetime.today()
    weekday = weekdays[today.weekday()]

    summary_table = _build_summary_table(rows)
    stock_sections = "".join(_build_stock_section(row) for row in rows)

    grade_counts: dict[str, int] = {}
    for row in rows:
        g = row["analysis"]["grade_kr"]
        grade_counts[g] = grade_counts.get(g, 0) + 1
    grade_order = ["적극매수", "매수", "중립", "매도", "적극매도"]
    grade_summary = " / ".join(
        f"{g}: {grade_counts[g]}개" for g in grade_order if g in grade_counts
    )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:Arial,'Malgun Gothic',sans-serif;">
  <div style="max-width:720px;margin:20px auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.1);">

    <!-- 헤더 -->
    <div style="background:linear-gradient(135deg,#0d1b2a 0%,#1a237e 100%);padding:24px 28px;">
      <h1 style="margin:0 0 4px 0;color:#fff;font-size:20px;letter-spacing:-0.5px;">한국 주식 종목 분석 리포트</h1>
      <p style="margin:0;color:#9fa8da;font-size:13px;">{report_date} ({weekday}) &nbsp;|&nbsp; {len(rows)}개 종목 분석</p>
      <p style="margin:4px 0 0 0;color:#c5cae9;font-size:12px;">{grade_summary}</p>
    </div>

    <!-- 요약 테이블 -->
    <div style="padding:20px 12px 12px 12px;">
      <h2 style="margin:0 0 12px 0;font-size:14px;color:#333;border-left:3px solid #1a237e;padding-left:10px;">종합 요약</h2>
      {summary_table}
    </div>

    <!-- 종목별 상세 분석 -->
    <div style="padding:12px 12px 24px 12px;">
      <h2 style="margin:0 0 14px 0;font-size:14px;color:#333;border-left:3px solid #1a237e;padding-left:10px;">종목별 상세 분석</h2>
      {stock_sections}
    </div>

    <!-- 푸터 -->
    <div style="background:#f5f5f5;padding:14px 24px;text-align:center;border-top:1px solid #e0e0e0;">
      <p style="margin:0;color:#aaa;font-size:11px;">AI 생성 분석 리포트입니다. 투자 판단의 근거로 사용하지 마세요.</p>
      <p style="margin:4px 0 0 0;color:#bbb;font-size:10px;">데이터: KRX(pykrx), FinanceDataReader, DART(공시) &nbsp;|&nbsp; 분석: Claude claude-haiku-4-5</p>
    </div>

  </div>
</body>
</html>"""


# ─── 진입점 ────────────────────────────────────────────────────────────────

def run(
    stock_path: str = ".tmp/r02_stock_data.json",
    fundamentals_path: str = ".tmp/r02_fundamentals.json",
    output_path: str = ".tmp/analysis_report.html",
) -> None:
    stock_list = []
    if os.path.exists(stock_path):
        with open(stock_path, encoding="utf-8") as f:
            stock_list = json.load(f)

    fund_data = {"market_averages": {}, "stocks": []}
    if os.path.exists(fundamentals_path):
        with open(fundamentals_path, encoding="utf-8") as f:
            fund_data = json.load(f)

    market_avgs = fund_data.get("market_averages", {})
    fund_map = {s["ticker"]: s for s in fund_data.get("stocks", [])}

    rows = []
    for sd in stock_list:
        ticker = sd["ticker"]
        fd = fund_map.get(ticker, {"ticker": ticker, "name": sd["name"], "market": "KOSPI"})
        an = analyze_stock.analyze(sd, fd, market_avgs)
        rows.append({"stock_data": sd, "fundamentals": fd, "analysis": an})

    # grade_kr 기준 정렬 (적극매수 → 매수 → 중립 → 매도 → 적극매도)
    grade_order = {"적극매수": 0, "매수": 1, "중립": 2, "매도": 3, "적극매도": 4}
    rows.sort(key=lambda r: grade_order.get(r["analysis"]["grade_kr"], 2))

    report_date = datetime.today().strftime("%Y년 %m월 %d일")
    html = build_full_report(rows, report_date)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[generate_report] 완료: {len(rows)}개 종목 분석 → {output_path}")


if __name__ == "__main__":
    run()

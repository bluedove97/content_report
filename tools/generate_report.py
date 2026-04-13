"""
HTML 리포트 생성 Tool
주가 데이터와 뉴스 데이터를 합쳐 Gmail 호환 HTML 이메일을 생성합니다.
"""

import json
import os
from datetime import datetime


def load_data_files(stock_path: str, news_path: str) -> tuple[list, dict]:
    stock_data = []
    if os.path.exists(stock_path):
        with open(stock_path, encoding="utf-8") as f:
            stock_data = json.load(f)

    news_data = {}
    if os.path.exists(news_path):
        with open(news_path, encoding="utf-8") as f:
            news_data = json.load(f)

    return stock_data, news_data


def build_stock_table(stock_data: list) -> str:
    if not stock_data:
        return '<p style="color:#888;font-size:14px;">주가 데이터를 가져오지 못했습니다.</p>'

    rows = ""
    for s in stock_data:
        pct = s["change_pct"]
        color = "#1565c0" if pct < 0 else ("#d32f2f" if pct > 0 else "#555")
        arrow = "▼" if pct < 0 else ("▲" if pct > 0 else "―")
        pct_str = f"{arrow} {abs(pct):.2f}%"

        td_name = f'<td rowspan="2" style="padding:10px 12px;border-bottom:2px solid #eee;font-weight:600;vertical-align:middle;width:35%;"><span style="display:block;">{s["name"]}</span><span style="display:block;color:#999;font-size:11px;margin-top:3px;">{s["ticker"]}</span></td>'
        td_price = f'<td style="padding:10px 12px 4px 12px;text-align:right;font-weight:600;font-size:15px;">{s["current_price"]:,}<span style="font-size:11px;font-weight:400;">원</span></td>'
        td_high  = f'<td style="padding:10px 12px 4px 12px;text-align:right;color:#888;font-size:13px;">↑ {s["week_high"]:,}</td>'
        td_pct   = f'<td style="padding:4px 12px 10px 12px;text-align:right;color:{color};font-weight:600;border-bottom:2px solid #eee;">{pct_str}</td>'
        td_low   = f'<td style="padding:4px 12px 10px 12px;text-align:right;color:#888;font-size:13px;border-bottom:2px solid #eee;">↓ {s["week_low"]:,}</td>'

        rows += f"""
        <tr>{td_name}{td_price}{td_high}</tr>
        <tr>{td_pct}{td_low}</tr>"""

    return f"""
    <table style="width:100%;border-collapse:collapse;font-size:14px;font-family:Arial,sans-serif;">
      <thead>
        <tr style="background:#f5f5f5;">
          <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #ddd;"><span style="display:block;">종목명</span><span style="display:block;font-weight:400;font-size:11px;color:#999;">코드</span></th>
          <th style="padding:8px 12px;text-align:right;border-bottom:2px solid #ddd;"><span style="display:block;">현재가</span><span style="display:block;font-weight:400;font-size:11px;color:#999;">주간 등락</span></th>
          <th style="padding:8px 12px;text-align:right;border-bottom:2px solid #ddd;"><span style="display:block;">주간 고가</span><span style="display:block;font-weight:400;font-size:11px;color:#999;">주간 저가</span></th>
        </tr>
      </thead>
      <tbody>{rows}
      </tbody>
    </table>"""


def build_company_section(name: str, stock: dict | None, news_list: list) -> str:
    # 주가 미니 바 차트 (텍스트 기반)
    price_bar = ""
    if stock:
        prices = stock.get("close", [])
        dates = stock.get("dates", [])
        volumes = stock.get("volumes", [])
        close_prev = stock.get("close_prev")  # 표시 범위 이전 날 종가 (등락 계산용)
        if prices and dates:
            # 전일대비: changes[i] = prices[i] - prices[i-1]
            # close_prev가 있으면 첫 번째 행도 계산 가능
            prev_for_first = close_prev if close_prev is not None else None
            changes = (
                [prices[0] - prev_for_first] if prev_for_first is not None else [None]
            ) + [prices[i] - prices[i-1] for i in range(1, len(prices))]

            td = 'style="padding:5px 8px;font-size:12px;border-bottom:1px solid #eee;"'
            td_r = 'style="padding:5px 8px;font-size:12px;text-align:right;border-bottom:1px solid #eee;"'

            rows = ""
            for d, p, c, v in zip(reversed(dates), reversed(prices), reversed(changes), reversed(volumes) if volumes else ["-"]*len(prices)):
                if c is None:
                    info_td = f'<td {td_r}>-</td>'
                else:
                    color = "#d32f2f" if c > 0 else ("#1565c0" if c < 0 else "#555")
                    arrow = "▲" if c > 0 else ("▼" if c < 0 else "―")
                    rate  = c / (p - c) * 100 if (p - c) != 0 else 0
                    vol_str = f'{v:,}' if isinstance(v, int) else v
                    info_td = (
                        f'<td {td_r}>'
                        f'<span style="color:{color};display:block;">{arrow} {abs(c):,}</span>'
                        f'<span style="color:{color};display:block;">{rate:+.2f}%</span>'
                        f'<span style="color:#555;display:block;">{vol_str}</span>'
                        f'</td>'
                    )
                rows += f'<tr><td {td}>{d}</td><td {td_r}><b>{p:,}</b></td>{info_td}</tr>'

            price_bar = f"""
            <table style="width:100%;border-collapse:collapse;background:#fafafa;border-radius:6px;margin-bottom:10px;table-layout:fixed;">
              <colgroup>
                <col style="width:30%;">
                <col style="width:30%;">
                <col style="width:40%;">
              </colgroup>
              <thead>
                <tr style="background:#f0f0f0;">
                  <th style="padding:5px 8px;font-size:11px;color:#888;font-weight:600;text-align:left;">날짜</th>
                  <th style="padding:5px 8px;font-size:11px;color:#888;font-weight:600;text-align:right;">종가</th>
                  <th style="padding:5px 8px;font-size:11px;color:#888;font-weight:600;text-align:right;">등락,거래량</th>
                </tr>
              </thead>
              <tbody>{rows}</tbody>
            </table>"""

    # 뉴스 목록
    news_html = ""
    valid_news = [a for a in news_list if "error" not in a]
    if valid_news:
        items = ""
        for article in valid_news:
            source_str = f'<span style="color:#888;font-size:11px;"> — {article["source"]}</span>' if article.get("source") else ""
            date_str = f'<span style="color:#aaa;font-size:11px;margin-left:8px;">{article.get("published","")}</span>'
            items += f"""
            <li style="padding:6px 0;border-bottom:1px solid #f0f0f0;list-style:none;">
              <a href="{article['link']}" style="color:#1a73e8;text-decoration:none;font-size:13px;">{article['title']}</a>
              {source_str}{date_str}
            </li>"""
        news_html = f'<ul style="padding:0;margin:0;">{items}</ul>'
    else:
        news_html = '<p style="color:#aaa;font-size:13px;">뉴스 없음</p>'

    return f"""
    <div style="background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:16px 20px;margin-bottom:16px;">
      <h3 style="margin:0 0 10px 0;font-size:15px;color:#222;">{name}</h3>
      {price_bar}
      {news_html}
    </div>"""


def build_full_report(stock_data: list, news_data: dict, report_date: str) -> str:
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    today = datetime.today()
    weekday = weekdays[today.weekday()]

    stock_table = build_stock_table(stock_data)

    # 종목별 섹션 (config 순서 유지)
    company_names = list(news_data.keys())
    if not company_names and stock_data:
        company_names = [s["name"] for s in stock_data]

    stock_by_name = {s["name"]: s for s in stock_data}
    sections = ""
    for name in company_names:
        stock = stock_by_name.get(name)
        news = news_data.get(name, [])
        sections += build_company_section(name, stock, news)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:Arial,sans-serif;">
  <div style="max-width:680px;margin:20px auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">

    <!-- 헤더 -->
    <div style="background:#1a237e;padding:20px 24px;">
      <h1 style="margin:0;color:#fff;font-size:18px;">한국 주식 모닝 리포트</h1>
      <p style="margin:4px 0 0 0;color:#9fa8da;font-size:13px;">{report_date} ({weekday})</p>
    </div>

    <!-- 주가 요약 표 -->
    <div style="padding:20px 24px 10px 24px;">
      <h2 style="margin:0 0 12px 0;font-size:15px;color:#333;border-left:3px solid #1a237e;padding-left:10px;">주간 주가 현황</h2>
      {stock_table}
    </div>

    <!-- 종목별 뉴스 -->
    <div style="padding:10px 24px 24px 24px;">
      <h2 style="margin:0 0 12px 0;font-size:15px;color:#333;border-left:3px solid #1a237e;padding-left:10px;">종목별 뉴스</h2>
      {sections}
    </div>

    <!-- 푸터 -->
    <div style="background:#f5f5f5;padding:12px 24px;text-align:center;">
      <p style="margin:0;color:#aaa;font-size:11px;">자동 생성된 리포트입니다. 투자 판단의 근거로 사용하지 마세요.</p>
    </div>

  </div>
</body>
</html>"""


def run(
    stock_path: str = ".tmp/stock_data.json",
    news_path: str = ".tmp/news_data.json",
    output_path: str = ".tmp/report.html",
) -> None:
    stock_data, news_data = load_data_files(stock_path, news_path)
    report_date = datetime.today().strftime("%Y년 %m월 %d일")
    html = build_full_report(stock_data, news_data, report_date)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    total_news = sum(len(v) for v in news_data.values())
    print(f"[generate_report] 완료: {len(stock_data)}개 종목, {total_news}개 기사 → {output_path}")


if __name__ == "__main__":
    run()

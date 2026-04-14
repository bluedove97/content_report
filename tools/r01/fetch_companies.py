"""
종목 목록 조회 Tool
MySQL DB의 TB_STOCK_MORNING 테이블에서 사용 중인 종목 목록을 가져옵니다.
DB 조회 실패 시 config.json의 companies 항목으로 자동 대체합니다.
"""

import json
import os
import sys

import pymysql


def get_companies() -> list[dict]:
    """
    DB에서 종목 목록을 조회해 [{"ticker": "...", "name": "..."}] 형태로 반환합니다.
    연결 실패 시 예외를 발생시켜 호출자가 처리하도록 합니다.
    """
    conn = pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", 3306)),
        db=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        charset="utf8mb4",
        connect_timeout=10,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT TICKER, NAME FROM TB_STOCK_MORNING WHERE USE_YN='Y' ORDER BY SEQ"
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    companies = [{"ticker": row[0], "name": row[1]} for row in rows]
    print(f"[fetch_companies] DB에서 {len(companies)}개 종목 조회 완료")
    return companies


def get_companies_with_fallback(config_path: str = "config.json") -> list[dict]:
    """
    DB 조회를 시도하고, 실패하면 config.json의 companies로 대체합니다.
    """
    try:
        return get_companies()
    except Exception as e:
        print(f"[fetch_companies] DB 조회 실패: {e}", file=sys.stderr)
        print(f"[fetch_companies] config.json으로 대체합니다.", file=sys.stderr)
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        companies = config.get("companies", [])
        print(f"[fetch_companies] config.json에서 {len(companies)}개 종목 로드")
        return companies


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    for c in get_companies_with_fallback():
        print(c)

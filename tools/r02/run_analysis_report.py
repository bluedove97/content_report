"""
종목 분석 리포트 오케스트레이터
매일 오전 7:30 cron에 의해 실행됩니다.
fetch_stock_data → fetch_fundamentals → generate_report → send_email 순으로 실행하고,
일부 실패해도 가능한 데이터로 리포트를 생성합니다.
"""

import logging
import os
import sys
import time
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

# 프로젝트 루트 기준으로 실행되도록
ROOT = Path(__file__).parent.parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "tools" / "r02"))

import fetch_fundamentals
import fetch_stock_data
import generate_report
import send_email


def setup_logging() -> logging.Logger:
    os.makedirs(".tmp", exist_ok=True)
    logger = logging.getLogger("analysis_report")
    logger.setLevel(logging.INFO)

    handler = RotatingFileHandler(
        ".tmp/analysis_report.log",
        maxBytes=500 * 1024,
        backupCount=7,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    logger.addHandler(handler)
    logger.addHandler(console)
    return logger


def run_tool(name: str, func, *args, logger: logging.Logger) -> bool:
    try:
        logger.info(f"--- {name} 시작")
        func(*args)
        logger.info(f"--- {name} 완료")
        return True
    except Exception:
        logger.error(f"--- {name} 실패:\n{traceback.format_exc()}")
        return False


def send_error_notification(error_summary: str, logger: logging.Logger) -> None:
    try:
        app_password = os.environ.get("GMAIL_APP_PASSWORD", "")
        sender = os.environ.get("GMAIL_SENDER", "")
        recipient_raw = os.environ.get("GMAIL_RECIPIENT", "")
        recipients = [r.strip() for r in recipient_raw.split(",") if r.strip()]
        if not (app_password and sender and recipients):
            logger.warning("Gmail 인증 정보 없음. 에러 알림 발송 불가.")
            return

        today = datetime.today().strftime("%Y-%m-%d")
        subject = f"[종목 분석] 오류 발생 - {today}"
        body = f"<pre style='font-family:monospace;'>{error_summary}</pre>"
        send_email.send_report(body, subject, sender, recipients, app_password)
        logger.info("에러 알림 이메일 발송 완료")
    except Exception:
        logger.error(f"에러 알림 발송도 실패:\n{traceback.format_exc()}")


def main() -> None:
    load_dotenv()
    logger = setup_logging()
    start_time = time.time()
    logger.info("========== 종목 분석 리포트 시작 ==========")

    if not os.path.exists("config.json"):
        logger.error("config.json 파일이 없습니다. 실행을 중단합니다.")
        sys.exit(1)

    failures = []

    stock_ok = run_tool("fetch_stock_data", fetch_stock_data.run, logger=logger)
    if not stock_ok:
        failures.append("fetch_stock_data")

    fund_ok = run_tool("fetch_fundamentals", fetch_fundamentals.run, logger=logger)
    if not fund_ok:
        failures.append("fetch_fundamentals")

    # 최소 하나라도 성공하면 리포트 생성
    if stock_ok or fund_ok:
        report_ok = run_tool("generate_report", generate_report.run, logger=logger)
        if report_ok:
            email_ok = run_tool("send_email", send_email.run, logger=logger)
            if not email_ok:
                failures.append("send_email")
        else:
            failures.append("generate_report")
    else:
        logger.error("모든 데이터 수집 실패. 리포트 생성 중단.")
        error_msg = "데이터 수집 전체 실패:\n" + "\n".join(failures)
        send_error_notification(error_msg, logger)
        sys.exit(1)

    elapsed = round(time.time() - start_time, 1)
    if failures:
        logger.warning(f"========== 완료 (일부 실패: {failures}) / {elapsed}초 ==========")
    else:
        logger.info(f"========== 완료 (전체 성공) / {elapsed}초 ==========")


if __name__ == "__main__":
    main()

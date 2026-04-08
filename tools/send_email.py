"""
Gmail 발송 Tool
Gmail SMTP (SSL, 포트 465)를 사용하여 HTML 리포트를 이메일로 발송합니다.
.env에서 GMAIL_APP_PASSWORD, GMAIL_SENDER, GMAIL_RECIPIENT를 읽습니다.
"""

import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def validate_env() -> tuple[str, str, str]:
    missing = []
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    sender = os.environ.get("GMAIL_SENDER", "")
    recipient = os.environ.get("GMAIL_RECIPIENT", "")

    if not app_password:
        missing.append("GMAIL_APP_PASSWORD")
    if not sender:
        missing.append("GMAIL_SENDER")
    if not recipient:
        missing.append("GMAIL_RECIPIENT")

    if missing:
        raise ValueError(f".env에 다음 키가 없습니다: {', '.join(missing)}")

    return app_password, sender, recipient


def send_report(html_body: str, subject: str, sender: str, recipient: str, app_password: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    plain_text = "이 이메일은 HTML 형식입니다. HTML을 지원하는 메일 클라이언트에서 열어주세요."
    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, app_password)
        smtp.sendmail(sender, recipient, msg.as_string())


def run(report_path: str = ".tmp/report.html") -> None:
    app_password, sender, recipient = validate_env()

    if not os.path.exists(report_path):
        raise FileNotFoundError(f"리포트 파일을 찾을 수 없습니다: {report_path}")

    with open(report_path, encoding="utf-8") as f:
        html_body = f.read()

    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    today = datetime.today()
    subject = f"[주식 리포트] {today.strftime('%Y년 %m월 %d일')} ({weekdays[today.weekday()]})"

    send_report(html_body, subject, sender, recipient, app_password)
    print(f"[send_email] 발송 완료: {recipient} / 제목: {subject}")


if __name__ == "__main__":
    run()

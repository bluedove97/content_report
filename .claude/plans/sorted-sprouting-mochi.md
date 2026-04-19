# Plan: 수동 실행 기능 추가 (run_manual)

## Context
기존 r01/r02는 crontab으로 자동 실행되지만, 사용자가 필요할 때 즉시 특정 종목/이메일을 지정해서 실행할 수 있는 수동 트리거가 필요함.
Linux shell script → docker exec → 새 Python 파일(run_manual_rXX.py) 경로로 실행.

---

## 변경 파일 목록

| 파일 | 작업 |
|------|------|
| `tools/r01/send_email.py` | `recipient` 파라미터 추가 (옵션, 기존 동작 유지) |
| `tools/r02/send_email.py` | `recipient` 파라미터 추가 (옵션, 기존 동작 유지) |
| `tools/r01/run_manual_r01.py` | **신규** — CLI 인자 받아 r01 파이프라인 실행 |
| `tools/r02/run_manual_r02.py` | **신규** — CLI 인자 받아 r02 파이프라인 실행 |
| `run_report.sh` | **신규** — Linux 루트에서 실행하는 shell script |

---

## 구현 상세

### 1. `tools/r01/send_email.py` 수정
- `send_email(html_content, recipient=None)` 로 시그니처 변경
- `recipient` 가 `None` 이면 기존대로 `os.environ.get('GMAIL_RECIPIENT')` 사용
- 기존 cron 호출 (`send_email(html)`) 은 변경 없이 작동

### 2. `tools/r02/send_email.py` 수정
- r01과 동일한 방식으로 `recipient` 파라미터 추가

### 3. `tools/r01/run_manual_r01.py` (신규)
```
CLI 인자: --tickers "005380,035420" --emails "a@b.com,c@d.com"
흐름:
  1. argparse로 tickers, emails 파싱
  2. pykrx로 종목명 조회 → companies 리스트 구성
     (pykrx 실패 시 ticker 그대로 name으로 사용)
  3. fetch_stock.fetch_stock_data(companies)
  4. fetch_news.fetch_news(companies)
  5. generate_report.generate_report(stock_data, news_data)
  6. send_email.send_email(html, recipient=args.emails)
  7. 오류 시 stderr 출력 후 exit(1)
```
로그는 stdout/stderr (cron 아니므로 rotating log 불필요)

### 4. `tools/r02/run_manual_r02.py` (신규)
```
CLI 인자: --tickers "005380,035420" --emails "a@b.com,c@d.com"
흐름:
  1. argparse로 tickers, emails 파싱
  2. pykrx로 종목명 조회 → companies 리스트 구성
  3. fetch_stock_data.fetch_stock_data(companies)
  4. fetch_fundamentals.fetch_fundamentals(companies)
  5. analyze_stock.analyze_stocks(stock_data, fundamentals)
  6. generate_report.generate_report(...)
  7. send_email.send_email(html, recipient=args.emails)
  8. 오류 시 stderr 출력 후 exit(1)
```

### 5. `run_report.sh` (신규, 프로젝트 루트)
```bash
#!/bin/bash
# ─────────────────────────────
# 수동 리포트 실행 스크립트
# ─────────────────────────────
MODULE="r01"                          # r01 또는 r02
TICKERS="005380,035420"               # 종목코드 (,로 여러 개)
EMAILS="bluedove@utcloud.io"          # 수신 이메일 (,로 여러 개)
# ─────────────────────────────

docker exec -i stock_report python /app/tools/${MODULE}/run_manual_${MODULE}.py \
  --tickers "${TICKERS}" \
  --emails "${EMAILS}"
```

---

## 기존 cron 영향 없음 확인
- `run_morning_report.py`, `run_analysis_report.py` 는 수정하지 않음
- `send_email()` 은 기존 인자 그대로 호출 가능 (`recipient` 기본값 `None`)
- 새 파일들은 독립적으로 동작 — crontab 변경 없음

---

## 검증 방법
```bash
# Linux 미니PC에서
chmod +x /app/run_report.sh    # 또는 프로젝트 루트 경로
bash run_report.sh

# 직접 docker exec 테스트
docker exec -i stock_report python /app/tools/r01/run_manual_r01.py \
  --tickers "005380" --emails "bluedove@utcloud.io"

docker exec -i stock_report python /app/tools/r02/run_manual_r02.py \
  --tickers "005380" --emails "bluedove@utcloud.io"
```
이메일이 수신되면 성공.

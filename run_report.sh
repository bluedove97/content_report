#!/bin/bash
# ─────────────────────────────────────────────
# 수동 리포트 실행 스크립트
# 아래 3개 변수를 원하는 값으로 바꾼 뒤 실행하세요.
# ─────────────────────────────────────────────

MODULE="r01"                       # r01(모닝 리포트) 또는 r02(종목 분석)
TICKERS="005380,035420"            # 종목코드 — 여러 개는 쉼표로 구분
EMAILS="bluedove@utcloud.io"       # 수신 이메일 — 여러 개는 쉼표로 구분

# ─────────────────────────────────────────────

docker exec -i stock_report python /app/tools/${MODULE}/run_manual_${MODULE}.py \
  --tickers "${TICKERS}" \
  --emails "${EMAILS}"

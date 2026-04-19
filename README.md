# 한국 주식 모닝 리포트

## 모듈 : r01

### 목적

DB에 등록된 한국 주식(KOSPI/KOSDAQ) 종목들에 대해 

매일 오전 7시,

주간 주가 현황과 최신 뉴스를 수집하고 HTML 이메일로 자동 발송한다.

## 모듈 : r02

### 목적

DB에 등록된 한국 주식(KOSPI/KOSDAQ) 종목들에 대해

매일 오후 16시30분, 

증권사 애널리스트 스타일의 심층 분석을 수행하고 매수/매도 추천을 포함한 HTML 이메일을 발송한다.

### 분석 엔진

| 역할 | 도구 |
|---|---|
| 가격/기술적 지표 | FinanceDataReader + pandas-ta |
| 시장 재무비율 (PER/PBR 등) | pykrx (KRX 공식) |
| 3개년 재무제표 | DART 공시 API (OpenDartReader) |
| 종목 분석 AI | Claude API — claude-haiku-4-5-20251001 |

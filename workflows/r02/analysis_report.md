# 워크플로우: 한국 주식 종목 분석 리포트 (r02)

## 목적

DB에 등록된 한국 주식(KOSPI/KOSDAQ) 종목들에 대해
증권사 애널리스트 스타일의 심층 분석을 수행하고 매수/매도 추천을 포함한 HTML 이메일을 발송한다.
**수동 실행 전용** — 필요할 때만 로컬에서 직접 실행한다.

## 분석 흐름

```
config.json / DB
    └── run_analysis_report.py (오케스트레이터)
            ├── fetch_stock_data.py   → .tmp/r02_stock_data.json
            │     OHLCV + RSI, MACD, 이동평균, 볼린저밴드, 1M/3M 수익률
            ├── fetch_fundamentals.py → .tmp/r02_fundamentals.json
            │     [pykrx] PER, PBR, EPS, BPS, 배당수익률 + 시장평균
            │     [DART]  3개년 재무제표: 매출, 영업이익, 순이익, ROE, 부채비율
            ├── generate_report.py    → .tmp/analysis_report.html
            │     6단계 분석 + Ollama(qwen3:8b) 매수/매도 판정 + HTML 생성
            └── send_email.py         → Gmail 발송
```

## 분석 엔진

| 역할 | 도구 |
|---|---|
| 가격/기술적 지표 | FinanceDataReader + pandas-ta |
| 시장 재무비율 (PER/PBR 등) | pykrx (KRX 공식) |
| 3개년 재무제표 | DART 공시 API (OpenDartReader) |
| 종목 분석 AI | Ollama qwen3:8b (로컬) |

---

## 최초 설정

### 1. .env 파일에 DART API 키 추가

```
DART_API_KEY=발급받은_40자리_키
```

DART API 키 발급: https://opendart.fss.or.kr → 인증키 신청/관리 (무료)

### 2. Ollama 설치 및 모델 준비

```bash
# Ollama 설치 후
ollama pull qwen3:8b          # 모델 다운로드 (~5GB)
ollama run qwen3:8b "안녕"    # 동작 확인
```

### 3. Python 패키지 설치

```bash
pip install opendartreader ollama
# 또는
pip install -r requirements.txt
```

---

## 수동 실행 방법

```bash
# 전체 파이프라인 (데이터 수집 → AI 분석 → 이메일 발송)
python tools/r02/run_analysis_report.py

# 단계별 실행 (디버깅용)
python tools/r02/fetch_stock_data.py     # 기술적 지표 수집
python tools/r02/fetch_fundamentals.py  # pykrx + DART 재무 수집
python tools/r02/generate_report.py     # HTML만 생성 (이메일 미발송)
```

---

## 에러 대응

| 상황 | 결과 |
|------|------|
| DART_API_KEY 없음 | pykrx 데이터만으로 계속 진행 (경고 로그) |
| 특정 종목 DART 조회 실패 | 해당 종목 pykrx만 사용, 분석 계속 |
| Ollama 연결 실패 | 해당 종목 "중립" fallback, 리포트는 계속 생성 |
| fetch_stock_data 실패 | 재무 데이터만으로 리포트 생성 |
| fetch_fundamentals 실패 | 기술적 지표만으로 리포트 생성 |
| 전체 실패 | 에러 내용 포함한 알림 이메일 발송 |

**로그 위치:** `.tmp/analysis_report.log` (최근 7개 파일 보관)

---

## 문제 발생 시 점검 순서

1. `.tmp/analysis_report.log` 에서 에러 확인
2. Ollama 실행 여부 확인: `ollama list` / `ollama run qwen3:8b "test"`
3. DART API 키 유효성: https://opendart.fss.or.kr 로그인 후 키 상태 확인
4. pykrx 오류: `pip install --upgrade pykrx`

---

## 주의사항

- **DART 데이터 시점:** 연간 사업보고서(11011) 기준 — 분기 데이터 아님. 최신 실적은 직전 연도 기준
- **Ollama 분석 시간:** 종목당 약 10~30초 소요 (qwen3:8b, 하드웨어에 따라 다름)
- **분석은 참고용:** 본 리포트는 AI가 생성한 참고 자료이며 투자 조언이 아님

# 워크플로우: 한국 주식 모닝 리포트

## 목적

매일 오전 6시, `config.json`에 있는 한국 주식(KOSPI/KOSDAQ) 종목들에 대해
주간 주가 현황과 최신 뉴스를 수집하고 HTML 이메일로 자동 발송한다.

## 데이터 흐름

```
config.json
    └── run_morning_report.py (오케스트레이터)
            ├── fetch_stock.py   → .tmp/stock_data.json
            ├── fetch_news.py    → .tmp/news_data.json
            ├── generate_report.py → .tmp/report.html
            └── send_email.py    → Gmail 발송
```

---

## 최초 1회 설정

### 1. 종목 목록 설정

`config.json`을 열어 `companies` 배열에 원하는 종목을 입력한다.

```json
{ "ticker": "005930", "name": "삼성전자" }
```

- `ticker`: 네이버 금융에서 종목명 검색 → 종목 코드 6자리
- `name`: 리포트에 표시될 이름

### 2. .env 파일 설정

`.env` 파일에 아래 4개 값을 입력한다.

```
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
GMAIL_SENDER=내계정@gmail.com
GMAIL_RECIPIENT=받을계정@gmail.com
```

**Gmail 앱 비밀번호 발급 방법:**
1. Google 계정 → 보안 → 2단계 인증 활성화
2. 보안 → 앱 비밀번호 → "메일" 앱 선택 → 생성
3. 16자리 비밀번호를 `GMAIL_APP_PASSWORD`에 입력

### 3. 미니 서버에 Docker 배포

```bash
# 서버에서 실행
git clone [이 레포]
cd content_report
cp .env.example .env   # .env 편집
docker-compose up -d
```

배포 후 확인:
```bash
docker ps                    # 컨테이너 실행 중인지 확인
docker logs morning_report   # 로그 확인
```

---

## 수동 실행 방법

테스트하거나 즉시 리포트를 받고 싶을 때:

```bash
# 방법 1: 로컬에서 직접 실행
pip install -r requirements.txt
python tools/run_morning_report.py

# 방법 2: Docker 컨테이너 안에서 실행
docker-compose run --rm morning-report python tools/run_morning_report.py
```

---

## 종목 추가 / 제거

`config.json`의 `companies` 배열만 수정한다. 코드 변경 불필요.

```json
"companies": [
  { "ticker": "005930", "name": "삼성전자" },
  { "ticker": "000660", "name": "SK하이닉스" }
]
```

KRX 6자리 종목 코드 확인: [네이버 금융](https://finance.naver.com) 검색

---

## 에러 대응

| 상황 | 결과 |
|------|------|
| 특정 종목 주가 수집 실패 | 해당 종목 제외, 나머지로 리포트 생성 |
| 주가 전체 실패 | 뉴스만 포함한 리포트 발송 |
| 뉴스 전체 실패 | 주가만 포함한 리포트 발송 |
| 전체 실패 | 에러 내용 포함한 알림 이메일 발송 |

**로그 위치:** `.tmp/morning_report.log` (최근 7개 파일 보관)

**로그 실시간 확인:**
```bash
docker logs -f morning_report
# 또는
tail -f .tmp/morning_report.log
```

---

## 문제 발생 시 점검 순서

1. `.tmp/morning_report.log` 에서 에러 메시지 확인
2. 개별 Tool을 단독으로 실행해 에러 재현:
   ```bash
   python tools/fetch_stock.py
   python tools/fetch_news.py
   ```
3. `.env` 파일 키 누락 여부 확인
4. Gmail 앱 비밀번호 유효한지 확인 (구글 계정 보안 설정)
5. 인터넷 연결 상태 확인

---

## 나중에 추가 가능한 기능

- **DART 공시 데이터**: `tools/fetch_dart.py` 추가. opendart.fss.or.kr 무료 가입 필요.
- **주요 지수 요약**: KOSPI/KOSDAQ 지수 자체도 상단에 표시
- **해외 주식**: yfinance 연동 (ticker 형식: `AAPL`, `TSLA`)
- **Google Sheets 이력 저장**: 매일 데이터를 시트에 누적 저장

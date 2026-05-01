# 계획: r02 AI Provider/Model 환경변수 추상화

## Context

현재 `analyze_stock.py`는 Anthropic Claude API와 모델명(`claude-haiku-4-5-20251001`)이 코드에 하드코딩되어 있음. AI provider와 모델을 `.env`에서 선택할 수 있게 만들어, Anthropic Claude API와 로컬 Ollama API 중 하나를 유연하게 사용할 수 있도록 변경.

---

## 변경 파일

| 파일 | 변경 종류 |
|---|---|
| `tools/r02/analyze_stock.py` | `analyze` 함수 내부 수정 |
| `.env` | 환경변수 3줄 추가 |

나머지 r02 파일 전부 변경 없음.

---

## 1. `.env` 추가 내용

파일 하단에 아래 3줄 추가:

```
# AI Provider 설정 (anthropic 또는 ollama)
AI_PROVIDER=anthropic
AI_MODEL=claude-haiku-4-5-20251001

# Ollama 사용 시 (AI_PROVIDER=ollama 일 때만 참조)
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 2. `analyze_stock.py` 변경 내용

### 변경 범위: `analyze` 함수 (lines 173-240) 전체 교체

**Before (핵심 부분):**
```python
def analyze(stock_data, fundamentals, market_avgs):
    import anthropic
    ...
    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",  # 하드코딩
            ...
        )
        raw_text = response.content[0].text.strip()
    except Exception as e:
        ...
```

**After (핵심 부분):**
```python
def analyze(stock_data, fundamentals, market_avgs):
    ...
    provider = os.environ.get("AI_PROVIDER", "anthropic").strip().lower()
    model = os.environ.get("AI_MODEL", "claude-haiku-4-5-20251001").strip()

    def _call_anthropic() -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    def _call_ollama() -> str:
        import requests
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        resp = requests.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()

    raw_text = ""
    try:
        if provider == "ollama":
            raw_text = _call_ollama()
        else:
            raw_text = _call_anthropic()
    except Exception as e:
        err = f"AI API 호출 실패 [{provider}/{model}]: {e}"
        ...
```

### 설계 결정

- **인라인 헬퍼 패턴**: `_call_anthropic`, `_call_ollama`를 `analyze` 함수 내부에 정의 → `prompt`, `model`, `SYSTEM_PROMPT`를 클로저로 자연스럽게 공유, 별도 파일 불필요
- **lazy import**: `import anthropic`은 `_call_anthropic` 내부에서만, `import requests`는 `_call_ollama` 내부에서만 → ollama 환경에서 anthropic 미설치 시 에러 없음 (반대도 동일)
- **기본값**: `AI_PROVIDER` 미설정 시 `anthropic`, `AI_MODEL` 미설정 시 `claude-haiku-4-5-20251001` → 기존 동작 그대로 유지
- **timeout=120**: 로컬 Ollama 모델 첫 응답까지 수십 초 걸릴 수 있으므로 명시

---

## 사용 예시

```env
# Anthropic 사용
AI_PROVIDER=anthropic
AI_MODEL=claude-haiku-4-5-20251001

# Ollama로 전환
AI_PROVIDER=ollama
AI_MODEL=qwen3:8b
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 검증 방법

1. `.env`에서 `AI_PROVIDER=anthropic`, `AI_MODEL=claude-haiku-4-5-20251001` 설정 후 `python tools/r02/run_manual_r02.py --tickers "005930"` 실행 → 기존과 동일하게 작동 확인
2. Ollama가 실행 중인 경우, `.env`에서 `AI_PROVIDER=ollama`, `AI_MODEL=qwen3:8b` 변경 후 동일 명령 실행 → Ollama 응답으로 분석 결과 생성 확인
3. `AI_PROVIDER` 미설정 상태에서 실행 → anthropic 기본값으로 동작 확인

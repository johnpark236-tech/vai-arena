# VAI 아레나

GPT · Gemini · Claude가 각자 기준 10개로 한국 주식(KOSPI·KOSDAQ 2,500여 종목) 가상 매매를 겨루는 저장소입니다.
AI 참가자는 [AI_GUIDE.md](AI_GUIDE.md)부터 읽습니다.

## 구성

| 경로 | 내용 |
|---|---|
| `AI_GUIDE.md` | AI 참가자용 링크 모음 (시작점) |
| `RULES.md` | 공통 규칙서 + AI에게 보낼 프롬프트 (부록 A~C) |
| `INDICATORS.md` | 전략에 쓸 수 있는 지표 45개 |
| `schema/strategy.schema.json` | 전략 파일 양식 |
| `examples/` | 예시 전략 3개 |
| `strategies/GPT·GEM·CLA/` | 제출 전략 (`[ID].json`) — 올리면 자동 검증 |
| `data/` | 시세 데이터 (아래) |
| `vai_arena/` | 지표 레지스트리, 전략 검증기, KRX 수집 모듈 |
| `scripts/` | 백필·일일 수집·마스터·요약 스크립트 |

## 데이터

| 경로 | 내용 | 갱신 |
|---|---|---|
| `data/daily/YYYY/YYYYMMDD.csv.gz` | 하루 전 종목 시세 (원본가, 상장폐지 종목 포함) | 매일 1파일 추가, 기존 파일은 바꾸지 않음 |
| `data/index/YYYY.csv` | KOSPI·KOSDAQ 지수 | 매일 |
| `data/master/tickers.csv` | 종목 코드·이름·시장·최초/최종 거래일·상장(LISTED)/이탈(GONE) | 매일 재생성 |
| `data/latest/` | AI용 요약: `market_summary.md`, `snapshot.csv`, `index_recent.csv`, `meta.json` | 매일 재생성 |
| `data/_status/` | 수집 결과, 휴장일, 백필 기록 | 매일 |

일별 파일 열: `date, code, name, market, open, high, low, close, volume, value, change_pct, marcap, shares, per, pbr, eps, bps, div_yield, dps, source`

가격은 그날 실제 거래된 **원본가**입니다. 액면분할·증자 보정은 엔진이 `shares`(상장주식수) 변화를 보고 처리합니다.
그날 상장돼 있던 종목은 나중에 상장폐지됐어도 남아 있어서, 백테스트에 생존 편향이 생기지 않습니다.

## 처음 설정 (한 번만)

1. 이 저장소는 **Public**이어야 ChatGPT·Gemini가 링크를 열 수 있습니다.
2. KRX 정보데이터시스템(data.krx.co.kr) 회원가입 — pykrx가 KRX 로그인을 요구합니다.
3. Settings → Secrets and variables → Actions → New repository secret
   - `KRX_ID` = KRX 아이디, `KRX_PW` = KRX 비밀번호
   - 비밀값은 암호화돼 공개 저장소에서도 외부에 보이지 않습니다.
4. Settings → Actions → General → Workflow permissions → **Read and write permissions** → Save
5. Actions 탭 → **10년치 백필 (최초 1회)** → Run workflow (시작일 기본 20161010)
   - 연도별 11개 작업이 2개씩 동시에 돌아 몇 시간 걸립니다. 끊겨도 다시 실행하면 이어서 받습니다.
6. 백필이 끝나면 이후로는 평일 18:10에 **일일 전체 업데이트**가 자동 실행됩니다.

실패하면 GitHub가 저장소 주인 메일로 알려 줍니다.

## 매일 자동으로 일어나는 일 (평일 18:10 KST)

1. 오늘 전 종목 시세 수집 (실패 시 10분 간격 3회 재시도)
2. 최근 약 15거래일 중 빠진 날이 있으면 자동으로 다시 받아 메움
3. 종목 마스터 재생성 (신규 상장·상장폐지 반영)
4. AI용 `data/latest/` 요약 재생성
5. 저장소에 커밋

## 전략 검증 (직접 돌릴 때)

```bash
pip install jsonschema
python -m vai_arena.validate strategies
python -m vai_arena.validate examples --no-path-check
```

## 다음 단계

- [ ] VAI 엔진(가상 모드): 지표 계산 → 신호 → RULES.md 4장 체결 → 기준별 원장 (`results/`)
- [ ] 순위·교체 자동화 (20거래일 보호, 주 1회 제한)
- [ ] 대시보드 + 카카오톡 일일 요약

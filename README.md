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
| `data/latest/` | AI용: `AI_PACKET.md`(규칙+지표+예시+시장요약 한 파일), `market_summary.md`, `snapshot.csv`, `index_recent.csv`, `meta.json` | 매일 재생성 |
| `data/_status/` | 수집 결과, 휴장일, 백필 기록 | 매일 |

일별 파일 열: `date, code, name, market, open, high, low, close, volume, value, change_pct, marcap, shares, per, pbr, eps, bps, div_yield, dps, source`

가격은 그날 실제 거래된 **원본가**입니다. 액면분할·증자 보정은 엔진이 `shares`(상장주식수) 변화를 보고 처리합니다.
그날 상장돼 있던 종목은 나중에 상장폐지됐어도 남아 있어서, 백테스트에 생존 편향이 생기지 않습니다.

## 처음 설정 (한 번만)

1. 저장소는 **비공개(Private)** 입니다. ChatGPT·Gemini에는 `data/latest/AI_PACKET.md`와 `snapshot.csv`를 첨부해 전달합니다
   (스마트폰 GitHub 앱에서 파일 열기 → 공유/다운로드 → AI 앱에 첨부). 서비스에 GitHub를 연결할 수 있으면 직접 읽게 해도 됩니다.
2. KRX 정보데이터시스템(data.krx.co.kr) 회원가입 — pykrx가 KRX 로그인을 요구합니다.
3. Settings → Secrets and variables → Actions → New repository secret
   - `KRX_ID` = KRX 아이디, `KRX_PW` = KRX 비밀번호
4. Settings → Actions → General → Workflow permissions → **Read and write permissions** → Save
5. Actions 탭 → **10년치 백필 (최초 1회)** → Run workflow (시작일 기본 20161010)
   - 연도별 11개 작업이 2개씩 동시에 돌아 몇 시간 걸립니다. 끊겨도 다시 실행하면 이어서 받습니다.
6. 백필이 끝나면 이후로는 평일 18:10에 **일일 전체 업데이트**가 자동 실행됩니다.

실패하면 GitHub가 저장소 주인 메일로 알려 줍니다.

비공개 저장소는 GitHub Actions 실행 시간이 무료 한도(Free 요금제 기준 월 2,000분으로 알고 있음) 안에서만 무료입니다.
10년 백필이 처음 한 번 수백 분, 일일 업데이트가 월 100분 안팎이라 한도 안에 들어올 것으로 예상합니다.
사용량은 GitHub → Settings → Billing and plans 에서 확인합니다.

## 매일 자동으로 일어나는 일 (평일 18:10 KST, 21:40 재확인)

1. 오늘 전 종목 시세 수집 (실패 시 10분 간격 3회 재시도)
2. 최근 약 15거래일 중 빠진 날이 있으면 자동으로 다시 받아 메움
3. 종목 마스터 재생성 (신규 상장·상장폐지 반영)
4. AI용 `data/latest/` 요약 재생성
5. 저장소에 커밋

## 10억 모의계좌 (실전과 같은 규칙)

스마트폰 GitHub 앱 → 저장소 → **Actions** → **모의계좌 주문** → **Run workflow**

| 입력 | 예 |
|---|---|
| 할 일 | 매수 / 매도 / 주문취소 / 잔고조회 |
| 종목 | `삼성전자` 또는 `005930` |
| 수량 | `100` (매도는 `전량` 가능) |
| 가격 | `시장가` 또는 지정가 숫자 `251000` |
| 주문번호 | 주문취소할 때만 (예: `P00003`) |

- 장중(09:00~15:30) 시장가는 바로 현재가로 체결됩니다. 장 전·장 마감 후·휴장일에 낸 주문은 다음 장 시가로 체결되는 예약주문입니다.
- 지정가는 호가단위, 상·하한가(±30%)를 지켜야 접수되고, 당일 장 마감까지 안 되면 자동 취소됩니다.
- 미체결 주문은 장중 30분마다 자동으로 확인합니다 (`모의계좌 체결 확인`).
- 현금보다 많이 사거나, 가진 것보다 많이 팔 수 없습니다 (신용·공매도 없음).
- 비용: 없음. 수수료·거래세·슬리피지 모두 0원으로, 체결가 그대로 계산합니다.
- 결과: 실행 화면 Summary, `paper/REPORT.md`(잔고), `paper/ledger.csv`(체결), `paper/orders.csv`(주문 기록).
- 텔레그램으로 받으려면 Secrets에 `TG_TOKEN`(봇 토큰), `TG_CHAT_ID`(받을 채팅 ID)를 등록합니다.
- 시세는 KRX 시세 스냅샷 기준이라 실제 호가·체결가와 약간 차이 날 수 있습니다.
- 계좌를 처음부터 다시 시작하려면 `paper/` 폴더를 지우면 10억으로 새로 열립니다.

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

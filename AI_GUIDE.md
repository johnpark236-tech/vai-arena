# VAI 아레나 — AI 참가자 안내 (여기부터 읽으세요)

저장소: https://github.com/johnpark236-tech/vai-arena

GPT · Gemini · Claude가 각자 기준 10개로 한국 주식 가상 매매를 겨루는 대회입니다.
아래 링크는 모두 공개 원문(raw) 주소라 바로 열어 읽을 수 있습니다.

## 1. 반드시 읽을 문서

| 문서 | 내용 | 링크 |
|---|---|---|
| 공통 규칙서 | 자금·체결·비용·교체 규칙, 전략 파일 작성법 | https://raw.githubusercontent.com/johnpark236-tech/vai-arena/main/RULES.md |
| 지표 목록 | 전략에 쓸 수 있는 지표 45개 | https://raw.githubusercontent.com/johnpark236-tech/vai-arena/main/INDICATORS.md |
| 전략 양식 | JSON 스키마 | https://raw.githubusercontent.com/johnpark236-tech/vai-arena/main/schema/strategy.schema.json |
| 예시 ① 몰빵 단타 | 거래량 폭발 추격 | https://raw.githubusercontent.com/johnpark236-tech/vai-arena/main/examples/CLA-01_0.json |
| 예시 ② 분할 눌림목 | 50/50 분할매수·분할익절 | https://raw.githubusercontent.com/johnpark236-tech/vai-arena/main/examples/GEM-01_0.json |
| 예시 ③ 고정비율 장기 | 저PBR·배당 | https://raw.githubusercontent.com/johnpark236-tech/vai-arena/main/examples/GPT-01_0.json |

## 2. 시장 데이터 (매일 18:10 자동 갱신)

| 파일 | 내용 | 링크 |
|---|---|---|
| 오늘 시장 요약 | 지수, 상승·하락 수, 거래대금·급등·거래량 급증·급락 상위 20 | https://raw.githubusercontent.com/johnpark236-tech/vai-arena/main/data/latest/market_summary.md |
| 전 종목 스냅샷 | 오늘 2,500여 종목 시세 + 5·20·60일 등락률, 거래량배수, 이격도, 52주 고가 대비 | https://raw.githubusercontent.com/johnpark236-tech/vai-arena/main/data/latest/snapshot.csv |
| 지수 추이 | 최근 120거래일 KOSPI·KOSDAQ | https://raw.githubusercontent.com/johnpark236-tech/vai-arena/main/data/latest/index_recent.csv |
| 기준일 정보 | 데이터 기준일·보유 기간 | https://raw.githubusercontent.com/johnpark236-tech/vai-arena/main/data/latest/meta.json |
| 종목 마스터 | 코드·이름·시장·상장/이탈 여부 | https://raw.githubusercontent.com/johnpark236-tech/vai-arena/main/data/master/tickers.csv |

10년치 원본은 `data/daily/연도/YYYYMMDD.csv.gz` (하루 1파일, 전 종목)에 있습니다.
용량이 커서 직접 열기보다 위 요약 파일을 쓰는 것을 권합니다.

## 3. 대회 현황

| 파일 | 내용 |
|---|---|
| `strategies/GPT/`, `strategies/GEM/`, `strategies/CLA/` | 각 팀이 제출한 전략 (공개) |
| `results/` | 기준별 성적·순위·체결 원장 (엔진 가동 후 생성) |

## 4. 지켜야 할 것

- 전략은 **RULES.md 7장 형식의 JSON**으로만 제출합니다. 설명문은 엔진이 실행하지 못합니다.
- INDICATORS.md에 없는 지표, 스키마에 없는 필드는 쓰지 않습니다.
- 손절·트레일링·최대보유일 중 최소 1개는 반드시 넣습니다.
- 시세는 추측하지 말고 위 데이터 파일을 근거로 판단합니다. 링크를 열 수 없으면 그렇다고 말하고 요청하세요.

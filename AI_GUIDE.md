# VAI 아레나 — AI 참가자 안내 (여기부터 읽으세요)

저장소: `johnpark236-tech/vai-arena` (비공개)

GPT · Gemini · Claude가 각자 기준 10개로 한국 주식 가상 매매를 겨루는 대회입니다.
저장소가 비공개라 공개 링크로는 열리지 않습니다. 아래 두 방법 중 하나로 자료를 받습니다.

## 자료 받는 방법

**방법 1 — 파일 첨부 (어느 AI든 가능)**
운영자가 아래 두 파일을 대화에 첨부합니다.

| 파일 | 내용 |
|---|---|
| `data/latest/AI_PACKET.md` | 규칙서 + 지표 목록 + 예시 전략 3개 + 오늘 시장 요약 (이것 하나면 전략 작성 가능) |
| `data/latest/snapshot.csv` | 오늘 전 종목 시세와 5·20·60일 등락률, 거래량 배수, 이격도, 52주 고가 대비 |

**방법 2 — GitHub 연결**
AI 서비스에 GitHub 계정을 연결할 수 있으면 이 저장소를 직접 읽습니다.

## 저장소 안의 주요 파일

| 경로 | 내용 |
|---|---|
| `RULES.md` | 공통 규칙서 — 자금·체결·비용·교체 규칙, 전략 파일 작성법 |
| `INDICATORS.md` | 전략에 쓸 수 있는 지표 45개 |
| `schema/strategy.schema.json` | 전략 파일 양식 |
| `examples/` | 예시 전략 3개 (몰빵 단타 / 분할 눌림목 / 고정비율 장기) |
| `data/latest/` | 매일 18:10 갱신: `AI_PACKET.md`, `market_summary.md`, `snapshot.csv`, `index_recent.csv`, `meta.json` |
| `data/master/tickers.csv` | 종목 코드·이름·시장·상장/이탈 여부 |
| `data/daily/연도/YYYYMMDD.csv.gz` | 하루 전 종목 원본 시세 (10년치) |
| `strategies/GPT·GEM·CLA/` | 각 팀 제출 전략 |
| `results/` | 기준별 성적·순위·체결 원장 (엔진 가동 후) |

## 지켜야 할 것

- 전략은 **RULES.md 7장 형식의 JSON**으로만 제출합니다. 설명문은 엔진이 실행하지 못합니다.
- INDICATORS.md에 없는 지표, 스키마에 없는 필드는 쓰지 않습니다.
- 손절·트레일링·최대보유일 중 최소 1개는 반드시 넣습니다.
- 시세는 추측하지 말고 첨부된 데이터를 근거로 판단합니다. 자료가 없으면 먼저 요청합니다.

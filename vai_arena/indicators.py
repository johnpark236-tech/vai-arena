"""
VAI 아레나 지표 레지스트리 (단일 기준 원본)

모든 전략 파일은 여기에 등록된 지표만 사용할 수 있다.
- 모든 지표는 '당일 장 마감까지 확정된 데이터'로 계산한다.
- 주문은 다음 거래일에 체결된다 (미래 데이터 사용 불가).
- "_N" 계열(직전 n일)은 당일을 제외한 과거 n일 기준이다.

scope:
  U = 종목 선별(universe.filters)
  E = 진입 조건(entry.conditions, entry.rank)
  X = 청산 조건(exit.signal_exit)
"""

INT = "int"
NUM = "num"
STR = "str"

# 파라미터 정의: (타입, 최소, 최대) 또는 (STR, 허용값 목록)
P_N = {"n": (INT, 1, 250)}
P_N2 = {"n": (INT, 2, 250)}
P_MARKET = {"market": (STR, ["KOSPI", "KOSDAQ"])}

ALL = {"U", "E", "X"}
EX = {"E", "X"}
X_ONLY = {"X"}

INDICATORS = {
    # ── 가격 ─────────────────────────────────────────────
    "OPEN":  {"params": {}, "scope": ALL, "unit": "원", "ko": "당일 시가"},
    "HIGH":  {"params": {}, "scope": ALL, "unit": "원", "ko": "당일 고가"},
    "LOW":   {"params": {}, "scope": ALL, "unit": "원", "ko": "당일 저가"},
    "CLOSE": {"params": {}, "scope": ALL, "unit": "원", "ko": "당일 종가"},
    "PREV_CLOSE": {"params": {}, "scope": ALL, "unit": "원", "ko": "전일 종가"},
    "CHANGE_PCT": {"params": P_N, "scope": ALL, "unit": "%",
                   "ko": "n일 전 종가 대비 오늘 종가 등락률 (n=1이면 전일 대비)"},
    "GAP_PCT": {"params": {}, "scope": ALL, "unit": "%",
                "ko": "전일 종가 대비 오늘 시가 갭 등락률"},
    "BODY_PCT": {"params": {}, "scope": ALL, "unit": "%",
                 "ko": "오늘 시가 대비 종가 등락률 (양봉이면 +)"},

    # ── 이동평균·이격 ───────────────────────────────────
    "MA":  {"params": P_N2, "scope": ALL, "unit": "원", "ko": "종가 n일 단순이동평균 (당일 포함)"},
    "EMA": {"params": P_N2, "scope": ALL, "unit": "원", "ko": "종가 n일 지수이동평균 (당일 포함)"},
    "DIST_MA_PCT": {"params": P_N2, "scope": ALL, "unit": "%",
                    "ko": "종가가 n일 이동평균보다 몇 % 위/아래인지 (이격도-100)"},

    # ── 거래량·거래대금 ─────────────────────────────────
    "VOLUME": {"params": {}, "scope": ALL, "unit": "주", "ko": "당일 거래량"},
    "VOL_MA": {"params": P_N2, "scope": ALL, "unit": "주", "ko": "직전 n일 평균 거래량 (당일 제외)"},
    "VOL_RATIO": {"params": P_N, "scope": ALL, "unit": "배",
                  "ko": "당일 거래량 ÷ 직전 n일 평균 거래량 (n=1이면 전일 대비 배수, VAI의 V1)"},
    "VALUE": {"params": {}, "scope": ALL, "unit": "원", "ko": "당일 거래대금"},
    "VALUE_MA": {"params": P_N2, "scope": ALL, "unit": "원", "ko": "직전 n일 평균 거래대금 (당일 제외)"},
    "MARCAP": {"params": {}, "scope": ALL, "unit": "원", "ko": "당일 종가 기준 시가총액"},

    # ── 모멘텀 ───────────────────────────────────────────
    "RSI": {"params": {"n": (INT, 2, 100)}, "scope": ALL, "unit": "0~100", "ko": "n일 RSI (Wilder 방식)"},
    "STOCH_K": {"params": {"n": (INT, 5, 100)}, "scope": ALL, "unit": "0~100",
                "ko": "n일 스토캐스틱 %K (최근 n일 범위에서 종가 위치)"},
    "MACD_LINE": {"params": {"fast": (INT, 2, 50), "slow": (INT, 5, 100)}, "scope": ALL, "unit": "원",
                  "ko": "MACD선 = EMA(fast) - EMA(slow)"},
    "MACD_SIGNAL": {"params": {"fast": (INT, 2, 50), "slow": (INT, 5, 100), "signal": (INT, 2, 50)},
                    "scope": ALL, "unit": "원", "ko": "MACD 시그널선 = MACD선의 EMA(signal)"},
    "MACD_HIST": {"params": {"fast": (INT, 2, 50), "slow": (INT, 5, 100), "signal": (INT, 2, 50)},
                  "scope": ALL, "unit": "원", "ko": "MACD 히스토그램 = MACD선 - 시그널선"},
    "UP_DAYS": {"params": {}, "scope": ALL, "unit": "일", "ko": "종가 기준 연속 상승 일수 (오늘 포함)"},
    "DOWN_DAYS": {"params": {}, "scope": ALL, "unit": "일", "ko": "종가 기준 연속 하락 일수 (오늘 포함)"},

    # ── 변동성 ───────────────────────────────────────────
    "ATR": {"params": {"n": (INT, 2, 100)}, "scope": ALL, "unit": "원", "ko": "n일 평균 실제 변동폭"},
    "ATR_PCT": {"params": {"n": (INT, 2, 100)}, "scope": ALL, "unit": "%", "ko": "ATR ÷ 종가 × 100"},
    "STDEV_PCT": {"params": {"n": (INT, 5, 250)}, "scope": ALL, "unit": "%",
                  "ko": "최근 n일 일간 등락률의 표준편차"},
    "BB_UPPER": {"params": {"n": (INT, 5, 100), "k": (NUM, 0.5, 4.0)}, "scope": ALL, "unit": "원",
                 "ko": "볼린저 상단 = MA(n) + k×표준편차"},
    "BB_LOWER": {"params": {"n": (INT, 5, 100), "k": (NUM, 0.5, 4.0)}, "scope": ALL, "unit": "원",
                 "ko": "볼린저 하단 = MA(n) - k×표준편차"},
    "BB_PCTB": {"params": {"n": (INT, 5, 100), "k": (NUM, 0.5, 4.0)}, "scope": ALL, "unit": "0~1",
                "ko": "볼린저 %B (0=하단, 1=상단)"},

    # ── 위치(신고가·신저가) ─────────────────────────────
    "HIGH_N": {"params": P_N2, "scope": ALL, "unit": "원", "ko": "직전 n일 최고 고가 (당일 제외)"},
    "LOW_N": {"params": P_N2, "scope": ALL, "unit": "원", "ko": "직전 n일 최저 저가 (당일 제외)"},
    "DIST_HIGH_PCT": {"params": P_N2, "scope": ALL, "unit": "%",
                      "ko": "종가가 직전 n일 최고가보다 몇 % 위/아래인지 (양수면 신고가 돌파)"},
    "DIST_LOW_PCT": {"params": P_N2, "scope": ALL, "unit": "%",
                     "ko": "종가가 직전 n일 최저가보다 몇 % 위/아래인지"},

    # ── 재무 (KRX 일별 공시값, 결측 가능) ──────────────
    "PER": {"params": {}, "scope": ALL, "unit": "배", "ko": "주가수익비율 (적자·결측이면 조건 불충족)"},
    "PBR": {"params": {}, "scope": ALL, "unit": "배", "ko": "주가순자산비율"},
    "EPS": {"params": {}, "scope": ALL, "unit": "원", "ko": "주당순이익"},
    "BPS": {"params": {}, "scope": ALL, "unit": "원", "ko": "주당순자산"},
    "DIV_YIELD": {"params": {}, "scope": ALL, "unit": "%", "ko": "배당수익률"},

    # ── 시장 지수 ────────────────────────────────────────
    "IDX_CLOSE": {"params": P_MARKET, "scope": ALL, "unit": "pt", "ko": "지수 종가"},
    "IDX_MA": {"params": {**P_MARKET, "n": (INT, 2, 250)}, "scope": ALL, "unit": "pt",
               "ko": "지수 n일 이동평균"},
    "IDX_CHANGE_PCT": {"params": {**P_MARKET, "n": (INT, 1, 250)}, "scope": ALL, "unit": "%",
                       "ko": "지수 n일 등락률"},

    # ── 보유 포지션 (청산 조건 전용) ────────────────────
    "POS_GAIN_PCT": {"params": {}, "scope": X_ONLY, "unit": "%",
                     "ko": "평균 매수가 대비 현재 종가 수익률 (비용 제외)"},
    "POS_HOLD_DAYS": {"params": {}, "scope": X_ONLY, "unit": "일", "ko": "최초 매수일부터 보유 거래일 수"},
    "POS_PEAK_DROP_PCT": {"params": {}, "scope": X_ONLY, "unit": "%",
                          "ko": "보유 중 최고 종가 대비 현재 종가 하락률 (항상 0 이하)"},
}

OPS_COMPARE = {">", ">=", "<", "<=", "=="}
OPS_CROSS = {"cross_above", "cross_below"}
OPS_RANGE = {"between"}
OPS = OPS_COMPARE | OPS_CROSS | OPS_RANGE

SCOPE_KO = {"U": "종목선별", "E": "진입", "X": "청산"}


def markdown_table() -> str:
    """INDICATORS.md 본문을 생성한다."""
    groups = [
        ("가격", ["OPEN", "HIGH", "LOW", "CLOSE", "PREV_CLOSE", "CHANGE_PCT", "GAP_PCT", "BODY_PCT"]),
        ("이동평균·이격", ["MA", "EMA", "DIST_MA_PCT"]),
        ("거래량·거래대금", ["VOLUME", "VOL_MA", "VOL_RATIO", "VALUE", "VALUE_MA", "MARCAP"]),
        ("모멘텀", ["RSI", "STOCH_K", "MACD_LINE", "MACD_SIGNAL", "MACD_HIST", "UP_DAYS", "DOWN_DAYS"]),
        ("변동성", ["ATR", "ATR_PCT", "STDEV_PCT", "BB_UPPER", "BB_LOWER", "BB_PCTB"]),
        ("신고가·신저가", ["HIGH_N", "LOW_N", "DIST_HIGH_PCT", "DIST_LOW_PCT"]),
        ("재무", ["PER", "PBR", "EPS", "BPS", "DIV_YIELD"]),
        ("시장 지수", ["IDX_CLOSE", "IDX_MA", "IDX_CHANGE_PCT"]),
        ("보유 포지션 (청산 전용)", ["POS_GAIN_PCT", "POS_HOLD_DAYS", "POS_PEAK_DROP_PCT"]),
    ]
    listed = {n for _, names in groups for n in names}
    assert listed == set(INDICATORS), "문서 그룹과 레지스트리 불일치"

    def fmt_params(p):
        if not p:
            return "-"
        out = []
        for k, spec in p.items():
            if spec[0] == STR:
                out.append(f"`{k}`: {'/'.join(spec[1])}")
            else:
                out.append(f"`{k}`: {spec[1]}~{spec[2]}")
        return ", ".join(out)

    lines = []
    for title, names in groups:
        lines.append(f"\n### {title}\n")
        lines.append("| 지표 | 파라미터 | 단위 | 사용 위치 | 설명 |")
        lines.append("|---|---|---|---|---|")
        for n in names:
            d = INDICATORS[n]
            sc = "·".join(SCOPE_KO[s] for s in ("U", "E", "X") if s in d["scope"])
            lines.append(f"| `{n}` | {fmt_params(d['params'])} | {d['unit']} | {sc} | {d['ko']} |")
    return "\n".join(lines)

"""
VAI 아레나 전략 검증기

사용법:
  python -m vai_arena.validate strategies/            # 폴더 전체
  python -m vai_arena.validate strategies/GPT/GPT-01_0.json
  python -m vai_arena.validate examples/ --no-path-check

종료 코드: 0 = 전부 통과, 1 = 하나 이상 반려
"""
import argparse
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .indicators import INDICATORS, OPS_COMPARE, OPS_CROSS, OPS_RANGE, INT, NUM, STR

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schema" / "strategy.schema.json").read_text(encoding="utf-8"))
_VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())

ID_RE = re.compile(r"^(GPT|GEM|CLA)-(\d{2})_(\d+)$")
EPS = 1e-9


class Report:
    def __init__(self, name):
        self.name = name
        self.errors = []
        self.warnings = []

    def err(self, where, msg):
        self.errors.append(f"[{where}] {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"[{where}] {msg}")

    @property
    def ok(self):
        return not self.errors


# ── 지표 참조 검사 ────────────────────────────────────────
def check_ref(ref, scope, where, rep):
    name = ref.get("ind")
    if name not in INDICATORS:
        rep.err(where, f"등록되지 않은 지표 '{name}' (INDICATORS.md 목록만 사용 가능)")
        return
    spec = INDICATORS[name]
    if scope not in spec["scope"]:
        rep.err(where, f"지표 '{name}'는 이 위치({scope})에서 사용할 수 없음")
    given = {k: v for k, v in ref.items() if k != "ind"}
    for p in given:
        if p not in spec["params"]:
            rep.err(where, f"지표 '{name}'에 없는 파라미터 '{p}'")
    for p, rule in spec["params"].items():
        if p not in given:
            rep.err(where, f"지표 '{name}'의 필수 파라미터 '{p}' 누락")
            continue
        v = given[p]
        if rule[0] == STR:
            if v not in rule[1]:
                rep.err(where, f"'{name}.{p}'는 {rule[1]} 중 하나여야 함 (입력: {v})")
        else:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                rep.err(where, f"'{name}.{p}'는 숫자여야 함")
                continue
            if rule[0] == INT and int(v) != v:
                rep.err(where, f"'{name}.{p}'는 정수여야 함 (입력: {v})")
            if not (rule[1] <= v <= rule[2]):
                rep.err(where, f"'{name}.{p}'={v} 허용 범위 {rule[1]}~{rule[2]} 벗어남")
    if name.startswith("MACD") and "fast" in given and "slow" in given:
        if given["fast"] >= given["slow"]:
            rep.err(where, f"'{name}': fast({given['fast']})는 slow({given['slow']})보다 작아야 함")


def check_condition(cond, scope, where, rep):
    check_ref(cond["left"], scope, f"{where}.left", rep)
    op, right = cond["op"], cond["right"]
    if op in OPS_RANGE:
        if not isinstance(right, list):
            rep.err(where, "'between'의 right는 [최소, 최대] 배열이어야 함")
        elif right[0] >= right[1]:
            rep.err(where, f"'between' 범위가 잘못됨 {right} (앞 값 < 뒤 값)")
        return
    if isinstance(right, list):
        rep.err(where, f"'{op}'에는 배열을 쓸 수 없음 (between 전용)")
        return
    if isinstance(right, dict):
        check_ref(right, scope, f"{where}.right", rep)
    if op == "==":
        rep.warn(where, "'=='는 실수 비교에서 거의 성립하지 않음. >=, <= 사용 권장")
    if op in OPS_CROSS and not isinstance(right, (dict, int, float)):
        rep.err(where, f"'{op}'의 right는 숫자 또는 지표여야 함")


# ── 의미 검사 ────────────────────────────────────────────
def semantic(s, rep, path=None, check_path=True):
    # 1) ID 일관성
    m = ID_RE.match(s["id"])
    team, slot, ver = m.group(1), int(m.group(2)), int(m.group(3))
    if s["team"] != team:
        rep.err("id", f"team '{s['team']}'와 ID 접두어 '{team}' 불일치")
    if s["slot"] != slot:
        rep.err("id", f"slot {s['slot']}과 ID 슬롯 {slot:02d} 불일치")
    if s["version"] != ver:
        rep.err("id", f"version {s['version']}과 ID 버전 {ver} 불일치")
    rp = s.get("replaces")
    if ver == 0 and rp:
        rep.err("replaces", "버전 0(최초 기준)은 replaces를 가질 수 없음")
    if ver > 0:
        if not rp:
            rep.err("replaces", f"버전 {ver}은 대체 대상(replaces) 필수 (예: {team}-{slot:02d}_{ver-1})")
        else:
            rm = ID_RE.match(rp)
            if rm and (rm.group(1) != team or int(rm.group(2)) != slot):
                rep.err("replaces", "같은 팀·같은 슬롯의 이전 기준만 대체 가능")
            if rm and int(rm.group(3)) >= ver:
                rep.err("replaces", "대체 대상 버전은 현재 버전보다 작아야 함")

    if check_path and path is not None:
        if path.stem != s["id"]:
            rep.err("file", f"파일명은 '{s['id']}.json' 이어야 함 (현재 {path.name})")
        if path.parent.name != team:
            rep.err("file", f"파일은 strategies/{team}/ 폴더에 있어야 함")

    # 2) 종목 선별
    u = s["universe"]
    for lo, hi in (("price_min", "price_max"), ("marcap_min", "marcap_max")):
        if u.get(lo) is not None and u.get(hi) is not None and u[lo] >= u[hi]:
            rep.err("universe", f"{lo}({u[lo]})는 {hi}({u[hi]})보다 작아야 함")
    for i, c in enumerate(u.get("filters", [])):
        check_condition(c, "U", f"universe.filters[{i}]", rep)

    # 3) 진입
    e = s["entry"]
    for i, c in enumerate(e["conditions"]):
        check_condition(c, "E", f"entry.conditions[{i}]", rep)
    check_ref(e["rank"]["by"], "E", "entry.rank.by", rep)

    # 4) 포지션
    p = s["position"]
    mp, sizing = p["max_positions"], p["sizing"]
    reserve = s["risk"]["cash_reserve_pct"]
    if sizing == "all_in":
        if mp != 1:
            rep.err("position", "all_in(몰빵)은 max_positions=1 이어야 함")
        if s["risk"]["max_weight_pct"] < 100 - reserve - EPS:
            rep.warn("position", "all_in인데 max_weight_pct가 100 미만이라 전액 투입이 제한됨")
    if sizing == "fixed_pct":
        pct = p.get("pct_per_position")
        if pct is None:
            rep.err("position", "fixed_pct는 pct_per_position 필수")
        elif pct * mp > 100 - reserve + EPS:
            rep.err("position", f"종목당 {pct}% × 최대 {mp}종목 = {pct*mp}% 가 투자 가능 비율 {100-reserve}% 초과")
    elif p.get("pct_per_position") is not None:
        rep.warn("position", f"sizing={sizing}에서는 pct_per_position이 무시됨")

    eo = p["entry_order"]
    if eo["type"] == "limit" and eo.get("offset_pct") is None:
        rep.err("position.entry_order", "limit 주문은 offset_pct 필수 (전일 종가 대비 %)")
    if eo["type"] == "open" and eo.get("offset_pct") is not None:
        rep.warn("position.entry_order", "open 주문에서는 offset_pct가 무시됨")

    sb = p["split_buy"]
    total = sum(t["pct"] for t in sb)
    if abs(total - 100) > 0.01:
        rep.err("position.split_buy", f"분할매수 비율 합계가 100이어야 함 (현재 {total})")
    if sb[0]["when"] != "entry":
        rep.err("position.split_buy", "첫 번째 분할은 when='entry' 여야 함")
    for i, t in enumerate(sb):
        if t["when"] == "entry":
            if i > 0:
                rep.err(f"position.split_buy[{i}]", "'entry'는 첫 번째에만 올 수 있음")
            continue
        v = t.get("value")
        if v is None:
            rep.err(f"position.split_buy[{i}]", f"'{t['when']}'는 value 필수")
        elif t["when"] == "drop_pct" and v >= 0:
            rep.err(f"position.split_buy[{i}]", "drop_pct value는 음수여야 함 (예: -3)")
        elif t["when"] == "gain_pct" and v <= 0:
            rep.err(f"position.split_buy[{i}]", "gain_pct value는 양수여야 함 (예: 3)")
    if len(sb) > 1 and p.get("split_expire_days") is None:
        rep.err("position", "분할매수가 2회 이상이면 split_expire_days(미체결 분할 취소 기한) 필수")

    # 5) 청산 — 최소 안전장치
    x = s["exit"]
    if x.get("stop_loss_pct") is None and x.get("max_hold_days") is None and x.get("trailing_stop_pct") is None:
        rep.err("exit", "손절(stop_loss_pct)·트레일링(trailing_stop_pct)·최대보유일(max_hold_days) 중 최소 1개 필수")
    tp = x.get("take_profit", [])
    if tp:
        gains = [t["gain_pct"] for t in tp]
        if gains != sorted(gains) or len(set(gains)) != len(gains):
            rep.err("exit.take_profit", "익절 단계는 gain_pct 오름차순, 중복 없이")
        sells = sum(t["sell_pct"] for t in tp)
        if sells > 100 + 0.01:
            rep.err("exit.take_profit", f"익절 매도 비율 합계 {sells}%가 100% 초과")
    if x.get("signal_exit"):
        for i, c in enumerate(x["signal_exit"]["conditions"]):
            check_condition(c, "X", f"exit.signal_exit.conditions[{i}]", rep)
    if not tp and not x.get("signal_exit") and x.get("trailing_stop_pct") is None:
        rep.warn("exit", "익절 규칙이 없어 손절/기간 청산으로만 매도됨")


def validate_obj(s, path=None, check_path=True):
    rep = Report(str(path) if path else s.get("id", "?"))
    errs = sorted(_VALIDATOR.iter_errors(s), key=lambda e: list(e.path))
    for e in errs:
        loc = ".".join(str(p) for p in e.path) or "(root)"
        rep.err(loc, f"양식 오류: {e.message}")
    if errs:
        return rep  # 구조가 틀리면 의미 검사 생략
    semantic(s, rep, path, check_path)
    return rep


def validate_file(path, check_path=True):
    try:
        s = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as ex:
        rep = Report(str(path))
        rep.err("json", f"JSON 문법 오류: {ex}")
        return rep, None
    return validate_obj(s, Path(path), check_path), s


def collect_files(target):
    t = Path(target)
    if t.is_file():
        return [t]
    return sorted(p for p in t.rglob("*.json") if not p.name.startswith("_"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="VAI 아레나 전략 검증기")
    ap.add_argument("targets", nargs="+")
    ap.add_argument("--no-path-check", action="store_true", help="파일명·폴더 규칙 검사 생략(예시 파일용)")
    args = ap.parse_args(argv)

    files = [f for t in args.targets for f in collect_files(t)]
    if not files:
        print("검증할 전략 파일이 없습니다.")
        return 0

    seen, failed = {}, 0
    for f in files:
        rep, s = validate_file(f, not args.no_path_check)
        if s and rep.ok:
            sid = s["id"]
            if sid in seen:
                rep.err("id", f"중복 ID — {seen[sid]} 와 같음")
            seen[sid] = str(f)
        status = "PASS" if rep.ok else "REJECT"
        print(f"{status}  {f}")
        for e in rep.errors:
            print(f"   ✗ {e}")
        for w in rep.warnings:
            print(f"   ! {w}")
        failed += 0 if rep.ok else 1

    # 팀별 활성 슬롯 수 (최신 버전 기준)
    latest = {}
    for sid in seen:
        m = ID_RE.match(sid)
        key = (m.group(1), int(m.group(2)))
        latest[key] = max(latest.get(key, -1), int(m.group(3)))
    for team in ("GPT", "GEM", "CLA"):
        n = sum(1 for k in latest if k[0] == team)
        if n:
            print(f"   {team}: 슬롯 {n}/10 사용")

    print(f"\n결과: {len(files) - failed}개 통과 / {failed}개 반려")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

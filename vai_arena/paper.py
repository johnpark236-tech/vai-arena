"""
VAI 10억 모의계좌 — 실전과 같은 규칙으로 체결되는 가상 증권계좌

저장 위치 (paper/)
  account.json   현금·보유종목·미체결 주문 (계좌 상태)
  ledger.csv     모든 체결 기록 (매수·매도, 수수료, 세금)
  orders.csv     모든 주문 기록 (접수·체결·취소·만료·거부)
  REPORT.md      잔고 보고서 (스마트폰 GitHub 앱에서 바로 보기)

실전과 같게 맞춘 것
  - 시장가: 장중이면 현재가로 즉시 체결, 장 마감 후·장 전이면 다음 장 시가로 체결(예약주문)
  - 지정가: 호가단위에 맞아야 하고 전일 종가 ±30%(상·하한가) 안이어야 접수
            매수는 현재가 ≤ 지정가일 때, 매도는 현재가 ≥ 지정가일 때 체결 (유리한 가격이면 그 가격)
            당일 장 마감까지 미체결이면 자동 취소 (당일 유효 주문)
  - 매수는 현금+수수료 범위 안에서만, 매도는 보유 수량 안에서만 (신용·공매도 없음)
  - 매도 체결분 대금은 즉시 재매수 가능 (실제는 D+2 결제지만 국내 증권사는 매도대금으로 재매수 허용)
  - 비용: 없음 (수수료·거래세·슬리피지 0원) — 체결가 그대로 계산

한계
  - 시세는 KRX 시세 스냅샷 기준이라 실제 호가·체결과 수십 초~수 분 차이가 날 수 있음
  - 미체결 지정가는 장중 약 30분마다 확인하므로 그 사이 잠깐 닿았다 떠난 가격은 놓칠 수 있음
"""
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "paper"

INITIAL_CASH = 1_000_000_000
# 비용 없음 (사용자 요청: 모든 수수료 제거). 되살리려면 아래 값만 바꾸면 됨
#   예) 수수료 0.00015, 거래세 0.0020, 시장가 슬리피지 0.0005
FEE_BUY = 0.0
FEE_SELL = 0.0
TAX_SELL = 0.0
SLIP = 0.0
PRICE_LIMIT = 0.30

LEDGER_COLS = ["time", "order_id", "side", "code", "name", "qty", "price", "amount",
               "fee", "tax", "cash_after", "realized_pnl", "note"]
ORDER_COLS = ["time", "order_id", "status", "side", "code", "name", "qty", "order_type",
              "limit_price", "fill_price", "message"]


def now_kst():
    return datetime.now(KST)


# ── 호가단위 (2023년 1월 개편 기준, KOSPI·KOSDAQ 동일) ───────
def tick_size(price: float) -> int:
    if price < 2000:
        return 1
    if price < 5000:
        return 5
    if price < 20000:
        return 10
    if price < 50000:
        return 50
    if price < 200000:
        return 100
    if price < 500000:
        return 500
    return 1000


def round_tick(price: float, up: bool) -> int:
    t = tick_size(price)
    return int(math.ceil(price / t) * t) if up else int(math.floor(price / t) * t)


# ── 장 시간 ──────────────────────────────────────────────
def market_phase(t: datetime, holidays: set) -> str:
    """'pre' 장 시작 전 / 'open' 장중 / 'closed' 장 마감 후 / 'off' 휴장일·주말"""
    d = t.strftime("%Y%m%d")
    if t.weekday() >= 5 or d in holidays:
        return "off"
    hm = t.hour * 100 + t.minute
    if hm < 900:
        return "pre"
    if hm < 1530:
        return "open"
    return "closed"


# ── 시세 ─────────────────────────────────────────────────
@dataclass
class Quote:
    code: str
    name: str
    market: str
    price: float      # 현재가 (장 마감 후면 종가)
    open: float
    high: float
    low: float
    prev_close: float
    volume: float
    session: str      # 이 시세가 속한 거래일 YYYYMMDD


class QuoteBook:
    def __init__(self, df: pd.DataFrame, session: str):
        self.session = session
        self.by_code = {}
        self.by_name = {}
        for r in df.itertuples(index=False):
            chg = getattr(r, "change_pct", None)
            prev = r.close / (1 + chg / 100) if chg is not None and not pd.isna(chg) and chg > -100 else r.close
            q = Quote(str(r.code).zfill(6), str(r.name), str(r.market), float(r.close), float(r.open),
                      float(r.high), float(r.low), round(prev), float(r.volume), session)
            self.by_code[q.code] = q
            self.by_name[q.name.replace(" ", "")] = q

    def find(self, key: str):
        k = str(key).strip().replace(" ", "")
        if k.isdigit():
            return self.by_code.get(k.zfill(6))
        if k in self.by_name:
            return self.by_name[k]
        hits = [q for n, q in self.by_name.items() if k in n]
        return hits[0] if len(hits) == 1 else None


def load_live_quotes() -> QuoteBook:
    """KRX 전 종목 현재 시세 (FinanceDataReader). 장중이면 지연 현재가, 마감 후면 종가."""
    import FinanceDataReader as fdr
    from . import krx
    s = fdr.StockListing("KRX")
    s = s[s["Market"].isin(["KOSPI", "KOSDAQ"])]
    df = pd.DataFrame({
        "code": s["Code"].astype(str).str.zfill(6), "name": s["Name"], "market": s["Market"],
        "open": s["Open"], "high": s["High"], "low": s["Low"], "close": s["Close"],
        "volume": s["Volume"], "change_pct": s.get("ChagesRatio", s.get("ChangesRatio")),
    })
    # 장중에 받은 시세는 오늘 것, 그 밖에는 지수로 확인한 직전 거래일 것
    phase = market_phase(now_kst(), krx.known_holidays())
    session = now_kst().strftime("%Y%m%d") if phase == "open" else \
        (krx.last_session_date() or now_kst().strftime("%Y%m%d"))
    return QuoteBook(df, session)


# ── 계좌 ─────────────────────────────────────────────────
class Account:
    def __init__(self, base: Path = PAPER):
        self.base = base
        self.base.mkdir(parents=True, exist_ok=True)
        p = base / "account.json"
        if p.exists():
            self.s = json.loads(p.read_text(encoding="utf-8"))
        else:
            self.s = {"initial_cash": INITIAL_CASH, "cash": INITIAL_CASH, "positions": {},
                      "pending": [], "next_id": 1, "realized_pnl": 0, "fees": 0, "taxes": 0,
                      "created_at": now_kst().isoformat(timespec="seconds"), "last_quote": {}}
        self.events = []  # 이번 실행에서 일어난 일 (알림용)

    # 저장
    def save(self):
        (self.base / "account.json").write_text(json.dumps(self.s, ensure_ascii=False, indent=2),
                                                encoding="utf-8")

    def _append(self, fname, cols, row):
        p = self.base / fname
        new = not p.exists()
        with p.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            if new:
                w.writeheader()
            w.writerow({c: row.get(c, "") for c in cols})

    def _order_log(self, o, status, fill_price="", message=""):
        self._append("orders.csv", ORDER_COLS, {
            "time": now_kst().isoformat(timespec="seconds"), "order_id": o["id"], "status": status,
            "side": o["side"], "code": o["code"], "name": o["name"], "qty": o["qty"],
            "order_type": o["type"], "limit_price": o.get("limit") or "", "fill_price": fill_price,
            "message": message})
        self.events.append(f"[{status}] {o['id']} {'매수' if o['side']=='buy' else '매도'} "
                           f"{o['name']}({o['code']}) {o['qty']:,}주"
                           + (f" @ {fill_price:,.0f}원" if fill_price != "" else "")
                           + (f" — {message}" if message else ""))

    # 조회
    def held_qty(self, code):
        return self.s["positions"].get(code, {}).get("qty", 0)

    def reserved_sell_qty(self, code, exclude=None):
        return sum(o["qty"] for o in self.s["pending"]
                   if o["side"] == "sell" and o["code"] == code and o["id"] != exclude)

    def reserved_cash(self, exclude=None):
        tot = 0
        for o in self.s["pending"]:
            if o["side"] == "buy" and o["id"] != exclude:
                px = o.get("limit") or o.get("ref_price", 0) * 1.3  # 시장가 예약은 상한가 기준으로 묶어 둠
                tot += o["qty"] * px * (1 + FEE_BUY + SLIP)
        return tot

    # 주문 접수
    def submit(self, side: str, key: str, qty, order_type: str, limit, book: QuoteBook, phase: str):
        q = book.find(key)
        oid = f"P{self.s['next_id']:05d}"
        stub = {"id": oid, "side": side, "code": str(key), "name": str(key), "qty": 0,
                "type": order_type, "limit": limit}
        if q is None:
            self.s["next_id"] += 1
            self._order_log(stub, "거부", message=f"종목을 찾을 수 없음: {key}")
            return None
        stub.update(code=q.code, name=q.name)

        # 수량
        if side == "sell" and str(qty).strip() in ("전량", "all", "ALL", "0"):
            qty = self.held_qty(q.code) - self.reserved_sell_qty(q.code)
        try:
            qty = int(str(qty).replace(",", ""))
        except ValueError:
            qty = 0
        stub["qty"] = qty
        self.s["next_id"] += 1
        if qty <= 0:
            self._order_log(stub, "거부", message="수량이 0 이하")
            return None
        if q.volume <= 0 and phase == "open":
            self._order_log(stub, "거부", message="거래정지 또는 거래 없음")
            return None

        # 가격제한폭 기준가: 장중이면 전일 종가, 장 밖에서 낸 주문(다음 장 체결)이면 직전 장 종가
        ref = q.prev_close if phase == "open" else q.price
        upper, lower = round_tick(ref * (1 + PRICE_LIMIT), False), round_tick(ref * (1 - PRICE_LIMIT), True)

        if order_type == "limit":
            try:
                limit = int(str(limit).replace(",", ""))
            except (TypeError, ValueError):
                self._order_log(stub, "거부", message="지정가 금액이 숫자가 아님")
                return None
            stub["limit"] = limit
            if limit % tick_size(limit) != 0:
                self._order_log(stub, "거부", message=f"호가단위 오류 — {tick_size(limit)}원 단위로 입력 "
                                                       f"(예: {round_tick(limit, False):,} 또는 {round_tick(limit, True):,})")
                return None
            if not (lower <= limit <= upper):
                self._order_log(stub, "거부", message=f"가격제한폭 밖 (하한 {lower:,} ~ 상한 {upper:,})")
                return None
        else:
            limit = None

        # 잔고 확인
        if side == "sell":
            avail = self.held_qty(q.code) - self.reserved_sell_qty(q.code)
            if qty > avail:
                self._order_log(stub, "거부", message=f"매도 가능 수량 부족 (가능 {avail:,}주)")
                return None
        else:
            px = limit if limit else (q.price * (1 + SLIP) if phase == "open" else upper)
            need = qty * px * (1 + FEE_BUY)
            avail_cash = self.s["cash"] - self.reserved_cash()
            if need > avail_cash + 0.5:
                maxq = int(avail_cash / (px * (1 + FEE_BUY))) if px > 0 else 0
                self._order_log(stub, "거부", message=f"주문 가능 현금 부족 (필요 {need:,.0f}원 / 가능 {avail_cash:,.0f}원, "
                                                       f"최대 {maxq:,}주)")
                return None

        o = {"id": oid, "side": side, "code": q.code, "name": q.name, "qty": qty, "type": order_type,
             "limit": limit, "ref_price": ref, "placed_at": now_kst().isoformat(timespec="seconds"),
             "placed_phase": phase, "valid_session": None}
        # 당일 유효 주문의 거래일: 장중이면 오늘, 장 전이면 오늘(휴장일이면 다음 장), 마감 후·휴장이면 다음 장
        o["valid_session"] = now_kst().strftime("%Y%m%d") if phase in ("open", "pre") else "NEXT"
        self.s["pending"].append(o)
        self._order_log(o, "접수", message="예약(다음 장)" if phase != "open" else "")
        if phase == "open":
            self.try_fill(o, book, phase, fresh=True)
        return o

    def cancel(self, oid: str):
        for o in list(self.s["pending"]):
            if o["id"] == oid.strip().upper():
                self.s["pending"].remove(o)
                self._order_log(o, "취소")
                return True
        self.events.append(f"[취소 실패] 미체결 주문 {oid} 없음")
        return False

    # 체결
    def try_fill(self, o, book: QuoteBook, phase: str, fresh=False):
        if phase != "open":
            return False
        q = book.by_code.get(o["code"])
        if q is None or q.volume <= 0:
            return False
        today = now_kst().strftime("%Y%m%d")
        if q.session != today:
            return False  # 오늘 시세가 아직 없음
        if o["valid_session"] == "NEXT":
            o["valid_session"] = today
        # 장 시작 전에 들어온 주문은 시가부터 오늘 하루 전체 가격대를 적용
        whole_day = o["placed_phase"] in ("pre", "closed", "off") and not fresh

        if o["type"] == "market":
            base = q.open if whole_day else q.price
            px = base * (1 + SLIP) if o["side"] == "buy" else base * (1 - SLIP)
        else:
            L = o["limit"]
            if o["side"] == "buy":
                if whole_day and q.open <= L:
                    px = q.open
                elif (whole_day and q.low <= L) or q.price <= L:
                    px = min(L, q.price) if not whole_day else L
                else:
                    return False
            else:
                if whole_day and q.open >= L:
                    px = q.open
                elif (whole_day and q.high >= L) or q.price >= L:
                    px = max(L, q.price) if not whole_day else L
                else:
                    return False
        self._execute(o, px)
        self.s["pending"].remove(o)
        return True

    def _execute(self, o, px):
        qty, code = o["qty"], o["code"]
        amount = qty * px
        pos = self.s["positions"]
        if o["side"] == "buy":
            fee = amount * FEE_BUY
            cost = amount + fee
            if cost > self.s["cash"] + 0.5:  # 예약 주문이 시가에 더 비싸게 체결되는 경우 → 살 수 있는 만큼만
                qty = int(self.s["cash"] / (px * (1 + FEE_BUY)))
                if qty <= 0:
                    self._order_log(o, "거부", message="체결 시점 현금 부족")
                    return
                amount, fee = qty * px, qty * px * FEE_BUY
                cost = amount + fee
                o["qty"] = qty
            p = pos.setdefault(code, {"name": o["name"], "qty": 0, "avg_price": 0.0, "cost": 0.0})
            p["cost"] += cost
            p["qty"] += qty
            p["avg_price"] = p["cost"] / p["qty"]
            self.s["cash"] -= cost
            self.s["fees"] += fee
            tax, realized = 0.0, 0.0
        else:
            p = pos[code]
            fee, tax = amount * FEE_SELL, amount * TAX_SELL
            proceeds = amount - fee - tax
            cost_part = p["avg_price"] * qty
            realized = proceeds - cost_part
            p["qty"] -= qty
            p["cost"] -= cost_part
            if p["qty"] == 0:
                del pos[code]
            self.s["cash"] += proceeds
            self.s["fees"] += fee
            self.s["taxes"] += tax
            self.s["realized_pnl"] += realized
        self.s["last_quote"][code] = px
        self._append("ledger.csv", LEDGER_COLS, {
            "time": now_kst().isoformat(timespec="seconds"), "order_id": o["id"], "side": o["side"],
            "code": code, "name": o["name"], "qty": qty, "price": round(px, 2), "amount": round(amount),
            "fee": round(fee), "tax": round(tax), "cash_after": round(self.s["cash"]),
            "realized_pnl": round(realized), "note": o["type"]})
        self._order_log(o, "체결", fill_price=px)

    def process_pending(self, book: QuoteBook, phase: str):
        for o in list(self.s["pending"]):
            self.try_fill(o, book, phase)
        if phase in ("closed",):
            today = now_kst().strftime("%Y%m%d")
            for o in list(self.s["pending"]):
                if o["valid_session"] == today:
                    self.s["pending"].remove(o)
                    self._order_log(o, "만료", message="당일 장 마감까지 미체결")

    # 평가
    def mark(self, book: QuoteBook | None):
        for code in self.s["positions"]:
            if book and code in book.by_code:
                self.s["last_quote"][code] = book.by_code[code].price
        mv = sum(p["qty"] * self.s["last_quote"].get(code, p["avg_price"])
                 for code, p in self.s["positions"].items())
        return mv

    def report(self, book: QuoteBook | None) -> str:
        mv = self.mark(book)
        total = self.s["cash"] + mv
        init = self.s["initial_cash"]
        lines = [f"# VAI 10억 모의계좌", "",
                 f"기준 시각: {now_kst():%Y-%m-%d %H:%M} KST", "",
                 "| 항목 | 금액 |", "|---|---|",
                 f"| 총 평가자산 | **{total:,.0f}원** |",
                 f"| 누적 수익률 | **{(total/init-1)*100:+.2f}%** ({total-init:+,.0f}원) |",
                 f"| 현금 | {self.s['cash']:,.0f}원 |",
                 f"| 주식 평가액 | {mv:,.0f}원 |",
                 f"| 실현 손익 | {self.s['realized_pnl']:+,.0f}원 |",
                 f"| 누적 수수료 / 세금 | {self.s['fees']:,.0f}원 / {self.s['taxes']:,.0f}원 |", ""]
        lines += ["## 보유 종목", ""]
        if self.s["positions"]:
            lines += ["| 종목 | 수량 | 평균단가 | 현재가 | 평가액 | 평가손익 | 수익률 |", "|---|---|---|---|---|---|---|"]
            for code, p in sorted(self.s["positions"].items(),
                                  key=lambda kv: -kv[1]["qty"] * self.s["last_quote"].get(kv[0], 0)):
                cur = self.s["last_quote"].get(code, p["avg_price"])
                val = p["qty"] * cur
                pnl = val - p["cost"]
                lines.append(f"| {p['name']}({code}) | {p['qty']:,} | {p['avg_price']:,.0f} | {cur:,.0f} | "
                             f"{val:,.0f} | {pnl:+,.0f} | {pnl/p['cost']*100:+.2f}% |")
        else:
            lines.append("보유 종목 없음")
        lines += ["", "## 미체결 주문", ""]
        if self.s["pending"]:
            lines += ["| 주문번호 | 구분 | 종목 | 수량 | 가격 | 접수 |", "|---|---|---|---|---|---|"]
            for o in self.s["pending"]:
                px = f"{o['limit']:,}" if o.get("limit") else "시장가"
                lines.append(f"| {o['id']} | {'매수' if o['side']=='buy' else '매도'} | {o['name']}({o['code']}) | "
                             f"{o['qty']:,} | {px} | {o['placed_at'][5:16].replace('T',' ')} |")
        else:
            lines.append("없음")
        lines += ["", "주문은 GitHub 앱 → Actions → **모의계좌 주문** → Run workflow.",
                  "평가액의 현재가는 KRX 시세 스냅샷 기준이며 실제와 약간 차이 날 수 있습니다."]
        text = "\n".join(lines) + "\n"
        (self.base / "REPORT.md").write_text(text, encoding="utf-8")
        return text

"""
VAI 10억 모의계좌 실행기

  주문:  python scripts/paper_trade.py order --side 매수 --stock 삼성전자 --qty 100 --price 시장가
         python scripts/paper_trade.py order --side 매도 --stock 005930 --qty 전량 --price 251000
  취소:  python scripts/paper_trade.py cancel --order P00003
  확인:  python scripts/paper_trade.py check      (미체결 체결 확인 + 마감 후 만료 + 보고서)
  조회:  python scripts/paper_trade.py report

결과는 paper/ 폴더에 저장되고, TG_TOKEN·TG_CHAT_ID 환경변수가 있으면 텔레그램으로도 보낸다.
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vai_arena import krx, paper  # noqa: E402

SIDE = {"매수": "buy", "buy": "buy", "매도": "sell", "sell": "sell"}


def notify(text: str):
    tok, chat = os.environ.get("TG_TOKEN"), os.environ.get("TG_CHAT_ID")
    if not (tok and chat and text.strip()):
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": text[:3900]}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=15)
    except Exception as ex:
        print(f"텔레그램 전송 실패: {ex}")


def summary_line(acc: paper.Account, book) -> str:
    mv = acc.mark(book)
    total = acc.s["cash"] + mv
    init = acc.s["initial_cash"]
    return (f"총자산 {total:,.0f}원 ({(total/init-1)*100:+.2f}%) · 현금 {acc.s['cash']:,.0f}원 · "
            f"보유 {len(acc.s['positions'])}종목 · 미체결 {len(acc.s['pending'])}건")


def main(argv=None, book=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["order", "cancel", "check", "report"])
    ap.add_argument("--side", default="")
    ap.add_argument("--stock", default="")
    ap.add_argument("--qty", default="")
    ap.add_argument("--price", default="시장가")
    ap.add_argument("--order", default="")
    a = ap.parse_args(argv)

    acc = paper.Account()
    phase = paper.market_phase(paper.now_kst(), krx.known_holidays())
    if book is None and a.action in ("order", "check", "report"):
        try:
            book = paper.load_live_quotes()
        except Exception as ex:
            if a.action == "order":
                print(f"시세 조회 실패 — 주문 거부: {ex}")
                notify(f"[VAI 모의] 시세 조회 실패로 주문을 처리하지 못했습니다: {ex}")
                return 1
            book = None
            print(f"시세 조회 실패 — 평가만 직전 값으로: {ex}")

    if a.action == "order":
        side = SIDE.get(a.side.strip())
        if side is None:
            print("매수/매도를 정확히 입력하세요")
            return 1
        price = a.price.strip().replace(",", "")
        otype = "market" if price in ("", "시장가", "market", "0") else "limit"
        if book is not None:
            acc.process_pending(book, phase)  # 먼저 기존 미체결 확인
        acc.submit(side, a.stock, a.qty, otype, None if otype == "market" else price, book, phase)
    elif a.action == "cancel":
        acc.cancel(a.order)
    elif a.action == "check":
        if book is not None:
            acc.process_pending(book, phase)

    acc.report(book)
    acc.save()

    head = f"[VAI 10억 모의계좌] {paper.now_kst():%m-%d %H:%M} ({ {'open':'장중','pre':'장 전','closed':'장 마감','off':'휴장'}[phase] })"
    body = "\n".join(acc.events) if acc.events else ("변동 없음" if a.action == "check" else "")
    msg = "\n".join(x for x in (head, body, summary_line(acc, book)) if x)
    print(msg)
    if acc.events or a.action in ("report", "order", "cancel"):
        notify(msg)
    gh = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh:
        with open(gh, "a", encoding="utf-8") as f:
            f.write("```\n" + msg + "\n```\n\n" + (paper.PAPER / "REPORT.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

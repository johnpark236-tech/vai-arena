"""
10년치 백필 — 지정 기간의 모든 거래일을 하루씩 받아 data/daily 에 저장한다.

  python scripts/backfill.py --start 20161010 --end 20161231

- 이미 받은 날짜는 건너뛴다(중간에 끊겨도 다시 돌리면 이어서 받음).
- 하루 실패해도 멈추지 않고 다음 날로 넘어간 뒤 실패 목록을 남긴다.
- 실패율이 5%를 넘으면 종료 코드 1 (Actions가 빨간불로 표시).
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vai_arena import krx  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--sleep", type=float, default=0.3, help="날짜 사이 대기(초) — KRX 부하 완화")
    a = ap.parse_args()

    krx.preload_names(krx.DATA / "master" / "tickers.csv")
    days = krx.trading_days(a.start, a.end)
    print(f"대상 {len(days)}일 ({a.start}~{a.end})", flush=True)

    stats = {"saved": 0, "exists": 0, "holiday": 0}
    failed = []
    t0 = time.time()
    for i, d in enumerate(days, 1):
        try:
            r = krx.collect_one(d, allow_fdr_today=False)
            stats[r] += 1
        except Exception as ex:
            failed.append({"date": d, "error": str(ex)[:200]})
            print(f"  ✗ {d}: {ex}", flush=True)
        if i % 20 == 0 or i == len(days):
            el = time.time() - t0
            print(f"  {i}/{len(days)} 진행 · 저장 {stats['saved']} · 기존 {stats['exists']} · "
                  f"휴장 {stats['holiday']} · 실패 {len(failed)} · {el/60:.1f}분", flush=True)
        if stats["saved"]:
            time.sleep(a.sleep)

    st = krx.DATA / "_status" / f"backfill_{a.start}_{a.end}.json"
    st.parent.mkdir(parents=True, exist_ok=True)
    st.write_text(json.dumps({"start": a.start, "end": a.end, **stats, "failed": failed,
                              "finished_at": krx.now_kst().isoformat(timespec="seconds")},
                             ensure_ascii=False, indent=2), encoding="utf-8")

    rate = len(failed) / max(1, len(days))
    print(f"완료: {stats} 실패 {len(failed)}일 ({rate:.1%})")
    return 1 if rate > 0.05 else 0


if __name__ == "__main__":
    sys.exit(main())

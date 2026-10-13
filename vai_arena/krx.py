"""
KRX 시세 수집 공용 모듈 — 일일 수집(collect_daily)과 10년 백필(backfill)이 같이 쓴다.

저장 규칙
  data/daily/YYYY/YYYYMMDD.csv.gz   하루 전 종목 스냅샷 (한 번 쓰면 바꾸지 않음)
  data/index/YYYY.csv               연도별 KOSPI·KOSDAQ 지수
  data/_status/holidays/YYYY.txt    연도별 휴장일 목록 (다시 조회하지 않기 위해)

가격은 '수정 전 원본가'다. 그날 실제로 거래된 가격 그대로이고,
상장폐지 종목도 그날 상장돼 있었다면 포함된다(생존 편향 없음).
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MIN_ROWS = 1500  # 2016년 상장 종목 수(약 2,000)를 감안한 하한

COLUMNS = ["date", "code", "name", "market",
           "open", "high", "low", "close", "volume", "value", "change_pct",
           "marcap", "shares", "per", "pbr", "eps", "bps", "div_yield", "dps",
           "source"]

_NAME_CACHE: dict = {}


def now_kst():
    return datetime.now(KST)


def iso(d: str) -> str:
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def daily_path(d: str) -> Path:
    return DATA / "daily" / d[:4] / f"{d}.csv.gz"


# ── 휴장일 기록 ──────────────────────────────────────────
def _holiday_file(year: str) -> Path:
    # 연도별 파일 — 백필 작업이 연도별로 병렬 실행돼도 서로 충돌하지 않게
    return DATA / "_status" / "holidays" / f"{year}.txt"


def known_holidays() -> set:
    out = set()
    for p in (DATA / "_status" / "holidays").glob("*.txt"):
        out |= set(p.read_text().split())
    return out


def mark_holiday(d: str):
    p = _holiday_file(d[:4])
    p.parent.mkdir(parents=True, exist_ok=True)
    h = (set(p.read_text().split()) if p.exists() else set()) | {d}
    p.write_text("\n".join(sorted(h)) + "\n")


# ── 거래일 달력 ──────────────────────────────────────────
def candidate_days(start: str, end: str) -> list:
    """start~end 사이 평일 목록 (YYYYMMDD). 공휴일은 조회 결과로 걸러낸다."""
    days = pd.bdate_range(iso(start), iso(end))
    return [x.strftime("%Y%m%d") for x in days]


def trading_days(start: str, end: str) -> list:
    """가능하면 KRX 영업일 달력을 쓰고, 실패하면 평일 목록을 쓴다."""
    try:
        from pykrx import stock
        days = stock.get_previous_business_days(fromdate=start, todate=end)
        out = [pd.Timestamp(x).strftime("%Y%m%d") for x in days]
        if out:
            return out
    except Exception:
        pass
    return candidate_days(start, end)


# ── 종목명 ───────────────────────────────────────────────
def ticker_name(code: str) -> str | None:
    if code in _NAME_CACHE:
        return _NAME_CACHE[code]
    name = None
    try:
        from pykrx import stock
        name = stock.get_market_ticker_name(code)
        if not isinstance(name, str) or not name.strip():
            name = None
    except Exception:
        name = None
    _NAME_CACHE[code] = name
    return name


def preload_names(master_csv: Path | None = None):
    """종목 마스터와 FDR 현재 상장목록으로 이름 캐시를 미리 채운다."""
    if master_csv and master_csv.exists():
        m = pd.read_csv(master_csv, dtype=str)
        _NAME_CACHE.update({r.code: r.name for r in m.itertuples() if isinstance(r.name, str)})
    try:
        import FinanceDataReader as fdr
        s = fdr.StockListing("KRX")
        _NAME_CACHE.update(dict(zip(s["Code"].astype(str).str.zfill(6), s["Name"])))
    except Exception:
        pass


# ── 하루치 조회 ──────────────────────────────────────────
def _require_login():
    if not (os.environ.get("KRX_ID") and os.environ.get("KRX_PW")):
        raise RuntimeError("KRX_ID / KRX_PW 환경변수가 없습니다 (GitHub Secrets 확인)")


def fetch_day_pykrx(d: str):
    """(전종목 DataFrame, 지수 DataFrame) 반환. 휴장일이면 (None, None)."""
    _require_login()
    from pykrx import stock

    frames = []
    for mkt in ("KOSPI", "KOSDAQ"):
        o = stock.get_market_ohlcv(d, market=mkt)
        if o is None or o.empty:
            continue
        o = o.rename(columns={"시가": "open", "고가": "high", "저가": "low", "종가": "close",
                              "거래량": "volume", "거래대금": "value", "등락률": "change_pct"})
        try:
            cap = stock.get_market_cap(d, market=mkt).rename(
                columns={"시가총액": "marcap", "상장주식수": "shares"})
            o = o.join(cap[[c for c in ("marcap", "shares") if c in cap]], how="left")
        except Exception:
            pass
        try:
            fun = stock.get_market_fundamental(d, market=mkt).rename(
                columns={"PER": "per", "PBR": "pbr", "EPS": "eps", "BPS": "bps",
                         "DIV": "div_yield", "DPS": "dps"})
            o = o.join(fun[[c for c in ("per", "pbr", "eps", "bps", "div_yield", "dps") if c in fun]],
                       how="left")
        except Exception:
            pass
        o["market"] = mkt
        frames.append(o)

    if not frames:
        return None, None
    df = pd.concat(frames)
    df.index.name = "code"
    df = df.reset_index()
    df["code"] = df["code"].astype(str).str.zfill(6)
    if pd.to_numeric(df["volume"], errors="coerce").fillna(0).sum() == 0:
        return None, None  # 휴장일
    df["source"] = "PYKRX"

    idx_rows = []
    for mkt, tk in (("KOSPI", "1001"), ("KOSDAQ", "2001")):
        try:
            ix = stock.get_index_ohlcv(d, d, tk)
            if ix is not None and not ix.empty:
                r = ix.iloc[-1]
                idx_rows.append({"date": iso(d), "market": mkt, "open": r["시가"], "high": r["고가"],
                                 "low": r["저가"], "close": r["종가"], "volume": r["거래량"]})
        except Exception:
            pass
    return df, pd.DataFrame(idx_rows)


def last_session_date() -> str | None:
    """가장 최근에 실제로 열린 장의 날짜 (KOSPI 지수 마지막 일자)."""
    import FinanceDataReader as fdr
    since = (now_kst() - timedelta(days=14)).strftime("%Y-%m-%d")
    ix = fdr.DataReader("KS11", since)
    if ix is None or ix.empty:
        return None
    return pd.Timestamp(ix.index[-1]).strftime("%Y%m%d")


def fetch_day_fdr_today(d: str):
    """FDR 현재 시세 스냅샷으로 대체 수집.
    스냅샷은 '가장 최근 장'의 시세이므로 실제 장 날짜를 확인해 그 날짜로 반환한다.
    반환: (df, idx, 실제_날짜)"""
    import FinanceDataReader as fdr
    actual = last_session_date()
    if actual is None:
        raise RuntimeError("FDR 지수로 최근 장 날짜를 확인할 수 없음")
    s = fdr.StockListing("KRX")
    s = s[s["Market"].isin(["KOSPI", "KOSDAQ"])].copy()
    df = pd.DataFrame({
        "code": s["Code"].astype(str).str.zfill(6), "name": s["Name"], "market": s["Market"],
        "open": s["Open"], "high": s["High"], "low": s["Low"], "close": s["Close"],
        "volume": s["Volume"], "value": s["Amount"],
        "change_pct": s.get("ChagesRatio", s.get("ChangesRatio")),
        "marcap": s["Marcap"], "shares": s["Stocks"],
    })
    if pd.to_numeric(df["volume"], errors="coerce").fillna(0).sum() == 0:
        return None, None, actual
    df["source"] = "FDR_SNAPSHOT"
    idx_rows = []
    for mkt, sym in (("KOSPI", "KS11"), ("KOSDAQ", "KQ11")):
        ix = fdr.DataReader(sym, iso(actual), iso(actual))
        if not ix.empty:
            r = ix.iloc[-1]
            idx_rows.append({"date": iso(actual), "market": mkt, "open": r["Open"], "high": r["High"],
                             "low": r["Low"], "close": r["Close"], "volume": r["Volume"]})
    return df, pd.DataFrame(idx_rows), actual


_FDR_CACHE: dict = {}


def _fdr_snapshot_cached(d: str):
    """한 번 실행 중 FDR 스냅샷은 한 번만 받는다."""
    if "snap" not in _FDR_CACHE:
        try:
            _FDR_CACHE["snap"] = fetch_day_fdr_today(d)
        except Exception as ex:
            _FDR_CACHE["snap"] = (None, None, "00000000")
            _FDR_CACHE["err"] = str(ex)
    return _FDR_CACHE["snap"]


def session_closed(d: str) -> bool:
    """d일 장이 끝났는지. 과거 날짜는 True, 오늘은 16:00 KST 이후만 True."""
    now = now_kst()
    today = now.strftime("%Y%m%d")
    return d < today or (d == today and now.hour >= 16)


# ── 저장 ─────────────────────────────────────────────────
def finalize(df: pd.DataFrame, d: str) -> pd.DataFrame:
    if "name" not in df:
        df["name"] = pd.NA
    missing = df["name"].isna()
    if missing.any():
        df.loc[missing, "name"] = df.loc[missing, "code"].map(ticker_name)
    df["date"] = iso(d)
    for c in COLUMNS:
        if c not in df:
            df[c] = pd.NA
    return df[COLUMNS].sort_values("code").reset_index(drop=True)


def write_day(d: str, df: pd.DataFrame, idx: pd.DataFrame | None) -> Path:
    if len(df) < MIN_ROWS:
        raise ValueError(f"{d}: 종목 수 {len(df)} < {MIN_ROWS} — 비정상 데이터로 저장하지 않음")
    out = daily_path(d)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8", compression="gzip")
    if idx is not None and not idx.empty:
        ip = DATA / "index" / f"{d[:4]}.csv"
        ip.parent.mkdir(parents=True, exist_ok=True)
        old = pd.read_csv(ip) if ip.exists() else pd.DataFrame()
        allidx = pd.concat([old, idx]).drop_duplicates(["date", "market"], keep="last")
        allidx.sort_values(["date", "market"]).to_csv(ip, index=False)
    return out


def collect_one(d: str, allow_fdr_today: bool = True) -> str:
    """하루 수집.
    반환: 'saved' | 'exists' | 'holiday' | 'not_closed' | 'saved:YYYYMMDD'(대체 수집이 다른 날짜로 저장된 경우)
    실패 시 예외."""
    if daily_path(d).exists():
        return "exists"
    if d in known_holidays():
        return "holiday"
    if not session_closed(d):
        # 장 시작 전·장중에는 빈 결과가 와도 휴장일로 기록하면 안 된다
        return "not_closed"
    df = idx = None
    err = None
    try:
        df, idx = fetch_day_pykrx(d)
        if df is None:
            mark_holiday(d)
            return "holiday"
    except Exception as ex:
        err = ex
    if df is None and allow_fdr_today:
        # FDR 스냅샷은 '가장 최근 장' 하루치만 준다 → 그 날짜와 맞을 때만 사용
        fdf, fidx, actual = _fdr_snapshot_cached(d)
        today = now_kst().strftime("%Y%m%d")
        if actual == d and fdf is not None:
            df, idx = fdf, fidx
        elif d == today and actual < d:
            # 오늘은 장이 열리지 않았음(휴장일). 스냅샷은 지난 장 시세 → 그 날짜로 저장
            mark_holiday(d)
            if fdf is None or daily_path(actual).exists():
                return "holiday"
            write_day(actual, finalize(fdf.copy(), actual), fidx)
            return f"saved:{actual}"
    if df is None:
        raise RuntimeError(f"{d} 수집 실패: {err}")
    write_day(d, finalize(df, d), idx)
    return "saved"


def read_day(d: str) -> pd.DataFrame:
    return pd.read_csv(daily_path(d), dtype={"code": str}, compression="gzip")


def saved_days() -> list:
    return sorted(p.name[:8] for p in (DATA / "daily").glob("*/*.csv.gz"))

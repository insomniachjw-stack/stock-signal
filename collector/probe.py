"""데이터 소스 점검: GitHub Actions에서 어떤 한국 주식 시세 소스가 실제로 열리는지 확인."""
import json, sys, traceback, datetime as dt
import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
out = {}

def check(name, fn):
    try:
        out[name] = {"ok": True, "info": fn()}
    except Exception as e:
        out[name] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:200]}"}
    print(name, json.dumps(out[name], ensure_ascii=False)[:600], flush=True)

def naver_list():
    r = requests.get("https://m.stock.naver.com/api/stocks/marketValue/KOSPI?page=1&pageSize=100", headers=UA, timeout=20)
    r.raise_for_status(); j = r.json()
    return {"total": j.get("totalCount"), "first": {k: j["stocks"][0].get(k) for k in ("itemCode", "stockName", "closePrice", "accumulatedTradingValue", "marketValue", "stockEndType")}, "keys": list(j["stocks"][0].keys())}

def naver_day():
    r = requests.get("https://fchart.stock.naver.com/siseJson.nhn?symbol=005930&requestType=1&startTime=20240101&endTime=20261231&timeframe=day", headers=UA, timeout=20)
    r.raise_for_status(); t = r.text.strip().splitlines()
    return {"lines": len(t), "head": t[:2], "tail": t[-3:]}

def naver_api_day():
    r = requests.get("https://api.stock.naver.com/chart/domestic/item/005930/day?startDateTime=202401010000&endDateTime=202612310000", headers=UA, timeout=20)
    r.raise_for_status(); j = r.json()
    return {"n": len(j), "last": j[-1]}

def naver_index():
    r = requests.get("https://fchart.stock.naver.com/siseJson.nhn?symbol=KOSPI&requestType=1&startTime=20260101&endTime=20261231&timeframe=day", headers=UA, timeout=20)
    r.raise_for_status(); t = r.text.strip().splitlines()
    return {"lines": len(t), "tail": t[-3:]}

def yahoo():
    r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/005930.KS?range=1mo&interval=1d", headers=UA, timeout=20)
    r.raise_for_status(); j = r.json()["chart"]["result"][0]
    return {"n": len(j["timestamp"]), "last_close": j["indicators"]["quote"][0]["close"][-1]}

def fdr_listing():
    import FinanceDataReader as fdr
    df = fdr.StockListing("KRX")
    return {"rows": len(df), "cols": list(df.columns)}

def fdr_price():
    import FinanceDataReader as fdr
    df = fdr.DataReader("005930", "2024-01-01")
    return {"rows": len(df), "last": str(df.index[-1]), "close": float(df["Close"].iloc[-1])}

def pykrx_all():
    from pykrx import stock
    d = dt.date.today()
    for i in range(1, 8):
        day = (d - dt.timedelta(days=i)).strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_ticker(day, market="ALL")
        if len(df) and df["거래량"].sum() > 0:
            return {"day": day, "rows": len(df), "cols": list(df.columns)}
    raise RuntimeError("no data in last 7 days")

for n, f in [("naver_list", naver_list), ("naver_day", naver_day), ("naver_api_day", naver_api_day), ("naver_index", naver_index),
             ("yahoo", yahoo), ("fdr_listing", fdr_listing), ("fdr_price", fdr_price), ("pykrx_all", pykrx_all)]:
    check(n, f)

json.dump(out, open("probe_result.json", "w"), ensure_ascii=False, indent=1)

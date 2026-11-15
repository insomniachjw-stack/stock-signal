"""시가총액 상위 종목의 장기 일봉을 네이버 금융에서 받아 parquet으로 저장한다."""
import ast, re, sys, time, json
from concurrent.futures import ThreadPoolExecutor
import pandas as pd, requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
TOP_N, START = 600, "20130101"
# 자산배분용 ETF: 코스피200, 코스닥150, 나스닥100, S&P500(H), 국고채10년, 골드(H), 달러, 단기채권
ETFS = ["069500", "229200", "133690", "143850", "148070", "132030", "138230", "153130"]
S = requests.Session(); S.headers.update(UA)

def get(url, tries=4):
    for i in range(tries):
        try:
            r = S.get(url, timeout=30); r.raise_for_status(); return r
        except Exception:
            if i == tries - 1: raise
            time.sleep(1.5 * (i + 1))

def num(x):
    try: return float(str(x).replace(",", ""))
    except Exception: return float("nan")

def universe():
    rows = []
    for mkt in ("KOSPI", "KOSDAQ"):
        page = 1
        while True:
            j = get(f"https://m.stock.naver.com/api/stocks/marketValue/{mkt}?page={page}&pageSize=100").json()
            st = j.get("stocks") or []
            if not st: break
            for s in st:
                rows.append({"code": s["itemCode"], "name": s["stockName"], "market": mkt, "type": s.get("stockEndType"),
                             "marcap": num(s.get("marketValue")), "close": num(s.get("closePrice")),
                             "value": num(s.get("accumulatedTradingValue")), "stop": s.get("tradeStopType", {}).get("name") if isinstance(s.get("tradeStopType"), dict) else None})
            if page * 100 >= j.get("totalCount", 0): break
            page += 1
    df = pd.DataFrame(rows)
    df = df[(df["type"] == "stock") & df["code"].str.match(r"^\d{5}0$") & ~df["name"].str.contains("스팩|리츠|인프라")]
    return df.sort_values("marcap", ascending=False).drop_duplicates("code")

def history(code):
    t = get(f"https://fchart.stock.naver.com/siseJson.nhn?symbol={code}&requestType=1&startTime={START}&endTime=20991231&timeframe=day").text
    data = ast.literal_eval(re.sub(r"\s+", "", t))
    df = pd.DataFrame(data[1:], columns=["date", "open", "high", "low", "close", "volume", "frn"][:len(data[0])])
    df["code"] = code
    return df[["date", "code", "open", "high", "low", "close", "volume"]]

if __name__ == "__main__":
    if len(sys.argv) > 1: TOP_N = int(sys.argv[1])
    if len(sys.argv) > 2: START = sys.argv[2]
    uni = universe()
    print("universe", len(uni), flush=True)
    uni.to_csv("universe.csv", index=False)
    codes = list(uni["code"].head(TOP_N)) + ["KOSPI", "KOSDAQ"] + ETFS
    out, fail = [], []
    def job(c):
        try: return history(c)
        except Exception as e:
            fail.append((c, str(e)[:100])); return None
    with ThreadPoolExecutor(6) as ex:
        for i, df in enumerate(ex.map(job, codes)):
            if df is not None and len(df): out.append(df)
            if i % 100 == 0: print("fetched", i, flush=True)
    px = pd.concat(out, ignore_index=True)
    px["date"] = pd.to_datetime(px["date"].astype(str))
    for c in ("open", "high", "low", "close", "volume"): px[c] = pd.to_numeric(px[c], errors="coerce")
    px.to_parquet("prices.parquet", compression="zstd", index=False)
    print("rows", len(px), "codes", px["code"].nunique(), "fail", len(fail), fail[:5], "last", px["date"].max())

import requests, json, urllib.parse as up
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
ORI = dict(UA, Origin="https://insomniachjw-stack.github.io")
def t(name, fn):
    try: print("##", name, "OK", str(fn())[:700], flush=True)
    except Exception as e: print("##", name, "FAIL", type(e).__name__, str(e)[:200], flush=True)
def g(url, h=UA, **kw):
    r = requests.get(url, headers=h, timeout=20, **kw); return r
def cors(url):
    r = g(url, ORI); return {"status": r.status_code, "acao": r.headers.get("access-control-allow-origin"), "body": r.text[:200]}
t("kr realtime polling CORS", lambda: cors("https://polling.finance.naver.com/api/realtime/domestic/stock/005930"))
t("kr basic CORS", lambda: cors("https://m.stock.naver.com/api/stock/005930/basic"))
t("us naver basic CORS", lambda: cors("https://api.stock.naver.com/stock/AAPL.O/basic"))
t("us naver day", lambda: g("https://api.stock.naver.com/chart/foreign/item/AAPL.O/day?startDateTime=202610010000&endDateTime=202612310000").text[-300:])
t("yahoo AAPL CORS", lambda: cors("https://query1.finance.yahoo.com/v8/finance/chart/AAPL?range=5d&interval=1d"))
t("usdkrw naver", lambda: g("https://m.stock.naver.com/front-api/marketIndex/productDetail?category=exchange&reutersCode=FX_USDKRW").text[:300])
q = up.quote("삼성퇴직연금KOSPI200")
t("naver ac fund", lambda: g(f"https://ac.stock.naver.com/ac?q={q}&target=stock,index,fund,etf").text[:500])
t("naver fund search page", lambda: (lambda r: (r.status_code, r.url, len(r.text)))(g(f"https://finance.naver.com/fund/fundFinderList.naver?search={q}")))
t("funetf search", lambda: (lambda r: (r.status_code, r.text[:400]))(g(f"https://www.funetf.co.kr/api/public/product/search?keyword={q}")))
t("funetf main", lambda: (lambda r: (r.status_code, len(r.text)))(g("https://www.funetf.co.kr/")))
t("daum funds", lambda: (lambda r: (r.status_code, r.text[:400]))(g(f"https://finance.daum.net/api/search/funds?q={q}", dict(UA, Referer="https://finance.daum.net/funds"))))
def kofia(svc, fn, dto, body):
    x = f'<?xml version="1.0" encoding="utf-8"?><message><proframeHeader><pfmAppName>FS-DIS2</pfmAppName><pfmSvcName>{svc}</pfmSvcName><pfmFnName>{fn}</pfmFnName></proframeHeader><systemHeader></systemHeader><{dto}>{body}</{dto}></message>'
    r = requests.post("https://dis.kofia.or.kr/proframeWeb/XMLSERVICES/", data=x.encode("utf-8"), headers=dict(UA, **{"Content-Type": "text/xml; charset=utf-8"}), timeout=30)
    return r.status_code, len(r.text), r.text[:900]
t("kofia fund search by name", lambda: kofia("DISFundAnnSO", "select", "DISCondFuncDTO", "<tmpV30>20261101</tmpV30><tmpV31>20261116</tmpV31><tmpV10>0</tmpV10><tmpV12>삼성퇴직연금KOSPI200</tmpV12>"))
t("kofia std price list", lambda: kofia("DISFundStdPrcStutSO", "select", "DISCondFuncDTO", "<tmpV30>20261101</tmpV30><tmpV31>20261116</tmpV31><tmpV10>0</tmpV10><tmpV12>삼성퇴직연금KOSPI200</tmpV12>"))
t("kofia main", lambda: (lambda r: (r.status_code, len(r.text)))(g("https://dis.kofia.or.kr/websquare/index.jsp?w2xPath=/wq/fundann/DISFundAnn.xml&divisionId=MDIS01004001000000&serviceId=SDIS01004001000")))

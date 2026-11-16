import requests, json, urllib.parse as up
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S918N) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36", "Referer": "https://stock.naver.com/"}
B = "https://m.stock.naver.com/front-api"; C = "K55105BT4531"
def show(name, url, n=900):
    try:
        r = requests.get(url, headers=UA, timeout=20); print("##", name, r.status_code, r.text[:n].replace("\n", " "), "...LEN", len(r.text), flush=True)
    except Exception as e: print("##", name, "FAIL", str(e)[:150], flush=True)
show("daily", f"{B}/fund/price/list/daily?fundCode={C}&date=2026-11-16")
show("daily ps", f"{B}/fund/price/list/daily?fundCode={C}&date=2026-11-16&pageSize=100", 300)
show("term", f"{B}/fund/term/list?fundCode={C}")
show("chart", f"{B}/fund/basePrice/chart?fundCode={C}")
for t in ("1Y", "ONE_YEAR", "year1", "3M", "THREE_MONTH", "12M", "ALL"):
    show("chart " + t, f"{B}/fund/basePrice/chart?fundCode={C}&term={t}", 350)
show("period", f"{B}/fund/return/period?fundCode={C}")
show("alloc", f"{B}/fund/portfolio/allocation?fundCode={C}", 1500)
show("asset", f"{B}/fund/asset/allocation?fundCode={C}", 600)
for q in ("삼성퇴직연금KOSPI200증권자투자신탁제1호", "미래에셋미국나스닥100인덱스증권자투자신탁", "과학기술인공제회", "iM에셋월드골드증권자투자신탁"):
    show("ac " + q, "https://ac.stock.naver.com/ac?target=fund&q=" + up.quote(q), 1200)
show("list", f"{B}/fund/list?page=1&pageSize=5", 700)

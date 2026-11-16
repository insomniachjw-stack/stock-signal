import requests, re, json
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S918N) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36", "Referer": "https://stock.naver.com/"}
C = "K55105BT4531"
def show(name, url):
    try:
        r = requests.get(url, headers=UA, timeout=20); print("##", name, r.status_code, r.headers.get("content-type", "")[:30], r.text[:500].replace("\n", " "), flush=True)
    except Exception as e: print("##", name, "FAIL", str(e)[:150], flush=True)
for n, u in [("a", f"https://stock.naver.com/api/domestic/fund/{C}/basic"), ("b", f"https://m.stock.naver.com/api/fund/{C}/basic"), ("c", f"https://api.stock.naver.com/fund/{C}/basic"),
             ("d", f"https://api.stock.naver.com/fund/{C}/price?page=1&pageSize=20"), ("e", f"https://m.stock.naver.com/front-api/fund/basic?fundCode={C}"),
             ("f", f"https://stock.naver.com/api/fund/{C}"), ("g", f"https://api.stock.naver.com/chart/domestic/fund/{C}/day?startDateTime=202601010000&endDateTime=202612310000")]:
    show(n, u)
r = requests.get(f"https://stock.naver.com/domestic/fund/{C}/total", headers=UA, timeout=20); h = r.text
print("## page", r.status_code, len(h), flush=True)
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
if m: print("## nextdata", m.group(1)[:1500])
srcs = sorted(set(re.findall(r'(?:src|href)="([^"]+\.js[^"]*)"', h))); print("## scripts", len(srcs))
found = set()
for s in srcs:
    u = s if s.startswith("http") else "https://stock.naver.com" + s
    try: js = requests.get(u, headers=UA, timeout=20).text
    except Exception: continue
    for x in re.findall(r'["`]([^"`\s]{0,80}fund[^"`\s]{0,120})["`]', js, re.I):
        if "/" in x and len(x) < 200: found.add(x)
for x in sorted(found)[:150]: print("## path", x)

import requests, re, json
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S918N) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36", "Referer": "https://stock.naver.com/"}
C = "K55105BT4531"
def show(name, url):
    try:
        r = requests.get(url, headers=UA, timeout=20); print("##", name, r.status_code, r.text[:900].replace("\n", " "), flush=True); return r
    except Exception as e: print("##", name, "FAIL", str(e)[:150], flush=True)
for b in ("https://stock.naver.com/api", "https://m.stock.naver.com/front-api", "https://api.stock.naver.com", "https://stock.naver.com/api/domestic"):
    show(b + " detail", f"{b}/fund/detail?fundCode={C}")
h = requests.get(f"https://stock.naver.com/domestic/fund/{C}/total", headers=UA, timeout=20).text
srcs = sorted(set(re.findall(r'(?:src|href)="([^"]+\.js[^"]*)"', h)))
seen = 0
for s in srcs:
    u = s if s.startswith("http") else "https://stock.naver.com" + s
    try: js = requests.get(u, headers=UA, timeout=20).text
    except Exception: continue
    for key in ("/fund/price/list/daily", "/fund/detail", "/fund/basePrice/chart", "/fund/list", "/fund/return/period", "/fund/portfolio/allocation"):
        for m in re.finditer(re.escape(key), js):
            if seen < 14: print("## ctx", key, "::", js[max(0, m.start() - 350):m.end() + 350].replace("\n", " ")); seen += 1
    for m in re.finditer(r'baseURL\s*:\s*[^,}]{0,120}', js):
        print("## base", m.group(0)[:160])

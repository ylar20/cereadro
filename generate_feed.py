#!/usr/bin/env python3
import json
import re
from playwright.sync_api import sync_playwright

LIST_URL = "https://arhiiv.err.ee/audio/seeria/rahva-oma-kaitse?limit=500&sort=old"
API = "https://arhiiv.err.ee/api/v1/series/audio/rahva-oma-kaitse"

def year_of(v):
    if isinstance(v, int): return v
    m = re.search(r"\b(?:19|20)\d{2}\b", str(v))
    return int(m.group(0)) if m else None

def media_strings(obj, path=""):
    out=[]
    if isinstance(obj, dict):
        for k,v in obj.items(): out += media_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i,v in enumerate(obj): out += media_strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        s=obj.replace("\\/","/")
        if any(x in s.lower() for x in [".mp3", ".m4a", ".aac", ".m3u8", ".mpd", "heli.err.ee", "download"]):
            out.append((path,s))
    return out

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page()
    page.goto(LIST_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)

    all_entries=[]
    for n in range(1,8):
        result = page.evaluate("""async ({api,n}) => {
          const body = new URLSearchParams({limit:'500', page:String(n), sort:'old', all:'false'});
          const r = await fetch(api, {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'}, body});
          return {status:r.status, text:await r.text()};
        }""", {"api":API,"n":n})
        print("PAGE_STATUS",n,result["status"])
        if result["status"] != 200: break
        data=json.loads(result["text"])
        al=data.get("activeList") or {}
        entries=al.get("data") or []
        if not entries: break
        years=[year_of(e.get("date")) for e in entries]
        years=[y for y in years if y]
        print("PAGE_RANGE",n,len(entries),min(years) if years else None,max(years) if years else None,"TOTAL",al.get("totalCount"))
        all_entries.extend(entries)
        if len(entries)<500: break

    old=[e for e in all_entries if year_of(e.get("date")) in range(2005,2010)]
    print("MATCHING_COUNT",len(old))
    if not old: raise SystemExit("No 2005-2009 entries found after pagination")
    e=old[0]
    print("TEST_ENTRY",json.dumps({k:e.get(k) for k in ["date","fileId","heading","url","seriesId"]},ensure_ascii=False))
    ep_url="https://arhiiv.err.ee/audio/vaata/"+e["url"]
    print("EPISODE_URL",ep_url)

    ep=browser.new_page()
    captured=[]
    def ep_resp(resp):
        u=resp.url
        ct=(resp.headers.get("content-type") or "").lower()
        if "/api/" in u or "json" in ct:
            try: data=resp.json()
            except: return
            ms=media_strings(data)
            if ms or "arhiiv.err.ee/api" in u:
                captured.append((u, list(data.keys())[:30] if isinstance(data,dict) else ["list"], ms))
    ep.on("response",ep_resp)
    ep.goto(ep_url,wait_until="domcontentloaded",timeout=60000)
    ep.wait_for_timeout(7000)
    print("CAPTURED_RESPONSES",len(captured))
    for u,keys,ms in captured[:40]:
        print("API",u)
        print("KEYS",keys)
        for path,s in ms[:30]: print("MEDIA",path,s)
    content=ep.content()
    urls=re.findall(r'https?[^"\'<> ]+',content,re.I)
    vals=[]
    for v in urls:
        v=v.replace("&amp;","&").replace("\\/","/")
        if any(x in v.lower() for x in [".mp3", ".m4a", ".aac", ".m3u8", ".mpd", "heli.err.ee", "download"]):
            if v not in vals: vals.append(v)
    for v in vals[:60]: print("HTML_MEDIA",v)
    browser.close()

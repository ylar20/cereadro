#!/usr/bin/env python3
import json
import re
from playwright.sync_api import sync_playwright

LIST_URL = "https://arhiiv.err.ee/audio/seeria/rahva-oma-kaitse?limit=500&sort=old"
MONTHS = {"jaanuar":1,"veebruar":2,"märts":3,"aprill":4,"mai":5,"juuni":6,"juuli":7,"august":8,"september":9,"oktoober":10,"november":11,"detsember":12}

def year_of(v):
    if isinstance(v, int): return v
    m = re.search(r"\b(19|20)\d{2}\b", str(v))
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
    series_data={}
    def list_resp(resp):
        if "/api/v1/series/audio/rahva-oma-kaitse" in resp.url:
            try: series_data.update(resp.json())
            except: pass
    page.on("response", list_resp)
    page.goto(LIST_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)
    entries=(series_data.get("activeList") or {}).get("data") or []
    old=[e for e in entries if year_of(e.get("date")) in range(2005,2010)]
    print("MATCHING_COUNT_IN_FIRST_500",len(old))
    if not old: raise SystemExit("No 2005-2009 entries found")
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
            try:
                data=resp.json()
            except: return
            ms=media_strings(data)
            if ms or "arhiiv.err.ee/api" in u:
                captured.append((u, list(data.keys())[:30] if isinstance(data,dict) else ["list"], ms))
    ep.on("response",ep_resp)
    ep.goto(ep_url,wait_until="domcontentloaded",timeout=60000)
    ep.wait_for_timeout(8000)
    print("CAPTURED_RESPONSES",len(captured))
    for u,keys,ms in captured[:30]:
        print("API",u)
        print("KEYS",keys)
        for path,s in ms[:20]: print("MEDIA",path,s)
    content=ep.content()
    for pat in [r'https?[^"\'<> ]+\.(?:mp3|m4a|aac|m3u8|mpd)[^"\'<> ]*', r'https?[^"\'<> ]*heli\.err\.ee[^"\'<> ]*']:
        vals=[]
        for v in re.findall(pat,content,re.I):
            v=v.replace("&amp;","&").replace("\\/","/")
            if v not in vals: vals.append(v)
        for v in vals[:30]: print("HTML_MEDIA",v)
    browser.close()

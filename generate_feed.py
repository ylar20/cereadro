#!/usr/bin/env python3
import html
import json
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

LIST_URL="https://arhiiv.err.ee/audio/seeria/rahva-oma-kaitse?limit=500&sort=old"
SERIES_API="https://arhiiv.err.ee/api/v1/series/audio/rahva-oma-kaitse"
BASE="https://arhiiv.err.ee"
OUT=Path("feed.xml")

MONTHS={"jaanuar":1,"veebruar":2,"märts":3,"aprill":4,"mai":5,"juuni":6,"juuli":7,"august":8,"september":9,"oktoober":10,"november":11,"detsember":12}

def year_of(v):
    if isinstance(v,int): return v
    m=re.search(r"\b(?:19|20)\d{2}\b",str(v))
    return int(m.group(0)) if m else None

def parse_date(v):
    s=str(v).strip().lower()
    m=re.match(r"(\d{1,2})\.\s*([a-zõäöü]+)\s+((?:19|20)\d{2})",s)
    if m and m.group(2) in MONTHS:
        return datetime(int(m.group(3)),MONTHS[m.group(2)],int(m.group(1)),12,0,tzinfo=timezone.utc)
    y=year_of(v)
    return datetime(y,1,1,12,0,tzinfo=timezone.utc) if y else None

def esc(v): return html.escape(str(v or ""),quote=True)

def duration_from_metadata(md):
    for section in (md or {}).get("data") or []:
        for row in section.get("data") or []:
            if row.get("label")=="Kestus": return row.get("value") or ""
    return ""

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page()
    page.goto(LIST_URL,wait_until="domcontentloaded",timeout=60000)
    page.wait_for_timeout(2500)

    entries=[]
    for n in range(1,8):
        r=page.evaluate("""async ({api,n})=>{const body=new URLSearchParams({limit:'500',page:String(n),sort:'old',all:'false'});const x=await fetch(api,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'},body});return {status:x.status,text:await x.text()}}""",{"api":SERIES_API,"n":n})
        if r["status"]!=200: raise RuntimeError(f"ERR series API page {n}: {r['status']}")
        d=json.loads(r["text"]); block=d.get("activeList") or {}; batch=block.get("data") or []
        entries.extend(batch)
        if len(batch)<500: break

    entries=[e for e in entries if year_of(e.get("date")) in range(2005,2010)]
    print("Archive entries 2005-2009:",len(entries))
    if not entries: raise RuntimeError("No matching archive entries")

    episodes=[]
    for i,e in enumerate(entries,1):
        slug=e.get("url")
        api=f"{BASE}/api/v1/content/audio/{slug}"
        r=page.evaluate("""async u=>{const x=await fetch(u);return {status:x.status,text:await x.text()}}""",api)
        if r["status"]!=200:
            print("SKIP",slug,"status",r["status"]); continue
        d=json.loads(r["text"]); info=d.get("info") or {}; media=d.get("media") or {}; src=media.get("src") or {}
        hls=src.get("hls") or ""
        if hls.startswith("//"): hls="https:"+hls
        if not hls:
            print("SKIP",slug,"no HLS"); continue
        dt=parse_date(info.get("dateCombined") or e.get("date"))
        if not dt: continue
        duration=duration_from_metadata(d.get("metadata"))
        page_url=info.get("fullUrl") or f"{BASE}/audio/vaata/{slug}"
        synopsis=info.get("description") or info.get("synopsis") or "ERR arhiivi saade Rahva oma kaitse."
        episodes.append({"id":info.get("id") or e.get("fileId") or slug,"date":dt,"date_text":info.get("dateCombined") or e.get("date"),"title":info.get("title") or e.get("heading") or "Rahva oma kaitse","page":page_url,"hls":hls,"duration":duration,"description":synopsis})
        if i%25==0: print("Resolved",i,"of",len(entries))
    browser.close()

episodes.sort(key=lambda x:x["date"],reverse=True)
print("Playable episodes:",len(episodes))

items=[]
for e in episodes:
    title=f"Rahva oma kaitse — {e['date_text']}"
    items.append(f'''\n    <item>\n      <title>{esc(title)}</title>\n      <link>{esc(e['page'])}</link>\n      <guid isPermaLink="false">err-rokk-{esc(e['id'])}</guid>\n      <pubDate>{format_datetime(e['date'])}</pubDate>\n      <description>{esc(e['description'])}</description>\n      <enclosure url="{esc(e['hls'])}" length="0" type="audio/mp4" />\n      <itunes:duration>{esc(e['duration'])}</itunes:duration>\n      <itunes:explicit>false</itunes:explicit>\n    </item>''')

now=format_datetime(datetime.now(timezone.utc))
feed=f'''<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:content="http://purl.org/rss/1.0/modules/content/">\n  <channel>\n    <title>Rahva oma kaitse — arhiiv 2005–2009</title>\n    <link>{esc(LIST_URL)}</link>\n    <description>Isiklik mugavusvoog ERR arhiivis avalikult kuulatavatele Rahva oma kaitse saadetele aastatest 2005–2009. Audio striimitakse otse ERR serveritest.</description>\n    <language>et</language>\n    <lastBuildDate>{now}</lastBuildDate>\n    <itunes:author>ERR</itunes:author>\n    <itunes:explicit>false</itunes:explicit>\n    <itunes:category text="Comedy" />\n    {''.join(items)}\n  </channel>\n</rss>\n'''
OUT.write_text(feed,encoding="utf-8")

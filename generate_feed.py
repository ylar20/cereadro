#!/usr/bin/env python3
import json
from playwright.sync_api import sync_playwright

EP_URL = "https://arhiiv.err.ee/audio/vaata/rahva-oma-kaitse-rahva-oma-kaitse-152479"
API_URL = "https://arhiiv.err.ee/api/v1/content/audio/rahva-oma-kaitse-rahva-oma-kaitse-152479"

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page()
    page.goto(EP_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    result=page.evaluate("""async (u) => {const r=await fetch(u); return {status:r.status,text:await r.text()}}""", API_URL)
    print("CONTENT_STATUS",result["status"])
    d=json.loads(result["text"])
    print("INFO",json.dumps(d.get("info"),ensure_ascii=False,indent=2)[:12000])
    print("MEDIA",json.dumps(d.get("media"),ensure_ascii=False,indent=2)[:12000])
    print("METADATA",json.dumps(d.get("metadata"),ensure_ascii=False,indent=2)[:8000])
    print("DESCRIPTION",json.dumps(d.get("description"),ensure_ascii=False,indent=2)[:8000])
    print("LINKS")
    for a in page.locator("a").all():
        try:
            href=a.get_attribute("href")
            txt=(a.inner_text() or "").strip()
            if href and any(k in (href+" "+txt).lower() for k in ["download","laadi","mp3","m4a","audio"]):
                print(txt[:120],href)
        except: pass
    browser.close()

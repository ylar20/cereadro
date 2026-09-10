#!/usr/bin/env python3
import json
from playwright.sync_api import sync_playwright

URL = "https://arhiiv.err.ee/audio/seeria/rahva-oma-kaitse?limit=500&sort=old"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    seen = []

    def on_response(resp):
        u = resp.url
        ct = (resp.headers.get("content-type") or "").lower()
        if "json" not in ct and "/api/" not in u:
            return
        try:
            data = resp.json()
        except Exception:
            return
        if not isinstance(data, (dict, list)):
            return
        text = json.dumps(data, ensure_ascii=False)
        if any(k in text.lower() for k in ["rahva oma kaitse", "rahva-oma-kaitse", "seriesid", "activelist"]):
            seen.append((u, data))

    page.on("response", on_response)
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000)
    print(f"Captured {len(seen)} relevant JSON responses")
    for i, (u, data) in enumerate(seen[:20]):
        print(f"RESPONSE {i}: {u}")
        if isinstance(data, dict):
            print("TOP_KEYS", list(data.keys())[:40])
            print(json.dumps(data, ensure_ascii=False)[:5000])
        else:
            print("LIST_LEN", len(data))
            print(json.dumps(data[:3], ensure_ascii=False)[:5000])
    browser.close()

if not seen:
    raise SystemExit("No relevant ERR JSON API response captured")

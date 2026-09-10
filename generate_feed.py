#!/usr/bin/env python3
import html
import json
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

PAGE_URL = "https://arhiiv.err.ee/audio/seeria/rahva-oma-kaitse"
OUT = Path("feed.xml")

# ERR's legacy series extractor expects the internal series identifier. Resolve
# it from the public page first because the slug-based API currently returns 500.
req = urllib.request.Request(PAGE_URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as r:
    page = r.read().decode("utf-8", "replace")

patterns = [
    r'"seriesId"\s*:\s*"?(\d+)',
    r'"series_id"\s*:\s*"?(\d+)',
    r'\bseriesId\s*[=:]\s*["\']?(\d+)',
    r'\bseries_id\s*[=:]\s*["\']?(\d+)',
]
series_id = None
for pat in patterns:
    m = re.search(pat, page, re.I)
    if m:
        series_id = m.group(1)
        break
if not series_id:
    # Dump likely identifiers into logs for diagnostics without exposing page body.
    ids = sorted(set(re.findall(r'(?i)(?:series|content)[A-Za-z_]*[^0-9]{0,10}(\d{3,10})', page)))
    raise SystemExit(f"Could not resolve series ID; candidate IDs: {ids[:30]}")

print(f"Resolved ERR series ID: {series_id}")
SERIES_URL = f"https://arhiiv.err.ee/audio/seeria/{series_id}"

cmd = [
    "yt-dlp",
    "--skip-download",
    "--yes-playlist",
    "--dateafter", "20050101",
    "--datebefore", "20091231",
    "-f", "bestaudio",
    "--dump-json",
    SERIES_URL,
]

p = subprocess.run(cmd, text=True, capture_output=True)
if p.returncode != 0:
    raise SystemExit(p.stderr)

episodes = []
for line in p.stdout.splitlines():
    line = line.strip()
    if not line.startswith("{"):
        continue
    d = json.loads(line)
    upload_date = d.get("upload_date") or ""
    if len(upload_date) != 8 or not ("20050101" <= upload_date <= "20091231"):
        continue
    media_url = d.get("url")
    ext = d.get("ext") or "mp3"
    filesize = d.get("filesize") or d.get("filesize_approx") or 0
    if not media_url:
        reqs = d.get("requested_downloads") or []
        if reqs:
            media_url = reqs[0].get("url")
            ext = reqs[0].get("ext") or ext
            filesize = reqs[0].get("filesize") or reqs[0].get("filesize_approx") or filesize
    if not media_url:
        continue
    dt = datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=timezone.utc)
    episodes.append({
        "date": dt,
        "title": d.get("title") or d.get("episode") or "Rahva oma kaitse",
        "description": d.get("description") or "ERR arhiivi saade Rahva oma kaitse.",
        "page": d.get("webpage_url") or d.get("original_url") or PAGE_URL,
        "media": media_url,
        "ext": ext,
        "length": int(filesize or 0),
        "id": d.get("id") or media_url,
        "duration": int(d.get("duration") or 0),
    })

episodes.sort(key=lambda x: x["date"], reverse=True)

def x(s): return html.escape(str(s or ""), quote=True)
def mime(ext):
    return {"mp3":"audio/mpeg","m4a":"audio/mp4","mp4":"audio/mp4","aac":"audio/aac","ogg":"audio/ogg","opus":"audio/ogg"}.get((ext or "").lower(), "audio/mpeg")

items = []
for e in episodes:
    dur=e["duration"]; h,rem=divmod(dur,3600); m,s=divmod(rem,60); dur_s=f"{h:02d}:{m:02d}:{s:02d}" if dur else ""
    items.append(f'''\n    <item>\n      <title>{x(e['title'])}</title>\n      <link>{x(e['page'])}</link>\n      <guid isPermaLink="false">{x(e['id'])}</guid>\n      <pubDate>{format_datetime(e['date'])}</pubDate>\n      <description>{x(e['description'])}</description>\n      <enclosure url="{x(e['media'])}" length="{e['length']}" type="{mime(e['ext'])}" />\n      <itunes:duration>{x(dur_s)}</itunes:duration>\n      <itunes:explicit>false</itunes:explicit>\n    </item>''')

now = format_datetime(datetime.now(timezone.utc))
feed = f'''<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">\n  <channel>\n    <title>Rahva oma kaitse — ERR arhiiv 2005–2009</title>\n    <link>{PAGE_URL}</link>\n    <description>Isiklik mugavusvoog ERR arhiivis avalikult kättesaadavatele Rahva oma kaitse saadetele aastatest 2005–2009. Audio jääb ERR serveritesse.</description>\n    <language>et</language>\n    <lastBuildDate>{now}</lastBuildDate>\n    <itunes:author>ERR</itunes:author>\n    <itunes:explicit>false</itunes:explicit>\n    {''.join(items)}\n  </channel>\n</rss>\n'''
OUT.write_text(feed, encoding="utf-8")
print(f"Wrote {OUT} with {len(episodes)} episodes")

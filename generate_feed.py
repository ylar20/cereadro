#!/usr/bin/env python3
import html
import json
import subprocess
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

SERIES_URL = "https://arhiiv.err.ee/audio/seeria/rahva-oma-kaitse?limit=500&sort=old"
OUT = Path("feed.xml")

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
        req = d.get("requested_downloads") or []
        if req:
            media_url = req[0].get("url")
            ext = req[0].get("ext") or ext
            filesize = req[0].get("filesize") or req[0].get("filesize_approx") or filesize
    if not media_url:
        continue

    dt = datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=timezone.utc)
    episodes.append({
        "date": dt,
        "title": d.get("title") or d.get("episode") or "Rahva oma kaitse",
        "description": d.get("description") or "ERR arhiivi saade Rahva oma kaitse.",
        "page": d.get("webpage_url") or d.get("original_url") or "https://arhiiv.err.ee/audio/seeria/rahva-oma-kaitse",
        "media": media_url,
        "ext": ext,
        "length": int(filesize or 0),
        "id": d.get("id") or media_url,
        "duration": int(d.get("duration") or 0),
    })

episodes.sort(key=lambda x: x["date"], reverse=True)

def x(s):
    return html.escape(str(s or ""), quote=True)

def mime(ext):
    ext = (ext or "").lower()
    return {
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
        "mp4": "audio/mp4",
        "aac": "audio/aac",
        "ogg": "audio/ogg",
        "opus": "audio/ogg",
    }.get(ext, "audio/mpeg")

items = []
for e in episodes:
    dur = e["duration"]
    h, rem = divmod(dur, 3600)
    m, s = divmod(rem, 60)
    dur_s = f"{h:02d}:{m:02d}:{s:02d}" if dur else ""
    items.append(f"""
    <item>
      <title>{x(e['title'])}</title>
      <link>{x(e['page'])}</link>
      <guid isPermaLink="false">{x(e['id'])}</guid>
      <pubDate>{format_datetime(e['date'])}</pubDate>
      <description>{x(e['description'])}</description>
      <enclosure url="{x(e['media'])}" length="{e['length']}" type="{mime(e['ext'])}" />
      <itunes:duration>{x(dur_s)}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>""")

now = format_datetime(datetime.now(timezone.utc))
feed = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Rahva oma kaitse — ERR arhiiv 2005–2009</title>
    <link>https://arhiiv.err.ee/audio/seeria/rahva-oma-kaitse</link>
    <description>Isiklik mugavusvoog ERR arhiivis avalikult kättesaadavatele Rahva oma kaitse saadetele aastatest 2005–2009. Audio jääb ERR serveritesse.</description>
    <language>et</language>
    <lastBuildDate>{now}</lastBuildDate>
    <itunes:author>ERR</itunes:author>
    <itunes:explicit>false</itunes:explicit>
    {''.join(items)}
  </channel>
</rss>
'''

OUT.write_text(feed, encoding="utf-8")
print(f"Wrote {OUT} with {len(episodes)} episodes")

#!/usr/bin/env python3
import re
import urllib.parse
import urllib.request

URL="https://arhiiv.err.ee/audio/vaata/rahva-oma-kaitse-rahva-oma-kaitse-152479"
headers={"User-Agent":"Mozilla/5.0"}
def get(url):
    req=urllib.request.Request(url,headers=headers)
    with urllib.request.urlopen(req,timeout=30) as r: return r.read().decode("utf-8","replace")

html=get(URL)
scripts=[]
for src in re.findall(r'<script[^>]+src=["\']([^"\']+)',html,re.I):
    u=urllib.parse.urljoin(URL,src)
    if u not in scripts: scripts.append(u)
print("SCRIPTS",len(scripts))
needles=["downloadUrl","downloadurl","/api/v1/content/","filename","vod.err.ee","RMARHIIV","download"]
for u in scripts:
    try: text=get(u)
    except Exception as ex:
        print("FAIL",u,type(ex).__name__); continue
    low=text.lower()
    hits=[n for n in needles if n.lower() in low]
    if not hits: continue
    print("SCRIPT",u,"HITS",hits,"SIZE",len(text))
    for needle in hits:
        pos=low.find(needle.lower())
        for _ in range(3):
            if pos<0: break
            a=max(0,pos-500); b=min(len(text),pos+900)
            print("CONTEXT",needle,text[a:b].replace("\n"," ")[:1400])
            pos=low.find(needle.lower(),pos+len(needle))

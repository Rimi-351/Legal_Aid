#!/usr/bin/env python3
"""
Quick connectivity test for official Bangladesh legal portals:
- http://bdlaws.minlaw.gov.bd/
- https://legislativediv.gov.bd/
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

urls = [
    "http://bdlaws.minlaw.gov.bd/",
    "http://bdlaws.minlaw.gov.bd/act-26.html",  # Contract Act
    "https://legislativediv.gov.bd/"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

for u in urls:
    try:
        req = urllib.request.Request(u, headers=headers)
        with urllib.request.urlopen(req, timeout=12, context=ctx) as r:
            content_type = r.headers.get("Content-Type")
            print(f"[+] {u} -> Status: {r.status}, Content-Type: {content_type}")
    except Exception as e:
        print(f"[X] {u} -> Error: {e}")

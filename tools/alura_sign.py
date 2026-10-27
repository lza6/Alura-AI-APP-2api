#!/usr/bin/env python3
"""
Alura AI — aperogroup RSA 签名链路验证工具
签名算法: signature = Base64(RSA-PKCS1v15(img_pub_key, "{ms_ts}@@@{img_api_key}@@@{uuid_nodash}"))
验证: presign → S3 PUT → 生成提交 → 轮询, 全链路无设备绑定, 客户端可完全自签。
用法: python alura_sign.py <remote_config.json> [image.jpg] [prompt]
"""
import base64, json, sys, uuid, time, urllib.request, ssl
from cryptography.hazmat.primitives.serialization import load_der_public_key
from cryptography.hazmat.primitives.asymmetric import padding

def load_rc(path):
    return json.load(open(path, encoding="utf-8"))["entries"]

def sig_headers(RC):
    key = load_der_public_key(base64.b64decode("".join(RC["img_pub_key"].split())))
    ts = str(int(time.time() * 1000))
    plain = f'{ts}@@@{RC["img_api_key"]}@@@{uuid.uuid4().hex}'
    return {"x-api-signature": base64.b64encode(key.encrypt(plain.encode(), padding.PKCS1v15())).decode(),
            "x-api-timestamp": ts, "x-api-bundleid": "com.lightsail.alurachat",
            "App-name": RC["app_name_in_api"], "country-code": "IN",
            "app-version": "1.3.9", "Content-Type": "application/json"}

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

def full_chain(RC, img_bytes, prompt="cinematic slow zoom"):
    # 1. presign
    r = urllib.request.urlopen(urllib.request.Request(RC["vid_pre_sign_link"], headers=sig_headers(RC)), context=CTX, timeout=30)
    pd = json.loads(r.read())["data"]
    # 2. S3 PUT
    req = urllib.request.Request(pd["url"], data=img_bytes, method="PUT", headers={"Content-Type": "image/jpeg"})
    urllib.request.urlopen(req, context=CTX, timeout=120)
    # 3. 提交生成
    body = json.dumps({"notificationProvider": "fcm", "notificationId": "e" * 152,
                       "files": [pd["path"]], "model": "inhouse", "mode": "i2v",
                       "positivePrompt": prompt, "positivePrompt2": "",
                       "frameRate": 20, "frameNumber": 101, "raw": True}).encode()
    r = urllib.request.urlopen(urllib.request.Request(RC["vid_edit_base_url"], data=body, headers=sig_headers(RC)), context=CTX, timeout=300)
    sub = json.loads(r.read())
    vid = sub["data"]["videoId"]
    print("videoId:", vid, "→ 轮询中 (典型 5-8 分钟)...")
    # 4. 轮询
    for _ in range(40):
        time.sleep(20)
        r = urllib.request.urlopen(urllib.request.Request(RC["vid_fetch_base_url"] + vid, headers=sig_headers(RC)), context=CTX, timeout=60)
        j = json.loads(r.read())
        res = j.get("data", {}).get("result", {})
        if res.get("videoStatus") == "completed":
            return res["resultFile"]
        print("  ...", res.get("videoStatus", j.get("statusCode")))
    return None

if __name__ == "__main__":
    RC = load_rc(sys.argv[1])
    img = open(sys.argv[2], "rb").read() if len(sys.argv) > 2 else None
    prompt = sys.argv[3] if len(sys.argv) > 3 else "cinematic slow zoom"
    if img:
        print("result:", full_chain(RC, img, prompt))
    else:
        r = urllib.request.urlopen(urllib.request.Request(RC["img_pre_sign_link"], headers=sig_headers(RC)), context=CTX, timeout=30)
        print("presign OK →", r.read()[:200])

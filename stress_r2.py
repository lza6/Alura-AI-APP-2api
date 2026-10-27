#!/usr/bin/env python3
"""Alura 2API 深度压测 R2 — 分级并发/延迟分布/错误分类/长稳"""
import base64, json, statistics, sys, time, urllib.request, ssl, concurrent.futures as cf
from collections import Counter

BASE = "http://127.0.0.1:8907"
JPG = open(__file__.replace('stress_test.py','').replace('stress_r2.py','') or '.', 'rb') if False else None
# 256x256 JPEG 测试图
import io
from PIL import Image
_b = io.BytesIO(); Image.new('RGB', (256, 256), (140, 160, 190)).save(_b, 'JPEG', quality=88)
JPG_B64 = base64.b64encode(_b.getvalue()).decode()

def call(path, payload, timeout=300):
    t0 = time.time()
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read()), time.time() - t0
    except Exception as ex:
        body = getattr(ex, 'read', lambda: b'')()[:200]
        return getattr(ex, 'code', 0), {"error": str(ex), "body": body.decode(errors='replace')}, time.time() - t0

def run(name, path, payload_fn, n, workers, ok_check, timeout=300):
    lat = []; ok = 0; errs = Counter(); results = []
    def one(i):
        code, data, dt = call(path, payload_fn(i), timeout)
        return code, data, dt
    t0 = time.time()
    with cf.ThreadPoolExecutor(workers) as ex:
        for code, data, dt in ex.map(one, range(n)):
            lat.append(dt); results.append((code, data))
            if ok_check(code, data): ok += 1
            else:
                key = f"HTTP{code}:{(data.get('error','') if isinstance(data,dict) else str(data))[:60]}"
                errs[key] += 1
    wall = time.time() - t0
    lat_s = sorted(lat)
    p50 = statistics.median(lat); p95 = lat_s[int(len(lat_s)*0.95)-1] if n > 1 else lat_s[0]
    p99 = lat_s[int(len(lat_s)*0.99)-1] if n > 1 else lat_s[0]
    print(f"[{name}] n={n} c={workers} 成功={ok}/{n} ({100*ok/n:.0f}%) "
          f"p50={p50:.2f}s p95={p95:.2f}s p99={p99:.2f}s max={max(lat):.2f}s 吞吐={n/wall:.2f}req/s")
    if errs: print("   错误分布:", dict(errs))
    return ok, n

if __name__ == "__main__":
    print("== Alura 2API 深度压测 R2 ==", time.strftime("%F %T"))
    # T1 chat 10 并发 x 20
    run("T1 chat c10", "/v1/chat/completions",
        lambda i: {"messages":[{"role":"user","content":"reply: ok"}], "max_tokens":10},
        n=20, workers=10, ok_check=lambda c,d: c==200 and d.get("choices"))
    # T2 chat 20 并发 x 40 (上游频控探测)
    run("T2 chat c20", "/v1/chat/completions",
        lambda i: {"messages":[{"role":"user","content":"say hi"}], "max_tokens":10},
        n=40, workers=20, ok_check=lambda c,d: c==200)
    # T3 chat 长输出
    run("T3 chat 长输出", "/v1/chat/completions",
        lambda i: {"messages":[{"role":"user","content":"write a 300 word story about a robot"}], "max_tokens":600},
        n=3, workers=3, ok_check=lambda c,d: c==200)
    # T4 image edit 5 并发 (真实生成, 慢)
    run("T4 imgedit c5", "/alura/image/edit",
        lambda i: {"image_base64": JPG_B64, "prompt": f"make it color #{i:06x} tone"},
        n=5, workers=5, ok_check=lambda c,d: c==200 and d.get("url"))
    # T5 image edit 10 并发
    run("T5 imgedit c10", "/alura/image/edit",
        lambda i: {"image_base64": JPG_B64, "prompt": "sharpen"},
        n=10, workers=10, ok_check=lambda c,d: c==200 and d.get("url"))
    # T6 video 提交 3 并发 (只到提交层)
    run("T6 video submit c3", "/alura/video",
        lambda i: {"image_base64": JPG_B64, "prompt": "slow zoom", "mode": "i2v",
                   "model": "inhouse", "frame_number": 101, "frame_rate": 20},
        n=3, workers=3, ok_check=lambda c,d: c==200 and isinstance(d.get("data") or {}, dict) and (d.get("data") or {}).get("videoId"))
    # T7 t2i 配额墙复核
    run("T7 t2i 复核", "/alura/txt2img", lambda i: {"prompt": "a cat"},
        n=1, workers=1, ok_check=lambda c,d: c==200 and d.get("status")=="success")
    print("done.")

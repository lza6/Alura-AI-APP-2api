# Alura AI APP 2api — 逆向报告与交付

> **Alura: AI Photo & Video Generator** (`com.lightsail.alurachat`) v1.5.7 (modded by PlatinumMods)
> Apero 旗下 AI 图像/视频/聊天订阅制 App。本项目对其上游协议做了完整还原，并交付 OpenAI 兼容 2API demo。

## 状态表

| 能力 | 上游 | 链路状态 | 备注 |
|---|---|---|---|
| 💬 Chat | `api.groq.com/openai/v1` | ✅ 打通 | RC 下发活 key，需 okhttp UA 过 CF；仅 `openai/gpt-oss-20b` 未被 org 封禁 |
| 🖼️ 图像编辑 | `api-img-gen-wrapper.aperogroup.ai/api/v5.1/qwen-editing` | ✅ **全链路真实出图** | presign→S3→POST，RSA 自签 |
| 🎬 图生视频 | `video-gen-core.aperogroup.ai/api/v5/image-2-video` | ✅ **全链路真实出片**（~7 分钟） | model=inhouse, mode=i2v, 101 帧 @20fps |
| 🌅 文生图 | `us-central1-prisam-ai.cloudfunctions.net` (ModelSLab 转售) | ⛔ 企业 plan 过期 | 配额墙，协议本身已还原 |

## 上游架构

几乎所有配置经 **Firebase Remote Config** 运行时下发（170 项），APK 仅存兜底值：

```
Remote Config entries
├── groq_base_url        = aHR0cHM6... (base64)  → https://api.groq.com/openai/v1/
├── DYEKEYNEW            = gsk_... (Groq 活 key)
├── image_generate_base_url → us-central1-prisam-ai.cloudfunctions.net/ (ModelSLab)
├── img_api_key / img_pub_key / t2i_key           → aperogroup 签名体系
├── img_edit_base_url / img_pre_sign_link         → qwen-editing v5.1
├── vid_edit_base_url / vid_pre_sign_link / vid_fetch_base_url → image-2-video v5
└── name_account_demo / password_demo             → PhotoCreator / PhotoCreator@469
```

**Remote Config 收割方法**（见 `tools/fetch_remote_config.py`）：

```
POST https://firebaseremoteconfig.googleapis.com/v1/projects/{proj}/namespaces/firebase:fetch?key={AIza_KEY}
body: {"app_id":"1:...:android:...","app_instance_id":"<32hex>","app_version":"157","sdk_version":"23.2.0"}
坑: 不带 ?key= → 403; body 带 country/locale 字段 → 400; 响应在 entries 字段
```

## RSA 签名体系（aperogroup 通用）

`x-api-signature` 等头的生成（还原自 `o/fk1.java g()`）：

```
signature = Base64( RSA-PKCS1v15( img_pub_key, "{ms_timestamp}@@@{img_api_key}@@@{uuid_nodash}" ) )
```

- `img_pub_key` / `img_api_key` 均为 RC 下发；客户端可完全自签，**无设备绑定**（不同于 Seekee 的 deviceId 注册体系）
- 请求头：`x-api-signature / x-api-timestamp / x-api-bundleid / App-name / country-code / app-version(写死1.3.9)`

### 图像编辑 (qwen-editing)
```
GET  presigned-link        (签名头) → {data:{url(S3预签名), path}}
PUT  url  (image/jpeg)              → 200
POST qwen-editing                  → {files:[path], mode:"IMAGE_EDITING", positivePrompt:"..."}
     注意: files 必须是数组，否则 400 ERR16；响应 data.url 为成品
```

### 图生视频 (image-2-video)
```
GET  presigned-link → PUT S3 → POST image-2-video:
     {notificationProvider:"fcm", notificationId:"<FCM token, 152字符, 可随意>",
      files:[path], model:"inhouse", mode:"i2v",
      positivePrompt, positivePrompt2:"", frameRate:20, frameNumber:101, raw:true}
     注意: 不要传 width/height (400 ERR16)
GET  image-2-video/video/{videoId} 轮询 (20s 间隔, 典型 5-8 分钟, videoTimeout=600s)
     → data.result.videoStatus=="completed" + data.result.resultFile (mp4 URL)
```

### Chat (Groq)
```
POST /openai/v1/chat/completions, Bearer {DYEKEYNEW}
坑① CF 指纹墙: python/curl 默认 UA → 403 error 1010; 须 User-Agent: okhttp/4.12.0
坑② org 封模型: 12 个模型里 11 个 model_permission_blocked_org, 仅 openai/gpt-oss-20b 可用
坑③ BuildConfig.DYEKEY 是编译兜底, RC 的 DYEKEYNEW 才是活 key
```

## 深度压测 (R2, 实测数据)

| 场景 | 并发 | 结果 | p50 | p95 | 吞吐 |
|---|---|---|---|---|---|
| chat | 10 | 20/20 (100%) | 0.99s | 3.33s | 3.9 req/s |
| chat | 20 | 40/40 (100%) | 1.08s | 2.16s | 10.2 req/s |
| chat 长输出 | 3 | 3/3 | 1.68s | — | — |
| 图像编辑 | 5 | 5/5 (100%) | 15.7s | 17.4s | 0.24 req/s |
| 图像编辑 | 10 | 10/10 (100%) | 18.5s | 24.1s | 0.41 req/s |
| 视频提交 | 3 | 3/3 (100%) | 5.9s | — | 0.5 req/s |
| 视频出片 | 1 | ✅ completed | ~7 min | — | — |
| t2i | 1 | ⛔ plan 过期 | — | — | — |

**结论：无 429/频控（20 并发 chat、10 并发图像编辑均零失败），瓶颈在上游生成耗时。风险：key 是 App 开发者的 Groq org key，随时可能轮换/封禁。**

## Demo 截图

Chat（真实 Groq 回复）：
![chat](demo_chat.png)

图像编辑（presign→S3→qwen-editing 真实出图）：
![imgedit](demo_imgedit.png)

## 使用

```bash
pip install cryptography pillow
# 从 APK 收割 RC 并保存 remote_config.json
python tools/fetch_remote_config.py "Alura-1.5.7.apk"
# 启动 2API demo (默认 127.0.0.1:8907)
python demo_server.py
#   POST /v1/chat/completions  (OpenAI 兼容)
#   POST /alura/image/edit     {image_base64, prompt}
#   POST /alura/video          {image_base64, prompt} → GET /alura/video/<id>
# 全链路签名验证 (视频出片端到端)
python tools/alura_sign.py remote_config.json test.jpg "cinematic slow zoom"
```

## 逆向证据链

- 反编译：jadx (`classes6.dex` 为主)
- 关键类：`api/RetrofitClient`（BASE_URL=b64(groq_base_url)、groqAuthInterceptor→Bearer DYEKEY）、`api/ImageApiService`（txt2img/img2img form 接口, key=t2i_key）、`o/fk1.g()`（RSA 签名）、`o/tr1`（qwen-editing 请求体）、`aperovideo/VideoGenViewModel`（视频链路）、`utils/RemoteConfigUtils`（RC 全键名）
- 签名锚点：`BaseUtilsKt.decodeFromBase64(getGroqUrl())` — base URL 是 base64 藏的
- Firebase 凭证：resources.arsc (`AIzaSyDceZdjZjh33mg77wi4g5JcZ-3Fo4sTYbw`, project 705388983171)

## 声明

仅供安全研究与协议学习。所有上游服务归 Apero/Groq/ModelSLab 各自所有；key 来自公开分发的 APK，请勿用于商业用途。视频/图像生成会消耗上游真实算力，请克制使用。

## License

MIT

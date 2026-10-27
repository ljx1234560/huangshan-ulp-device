# VelaPet AI integration plan

Last reviewed: 2026-10-25. This is a migration plan for the SiFli-SDK/RT-Thread product, not an openVela integration guide. The historical implementation under `member_code/组员五/后端与AI开发/后端与AI开发` remains read-only input. Its reviewed text-chat subset has now been migrated into the product repository at `host/ai-backend/`; the historical image pipeline and POSIX device bridge were not copied.

## What exists and what is proven

- The current product firmware has a local LVGL screen and a working custom BLE GATT read/write characteristic. The characteristic is a four-byte diagnostic value, **not** an Internet link or AI protocol. Phone discovery, connection, write, and read were proven; automatic advertising restart after disconnect has a newly flashed SDK-option fix but still needs a phone disconnect/reconnect check.
- The external ESP-01S is not installed. Its two-pin GH1.25 pigtail cannot carry the module's power, UART, and control signals. Do not attach or power the ESP until `wifi-esp01s.md`'s electrical gate is satisfied.
- The historical Python FastAPI backend implements health, chat, and asynchronous image jobs. Its 20 local tests and full local HTTP smoke test passed again on 2026-10-25. The product-owned text backend adds safe loopback binding, a non-loopback authentication gate, selectable MiMo/DeepSeek OpenAI-compatible providers, clearer provider errors, and local fallback.
- The existing MiMo key reached the provider successfully. The historical `mimo-v2.5-pro` configuration returned HTTP 400 `Unsupported model`; the account's `/v1/models` list instead exposed `mimo-v2.6-flash`, `mimo-v2.6-pro`, and `mimo-v2.6-pro-ultraspeed` for chat. A minimal `mimo-v2.6-flash` request then returned HTTP 402, so network and authentication are proven but the account currently has no usable quota. The product backend maps this to `MIMO_PAYMENT_REQUIRED` and still returns a usable `source=local_fallback` HTTP 200 response.
- DeepSeek is now the selected host provider. The cost-controlled request profile uses the current `deepseek-flash` model, disables thinking, caps output at 256 tokens, and requests JSON output. One live bounded request returned a valid short Chinese NOVA reply with `source=deepseek` and no error code. The real key exists only in the ignored backend `.env`; because it was supplied through chat, rotate it before longer-lived or shared use.
- The old C AI client defines useful JSON contracts and four HTTP transport callbacks. The old bridge depends on `pthread`, the old VelaPet ABI/UI lifecycle, and `/data/agent/...` paths; do not compile it unchanged into the RT-Thread product.

## Target boundary

```text
pet state and UI on SF32LB52
  -> asynchronous AI service (queue, timeout, offline fallback)
  -> transport-neutral HTTPS/HTTP client
  -> verified network adapter: external ESP-01S UART, or later Bluetooth PAN
  -> VelaPet backend on a reachable host
  -> optional model/image provider (keys stay on backend)
```

The board owns authoritative pet state, task completion, EXP, and rewards. The backend receives a bounded snapshot and returns copy for the UI; it must not overwrite local progression. No cloud operation may block the LVGL thread. The offline UI and pet rules must continue to work when the backend or network is absent.

## Existing backend contract worth retaining

| Operation | Historical endpoint and behavior | Product-side rule |
| --- | --- | --- |
| Health | `GET /health`, no token; includes provider and `auth_required` state | Development check only; reject an accidentally unauthenticated LAN deployment |
| Short text reply | `POST /api/v1/chat` with JSON and `X-VelaPet-Token` | Start here; timeout and display `reply` from `deepseek`, `mimo`, or `local_fallback` |
| Image request | `POST /api/v1/pet-assets/jobs` multipart upload, HTTP 202 | Later milestone; never retry a potentially billable creation automatically after an ambiguous timeout |
| Job status | `GET /api/v1/pet-assets/jobs/{job_id}` | Poll with bounded total wait; retain old asset on failure |
| Image download | `GET /api/v1/pet-assets/{job_id}/files/{filename}` | Verify size and SHA-256, replace atomically, then invalidate LVGL image cache on UI thread |

The chat request uses `device_id`, `prompt_type` (`cheer`, `task`, `level`, `greeting`, `custom`), optional `message`, `locale`, `max_chars`, and a pet `context`. The historical context has `pet_name`, level/EXP, title, skins, total steps, consecutive days, daily progress, and task progress. It does **not** contain a trustworthy `today_steps`; do not infer that from `total_steps`. `max_chars` is 16–80 by the backend model, with 50 recommended for the watch. Character count is Unicode, whereas firmware buffers must be sized in UTF-8 bytes.

The response contains `request_id`, `reply`, `intent`, `emotion`, `source`, `reward`, `error_code`, and `created_at`. A cloud result uses `source=mimo` or `source=deepseek`; HTTP 200 with `source=local_fallback` and a non-null `error_code` can still be a usable reply. `reward.eligible` is only a suggestion; any eventual EXP grant must use a durable, locally validated `event_id` and cooldown/idempotency rule. Do not award EXP merely because a network packet was received.

The backend image contract contains `avatar`, `home`, and `skin` artifacts with `download_url`, `sha256`, `byte_size`, dimensions, and MIME type. Historical `device_path` values point to `/data/agent/assets/pet/...` and are **not** valid product storage paths. Treat those fields as untrusted suggestions, map each kind to a fixed product-owned filename, and only enable downloads after a writable filesystem and PNG/LVGL decode path pass validation. The old `skin_custom.png` is not automatically an equipable skin in the pet rules.

## Secure connection rules

- The model provider API key belongs on the backend only. Configure a distinct device token for the board; never embed a model key in firmware or commit a `.env` file. Select DeepSeek with `VELAPET_CHAT_PROVIDER=deepseek`, `DEEPSEEK_API_KEY`, and the current documented `deepseek-flash` model; provider changes do not alter the board-facing JSON contract.
- In the historical backend, no `VELAPET_DEVICE_TOKENS` means `auth_required=false`. Set a development token before binding to a LAN interface; verify `/health` reports `auth_required=true` before device use. The historical default bind address is `0.0.0.0:8000`, so an unconfigured run can be reachable beyond localhost.
- Use a literal, configured backend origin and a verified certificate/hostname for HTTPS. Do not disable TLS verification. Do not forward the device token across redirects to another host. Plain HTTP is only for a clearly isolated local development network, never for a real deployment.
- Limit JSON body/response sizes, validate schema and UTF-8, set independent connection and operation timeouts, and scrub tokens and private messages from UART logs.

## Minimal sequence to an on-device chat reply

1. **Host-only contract check — complete:** the historical 20-test suite and full HTTP smoke test pass. The product backend's seven tests, real loopback HTTP smoke test, and one bounded live `deepseek-flash` request pass. The ignored `.env` is loopback-only and no persistent server is currently running. Before LAN use, set a disposable device token, change the bind address deliberately, and verify `/health` reports `auth_required=true`.
2. **Port the local data boundary — core complete:** `src/app/velapet_core.*` is now the canonical platform-independent pet/task/reward core. The RT-Thread snapshot/serialization adapter remains to be written; fixed test context must not be presented as live sensor data.
3. **Bring up an IP route:** first pass the ESP electrical/AT gate, then association, IP, DNS, and a bounded backend health request. Bluetooth PAN is an alternative only after a real PAN/IP route is proven; the existing four-byte BLE GATT service cannot carry ordinary HTTP by itself. A phone companion relay would be a separate protocol and app deliverable.
4. **Implement a small RT-Thread AI client:** use an RT-Thread worker/queue and the SDK's available cJSON/webclient/TLS facilities only after enabling and validating them in the product build. Keep request construction, response parsing, transport, and LVGL presentation separate. Post results to the UI thread; free/cancel safely when pages change. Do not transplant the old `pthread` bridge wholesale.
5. **Prove one live round trip:** press CHAT, send a bounded `cheer` request, log request ID/status/source without secrets, and show the returned text. Test offline fallback and reconnect. Only then consider image upload/download, after storage and image decode are ready.

The SDK tree contains cJSON, webclient, and mbedTLS components, but their presence in source is not evidence that the current firmware enables them or has an IP transport. The host DeepSeek result is not a live board-to-backend round trip. Provider choice is intentionally not locked to the retired Xiaomi/openVela competition: DeepSeek is the current low-cost host choice, MiMo remains optional, and the local fallback is useful without any cloud account. A working provider is not sufficient for an on-watch result until the board has a verified IP adapter.

## Migration source map

- Backend routes and schemas: historical `app/main.py`, `app/models.py`, `app/config.py`, `app/services/chat.py`.
- Transport callback contract: historical `device/include/velapet_ai_client.h` and `device/src/velapet_ai_client.c`.
- UI bridge assumptions to replace: historical `device/src/velapet_ai_bridge.c`, `integration/frontend-ai.patch`, and `docs/交接代码问题清单.md`.
- Current product boundaries: `src/services/`, `src/ui/`, `docs/architecture.md`, `docs/wifi-esp01s.md`, and `docs/hardware-validation.md`.

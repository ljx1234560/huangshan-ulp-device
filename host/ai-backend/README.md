# VelaPet AI backend

This is the product-owned, text-chat subset migrated from the historical member
five delivery. The model API key stays here; firmware receives only a distinct
device token and calls `POST /api/v1/chat`.

## Local setup

From the repository root, reuse the isolated environment created by
`scripts/test-ai-backend.ps1`, then copy `.env.example` to `.env` and set:

- `VELAPET_DEVICE_TOKENS`: a random development device token;
- `VELAPET_CHAT_PROVIDER`: `deepseek` or `mimo`;
- the selected provider's backend-only API key and model.

For DeepSeek, use `DEEPSEEK_API_KEY` and the current documented model
`deepseek-flash`. For MiMo, use `MIMO_API_KEY`; its model availability is
account-specific. Never copy either key into firmware.

The low-cost DeepSeek profile uses `deepseek-flash`, disables thinking, caps
output at 256 tokens, and requests JSON output. One live bounded request passed
on 2026-10-25. Provider pricing and model availability can change, so recheck
the official provider documentation before a larger test campaign.

Start with `python host/ai-backend/run.py`. The default bind is loopback only.
Binding to `0.0.0.0` or a LAN address without a device token is rejected.

Run contract tests with `.\scripts\test-ai-backend.ps1`. From the backend
directory, `python tools/smoke_http.py` starts a temporary loopback server,
checks authentication and a fallback chat over real TCP, then stops it.
With a provider key set only in the process environment or ignored `.env`,
`python tools/live_chat_check.py` makes exactly one bounded text request and
prints the selected provider, model, source, error code, and short reply without
printing credentials.

## Contract

- `GET /health` is unauthenticated and reports configuration, not provider
  reachability.
- `POST /api/v1/chat` accepts the VelaPet context and `X-VelaPet-Token`.
- A usable HTTP 200 reply may have `source=local_fallback` and a non-null
  `error_code`. Provider failures never block the offline product path.
- `MIMO_PAYMENT_REQUIRED` means networking and authentication reached MiMo but
  the account has no usable quota. `MIMO_MODEL_UNAVAILABLE` means the configured
  model is not available to the account.
- DeepSeek failures use the same stable suffixes with a `DEEPSEEK_` prefix, for
  example `DEEPSEEK_AUTH_FAILED`, `DEEPSEEK_PAYMENT_REQUIRED`, and
  `DEEPSEEK_MODEL_UNAVAILABLE`.

The current account inspection on 2026-10-25 listed `mimo-v2.6-flash`,
`mimo-v2.6-pro`, and `mimo-v2.6-pro-ultraspeed`; model availability is account-
specific and may change. The backend default is therefore configuration, not a
guarantee of entitlement.

This slice intentionally omits image generation. It must not be reintroduced
until text chat, board IP transport, storage, and image decoding are proven.

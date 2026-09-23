# ArvanCloud AIaaS — Integration (Filing Divar)

## Architecture chain (production)

```
Feature → context builder → prompt → gateway.run()
  → cache (AI_CACHE_VERSION) / quota / validation
  → HTTP providers (provider_attempt index):
       1. Arvan AIaaS (if configured)
            → internal: ARVAN_AI_MODEL then ARVAN_AI_FALLBACK_MODEL
       2. OpenRouter (:free only, if OPENROUTER_API_KEY)
       3. Gemini Primary (GEMINI_MODEL)
       4. Gemini Lite (GEMINI_FALLBACK_MODEL)
  → parse / salvage
  → on total HTTP failure: RuleBasedProvider (attempt = len(chain)+1)
```

Views and mobile API **only** call `gateway.run()` — never Arvan directly.

## Environment variables

| Variable | Description |
|----------|-------------|
| `ARVAN_AI_ENABLED` | `true` to include Arvan in HTTP chain |
| `ARVAN_AI_BASE_URL` | Private endpoint base from Arvan panel (e.g. `https://arvancloudai.ir/gateway/models/.../v1`) |
| `ARVAN_AI_API_KEY` | Machine User API key — **never commit** |
| `ARVAN_AI_MODEL` | Default `Gemini-2.5-Flash-lite` (change via env only) |
| `ARVAN_AI_FALLBACK_MODEL` | Optional second model on same endpoint |
| `ARVAN_AI_TIMEOUT_SECONDS` | Default `10` |
| `ARVAN_AI_MAX_RETRIES` | Transient retries per model (default `1` = 2 attempts) |
| `ARVAN_AI_TEMPERATURE` | Default `0.4` |
| `ARVAN_AI_MAX_TOKENS` | Default `1200` |

Auth header (REST): `Authorization: apikey <KEY>`  
POST URL: `{BASE}/chat/completions` (see `arvan_http.build_chat_completions_url`).

## IAM & secrets

- Create a **Machine User** in Arvan IAM with least privilege for the filing AI endpoint only.
- Store `ARVAN_AI_API_KEY` only in server `.env` / secret manager.
- Do not use owner/full-access keys for the app.
- Rotate keys if exposed.

## Rollback

- Set `ARVAN_AI_ENABLED=false` — chain becomes: OpenRouter (:free) → Gemini Primary → Lite → RuleBased.
- No code deploy required for emergency disable of Arvan.

## OpenRouter

| Component | Status |
|-----------|--------|
| `OpenRouterProvider` | Active **after Arvan** when `OPENROUTER_API_KEY` is set |
| Model routing | Only `:free` / `openrouter/free` via `openrouter_models.py` |
| Paid models | **Never** selected by discovery filter |

## Quota & cache

Unchanged: per-user limits, per-feature caps, `AI_GLOBAL_DAILY_CAP`, `AI_DAILY_TOKEN_LIMIT`. Cache key includes `AI_CACHE_VERSION` (default `v2`) + feature + entity + content_version + prompt_hash. Cache hits do not consume quota.

## Timeout / retry

- Arvan: configurable timeout; max 1 retry on 429, 5xx, timeout, connection errors.
- Gateway does **not** duplicate retries (same as Gemini pattern).
- On controlled failure → next provider or RuleBased.

## Smoke test

```bash
cd django
# Requires ARVAN_AI_* env on host — skipped if not configured
python manage.py ai_provider_smoke_test --provider arvan
```

No secrets printed.

## Guardrail warning (endpoint-level on Arvan)

Sensitive Data Guardrail can **mask/redact/block** phone, email, national ID.  
Filing CRM **requires phone numbers** in CRM message flows. **Do not enable** Sensitive Data Guardrail on endpoints that process contact/CRM context without staging tests.

Guardrails are **not** configured from application code in this integration.

## Knowledge Base / RAG

Out of scope. Future use: Academy, FAQ, support docs — not for `listing_summary` / `crm_message` / `upload_brief` (context builders remain source of truth).

## References

- https://docs.arvancloud.ir/fa/aiaas/
- https://docs.arvancloud.ir/fa/aiaas/api-usage/
- https://docs.arvancloud.ir/fa/aiaas/examples/openai/
- https://docs.arvancloud.ir/fa/aiaas/iam/
- https://docs.arvancloud.ir/fa/aiaas/guardrail/

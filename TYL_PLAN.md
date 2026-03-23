# Webmaster — Project Plan

**Product name:** Webmaster
**First tenant:** TYL (professional pianist)
**Project root:** `C:\Users\Scott\Desktop\WKG\TYL\`
**AWS region:** us-west-2
**Demo site:** `http://webmaster-tyl.s3-website-us-west-2.amazonaws.com`

---

## Overview

Webmaster is a hosted website platform for non-technical users. The user updates their website **entirely via email** — no dashboard, no login, no web forms. One email address. An LLM (Bedrock Claude) classifies intent from Subject + Body and executes the appropriate action.

**Email address:** `tyl_update@scottgross.works`
**Actions:** NEW_POST, STATIC_UPDATE, REMOVE, REMOVE_ALL, ERROR

See `TYL_API.md` for the full API reference.

---

## Architecture

```
EMAIL INPUT (1 Lambda, 1 address, LLM classifies intent from one Bedrock call):
  tyl_update@ → SES → webmaster-tyl-ingest → Bedrock classifies:
    NEW_POST      → polish text → DDB + S3 image → publisher → confirmation email
    STATIC_UPDATE → route to section (about/contact/intro) → DDB → publisher → confirmation w/ previous content
    REMOVE        → match post → delete DDB → publisher → confirmation w/ full removed text
    REMOVE_ALL    → delete all posts → publisher → confirmation w/ count
    ERROR         → no changes → error email w/ LLM conclusion + original message + examples

PUBLISH (1 Lambda):
  webmaster-tyl-publisher → read DDB → Jinja2 → index.html + CSS + JS → S3

CONTACT FORM (1 Lambda):
  Browser → fetch() POST → API Gateway → webmaster-tyl-contact → SES → TYL's Gmail

READ PATH:
  Visitor → S3 static website hosting → done
```

### 3 Lambda Zips

| Zip | Lambda | Trigger |
|-----|--------|---------|
| `ingest.zip` | `webmaster-tyl-ingest` | SES: `tyl_update@scottgross.works` |
| `publisher.zip` | `webmaster-tyl-publisher` | Lambda invoke (from ingest) |
| `contact.zip` | `webmaster-tyl-contact` | API Gateway: `POST /contact` |

---

## AWS Resources

| Resource | Name | Status |
|----------|------|--------|
| S3 (public, static hosting) | `webmaster-tyl` | Done |
| S3 (private, SES inbound) | `webmaster-ses-inbound` | Done |
| DynamoDB | `webmaster-tyl` (pk/sk strings) | Done |
| IAM role | `webmaster-lambda-role` | Done |
| SES receipt rule | `webmaster_tyl_ingest` (tyl_update@) | Done |
| Lambda | `webmaster-tyl-publisher` | Deployed |
| Lambda | `webmaster-tyl-ingest` | Deployed |
| API Gateway | `webmaster-api` — `POST /contact` | **Pending** |
| Lambda | `webmaster-tyl-contact` | **Pending** |

### Lambda Environment Variables (webmaster-tyl-ingest)

| Env Var | Value |
|---------|-------|
| `TENANT_ID` | `tyl` |
| `SENDER_WHITELIST` | `scottgrossworks@gmail.com` |
| `DDB_TABLE` | `webmaster-tyl` |
| `ASSET_BUCKET` | `webmaster-tyl` |
| `SES_INBOUND_BUCKET` | `webmaster-ses-inbound` |
| `CONFIRM_EMAIL_TO` | `scottgrossworks@gmail.com` |
| `PUBLISHER_FUNCTION` | `webmaster-tyl-publisher` |
| `SES_FROM_ADDRESS` | `noreply@scottgross.works` |
| `BEDROCK_MODEL_ID` | `anthropic.claude-haiku-4-5-20251001-v1:0` |
| `UPDATE_ADDRESS` | `tyl_update@scottgross.works` |

### Lambda Environment Variables (webmaster-tyl-publisher)

| Env Var | Value |
|---------|-------|
| `DDB_TABLE` | `webmaster-tyl` |
| `SITE_BUCKET` | `webmaster-tyl` |
| `POSTS_PER_PAGE` | `3` |
| `SITE_TITLE` | `TYL Piano` |
| `ASSET_BUCKET` | `webmaster-tyl` |

### DDB Schema

- Posts: `pk=post`, `sk={ISO timestamp}`, `title_en`, `title_ko`, `text_en`, `text_ko`, `date`, `image_key`
- Config: `pk=config`, `sk={about|contact|intro}`, `text_en`, `text_ko`

### Bilingual

All content en + ko. LLM produces both from every email. Template renders both in `lang-en`/`lang-ko` divs. JS toggles body class.

---

## File Structure

```
C:\Users\Scott\Desktop\WKG\TYL\
├── ingest\
│   ├── lambda_function.py    ← unified intent classification, all action handlers
│   └── llm_config.json       ← LLM prompts + error messages (string.Template $variable syntax)
├── publisher\
│   ├── lambda_function.py    ← reads DDB, renders Jinja2, writes to S3
│   ├── templates\
│   │   └── index.html        ← Jinja2 template with editable tags + post loop + bilingual
│   └── static\
│       ├── style.css
│       └── site.js           ← language toggle + contact form
├── contact\
│   └── lambda_function.py    ← API Gateway POST → SES forward (PENDING)
├── scripts\
│   └── seed_data.py          ← one-time DDB loader (already run)
├── TYL_PLAN.md               ← this file
├── TYL_API.md                ← email API reference
└── CLAUDE.md                 ← coding rules for agents
```

---

## Ingest Lambda — Design

### Single-prompt architecture

One Bedrock call per email. The prompt includes Subject, Body, all current config section values, and all post titles/dates. The LLM returns ONE JSON object with an `action` field and the processed content.

**Prompts live in `ingest/llm_config.json`** — not hardcoded in Python. Uses `string.Template` with `$variable` syntax (avoids brace conflicts with JSON examples in the prompt). Python loads the JSON at module level and substitutes at call time.

### Action handlers

| Action | What happens | Confirmation email includes |
|--------|-------------|---------------------------|
| `new_post` | Store image to S3, write post to DDB, invoke publisher | New title + content preview |
| `static_update` | Validate section, write to DDB, invoke publisher | New content + **previous content** for recovery |
| `remove` | Read full post, delete from DDB, invoke publisher | **Full removed text** (EN + KO) + date + re-add instructions |
| `remove_all` | Delete all posts, invoke publisher | Count of removed posts |
| `error` | No changes to site | LLM conclusion + original subject/body + example commands |

### Merge vs Replace (static updates)

LLM decides from context — no procedural logic in Python.
- Partial info ("new phone: 555-1234") → merge into existing section
- Full replacement ("Here is my new bio: [text]") → replace entire section
- `previous_en` / `previous_ko` always included in response for recovery

### Error handling

**Eager errors.** A wrong action is worse than a polite error email. Every error email includes:
- Friendly message ("Webmaster couldn't figure out what you wanted")
- LLM's conclusion (what it thought you meant)
- Original subject + body (so user can rephrase)
- Example commands

**Every failure path sends an email:** Bedrock failure, JSON parse failure, invalid section, post not found, unrecognized action, uncaught exceptions. User ALWAYS gets a reply (except unauthorized senders).

---

## Completed Work

- [x] Mock Template + CSS + JS (`publisher/templates/`, `publisher/static/`)
- [x] Publisher Lambda — deployed, tested, renders site from DDB
- [x] Seed Data Script — run, DDB populated with placeholder content
- [x] AWS infrastructure: S3 buckets, DDB table, IAM role, SES receipt rule
- [x] Ingest Lambda — deployed, unified single-prompt processing with `llm_config.json`
- [x] Demo site live at S3 URL

---

## Remaining Work

### Resolve Bedrock Access
- Marketplace IAM permissions needed on `webmaster-lambda-role`
- `aws-marketplace:ViewSubscriptions` and `aws-marketplace:Subscribe`
- Verify Claude 3.5 Haiku is enabled in Bedrock model catalog

### SES Cleanup
- Remove `tyl_about@scottgross.works` from `webmaster_tyl_ingest` receipt rule (no longer used)
- Remove `ABOUT_ADDRESS` env var from ingest Lambda (if still present)

### Contact Form Lambda (Task 5)
**File:** `C:\Users\Scott\Desktop\WKG\TYL\contact\lambda_function.py`

API Gateway `POST /contact` → Lambda → SES forward to Gmail with Reply-To.
~30 lines. Honeypot check, validation, CORS headers, OPTIONS preflight. No pip deps.

**AWS setup:**
- [ ] Create `webmaster-tyl-contact` Lambda (Python 3.12, `webmaster-lambda-role`)
- [ ] Create `webmaster-api` API Gateway, `POST /contact` route, CORS enabled
- [ ] Set `CONFIRM_EMAIL_TO` and `SES_FROM_ADDRESS` env vars on contact Lambda
- [ ] Update `data-api` attribute in template with API Gateway URL

---

## Decisions Log

| Decision | Answer |
|----------|--------|
| Product name | **Webmaster** |
| Dashboard | **No.** Email-only. |
| Email addresses | 1: `tyl_update@` — everything. LLM classifies intent. |
| Demo domain | `scottgross.works` |
| Sender auth | Whitelist via env var |
| Posts per page | Configurable env var, default 3, static, no pagination |
| Copyright year | `datetime.now().year` at render time |
| Config storage | Lambda env vars (not DDB, not JSON-in-zip) |
| LLM prompts | `llm_config.json` in ingest zip. `string.Template` syntax. |
| AWS isolation | All resources prefixed `webmaster-` |
| Subject line | Optional hint. LLM uses for context. Body sufficient alone. |
| Contact form | API Gateway (browser client). Reply-To for Gmail forwarding. |
| Frontend | Vanilla HTML + CSS + JS. No frameworks. |
| Bilingual | All content en + ko. Toggle via body class. |
| Edit workflow | Remove + re-add. Removal returns full text. |
| Error handling | Eager errors. Always reply. Include original message + LLM conclusion. |

### Still Open
- Domain strategy for production tenants
- LLM prompt tuning (tone, SEO, voice)
- Bedrock model access / Marketplace IAM

---

## Multi-Tenant Vision

TYL is proof-of-concept. Goal: hosted websites for non-technical musicians.

**Per-tenant:** Template, CSS, S3 bucket, DDB table, SES rules, Lambda env vars, whitelisted email.
**Shared:** Lambda code (identical — only env vars change), Bedrock, API Gateway, IAM role, Scott's AWS account.

New tenant = duplicate Lambdas (`webmaster-joe-*`), new DDB table, new S3, new SES rules.

---

## Phase 2 — `/templatize` Skill (TBD)

Deferred until demo pipeline proven. One-afternoon client onboarding:

1. Design session — Claude builds static HTML/CSS from screenshots + client feedback
2. `/templatize` skill converts approved HTML into Jinja2 template + seed_data.json
3. Deploy. Live by end of afternoon.

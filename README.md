# Webmaster

A hosted website platform for non-technical users. Update your website entirely by email — no dashboard, no login, no web forms. Send an email, the site updates itself.

An LLM (AWS Bedrock / Claude) classifies intent from the Subject + Body and executes the appropriate action. All content is generated bilingually (English + Korean).

---

## Architecture

```
Email → SES → ingest Lambda → Bedrock (intent classification)
                                    ↓
                         new_post / static_update / remove / remove_all / error
                                    ↓
                         publisher Lambda → Jinja2 → S3 static site
```

**Three Lambdas:**
- `webmaster-tyl-ingest` — receives email, calls Bedrock, executes action
- `webmaster-tyl-publisher` — reads DynamoDB, renders Jinja2 template, writes to S3
- `webmaster-tyl-contact` — handles contact form submissions via API Gateway

**Storage:** DynamoDB (posts + config), S3 (static site + image assets)

---

## How to Use It

Send an email to your update address. The subject line is optional — the LLM figures out what you want from the body alone.

### Add a blog post
Write your content in the email body. Attach a photo if you want one. The LLM polishes the text and publishes it.

### Update bio, contact info, or intro
Describe the change:
- `"new phone: 555-1234"` — merges into existing contact section
- `"Here is my new bio: [text]"` — replaces the entire bio

### Remove a post
Describe it in any way — title, topic, date, or paste the body text:
- `"remove the post about the spring recital"`
- `"delete the one from last Tuesday"`

If the description is ambiguous, you'll get an error email listing all posts so you can be more specific.

### Remove all posts
Send: `"remove all posts"` — must be explicit.

### Edit a post
No edit command. Remove the post (you'll receive the full text in the confirmation email), modify it, and resend as a new post.

---

## Quick Reference

| Intent | Body | Subject (optional) |
|--------|------|--------------------|
| New blog post | Your content (+ photo attachment) | Context hint |
| Update phone | `"new phone: 555-1234"` | `"phone"` |
| Update bio | `"update bio: [text]"` | `"bio"` |
| Replace bio | `"Here is my new bio: [full text]"` | `"replace bio"` |
| Update intro | `"change intro to: [text]"` | `"intro"` |
| Remove a post | `"remove [description or title]"` | — |
| Remove all posts | `"remove all posts"` | — |
| Edit a post | Remove it, then re-add corrected version | — |

---

## Confirmation Emails

Every action sends a reply — success or failure, never silent (except unauthorized senders).

- **Success:** subject `"Website updated"` — describes what changed, includes previous/removed content for recovery
- **Error:** subject `"Website update failed"` — includes the LLM's conclusion, your original message, and examples

---

## Repo Structure

```
ingest/
  lambda_function.py   — intent classification + all action handlers
  llm_config.json      — LLM prompts (string.Template $variable syntax)
  requirements.txt
  build.bat

publisher/
  lambda_function.py   — reads DDB, renders Jinja2, writes to S3
  templates/index.html — bilingual Jinja2 template
  static/style.css
  static/site.js       — language toggle + contact form
  requirements.txt
  build.bat

scripts/
  seed_data.py         — one-time DDB seed loader
```

---

## Environment Variables

**ingest Lambda:**

| Variable | Purpose |
|----------|---------|
| `TENANT_ID` | Tenant identifier (e.g. `tyl`) |
| `SENDER_WHITELIST` | Comma-separated authorized sender emails |
| `DDB_TABLE` | DynamoDB table name |
| `ASSET_BUCKET` | S3 bucket for image uploads |
| `SES_INBOUND_BUCKET` | S3 bucket where SES drops raw emails |
| `CONFIRM_EMAIL_TO` | Where confirmation emails are sent |
| `PUBLISHER_FUNCTION` | Name of the publisher Lambda to invoke |
| `SES_FROM_ADDRESS` | From address for outbound SES emails |
| `BEDROCK_MODEL_ID` | Inference profile ID (e.g. `us.anthropic.claude-haiku-4-5-20251001-v1:0`) |
| `UPDATE_ADDRESS` | The inbound email address (included in error messages) |

**publisher Lambda:**

| Variable | Purpose |
|----------|---------|
| `DDB_TABLE` | DynamoDB table name |
| `SITE_BUCKET` | S3 bucket for the public static site |
| `ASSET_BUCKET` | S3 bucket for images |
| `POSTS_PER_PAGE` | Number of posts to display (default: 3) |
| `SITE_TITLE` | Site title rendered in the template |

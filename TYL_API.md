# Webmaster — API Reference

## Email API

**One address:** `tyl_update@scottgross.works`
**Authorized sender:** whitelisted email only (env var). All other senders silently dropped.
**All actions** go to this one address. The LLM classifies intent from Subject + Body.

---

### Actions

#### NEW_POST — Add a blog post
- **Body:** Your content (any language — EN, KO, mixed)
- **Subject:** Optional context hint
- **Attachment:** Optional, one image (first `image/*` MIME part used, rest ignored)
- **Result:** LLM polishes text, generates bilingual title + body, stores image to S3, writes post to DDB, rebuilds site
- **Confirmation:** "Website updated — New post: [title]" + content preview

#### STATIC_UPDATE — Change bio, contact info, or intro
- **Body:** Describe the change. Examples: "new phone: 555-1234", "Here is my new bio: [text]", "Change intro to: [text]"
- **Subject:** Optional hint ("phone", "bio", "intro")
- **Sections:** `about` (bio), `contact` (phone/email/address), `intro` (tagline/welcome)
- **Merge vs Replace:**
  - Partial info ("new phone: 555-1234") → merges into existing section, keeps everything else
  - Full replacement ("Here is my new bio: [full text]") → replaces entire section
  - LLM decides based on context — no procedural logic
- **Result:** LLM routes to correct section, produces bilingual output, writes to DDB, rebuilds site
- **Confirmation:** "Website updated — [section] changed" + new content + **previous content** (for recovery)

#### REMOVE — Delete a specific post
- **Body:** Describe which post. Examples: "remove the post about the spring recital", "delete the one from last Tuesday", exact title
- **Scope:** Searches ALL posts in DDB, not just the 3 currently displayed
- **Safety:** Never matches more than one post. If ambiguous, returns error listing all posts.
- **Result:** Deletes post from DDB, rebuilds site
- **Confirmation:** "Website updated — Post removed: [title]" + **full removed text** (EN + KO) + date + "To re-add with changes, email tyl_update@..."

#### REMOVE_ALL — Delete every post
- **Body:** "remove all posts" (must be explicit and unambiguous)
- **Result:** Deletes all posts from DDB, rebuilds site
- **Confirmation:** "Website updated — Removed N posts"

#### ERROR — Intent unclear
- If the LLM cannot determine what the user wants, **no changes are made to the site**
- The system errs on the side of error — it will never guess. A polite error email is better than a wrong action.
- **Error email includes:**
  - Friendly message: "Webmaster couldn't figure out what you wanted"
  - What the AI concluded (helps you understand the confusion)
  - Your original subject + body (so you can see what you sent)
  - Examples of clear commands
- Also triggered by: Bedrock service errors, invalid section names, post not found for removal, any unexpected failure
- **The user always gets a reply.** Success or failure. Never a silent drop (except unauthorized senders).

---

### Edit workflow

No edit command. Remove the post → receive full text in confirmation email → modify → resend as new post.

---

### Confirmation emails

Every action sends a confirmation to `CONFIRM_EMAIL_TO`:
- **Success:** Subject "Website updated", body describes action + changes + previous/removed content where applicable
- **Error:** Subject "Website update failed", body explains why

---

## Contact Form API

**Endpoint:** `POST {webmaster-api}/contact`
**Trigger:** Visitor submits form on the website (browser fetch)

**Request body (JSON):**
```json
{"name": "Visitor Name", "email": "visitor@example.com", "message": "..."}
```

**Honeypot:** If `honeypot` field present and non-empty, returns 200 silently (bot).

**Result:** SES email sent to `CONFIRM_EMAIL_TO` with `Reply-To: visitor email`. TYL hits Reply in Gmail → talks directly to visitor.

**CORS:** `POST` and `OPTIONS` supported. `Access-Control-Allow-Origin: *` (tighten to site domain in production).

---

## Quick Reference

| Intent | Body | Subject (optional) |
|---|---|---|
| New blog post | Your content (+ photo attachment) | Context hint |
| Update phone | "new phone: 555-1234" | "phone" |
| Update bio | New bio text or "update bio: [text]" | "bio" |
| Replace bio | "Here is my new bio: [full text]" | "replace bio" |
| Update intro | "change intro to: [text]" | "intro" |
| Remove a post | "remove [description or title]" | — |
| Remove all posts | "remove all posts" | — |
| Edit a post | Remove it, then re-add corrected version | — |

All sent to: `tyl_update@scottgross.works`

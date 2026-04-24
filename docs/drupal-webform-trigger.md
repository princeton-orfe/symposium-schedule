# Triggering Schedule PDF Generation from Drupal 10 Webforms

## Overview

This guide configures a Drupal 10 Webform button that triggers the GitHub Actions workflow to regenerate the symposium schedule PDFs. Since Webforms can only make outbound HTTP POST requests (via handlers), we use GitHub's workflow dispatch API as the target.

**Limitations:**
- Drupal Webforms cannot receive async callbacks, so we cannot show real-time "PDF ready" status
- We use artificial confirmation messaging to give the user feedback
- The workflow takes ~25 seconds to complete; the user sees a confirmation message immediately

---

## Architecture

```
[Drupal Webform Button]
    → POST to GitHub API (workflow_dispatch)
        → GitHub Actions runs generate workflow
            → PDFs updated in GitHub Release
```

---

## Part 1: GitHub Setup

### 1A. Create a Fine-Grained Personal Access Token (PAT)

1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens**
2. Click **Generate new token**
3. Configure:
   - **Token name:** `drupal-schedule-trigger`
   - **Expiration:** Set an appropriate expiration (e.g., 90 days — set a calendar reminder to rotate)
   - **Repository access:** Select **Only select repositories** → choose `symposium-schedule`
   - **Permissions:**
     - **Actions:** Read and write (required to trigger workflows)
     - All other permissions: No access
4. Click **Generate token** and copy the token immediately — you won't see it again

### 1B. Verify the API Endpoint Works

Test from your terminal before configuring Drupal:

```bash
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  https://api.github.com/repos/pu-orfe/symposium-schedule/actions/workflows/generate.yml/dispatches \
  -d '{"ref":"main","inputs":{"force_generate":"true"}}'
```

- **204 No Content** = success (the API returns no body)
- **404 Not Found** = wrong repo path or token lacks Actions permission
- **422 Unprocessable Entity** = wrong ref or input names

### 1C. Stable PDF Download URL

Once generated, the PDF is always available at this stable release URL:

```
https://github.com/pu-orfe/symposium-schedule/releases/download/latest/symposium_schedule.pdf
https://github.com/pu-orfe/symposium-schedule/releases/download/latest/symposium_schedule_grid.pdf
```

You can link to these from the confirmation page.

---

## Part 2: Drupal 10 Webform Configuration

### 2A. Create the Webform

1. Go to **Structure → Webforms → Add webform**
2. **Title:** `Regenerate Schedule PDFs`
3. **Administrative description:** `Triggers GitHub Actions to regenerate symposium schedule PDFs from the live website`

### 2B. Build the Form Elements

Go to the **Build** tab and add these elements:

#### Element 1: Markup (instructions)

- **Type:** Basic HTML / Markup
- **Key:** `instructions`
- **Markup:**
```html
<div class="messages messages--info">
  <h3>Regenerate Schedule PDFs</h3>
  <p>Click the button below to regenerate the symposium schedule PDFs from the
  current website content. The process takes approximately 30 seconds.</p>
  <p><strong>Note:</strong> If the website is in maintenance mode, the existing
  PDFs will be preserved.</p>
</div>
```

#### Element 2: Hidden field (payload)

This is needed because Webforms requires at least one input element to submit. It also carries the API payload.

- **Type:** Hidden
- **Key:** `ref`
- **Default value:** `main`

#### Element 3: Submit Button

- **Label:** `Regenerate PDFs Now`
- Under **Button attributes → Class**, add: `button--primary`

### 2C. Configure the Confirmation Page

Go to the **Settings** tab → **Confirmation**:

1. **Confirmation type:** Inline message
2. **Confirmation message:**

```html
<div class="messages messages--status">
  <h3>PDF Regeneration Triggered</h3>
  <p>The schedule PDFs are being regenerated. This typically takes about 30 seconds.</p>
  <p>Updated files will be available shortly at:</p>
  <ul>
    <li><a href="https://github.com/pu-orfe/symposium-schedule/releases/download/latest/symposium_schedule.pdf" target="_blank">Schedule PDF (with QR codes)</a></li>
    <li><a href="https://github.com/pu-orfe/symposium-schedule/releases/download/latest/symposium_schedule_grid.pdf" target="_blank">Grid Schedule PDF (landscape)</a></li>
  </ul>
  <p><em>If the website is currently in maintenance mode, the previous versions will remain unchanged.</em></p>
</div>
```

3. Under **Confirmation back**:
   - **Display back to form link:** Yes
   - **Back link label:** `← Regenerate again`

### 2D. Configure the Remote Post Handler

This is the key step — it makes the outbound API call to GitHub.

1. Go to the **Handlers** tab → **Add handler** → **Remote post**
2. Configure:

**General:**
- **Title:** `Trigger GitHub Workflow`
- **Submission status:** Completed submissions only

**Remote Post Settings:**

| Setting | Value |
|---------|-------|
| **Completed URL** | `https://api.github.com/repos/pu-orfe/symposium-schedule/actions/workflows/generate.yml/dispatches` |
| **Completed method** | `POST` |
| **Type** | `JSON` |

**Custom Data (Completed):**

In the **Completed custom data** textarea, enter this exact JSON:

```json
{
  "ref": "main",
  "inputs": {
    "force_generate": "true"
  }
}
```

> **Important:** This overrides the form submission data with the exact payload GitHub expects. Without this, the Remote Post handler would send the webform field values, which GitHub would reject.

**Custom Headers:**

Add these headers (one per line, colon-separated):

```
Authorization: Bearer YOUR_GITHUB_PAT_HERE
Accept: application/vnd.github+json
User-Agent: Drupal-Webform
```

> **Security note:** The PAT is stored in the handler config. Only users with Webform admin access can view it. For additional security, consider using Drupal's Key module to store the token separately (see Security Considerations below).

**Error Handling:**
- **Completed debug:** Disable in production (enable temporarily for troubleshooting)
- Set **Message** for error state: `The PDF regeneration request could not be sent. Please try again later or contact the site administrator.`

### 2E. Access Control

Restrict who can use this form:

1. Go to **Settings** tab → **Access**
2. Under **Create submissions:**
   - Set **Roles** to only the roles that should trigger regeneration (e.g., `administrator`, `content_editor`)
3. Under **View submissions:**
   - Restrict to `administrator` only (submission data is not meaningful here)

### 2F. Submission Settings

Since this is a trigger button, not a data collection form:

1. Go to **Settings** tab → **Submissions**
2. **Saving of results:**
   - Set **Submission storage** to **Delete all submissions** or set a low purge limit (e.g., keep last 10)
   - This prevents the submission table from growing endlessly
3. **Limits:**
   - **Total submission limit:** Unlimited
   - **Per-user submission limit:** Consider setting to 1 per 5 minutes to prevent accidental rapid re-triggers (the workflow has its own rate limiting, but this prevents unnecessary API calls)

---

## Part 3: Testing

### Step 1: Test the Handler

1. Enable **Completed debug** on the Remote Post handler
2. Submit the form
3. Check **Reports → Recent log messages** for the remote post debug output
4. You should see a **204** response code (success — no body)

### Step 2: Verify the Workflow Ran

```bash
gh run list --limit 3
```

You should see a `workflow_dispatch` triggered run.

### Step 3: Verify PDFs Updated

Check the release page or download the PDFs from the stable URLs.

### Step 4: Disable Debug

Turn off **Completed debug** once everything works.

---

## Security Considerations

### Token Storage

The GitHub PAT is stored in the Webform handler configuration. To improve security:

**Option A: Drupal Key Module (recommended)**
1. Install the [Key module](https://www.drupal.org/project/key)
2. Store the PAT as a key
3. Reference it in the handler header via token replacement

**Option B: Environment variable**
1. Set `GITHUB_PAT` in your Drupal environment
2. Use Drupal's settings.php or a custom module to inject it

**Option C: Accept the risk**
- The handler config is only visible to Webform admins
- The PAT has minimal scope (Actions on one repo)
- Set a short expiration and rotate regularly

### Rate Limiting

Multiple layers of protection prevent abuse:
1. **Drupal Webform:** Per-user submission limits
2. **Drupal access control:** Role-based form access
3. **GitHub workflow:** Built-in 5-minute rate limiting between runs
4. **GitHub API:** Token-based rate limits (5,000 requests/hour)

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Form submits but no workflow runs | 401/403 from GitHub | Check PAT is valid and has Actions write permission |
| 404 from GitHub API | Wrong repository path or workflow filename | Verify URL matches exactly |
| 422 from GitHub API | Bad JSON payload | Check custom data JSON syntax; ensure `ref` is `main` |
| Confirmation shows but PDFs not updated | Workflow ran but hash unchanged | Use `force_generate: true` in custom data (already configured above) |
| PDFs still old after 30+ seconds | Site in maintenance mode | Check workflow run in GitHub Actions for the warning annotation |
| "Remote post error" in Drupal logs | Network/firewall issue | Ensure outbound HTTPS to api.github.com is allowed |
| Old PDFs served after update | CDN/browser caching | GitHub release downloads have cache headers; try hard refresh or append `?v=timestamp` |

---

## Summary Checklist

- [ ] GitHub PAT created with Actions read/write on the symposium-schedule repo
- [ ] API endpoint tested via curl (204 response)
- [ ] Webform created with markup, hidden field, and submit button
- [ ] Remote Post handler configured with correct URL, JSON payload, and auth header
- [ ] Confirmation message configured with download links
- [ ] Access restricted to appropriate roles
- [ ] Submission storage set to auto-purge
- [ ] Tested end-to-end: form submit → workflow runs → PDFs updated
- [ ] Debug mode disabled in production

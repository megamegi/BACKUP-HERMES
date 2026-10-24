---
name: meta-graph-api
description: Use when integrating Meta or Instagram Graph APIs.
version: 1.2.0
author: community
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Meta, Facebook, Instagram, Graph API, Social Media]
---

# Meta & Instagram Graph API

Procedures, token workflows, and pitfalls for integrating with Meta for Developers and the Instagram Graph API.

## Direct Links for User Guidance

When guiding a user to configure Meta Developer settings, always provide direct deep links rather than just textual menu descriptions:
- **Graph API Explorer:** `https://developers.facebook.com/tools/explorer/`
- **Apps Dashboard:** `https://developers.facebook.com/apps/`
- **Access Token Tool / Debugger:** `https://developers.facebook.com/tools/debug/accesstoken/`
- **Facebook Pages Management:** `https://www.facebook.com/pages/`
- **Create New Facebook Page:** `https://www.facebook.com/pages/create`

## Graph API Explorer Token Workflow

1. Open the [Graph API Explorer](https://developers.facebook.com/tools/explorer/).
2. Select the target **Meta App** in the top-right panel.
3. **Crucial:** Click the **User or Page** dropdown (defaults to *Get Token*) and select **Get User Access Token** first.
   - *Pitfall:* If "Get Token" is not clicked, the **Add a Permission** dropdown remains completely empty and **Generate Access Token** is disabled with "Please select at least one permission or configuration".
4. Add required permissions:
   - Profile & media: `instagram_basic`
   - Direct messaging: `instagram_manage_messages`
   - Content publishing: `instagram_content_publish`
   - Comments & engagement: `instagram_manage_comments`
   - Page connections: `pages_show_list`, `pages_read_engagement`
   - **Business Assets:** `business_management` (mandatory if pages/accounts are managed inside a Meta Business Portfolio).
5. Click **Generate Access Token** and approve the Facebook login modal.

## Connecting Instagram Professional Account to Facebook Page

Instagram Graph API queries for business accounts require the Instagram Professional (Business/Creator) account to be linked to a Facebook Page:

### Method 1: Via Instagram Mobile App (Recommended & Most Reliable)
1. Ensure the account is Professional: **Settings** -> **Account type and tools** -> **Switch to Professional Account**.
2. Go to **Profile** -> **Edit Profile**.
3. Under **Public Business Information**, tap **Page**.
4. Log into Facebook and select the existing Facebook Page (or create a new one).
*Note:* Always prefer this method over desktop web linking to avoid Accounts Center modal blocking bugs.

### Method 2: Via Meta Business Suite (Web)
1. Open [Meta Business Suite Instagram Settings](https://business.facebook.com/latest/settings/instagram_account).
2. Click **Connect Instagram Account** and complete credentials approval.

### Method 3: Via Facebook Page Settings (Web)
1. Navigate to the Facebook Page -> **Settings** -> **Linked Accounts** (`https://www.facebook.com/settings?tab=linked_instagram`).
2. Select **Instagram** -> **Connect Account** and complete the OAuth login.

## Development Mode & Instagram Tester Acceptance

When a Meta App is in Development mode, only accounts listed under **App roles** can be queried:
1. In Meta Dashboard, navigate to **App roles** -> **Roles** -> **Add People** -> **Instagram Tester**.
2. **Mandatory Acceptance Step:** Adding the handle does NOT grant access immediately. The owner of the Instagram account must actively accept the invitation:
   - Open Instagram (mobile app or web).
   - Go to **Settings** -> **Apps and Websites** (Aplikasi dan Situs Web).
   - Click the **Tester Invitations** tab.
   - Click **Accept** on the pending invite from the app.
3. Once accepted, generate the token under **Instagram** -> **Basic Display** / **API Setup** -> **User Token Generator**.

## Token Domains & Endpoint Routing

- **Tokens starting with `EAA...` (Facebook Graph User/Page Tokens):** Must query `https://graph.facebook.com/v21.0/...`. Calling `graph.instagram.com` with an `EAA...` token fails with OAuthException 190 (`Invalid OAuth access token - Cannot parse access token`).
- **Tokens starting with `IGQ...` / `IG...` (Instagram Basic Display Tokens):** Query `https://graph.instagram.com/v21.0/...`.
- **Finding Connected Instagram Business ID via Facebook Token:**
  1. Query `https://graph.facebook.com/v21.0/me/accounts?fields=id,name,instagram_business_account&access_token=$TOKEN`.
  2. If `data: []` returns empty, verify that:
     - `business_management` scope is present.
     - The target Facebook Page has an Instagram Business account connected.
  3. Query `https://graph.facebook.com/v21.0/{instagram_business_account_id}?fields=id,username,name,profile_picture_url,followers_count,media_count&access_token=$TOKEN`.

## Publishing Media to Instagram via Graph API

Publishing feed images is a two-step container flow:

### Step 1: Create Media Container
```http
POST https://graph.facebook.com/v21.0/{ig_user_id}/media
Content-Type: application/x-www-form-urlencoded

image_url={public_image_url}&caption={encoded_caption}&access_token={token}
```
Response:
```json
{ "id": "17937794694391703" }
```

### Step 2: Publish the Container
```http
POST https://graph.facebook.com/v21.0/{ig_user_id}/media_publish
Content-Type: application/x-www-form-urlencoded

creation_id=17937794694391703&access_token={token}
```
Response:
```json
{ "id": "18190681717410306" }
```

### Step 3: Verify & Get Post Permalink
```http
GET https://graph.facebook.com/v21.0/{media_id}?fields=id,permalink,caption,media_type,timestamp&access_token={token}
```

### Automated Design-to-Post Pipeline (Canva MCP + Instagram Graph API)
When generating social posts with Canva MCP before publishing:
1. Call `mcp__canva__create_design` with format `Instagram Post (Square)` and user brief.
2. Poll `mcp__canva__get_create_design_async_job` following the response wait interval until `status == "completed"`.
3. Provide the user with the editable Canva link for review / approval.
4. Once approved, call `mcp__canva__export_design` with `type: "jpg"` and `quality: 90` to obtain a publicly signed AWS S3/CDN download URL.
5. Pass the export URL directly as `image_url` to the Instagram media container endpoint (Step 1 above).

## Instagram Direct Messaging (DM) & Auto-Reply Automation

Automating responses to incoming Instagram Direct Messages (DMs) requires specific mobile permissions, endpoint querying, and strict window compliance:

### 1. Mandatory Prerequisite in Instagram Mobile App
Even with all developer permissions approved, Meta blocks API access to Instagram DMs until the user enables it on their mobile app:
1. Open the target Instagram business account on the mobile app.
2. Go to **Settings and privacy** -> **Messages and story replies**.
3. Under **Connected tools**, tap **Allow access to messages** and toggle it **ON**.
*Pitfall:* If this toggle is off, reading conversations returns empty lists and sending messages fails silently or with OAuthException errors.

### 2. Reading Inbound Messages (Polling or Webhooks)
Query the linked Facebook Page conversations endpoint using the Page Access Token:
```http
GET https://graph.facebook.com/v21.0/{facebook_page_id}/conversations?platform=instagram&fields=id,updated_time,messages{id,message,created_time,from}&limit=10&access_token={page_token}
```
*Note:* Ensure nested field expressions (e.g. `messages{id,message}`) are properly URL-encoded (`messages%7Bid,message%7D`) when querying via HTTP client libraries to avoid parsing errors.

### 3. Sending DM Replies
Send text messages back to the user's Instagram-Scoped ID (IGSID):
```http
POST https://graph.facebook.com/v21.0/me/messages?access_token={page_token}
Content-Type: application/json

{
  "recipient": {
    "id": "<IGSID_OF_CUSTOMER>"
  },
  "message": {
    "text": "<REPLY_TEXT>"
  }
}
```

### 4. 24-Hour Messaging Window Rule & Subcode 2534022 Causes
Meta enforces strict messaging windows. Calling `POST /me/messages` returns OAuthException code 10, subcode 2534022:
`(#10) This message is sent outside of allowed window.`

This subcode is triggered by THREE distinct conditions (not just 24-hour expiration):
1. **Message Age:** The customer's inbound message is actually older than 24 hours. (Enforce a 15–30 minute timestamp cutoff in polling loops).
2. **Development Mode Recipient Restriction:** When the Meta App is in **Development Mode**, the Messaging API refuses to deliver outgoing messages to general public users, returning subcode 2534022 even if the inbound DM arrived seconds ago. Only registered **App Roles (Instagram Testers / Developers)** can receive replies in Development mode.
3. **Instagram Message Request Quarantine:** Inbound DMs from non-mutual followers land in Instagram's **Message Requests (Permintaan Pesan)** folder. Replying via API is blocked until the request is accepted or the app has Advanced Access in Live mode.

### 5. Transitioning to Live Mode & Advanced Access
To reply to arbitrary public customer DMs without tester restrictions:
1. Complete App Settings: In Meta App Dashboard -> **Settings** -> **Basic**, supply **Privacy Policy URL**, **App Icon (1024x1024)**, and **Category**.
2. Switch Status: Toggle the top header switch from **In development** to **Live**.
3. Request Advanced Access: Go to **App Review** -> **Permissions and Features** -> find `instagram_manage_messages` -> click **Request Advanced Access** (requires a brief screen recording demonstrating the bot receiving and replying to customer DMs). Standard Access in Live mode remains restricted to app administrators.

## Exchanging Short-Lived Tokens for Long-Lived Tokens (60 Days)

Tokens from Graph API Explorer expire after 1–2 hours. Always exchange them for long-lived tokens (valid for 60 days) for scripts and automations.

### Instagram Graph API Exchange
```bash
curl -s -X GET "https://graph.instagram.com/access_token\
?grant_type=ig_exchange_token\
&client_secret=$APP_SECRET\
&access_token=$SHORT_LIVED_TOKEN" | python -m json.tool
```

### Facebook / Page Token Exchange
```bash
curl -s -X GET "https://graph.facebook.com/v21.0/oauth/access_token\
?grant_type=fb_exchange_token\
&client_id=$APP_ID\
&client_secret=$APP_SECRET\
&fb_exchange_token=$SHORT_LIVED_TOKEN" | python -m json.tool
```

## Refreshing Long-Lived Tokens

Long-lived Instagram tokens can be refreshed before expiration (valid if refreshed at least 24 hours after issuance and before 60 days):
```bash
curl -s -X GET "https://graph.instagram.com/refresh_access_token\
?grant_type=ig_refresh_token\
&access_token=$LONG_LIVED_TOKEN" | python -m json.tool
```

## Pitfalls

- **Empty Permission Dropdown:** Never assume permissions are missing or misconfigured if the dropdown is blank; verify that `Get User Access Token` has been selected from the `User or Page` dropdown first.
- **Empty `me/accounts` Response:** When `GET /me/accounts` returns `{"data": []}` despite the user administering pages, add the `business_management` permission to the token and verify the Instagram account is connected to a Facebook Page under Page Settings / Linked Accounts.
- **Accounts Center "Something went wrong" Web Error:** Connecting an Instagram account to a Facebook Page via desktop web settings often fails with *"Something went wrong. You can try again later or use another profile"* due to pending Meta Security Checkup actions or web Accounts Center session bugs. Bypass this by linking directly from the Instagram mobile app (`Edit Profile -> Page`) or Meta Business Suite (`business.facebook.com/latest/settings/instagram_account`).
- **Instagram Mobile "Allow Access to Messages" Toggle:** If this toggle is disabled in the mobile app, reading conversations or replying to DMs fails regardless of whether `instagram_manage_messages` was granted in Developer settings.
- **24-Hour Messaging Window Error (Code 10, Subcode 2534022):** Calling `me/messages` on conversations where the customer has not messaged within the last 24 hours triggers `(#10) This message is sent outside of allowed window`. Always enforce timestamp age limits and seed historical conversation IDs on bot startup.
- **Instagram Media URL Accessibility:** The `image_url` passed to `POST /{ig_user_id}/media` must be a direct, publicly accessible HTTP/HTTPS URL (e.g. Canva's signed export URL, AWS S3, or CDN). Local paths or web viewer pages cause OAuthException code 36003 (`Image failed to download`).
- **Wrong Graph Host for Token Prefix:** Do not call `graph.instagram.com` with `EAA...` tokens (which belong to `graph.facebook.com`); mismatched token prefixes cause `Invalid OAuth access token` errors.
- **Pending Tester Invite:** If a tester token cannot be generated or returns authentication errors, verify if the tester invitation was accepted on the Instagram mobile app or web under `Settings -> Apps and Websites -> Tester Invitations`.
- **Short-Lived Token Expiration:** Tokens directly generated in Graph API Explorer expire in 1-2 hours. Automations must exchange them for 60-day tokens immediately upon acquisition.
- **Account Type Limitation:** Most Graph API features (insights, publishing, automated DM webhooks) require an Instagram Professional (Business or Creator) account connected to a Facebook Page, not a personal account.

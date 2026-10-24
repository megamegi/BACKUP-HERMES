---
name: whatsapp-automation
description: Use when automating WhatsApp or building WA bot gateways.
version: 1.0.0
author: community
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [WhatsApp, Baileys, Chatbot, Messaging, Automation]
---

# WhatsApp Automation & Gateway

Procedures, architecture, and pitfalls for building headless WhatsApp automation, QR login flows, and AI auto-reply bots.

## Architecture Overview

When integrating WhatsApp without third-party SaaS fees, two paths exist:
1. **Official WhatsApp Cloud API (Meta):** Enterprise webhook architecture, requires approved templates for outbound messages outside the 24-hour customer service window, and dedicated business numbers.
2. **Local Multi-Device Gateway (Baileys):** Emulates a linked web device. Uses the user's existing phone number, keeps the mobile app functional simultaneously, incurs no per-message fees, and persists login sessions locally via multi-file auth.

## Setting Up a Baileys WhatsApp Gateway

### Step 1: Initialize Project & Dependencies
Create a dedicated gateway directory (e.g., `wa-gateway`):
```bash
npm init -y
npm i @whiskeysockets/baileys qrcode pino --no-audit
```

### Step 2: Gateway Implementation (`gateway.js`)
Implement session persistence, QR code image export, and auto-reconnection:

```javascript
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');
const pino = require('pino');
const QRCode = require('qrcode');
const path = require('path');
const fs = require('fs');

const AUTH_DIR = path.join(__dirname, 'auth_info_baileys');
const QR_PATH = path.join(__dirname, 'wa_qr.png');

async function startSock() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    version,
    logger: pino({ level: 'silent' }),
    printQRInTerminal: false,
    auth: state,
    browser: ['Hamdakost Automation', 'Chrome', '1.0.0']
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;

    // Render QR code to PNG file for instant visual delivery
    if (qr) {
      await QRCode.toFile(QR_PATH, qr, {
        width: 400,
        margin: 2,
        color: { dark: '#000000', light: '#ffffff' }
      });
      console.log('QR_READY:' + QR_PATH);
    }

    if (connection === 'close') {
      const statusCode = (lastDisconnect?.error)?.output?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      console.log(`Connection closed (code: ${statusCode}), reconnecting: ${shouldReconnect}`);
      if (shouldReconnect) {
        setTimeout(startSock, 3000);
      }
    } else if (connection === 'open') {
      console.log('WA_CONNECTED: Connected successfully as', sock.user?.id);
      if (fs.existsSync(QR_PATH)) {
        try { fs.unlinkSync(QR_PATH); } catch (e) {}
      }
    }
  });

  // Handle incoming messages
  sock.ev.on('messages.upsert', async (m) => {
    if (m.type !== 'notify') return;
    const msg = m.messages[0];
    if (!msg || msg.key.fromMe) return; // Prevent bot loop

    const sender = msg.key.remoteJid;
    // Filter out group messages and status updates
    if (!sender || sender.includes('@g.us') || sender === 'status@broadcast') {
      return;
    }

    const text = msg.message?.conversation || msg.message?.extendedTextMessage?.text || '';
    if (!text.trim()) return;

    console.log(`[MSG RECEIVED] from ${sender}: ${text}`);
    // Trigger auto-reply pipeline with typing presence
    await sock.sendPresenceUpdate('composing', sender);
    const reply = await handleAutoReply(sock, sender, text);
    await sock.sendPresenceUpdate('paused', sender);
    await sock.sendMessage(sender, { text: reply }, { quoted: msg });
  });

  return sock;
}

startSock().catch(console.error);
```

### Step 3: QR Code Delivery & Linking
1. Launch the gateway in the background via `terminal(command="node gateway.js", background=true)`.
2. Monitor process output with `process_manage(action="poll")` until `QR_READY:` is logged.
3. Deliver the QR image directly to the chat interface using `MEDIA:<path_to_qr.png>`.
4. Instruct the user to open WhatsApp on their phone:
   - Go to **Settings** -> **Linked Devices** -> **Link a Device**.
   - Point the camera at the received image.
5. Once connected, Baileys logs `WA_CONNECTED: Connected successfully as <phone>@s.whatsapp.net`. Auth credentials persist inside `auth_info_baileys/`.

## AI Auto-Reply Pipeline & Guardrails

To connect incoming WhatsApp messages to an AI response:
1. **Extract Inbound Text:** Handle both plain `conversation` and `extendedTextMessage.text` properties.
2. **Prevent Infinite Loops:** Always check `msg.key.fromMe` and skip outgoing messages.
3. **Conversational Memory & Identity Context:** Store the last 6–8 messages in memory per `remoteJid`. Prepend sender name (`msg.pushName`) into user turn text so the LLM identifies existing/booked clients vs new leads without asking redundant questions (e.g. asking a confirmed tenant if they are looking for a room).
4. **Complete Silence for Internal Contacts (Blacklist):** Do not send canned "wait for admin" messages to business owners, staff, family, or vendors. Internal discussions and logistics are disrupted by bot interventions. Completely drop and ignore their messages (no presence, no text) so human admins handle them directly.
5. **Fail-Silent Guardrail (Drop Reply When Unsure):** Instruct the LLM that whenever it is uncertain, encounters out-of-SOP requests, or lacks authoritative information, it must respond with a dedicated token like `[DIAM]` or `[SILENT]`. The gateway intercepts this token and sends **nothing**, allowing the human owner to answer naturally without bot interference or hallucinated promises.
6. **Normalize Phone Numbers for LID Matching:** WhatsApp increasingly routes messages via Linked Identities (`@lid`) rather than pure MSISDN (`@s.whatsapp.net`). Strip all non-digits (`remoteJid.replace(/[^0-9]/g, '')`) and match against substring digits rather than checking strict string equality.
7. **Simulate Typing Presence:** Call `sock.sendPresenceUpdate('composing', sender)` before making the LLM inference call and `paused` immediately after or when deciding to drop the message.
8. **Handling Temporal & Future Booking Inquiries:** Calon penghuni sering menanyakan ketersediaan untuk bulan depan atau tanggal jauh ke depan. Jangan biarkan bot diam atau mengira kamar kosong/penuh tanpa dasar: instruksikan LLM untuk menjelaskan bahwa ketersediaan bulan depan bergantung pada perpanjangan sewa penghuni berjalan, dan sebutkan jendela waktu booking resmi (misal: booking baru dibuka maksimal 2 minggu / H-14 sebelum tanggal masuk).

## Persistence & Auto-Start on System Boot (Windows)

To ensure the WhatsApp gateway automatically resumes whenever the host machine powers on or restarts without requiring manual terminal commands:

1. Create a lightweight VBScript launcher in the user's Windows Startup folder:
   Path: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\<service_name>.vbs`
   ```vbs
   Set WshShell = CreateObject("WScript.Shell")
   WshShell.CurrentDirectory = "D:\path\to\wa-gateway"
   WshShell.Run "node gateway.js", 0, False
   ```
2. The `0` parameter ensures the process runs headlessly in the background without spawning visible Command Prompt or PowerShell windows.
3. Because credentials persist in `auth_info_baileys`, the socket automatically reconnects on startup without prompting for QR scanning again.

## Pitfalls

- **Avoid Terminal ASCII QR Codes:** Terminal text-rendered QR codes distort across different fonts and font sizes on user devices. Always render QR codes to PNG via `qrcode.toFile` and deliver as native image files (`MEDIA:`).
- **Stream Error 515 Restart:** During initial device pairing, WhatsApp servers frequently issue a stream error with status code `515 (Stream Errored - restart required)`. Ensure reconnection logic does not abort on code 515; a simple re-call of `startSock()` picks up the newly saved session state and successfully opens the connection.
- **WebSocket Duplicate Instance Conflict (Code 440 Replaced):** If two Node.js processes run `gateway.js` simultaneously using the same credentials folder, WhatsApp closes the connection with `Stream Errored (conflict) / status 440 replaced`. Always inspect active background tasks (via `Get-CimInstance Win32_Process` or task manager) and kill stale instances before starting a new socket.
- **Bot Reply Feedback Loops:** Always verify `!msg.key.fromMe` and `m.type === 'notify'` before processing an incoming message event; failing to check sender identity causes the bot to process and respond to its own messages endlessly.
- **Process Termination on Agent Finish:** Background server processes started with `terminal(background=true)` must be monitored or managed as persistent services if meant to run indefinitely. Do not run the gateway in blocking foreground mode if waiting on user interaction to scan the QR code.
- **Group Message Leaks:** Without filtering `remoteJid.includes('@g.us')`, auto-reply bots will reply to every general announcement, mention, or chat inside WhatsApp Groups. Always explicitly filter out group JIDs.
- **Out-of-Domain Hallucinations:** Without strict scope boundaries, LLMs acting as customer service bots will attempt to answer random questions (recipes, general trivia, personal requests). Enforce a hard fallback clause in the system prompt to refer non-domain questions to the human administrator.
- **Canned Replies to Owners/Staff Annoy Stakeholders:** Sending automated templates like "Mohon tunggu admin" to owners, internal staff, or maintenance workers causes operational frustration. Always maintain a silent blacklist that drops messages completely.
- **LID Routing Bypasses Blacklists:** WhatsApp's multi-device architecture often delivers messages via `<lid>@lid` instead of `<phone>@s.whatsapp.net`. Matching only full phone JIDs allows blacklisted contacts to leak through; always check both normalized digits and `pushName` keywords.
- **Hallucinating Over Silence:** For customer service bots, silence is far better than a wrong guess or canned deflection. Enforce a fail-silent token (`[DIAM]`) in the prompt and gateway code so unanswered edge cases fall back to human handling.
- **Incomplete Temporal Scope Silences Valid Inquiries:** If an auto-reply bot only understands immediate real-time availability, questions about future dates or next month trigger the fail-silent guardrail unnecessarily. Always include explicit handling for future inquiries and booking timeframes in the system prompt.

# Pip · a little desktop company

A draggable, animated Windows desktop character with a chat window and a Chrome / Edge extension. Built with Python's standard library: no npm install or Python packages needed.

## Start Pip

This laptop already has Python 3.11 with Tkinter. Double-click **launch.cmd** in this folder. Alternatively, run `python desktop.py` from this folder. Pip appears near the bottom-right of your screen and opens its chat window.

- Drag the character to move it; click to open chat.
- Closing the chat window leaves Pip running.
- Right-click the character and choose **Quit Pip** to exit.
- There is no automatic startup registration or system tray icon.

## Connect your browser (one-time setup)

1. Open `chrome://extensions` in Chrome, or `edge://extensions` in Edge.
2. Turn on **Developer mode** and select **Load unpacked**.
3. Select the **extension** folder inside this project.
4. Pin **Pip · share a page** using the browser's extensions menu.
5. In Pip's chat window, open **Settings**, then **Copy pairing code**.
6. Visit a normal webpage, click the Pip extension, paste the code, and click **Share this page**. The extension remembers the code locally.

The page title and character count appear in Pip's chat. Sharing alone does not call an AI service. The pairing code is separate from your API key; it only permits sending snapshots to the local app.

## Enable AI replies

Open Pip's **Settings**, paste an **OpenAI API key**, and choose **Save for this session**. The default model is `gpt-4.1-mini`; you can enter another Responses-compatible model available to your API account. Then ask a question or click **Summarise page**.

The key stays in the desktop process's memory, never the extension or a settings file. You will need to enter it again after quitting. Advanced option: set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` in your launch environment. Requests use the [OpenAI Responses API](https://developers.openai.com/api/docs/guides/text) with `store: false`. API usage may incur charges; the app does not configure billing.

## What Pip can read

Each click on **Share this page** captures a snapshot of readable DOM text, preferring the main/article area. It includes the page title and URL, stripping query strings and fragments. Text is limited to 24,000 characters; long pages may be incomplete. It skips form fields, editable areas, scripts and hidden elements. Text already rendered on a page can still contain private information.

Pip does not continuously track your active tab. **Share again after navigating or changing the page.** It cannot read browser settings pages, extension store pages, local files, cross-origin frames, closed shadow roots, canvas-rendered documents, or text inside images. PDF viewers may yield no text. It cannot click or type into websites.

When you ask an AI question, the shared snapshot plus up to six recent chat exchanges are sent to OpenAI over HTTPS. Page snapshots and chats stay in memory locally; they are not written to disk. Receiving a new snapshot clears the previous chat so that answers use the newly shared page. **Forget page & chat** clears local context and ignores old replies still in flight; it cannot recall a request already sent to OpenAI.

## Local connection

The app listens only on `127.0.0.1:17373`. Requests require a random pairing token stored in `.local/pairing-code.txt` (ignored by Git), reject ordinary website origins, and validate request size and data. This is a small authenticated HTTP loopback bridge, not a registered native-messaging host; it avoids an installer and registry changes for this prototype. The extension requests only `activeTab`, `scripting`, `storage`, and access to the loopback host. It has no persistent permission to read all websites. Browser permission to reach the local app may be requested by newer browser versions.

## Troubleshooting

- **Can't reach Pip:** launch the desktop app first. If your browser requests local network access, allow it for this extension. No inbound public network access is required.
- **Pairing code rejected:** copy the code again from Pip's Settings. If `.local` was deleted, the code changes on the next launch.
- **Port 17373 busy:** quit the other Pip instance. If another program owns the port, stop it or change the port in both `bridge.py` and `extension/popup.js`.
- **No readable text:** try a normal article page. Scanned PDFs, images, and canvas-based apps need a different reading mechanism.
- **AI error:** verify the API key, model access, and API quota in your account. You can still preview Pip and share pages without a key.

## Verification

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node --check extension/popup.js
node tests/extension.cjs
python tests/ui_smoke.py
```

The UI smoke check briefly opens Pip and closes it. Quit an existing Pip instance before running it. Automated tests mock the external AI service; a real reply requires your own API key. Browser extension installation and browser-specific permissions need a manual check in your browser.

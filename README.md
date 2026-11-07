# Screen Squatters

A little Windows desktop home for three AI housemates. They're here to hang out, tease each other, remember shared jokes and play games with you. Built with Python's standard library and a Chrome/Edge extension; no third-party packages required.

| Housemate | Personality |
| --- | --- |
| **Pip** | Dopey, distractible and sweet, with absurd ideas and a light stammer. |
| **Byte** | A smart, kind, excitable nerd who loves games, facts and terrible puns. Helpful when asked. |
| **Rex** | Arrogant, theatrical and mildly rude. Affectionate snark, competitive energy and a tiny crown. |

## Start the house

Windows with Python 3.10+ and Tkinter is required (Python 3.11 is already installed on this laptop). Double-click **launch.cmd**, or run `python desktop.py` in this folder. If an older Pip instance is running, right-click its character and quit it first: both versions use port 17373.

Only a small, borderless house appears on your desktop at launch. Click it: the front wall fades away to reveal three bedrooms and a little living room. Tap a character in their room to wake them; they walk out onto the desktop. Tap a room again to send that housemate home. Click the roof to put the front wall back. Drag the house to move it.

Click a desktop character or the sofa to open an optional conversation window. Closing that window leaves the house and its residents running. Right-click the house for chat, games, settings, pause and quit. Right-click an individual character for chat, sleep or memory. There is no dashboard at startup, automatic startup registration or tray service.

Right-click the house, open **Settings & memories → Connection**, enter a **Gemini API key** from [Google AI Studio](https://aistudio.google.com/api-keys) and save it for the session. The key stays in process memory and never goes into the extension or a settings file. Advanced launch options: `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) and `GEMINI_MODEL` environment variables. Default model: `gemini-3.5-flash-lite`; another model must support Gemini `generateContent`, JSON output, image inputs and `countTokens`. Model IDs can be entered with or without the `models/` prefix.

Character animation, settings and page reception can be previewed without a key. Conversations and agent game turns require a working API connection. API usage may incur charges.

## Hang out

- Wake any combination of housemates and click one to chat. Each awake character gets a separate turn and can react to what the others said. They glance toward the friend who spoke previously.
- **Automatic conversation** (house context menu or Housemates settings) enables one character to speak approximately every 25 seconds after a turn completes, rotating among awake characters. It starts enabled, but no requests run until a character is awake and an API key is present.
- Uncheck it for conversation only when you send a message. Game turns continue while a game is active.
- **Everyone home / pause** sends all three walking home and stops future AI turns and screenshots. Their natural wake cycle stays paused until you wake someone or toggle **Autonomous life** off and back on. A request already submitted may still finish and be charged.

They know they're AI companions. Their prompts emphasise social conversation and distinctive personalities rather than task completion. They have no tools to control your computer or browse independently.

## A life on the desktop

Autonomous life starts enabled. Everyone initially sleeps inside; their first natural wake times are staggered 45–120 seconds after startup. Each housemate wanders at a leisurely pace, stays on the primary display, and normally rests after 4–8 minutes awake. Rest lasts roughly 90–210 seconds before an eligible housemate wakes again. Gemini can also decide to wander or rest during a conversation turn. Game participants defer their natural rest cycle until the game ends.

Local movement and rhythm timers use no API tokens. Conversations still use each character's allowance. Budget exhaustion prevents automatic waking until you refill; there is no automatic refill. Moving or spontaneously waking windows don't take keyboard focus. Dragging a character holds off their next movement for 20 seconds so they don't fight your placement.

Disable **Autonomous life** from the house context menu or **Settings → Housemates** to stop automatic wandering and wake/rest cycles; explicit sleep still lets them walk home. Manual wake, chat and dragging remain available. Rhythms restart with everyone asleep on app launch. The house and its context menu remain available even when everyone is asleep.

## Looking at something interesting

During an ordinary AI turn, a housemate may choose an interest from its current observation. Browser snapshots include up to 12 visible headings, links, buttons or labelled media, with their viewport positions. Gemini chooses a target by index; the app resolves its location. With screenshot fallback, Gemini can identify a point within the image instead.

The housemate walks beside the target, looks at it, raises an arm, and shows a small coloured marker while saying its line. The marker lets pointer input pass through. They don't click, move your mouse or type into another app. Gestures are cleared if the foreground window changes, moves/resizes, or the browser target metadata changes. Old single-share snapshots without current window geometry can be discussed but cannot position a character.

Browser placement estimates the content viewport below the browser toolbar; side panels, unusual browser chrome and display scaling can make pointing approximate. Movement stays on the primary display. Screenshot understanding and interest selection depend on Gemini and can be mistaken. Game turns don't choose screen interests. Local wandering and return-home animations work without model inference.

## Token allowances and sleep

Each character has a separate allowance (default 20,000 tokens). Input, reply **and thinking** tokens count, including conversation context, personality instructions, memories and any image input. A token limit is an application allowance, not a currency spending cap.

Before each inference, the app calls Gemini's [`countTokens` endpoint](https://ai.google.dev/api/tokens) with the intended generation request, including system instructions and image parts. If the remaining allowance cannot fit the counted input and a minimum reply, the character goes home. Otherwise, `maxOutputTokens` is capped to fit. Gemini's reported `usageMetadata.totalTokenCount`, including thinking tokens, is reconciled after the response; if the provider exceeds its preflight allowance, automatic hangout stops. There is only one model turn in flight at a time. The default Flash-Lite model uses minimal thinking; Gemini 3 Flash/Pro models use low thinking, and Gemini 2.5 Flash models disable thinking to preserve room for short replies. Very small output budgets can still produce truncated JSON and pause hangout.

In **Settings → Housemates**, enter a new allowance (256–1,000,000) and click **Refill tokens** to reset that character's used count. Ordinary sleep/wake doesn't reset usage. You cannot refill a character during its in-flight turn.

The allowance remaining for an in-flight request is reserved on disk before sending. On success, unused reservation is returned. If usage cannot be verified, a conservative reservation is charged and automatic hangout pauses. If the app is closed or crashes during a request, the entire remaining reservation is counted on restart because the provider may still have billed it. This favours stopping over silently overspending; explicit refill/reset is available. Usage reported by the provider remains authoritative for billing.

## Memories

Each character has its own notebook of up to 30 short memories. During ordinary conversation, a character can leave up to two notes in its own or another character's notebook. Notes include their author and time, so Byte can remember something Rex said without losing the source.

The model is instructed to remember shared jokes, relationships, game outcomes and preferences explicitly volunteered by you. It is instructed not to memorise raw screen content, private identifiers or secret roles. Generated memories are observations and can be wrong. Inspect them with **Memory** and remove individual notes. Memory updates are disabled during games; the app records the public result when a game finishes.

Memories, allowances and usage are saved in `.local/house.json`, which is excluded from Git. Chat transcripts, browser snapshots and screenshots remain in memory. An app restart keeps memories and usage but sends everyone to sleep.

**Settings → Factory reset** restores all three characters, default allowances and memories, clears local conversation and the game, sends everyone home and turns screenshots off. It asks for confirmation in the app. Your API connection and extension pairing are kept. Reset cannot recall submitted requests or remove data already transmitted to a provider.

## Games

**Tic-tac-toe:** wake a housemate, right-click the house, choose **Play a game → Tic-tac-toe** and pick an opponent. With two or more awake, you can also watch the first two play each other. Click squares on your turn. The local engine validates turn order, occupied squares, wins and draws; a model's invalid move falls back to the first open square.

**Mafia:** wake all three. The four players are you, Pip, Byte and Rex, with one randomly assigned mafia member and three townsfolk. Everyone gets a discussion turn and a vote; ties eliminate nobody. At night the mafia secretly chooses one player to eliminate. The town wins by voting out the mafia; the mafia wins at parity. Eliminated players spectate. Your own role appears in the game window; each model receives only its own role. Night speech isn't published, and per-character token counters are hidden during Mafia to avoid revealing the actor. There are no doctor/detective roles in this four-player version.

Speak in the living room or click pass during your discussion turn. Vote/choose a night target in the game window. Game inference uses each character's own allowance. Sending a player home or exhausting their budget ends the current game. An API error ends the game and pauses automatic hangout rather than retrying paid requests repeatedly.

## Browser extension

1. Open `chrome://extensions` or `edge://extensions`.
2. Enable **Developer mode**, then **Load unpacked** and select this project's **extension** folder.
3. Pin **Screen Squatters · browser companion**.
4. Copy the pairing code from the home's **Settings → Connection** and paste it into the extension popup. It is a local bridge credential, separate from the API key.
5. On a normal webpage, click **Share this page** for a single snapshot.

If you installed the earlier Pip extension, reload it on the browser's Extensions page to apply this version's scripts and permissions.

**Start following focused pages** is optional. It asks for HTTP/HTTPS website access and registers a reader that checks every five seconds. It forwards text only from the focused browser window's active tab, while at least one housemate is awake. Reload other already-open tabs if necessary. **Stop following** disables forwarding and unregisters future injections; already-injected watchers stop reading when following is off. Website permission remains granted until you revoke it in the browser's extension settings.

The reader prefers `main`/`article` and extracts text intersecting the viewport. It skips hidden content, scripts, inputs, textareas and editable regions. Up to 24,000 characters are received locally; each AI turn uses at most 6,000. Page titles and URLs are included, with URL credentials/query/fragment removed. Displayed text can still contain private information.

It does not read browser settings, extension store pages, local files, cross-origin iframes, closed shadow roots or text rendered in canvas/images. PDF viewers may provide no text. Single shared snapshots are available for up to five minutes; they are snapshots, not a claim of live access. Automatic browser observations must be fresh and match the foreground browser title.

## Periodic screenshot fallback

In **Settings → Screen awareness**, enable **periodic foreground-window screenshots** and choose an interval (15–300 seconds, default 30). This resets to OFF each app launch.

While anyone is awake, the app checks the foreground window. Fresh matching browser text is preferred; otherwise, screenshot fallback captures the foreground window, downscaled to at most 1024 pixels on its longest side. It uses Windows APIs and encodes PNG in memory. It skips the house's own foreground windows and Windows sign-in surfaces. Protected windows can return blank images. Screen sharing isn't guaranteed to extract fine text from small/low-detail images.

The porch light is yellow while screenshot capture is enabled and someone is awake, mint when fresh browser text is available, and dim otherwise. Screenshots are never saved to disk. An eligible snapshot can be sent to Google Gemini on the next conversation turn, including automatic hangout. Snapshot inputs are untrusted reference data and cannot trigger actions in other apps. Game turns don't receive screen observations.

Turn capture off before viewing private material. **Settings → Screen awareness → Clear current snapshot** discards the snapshot; it doesn't erase conversation or stop future capture/following. Sleeping everyone stops further capture. The extension has its own stop-following switch.

## Connection and troubleshooting

The authenticated HTTP bridge listens only on `127.0.0.1:17373`. Its random token is stored in `.local/pairing-code.txt` (Git-ignored). Requests validate the host, origin, token, body size and page fields. `/status` reports whether anyone is awake; `/page` accepts snapshots. This prototype doesn't require a native-messaging installer or registry changes.

- **Port busy:** quit the older Pip or another Screen Squatters instance first.
- **Can't reach the house:** launch the desktop app. If your browser requests local network access, allow it for this extension.
- **Pairing rejected:** copy the code again from Connection settings. Deleting `.local` regenerates it on next launch.
- **HTTP 402 / prepaid credits depleted:** the key may be valid and `countTokens` may work while generation is blocked by billing. Open [Google AI Studio Projects](https://ai.studio/projects), check the API project's billing and add prepaid credits. Rejected generation requests don't spend the companion's local allowance.
- **Other AI errors:** messages include the HTTP code. Check key, API quota, and model compatibility. Automatic hangout pauses after errors; re-enable it after fixing the connection. Explicit client rejections (including 400/401/402/403/404/429) return their token reservation. Timeouts and server errors retain a conservative reservation because usage is uncertain.
- **Character falls asleep before reaching the exact limit:** the next input plus a usable reply wouldn't fit. Refill its allowance.
- **High usage:** context is charged on every turn, not just visible dialogue. Shorter context and fewer awake housemates reduce usage.

Requests use Google's [Gemini Developer API](https://ai.google.dev/api/generate-content): `generateContent`, JSON replies, and base64 PNG `inlineData` for screenshot inputs. API keys are sent in the `x-goog-api-key` header, never in URLs. No server-side conversation or explicit cache is created by the app. Google's [Gemini API terms and data handling policies](https://ai.google.dev/gemini-api/terms) apply to transmitted text and images.

Switching from the earlier build keeps local memories and used allowances. Restart the app, enter your Gemini key in Connection settings, and reload the extension to update its provider disclosure. Earlier provider environment variables are no longer used.

## Tests

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node tests/extension.cjs
python tests/ui_smoke.py
```

Core tests cover budgets, crash reservations, memory isolation, reset, game rules, role privacy, bridge authentication, snapshot selection and PNG encoding. Node tests use isolated mocked Chrome APIs for popup/worker contracts and text filtering. The UI smoke check uses a temporary house and random local port, mocks AI replies, opens real windows, exercises both games and captures only its own controlled window to verify native PNG encoding. It closes its windows afterward. No live API calls are made by the tests. Real model behaviour and extension installation/permissions still require testing with your API account and browser.

To diagnose connectivity, run `python diagnose_gemini.py`. It prompts for a key with hidden input (never saved), then checks model availability and token counting. Add `--generate` to also make one short generation request, which may use API credits. `--model MODEL_ID` selects a different model. Diagnostic output includes HTTP codes and usage metadata, not credentials or conversation/page content.

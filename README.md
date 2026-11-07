# Screen Squatters

A little Windows desktop home for three AI housemates. They're here to hang out, tease each other, remember shared jokes and play games with you. Built with Python's standard library and a Chrome/Edge extension; no third-party packages required.

| Housemate | Personality |
| --- | --- |
| **Pip** | Dopey, distractible and sweet, with absurd ideas and a light stammer. |
| **Byte** | A smart, kind, excitable nerd who loves games, facts and terrible puns. Helpful when asked. |
| **Rex** | Arrogant, theatrical and mildly rude. Affectionate snark, competitive energy and a tiny crown. |

## Start the house

Windows with Python 3.10+ and Tkinter is required (Python 3.11 is already installed on this laptop). Double-click **launch.cmd**, or run `python desktop.py` in this folder. If an older Pip instance is running, right-click its character and quit it first: both versions use port 17373.

Everyone starts asleep. Wake one, two or all three using their cards. Awake housemates appear as draggable, animated desktop characters, with speech bubbles. Click a character to open the home; right-click for its sleep and memory menu. Sleeping characters appear back inside their rooms. Closing the home exits the application; there is no startup registration or system tray service.

Open **Settings → Connection**, enter an OpenAI API key and save it for the session. The key stays in process memory and never goes into the extension or a settings file. Advanced launch options: `OPENAI_API_KEY` and `OPENAI_MODEL` environment variables. Default model: `gpt-4.1-mini`; another model must support Responses, JSON output, image inputs and input-token counting.

Character animation, settings and page reception can be previewed without a key. Conversations and agent game turns require a working API connection. API usage may incur charges.

## Hang out

- Wake any combination of housemates and type into the living room. Each awake character gets a separate turn and can react to what the others said.
- **Let awake housemates hang out** enables automatic conversation: one character speaks approximately every 25 seconds after a turn completes, rotating among awake characters. It starts enabled, but no requests run until a character is awake and an API key is present.
- Uncheck it for conversation only when you send a message. Game turns continue while a game is active.
- **Everyone home** sends all three to sleep and stops future AI turns and screenshots. A request already submitted may still finish and be charged.

They know they're AI companions. Their prompts emphasise social conversation and distinctive personalities rather than task completion. They have no tools to control your computer or browse independently.

## Token allowances and sleep

Each character has a separate allowance (default 20,000 tokens). Input **and** output tokens count, including conversation context, personality instructions, memories and any image input. A token limit is an application allowance, not a currency spending cap.

Before each inference, the app calls OpenAI's [input token counting endpoint](https://developers.openai.com/api/docs/guides/token-counting) with the intended context. If the remaining allowance cannot fit the input and a minimum reply, the character goes home. Otherwise, output is capped to fit. Reported usage is reconciled after the response. There is only one model turn in flight at a time.

Enter a new allowance (256–1,000,000) and click **Refill tokens** to reset that character's used count. Ordinary sleep/wake doesn't reset usage. You cannot refill a character during its in-flight turn.

The allowance remaining for an in-flight request is reserved on disk before sending. On success, unused reservation is returned. If usage cannot be verified, a conservative reservation is charged and automatic hangout pauses. If the app is closed or crashes during a request, the entire remaining reservation is counted on restart because the provider may still have billed it. This favours stopping over silently overspending; explicit refill/reset is available. Usage reported by the provider remains authoritative for billing.

## Memories

Each character has its own notebook of up to 30 short memories. During ordinary conversation, a character can leave up to two notes in its own or another character's notebook. Notes include their author and time, so Byte can remember something Rex said without losing the source.

The model is instructed to remember shared jokes, relationships, game outcomes and preferences explicitly volunteered by you. It is instructed not to memorise raw screen content, private identifiers or secret roles. Generated memories are observations and can be wrong. Inspect them with **Memory** and remove individual notes. Memory updates are disabled during games; the app records the public result when a game finishes.

Memories, allowances and usage are saved in `.local/house.json`, which is excluded from Git. Chat transcripts, browser snapshots and screenshots remain in memory. An app restart keeps memories and usage but sends everyone to sleep.

**Settings → Factory reset** restores all three characters, default allowances and memories, clears local conversation and the game, sends everyone home and turns screenshots off. It asks for confirmation in the app. Your API connection and extension pairing are kept. Reset cannot recall submitted requests or remove data already transmitted to a provider.

## Games

**Tic-tac-toe:** wake a housemate, click the game button and choose an opponent. With two or more awake, you can also watch the first two play each other. Click squares on your turn. The local engine validates turn order, occupied squares, wins and draws; a model's invalid move falls back to the first open square.

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

The status bar indicates screen capture and the current observation. Screenshots are never saved to disk. An eligible snapshot can be sent to OpenAI on the next conversation turn, including an automatic hangout turn. Snapshot inputs are treated as untrusted reference data and cannot trigger computer actions. Game turns don't receive screen observations.

Turn capture off before viewing private material. **Clear screen context** discards the current snapshot; it doesn't erase conversation or stop future capture/following. Sleeping everyone stops further capture. The extension has its own stop-following switch.

## Connection and troubleshooting

The authenticated HTTP bridge listens only on `127.0.0.1:17373`. Its random token is stored in `.local/pairing-code.txt` (Git-ignored). Requests validate the host, origin, token, body size and page fields. `/status` reports whether anyone is awake; `/page` accepts snapshots. This prototype doesn't require a native-messaging installer or registry changes.

- **Port busy:** quit the older Pip or another Screen Squatters instance first.
- **Can't reach the house:** launch the desktop app. If your browser requests local network access, allow it for this extension.
- **Pairing rejected:** copy the code again from Connection settings. Deleting `.local` regenerates it on next launch.
- **AI error:** check key, API quota, and model compatibility. Automatic hangout pauses after errors; re-enable it after fixing the connection.
- **Character falls asleep before reaching the exact limit:** the next input plus a usable reply wouldn't fit. Refill its allowance.
- **High usage:** context is charged on every turn, not just visible dialogue. Shorter context and fewer awake housemates reduce usage.

Requests use the [Responses API](https://developers.openai.com/api/docs/guides/text), `store: false`, JSON replies, and optional [image inputs](https://developers.openai.com/api/docs/guides/images-vision). This controls response storage, not all provider-side retention policies.

## Tests

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node tests/extension.cjs
python tests/ui_smoke.py
```

Core tests cover budgets, crash reservations, memory isolation, reset, game rules, role privacy, bridge authentication, snapshot selection and PNG encoding. Node tests use isolated mocked Chrome APIs for popup/worker contracts and text filtering. The UI smoke check uses a temporary house and random local port, mocks AI replies, opens real windows, exercises both games and captures only its own controlled window to verify native PNG encoding. It closes its windows afterward. No live API calls are made by the tests. Real model behaviour and extension installation/permissions still require testing with your API account and browser.

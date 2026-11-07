# Screen Squatters

A little Windows desktop home for three AI housemates. They're here to hang out, tease each other, remember shared jokes and play games with you. Built with Python's standard library and a Firefox extension; no third-party runtime packages required.

| Housemate | Personality |
| --- | --- |
| **Burt** | Lovable, literal and often confused. Hesitates naturally, makes terrible strategic plays, and very occasionally reveals PhD-level knowledge of tectonics and volcanoes. |
| **Byte** | A smart, kind, excitable nerd who loves games, facts and terrible puns. Helpful when asked. |
| **Rex** | Arrogant, theatrical and mildly rude. Affectionate snark, competitive energy and a tiny crown. |

## Start the house

Windows with Python 3.10+ and Tkinter is required (Python 3.11 is already installed on this laptop). Double-click **launch.cmd**, or run `python desktop.py` in this folder. If an older Screen Squatters instance is running, right-click its character and quit it first: both versions use port 17373.

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

Conversation now has a short typing pause, animated typing dots and a gradual text reveal in both the chat and character bubbles. Text arrives at roughly 20–26 characters per second, with extra pauses at punctuation. Long bubbles continue across short pages; the full reply remains in chat. The next AI turn waits until the visible reply finishes. Filler-only model responses such as “hmm…” become silence. Typing animation itself uses no tokens. Casual speech prompts encourage contractions, short reactions and self-corrections while preserving each character's personality.

The housemates have alternating steps, swinging arms, walking bounce, idle/sleep breathing, offset blinking and animated mouths/hand gestures while speaking. Speech bubbles have rounded corners, shadows, coloured name labels and bouncing typing dots. Stand still still freezes travel; expressive idle and talking animations remain.

## A life on the desktop

Autonomous life starts enabled. Everyone initially sleeps inside; their first natural wake times are staggered 45–120 seconds after startup. Each housemate wanders at a leisurely pace, stays on the primary display, and normally rests after 4–8 minutes awake. Rest lasts roughly 90–210 seconds before an eligible housemate wakes again. Gemini can also decide to wander or rest during a conversation turn. Game participants defer their natural rest cycle until the game ends.

Local movement and rhythm timers use no API tokens. Conversations still use each character's allowance. Sleeping gradually restores their available local allowance; a spent character can wake again once enough energy has recovered for another turn. Moving or spontaneously waking windows don't take keyboard focus. Dragging a character holds off their next movement for 20 seconds so they don't fight your placement.

Disable **Autonomous life** from the house context menu or **Settings → Housemates** to stop automatic wandering and wake/rest cycles; explicit sleep still lets them walk home. Manual wake, chat and dragging remain available. Rhythms restart with everyone asleep on app launch. The house and its context menu remain available even when everyone is asleep.

**Stand still**, in the house or character context menu, is a separate switch: it freezes autonomous movement while leaving chat and wake/rest behaviour available. Manual dragging still works. Sending someone home while frozen hides them immediately instead of leaving them stuck halfway home. The setting is remembered after restarting.

## Looking at something interesting

During an ordinary AI turn, a housemate may choose an interest from its current observation. Browser snapshots include up to 12 visible headings, links, buttons or labelled media, with their viewport positions. Gemini chooses a target by index; the app resolves its location. With screenshot fallback, Gemini can identify a point within the image instead.

The housemate walks beside the target, looks at it, raises an arm, and shows a small coloured marker while saying its line. The marker lets pointer input pass through. They don't click, move your mouse or type into another app. Gestures are cleared if the foreground window changes, moves/resizes, or the browser target metadata changes. Old single-share snapshots without current window geometry can be discussed but cannot position a character.

Browser placement estimates the content viewport below the browser toolbar; side panels, unusual browser chrome and display scaling can make pointing approximate. Movement stays on the primary display. Screenshot understanding and interest selection depend on Gemini and can be mistaken. Game turns don't choose screen interests. Local wandering and return-home animations work without model inference.

## Token allowances and sleep

Each character has a separate allowance (default 20,000 tokens). Input, reply **and thinking** tokens count, including conversation context, personality instructions, memories and any image input. A token limit is an application allowance, not a currency spending cap.

Before each inference, the app calls Gemini's [`countTokens` endpoint](https://ai.google.dev/api/tokens) with the intended generation request, including system instructions and image parts. If the remaining allowance cannot fit the counted input and a minimum reply, the character goes home. Otherwise, `maxOutputTokens` is capped to fit. Gemini's reported `usageMetadata.totalTokenCount`, including thinking tokens, is reconciled after the response; if the provider exceeds its preflight allowance, automatic hangout stops. There is only one model turn in flight at a time. The default Flash-Lite model uses minimal thinking; Gemini 3 Flash/Pro models use low thinking, and Gemini 2.5 Flash models disable thinking to preserve room for short replies. Very small output budgets can still produce truncated JSON and pause hangout.

In **Settings → Housemates**, enter a new allowance (256–1,000,000) and click **Refill tokens** to reset that character's used count immediately. Otherwise, **used tokens decrease gradually while the character is asleep inside the house**, increasing available energy without changing its maximum allowance. Recovery defaults to **1,000 tokens per minute per sleeping companion**.

Right-click the house → **Sleep recovery** to choose Off, 100, 500, 1,000 or 5,000 tokens per minute, or enter a custom rate (0–1,000,000). Fractional ticks accumulate so low rates work smoothly. The rate and recovered counts are saved locally; recovery runs only while the app is open. Awake characters, those still walking home, and requests with tokens still reserved don't recover. Characters exhausted before a usable request could fit wait until enough tokens have recovered before automatically waking.

Recovery restores the app's local energy allowance; it does not refund provider charges. Recovering and waking again can lead to further paid API usage, so this allowance is not a lifetime spending cap. You cannot manually refill a character during its in-flight turn.

The allowance remaining for an in-flight request is reserved on disk before sending. On success, unused reservation is returned. If usage cannot be verified, a conservative reservation is charged and automatic hangout pauses. If the app is closed or crashes during a request, the entire remaining reservation is counted on restart because the provider may still have billed it. This favours stopping over silently overspending; explicit refill/reset is available. Usage reported by the provider remains authoritative for billing.

## Memories

Each character has its own notebook of up to 30 short memories. During ordinary conversation, a character can leave up to two notes in its own or another character's notebook. Notes include their author and time, so Byte can remember something Rex said without losing the source.

The model is instructed to remember shared jokes, relationships, game outcomes and preferences explicitly volunteered by you. It is instructed not to memorise raw screen content, private identifiers or secret roles. Generated memories are observations and can be wrong. Inspect them with **Memory** and remove individual notes. Memory updates are disabled during games; the app records the public result when a game finishes.

Memories, allowances and usage are saved in `.local/house.json`, which is excluded from Git. Chat transcripts, browser snapshots and screenshots remain in memory. An app restart keeps memories and usage but sends everyone to sleep.

**Settings → Factory reset** restores all three characters, default allowances and memories, clears local conversation and the game, sends everyone home and turns screenshots off. It asks for confirmation in the app. Your API connection and extension pairing are kept. Reset cannot recall submitted requests or remove data already transmitted to a provider.

## Games

**Tic-tac-toe:** wake a housemate, right-click the house, choose **Play a game → Tic-tac-toe** and pick an opponent. With two or more awake, you can also watch the first two play each other. Click squares on your turn. The local engine validates turn order, occupied squares, wins and draws; a model's invalid move falls back to the first open square.

**Mafia:** wake all three. The four players are you, Burt, Byte and Rex, with one randomly assigned mafia member and three townsfolk. Everyone gets a discussion turn and a vote; ties eliminate nobody. At night the mafia secretly chooses one player to eliminate. The town wins by voting out the mafia; the mafia wins at parity. Eliminated players spectate. Your own role appears in the game window; each model receives only its own role. Night speech isn't published, and per-character token counters are hidden during Mafia to avoid revealing the actor. There are no doctor/detective roles in this four-player version.

Speak in the living room or click pass during your discussion turn. Vote/choose a night target in the game window. Game inference uses each character's own allowance. Sending a player home or exhausting their budget ends the current game. An API error ends the game and pauses automatic hangout rather than retrying paid requests repeatedly.

### Poker night

Right-click the house → **Play a game → Poker night**, or type **“play poker”** in chat. With a working API connection and energy available, all three housemates wake and sit with you around an animated table. Their desktop bodies reappear when you leave. Ordinary wandering and natural rest pause while the table is open. Movie mode ends when poker begins.

This is four-player **fixed-limit Texas hold'em with play chips**: two private cards each, a shared flop/turn/river, 5/10 blinds, bets of 10 before/on the flop and 20 on the turn/river, with up to three raises per street. Click **Fold**, **Check**, **Call** or **Bet/Raise** on your turn. The app enforces turn order and legal bets, evaluates the best five-card hand, and splits tied pots. Illegal model actions fall back to checking or calling. Each new hand starts everyone with 1,000 chips and rotates the dealer; stacks don't carry between hands, so there are no all-ins or side pots.

Your own cards always appear to you. Each model gets only its own cards, the shared board, public actions and hands that have explicitly been shown. Each housemate decides whether to reveal its cards after its action, including a fold. Leave **Show my cards after my action** unchecked to keep yours private, check it before acting to reveal afterward, or click **Reveal my cards now**. A reveal is public for the rest of that hand and cannot be undone. Even at the end, the local engine can determine the winner without forcing anyone's cards face-up. You can still reveal afterward. **Deal next hand** clears all reveals and deals fresh cards.

Only the public game result becomes a memory. Game state and hands aren't saved between app launches. AI decisions and banter use the normal token allowance; dealing, evaluation and animations are local. Generated speech is instructed to keep unrevealed cards private; this is a social companion prototype rather than an adversarial secure multiplayer service.

## Movie mode

Type **“Everybody watch something with me”**, **“Let's watch a movie”** or **“Movie mode”** into chat. You can also toggle **Movie mode** in the house or character context menu. The invitation works without an API key: everyone with available energy gathers on little armchairs with popcorn. By default they sit in the bottom-left corner; **Movie seats** in the house menu selects any corner. When Stand still is on, an explicit movie invitation places them directly in their seats. You can drag an individual chair to another spot.

While watching, they stay seated and defer natural wandering/rest, except that exhausted companions still go home. Recovering housemates can rejoin when their sleep timer and energy permit it. Ending movie mode packs away the chairs and resumes ordinary behaviour. **Stop movie mode** or **“We're done watching”** exits; starting a game or choosing **Everyone home / pause** also ends it. Movie mode itself isn't resumed automatically after an app restart; the seat corner is remembered.

Movie conversations focus on the shared film/show/video. Automatic reactions are quieter and less frequent (roughly 60–100 seconds after a turn completes), and no automatic inference runs without a recent shared observation. Empty/quiet replies are allowed. Direct questions still receive responses from the awake companions. Uncheck **Automatic conversation** to watch without unsolicited reactions. Movie turns ignore wander/inspect/rest intents, and don't write plot details into durable memories.

Movie mode **does not switch on screen capture**. Enable **Screen snapshots** or share visible captions/text through the extension. With screenshot permission on, movie mode prefers video frames over browser controls. It binds to the first observed foreground window/title and pauses observations when you switch apps or pages, so unrelated content doesn't become movie commentary. Invite them again (or toggle mode off/on) to watch a different window/title.

This is periodic still-frame/caption awareness, not continuous video or audio listening. The characters are instructed not to invent scenes, dialogue, music, motion, future plot or spoilers. Player controls/title alone aren't a basis for scene reactions. Protected video may produce black screenshots. Live reaction quality depends on Gemini, a working key and API credits.

## Firefox extension

Requires Firefox desktop 140 or newer. This directory now contains a Firefox-native Manifest V3 extension using `browser` APIs and background scripts.

1. Start the updated desktop app. In Firefox open `about:debugging#/runtime/this-firefox`.
2. Click **Load Temporary Add-on** and select **extension/manifest.json**, or the packaged **dist/screen-squatters-firefox-0.4.0.xpi**.
3. Open **Screen Squatters · Firefox live feed** from Firefox's extensions menu.
4. Copy the pairing code from the house's **Settings → Connection** into the popup. This local bridge credential is separate from your Gemini API key.
5. Click **Enable live updates** and allow website access. Focus a normal HTTP/HTTPS webpage. A **LIVE** badge and popup status show successful deliveries. **Share this page once** remains available without enabling the continuous feed.

This development build is unsigned. Firefox removes temporary add-ons when it closes; load it again next session. A permanent installation in standard Firefox requires Mozilla signing. Run `python tools/package_firefox.py` to rebuild the unsigned XPI; packaging alone does not sign it. See Mozilla's [packaging instructions](https://extensionworkshop.com/documentation/publish/package-your-extension/).

The extension sends the focused, non-private tab to the local desktop bridge about once a second, including while **all companions are asleep**. DOM changes, scrolling, navigation and media events also trigger debounced refreshes. Unchanged pages reuse cached text; URL changes invalidate it. Existing tabs are activated immediately when following starts. Desktop disconnections retry automatically. This feed does not make an AI request every second: companions use the latest context during their normal turns.

The feed includes title, cleaned URL, description, author, site name, language, page type, canonical URL, visible headings and links, reading progress, up to 12 visible target positions, media playback state and already-showing text-track captions. It sends up to 24,000 characters of viewport text and 12,000 of main/article context locally. Each AI turn receives up to 6,000 viewport characters, a 3,000-character page excerpt and bounded metadata. The extension does not record audio or capture screenshots/video frames. Movie visuals still use the desktop's separately enabled screenshot fallback.

The reader skips scripts, hidden content, inputs, textareas, selects and editable regions. It does not access passwords, field values, cookies or raw HTML. URL credentials, query strings and fragments are stripped. Ordinary displayed content and metadata can still contain private information. The popup explains that selected context may be sent to Google Gemini during companion turns.

**Pause live updates** stops reading and clears the desktop browser snapshot. Tab changes, loading, loss of browser focus and protected pages also clear the previous browser context; ordered stream messages prevent delayed snapshots from restoring it. Granted website permission remains until revoked in Firefox's extension settings. Private windows are excluded entirely.

Firefox internal pages, extension store/protected pages, local files, cross-origin iframes, closed shadow roots and canvas/image text are unavailable. PDF viewers may provide no text. Single shared snapshots remain available for up to five minutes. Automatic browser observations must be fresh and match the foreground browser title.

## Periodic screenshot fallback

In **Settings → Screen awareness**, enable **periodic foreground-window screenshots** and choose an interval (15–300 seconds, default 30). This resets to OFF each app launch.

While anyone is awake, the app checks the foreground window. Fresh matching browser text is preferred; otherwise, screenshot fallback captures the foreground window, downscaled to at most 1024 pixels on its longest side. It uses Windows APIs and encodes PNG in memory. It skips the house's own foreground windows and Windows sign-in surfaces. Protected windows can return blank images. Screen sharing isn't guaranteed to extract fine text from small/low-detail images.

The porch light is yellow while screenshot capture is enabled and someone is awake, mint when fresh browser text is available, and dim otherwise. Screenshots are never saved to disk. An eligible snapshot can be sent to Google Gemini on the next conversation turn, including automatic hangout. Snapshot inputs are untrusted reference data and cannot trigger actions in other apps. Game turns don't receive screen observations.

Turn capture off before viewing private material. **Settings → Screen awareness → Clear current snapshot** discards the snapshot; it doesn't erase conversation or stop future capture/following. Sleeping everyone stops further capture. The extension has its own stop-following switch.

## Connection and troubleshooting

The authenticated HTTP bridge listens only on `127.0.0.1:17373`. Its random token is stored in `.local/pairing-code.txt` (Git-ignored). Requests validate the host, Firefox/Chrome extension origin, token, body size and page fields. `/status` reports whether anyone is awake; `/page` accepts snapshots; `/browser-state` clears outdated context. This prototype doesn't require a native-messaging installer or registry changes.

- **Port busy:** quit the other Screen Squatters instance first.
- **Can't reach the house:** launch the desktop app. If your browser requests local network access, allow it for this extension.
- **Pairing rejected:** copy the code again from Connection settings. Deleting `.local` regenerates it on next launch.
- **HTTP 402 / prepaid credits depleted:** the key may be valid and `countTokens` may work while generation is blocked by billing. Open [Google AI Studio Projects](https://ai.studio/projects), check the API project's billing and add prepaid credits. Rejected generation requests don't spend the companion's local allowance.
- **Other AI errors:** messages include the HTTP code. Check key, API quota, and model compatibility. Automatic hangout pauses after errors; re-enable it after fixing the connection. Explicit client rejections (including 400/401/402/403/404/429) return their token reservation. Timeouts and server errors retain a conservative reservation because usage is uncertain.
- **Character falls asleep before reaching the exact limit:** the next input plus a usable reply wouldn't fit. Let it recover while sleeping, increase the sleep recovery rate, or refill its allowance.
- **High usage:** context is charged on every turn, not just visible dialogue. Shorter context and fewer awake housemates reduce usage.

Requests use Google's [Gemini Developer API](https://ai.google.dev/api/generate-content): `generateContent`, JSON replies, and base64 PNG `inlineData` for screenshot inputs. API keys are sent in the `x-goog-api-key` header, never in URLs. No server-side conversation or explicit cache is created by the app. Google's [Gemini API terms and data handling policies](https://ai.google.dev/gemini-api/terms) apply to transmitted text and images.

Switching from the earlier build keeps local memories and used allowances. Restart the app, enter your Gemini key in Connection settings, and reload the extension to update its provider disclosure. Earlier provider environment variables are no longer used.

Existing Pip saves migrate to Burt automatically, including token usage, interrupted-request reservations and memories. Memory authors and references use Burt's new name. If a save already has Burt, that record takes precedence. Factory reset restores Burt's new personality.

## Tests

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node tests/extension.cjs
python tests/ui_smoke.py
```

Core tests cover budgets, sleep recovery, frozen movement, movie commands/seats/prompts, crash reservations, memory isolation, reset, game rules, poker hand rankings/private views/optional reveals/chip conservation across 300 simulated hands, paced speech, role privacy, bridge authentication, stream ordering, metadata validation, snapshot selection and PNG encoding. Node tests use isolated Firefox API mocks for permissions, popup/background contracts, SPA navigation, continuous updates and text filtering. The UI smoke check uses a temporary house and random local port, mocks AI replies/movie frames, exercises games, movie mode, progressive transcript ordering, poker controls/reveals/redealing and browser pause/late-message clearing, and captures only its own opaque conversation window to verify native PNG encoding. It closes its windows afterward. No live AI API calls are made by the tests.

`python tools/preview_social.py` renders poker and speech-bubble fixture previews into `.local/`. It asks only its own opaque test windows to paint themselves through Windows `PrintWindow`, checks process ownership, and does not capture the desktop or use live AI.

`tests/firefox_live.py --web-ext-js PATH_TO_WEB_EXT_JS` additionally runs Mozilla's `web-ext` with installed Firefox in a disposable headless profile. It verifies real repeated updates while companions sleep, metadata/DOM changes, SPA navigation, visible captions, media state and private-field filtering against local fixture pages. It does not use your personal browser profile or Gemini key. Validate the extension with `web-ext lint --source-dir extension`.

To diagnose connectivity, run `python diagnose_gemini.py`. It prompts for a key with hidden input (never saved), then checks model availability and token counting. Add `--generate` to also make one short generation request, which may use API credits. `--model MODEL_ID` selects a different model. Diagnostic output includes HTTP codes and usage metadata, not credentials or conversation/page content.

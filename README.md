# Screen Squatters

A little Windows desktop home for four AI housemates. They're here to hang out, tease each other, remember shared jokes and play games with you. Built with Python's standard library and a Firefox extension; no third-party runtime packages required.

| Housemate | Personality |
| --- | --- |
| **Burt** | Lovable, literal and often confused. Hesitates naturally, makes terrible strategic plays, and very occasionally reveals PhD-level knowledge of tectonics and volcanoes. |
| **Cody** | Cheerful, kind, innocent and a little clueless. Loves maths, anime, games and tiny discoveries; enthusiastic logic can go wonderfully wrong. |
| **Victoria** | A proud, posh, sharp-tongued woman with a knowing smirk, crisp British delivery and a fiercely loyal heart beneath the polish. |
| **Mika** | Gentle, quietly certain peacemaker with a fictional garden charity, a love of tea and a hidden talent for precision goldsmithing. |

## Start the house

Windows with Python 3.10+ and Tkinter is required (Python 3.11 is already installed on this laptop). Double-click **launch.cmd**, or run `python desktop.py` in this folder. If an older Screen Squatters instance is running, right-click its character and quit it first: both versions use port 17373.

Only a compact, borderless 160×143 house appears at launch. Click it to expand to 360×320: the front wall fades away to reveal four bedrooms and a living room. Tap a character in their room to wake them; they walk out onto the desktop. Tap a room again to send that housemate home. Click the roof to close the wall and shrink the house again. Drag the house to move it.

Click the sofa or choose Have a chat on the house menu for group chat, addressed to Everyone by default. Clicking a character opens the same shared chat with that character selected in the To menu. Choose Everyone to address the whole household. Closing that window leaves the house and its residents running. Right-click the house for chat, games, settings, pause and quit. Right-click an individual character for chat, sleep or memory. There is no dashboard at startup, automatic startup registration or tray service.

Right-click the house, open **Settings & memories → Connection**, enter a **Gemini API key** from [Google AI Studio](https://aistudio.google.com/api-keys) and save it for the session. The key stays in process memory and never goes into the extension or a settings file. Advanced launch options: `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) and `GEMINI_MODEL` environment variables. Default model: `gemini-3.5-flash-lite`; another model must support Gemini `generateContent`, JSON output, image inputs and `countTokens`. Model IDs can be entered with or without the `models/` prefix.

Character animation, settings and page reception can be previewed without a key. Conversations and agent game turns require a working API connection. API usage may incur charges.

## Hang out

Player messages are accepted while an AI request is running. A newer message takes precedence over an outdated ambient reply; the next responder receives the actual player message first. Direct replies are required to say something, with an in-character acknowledgement if a model returns only filler. Existing typed chat is completed so the player is not waiting behind a long animation. In poker, a group question asks one housemate to keep play moving; directed replies never make an accidental bet.

- Wake any combination of housemates and click one to chat. Each awake character gets a separate turn and can react to what the others said. They glance toward the friend who spoke previously.
- **Automatic conversation** (house context menu or Housemates settings) enables one character to speak approximately every 25 seconds after a turn completes, rotating among awake characters. It starts enabled, but no requests run until a character is awake and an API key is present.
- Uncheck it for conversation only when you send a message. Game turns continue while a game is active.
- **Everyone home / pause** sends everyone home and stops future AI turns and screenshots. Their natural wake cycle stays paused until you wake someone or toggle **Autonomous life** off and back on. A request already submitted may still finish and be charged.

They know they're AI companions. Their prompts emphasise social conversation and distinctive personalities rather than task completion. They can request bounded window moves only where you explicitly allow them in Windows settings. They cannot click, type, close apps or browse independently.

Conversation now has a short typing pause, animated typing dots and a gradual text reveal in both the chat and character bubbles. Text arrives at roughly 20–26 characters per second, with extra pauses at punctuation. Long bubbles continue across short pages; the full reply remains in chat. Normal conversation waits until a visible reply finishes. Poker remarks use a faster pace and do not block the next betting turn. Filler-only model responses such as “hmm…” become silence. Typing animation itself uses no tokens. Casual speech prompts encourage contractions, short reactions and self-corrections while preserving each character's personality.

The housemates are coloured balls with accessories: Burt’s curl, Cody’s glasses, Victoria’s crown and Mika’s gold ring and leaf. They hop when wandering, breathe while idle/asleep, blink at different times and animate their mouths while speaking. Speech bubbles have rounded corners, shadows, coloured name labels and bouncing typing dots. Stand still still freezes travel; expressive idle and talking animations remain.

## A life on the desktop

Autonomous life starts enabled. Everyone initially sleeps inside; their first natural wake times are staggered 45–120 seconds after startup. Each housemate wanders at a leisurely pace, stays on the primary display, and normally rests after 4–8 minutes awake. Rest lasts roughly 90–210 seconds before an eligible housemate wakes again. Gemini can also decide to wander or rest during a conversation turn. Game participants defer their natural rest cycle until the game ends.

Local movement and rhythm timers use no API tokens. Conversations still use each character's allowance. Sleeping gradually restores their available local allowance; a spent character can wake again once enough energy has recovered for another turn. Moving or spontaneously waking windows don't take keyboard focus. Dragging and releasing while moving throws a character; a quiet placement holds off wandering for about 20 seconds.

Disable **Autonomous life** from the house context menu or **Settings → Housemates** to stop automatic wandering and wake/rest cycles; explicit sleep still lets them walk home. Manual wake, chat and dragging remain available. Rhythms restart with everyone asleep on app launch. The house and its context menu remain available even when everyone is asleep.

**Stand still**, in the house or character context menu, is a separate switch: it freezes autonomous travel and physics while leaving chat and wake/rest behaviour available. Manual dragging still works. Sending someone home while frozen hides them immediately instead of leaving them stuck halfway home. The setting is remembered after restarting.

## Native Windows awareness and window play

**Settings → Windows** tracks ordinary visible top-level windows with native WinEvent open/close/foreground notifications, backed by a two-second Win32 inventory. The local inventory includes app identity, title/class, bounds, focus and minimized/maximized state. It detects windows opening, closing and gaining focus. No screenshot or window-content reading is involved. A bounded summary of up to 20 windows and five recent events can accompany a normal AI turn; polling itself never calls Gemini. Brief local reactions acknowledge permitted opens, closes and switches while companions are awake. They do not require an AI request for each event. Rapid bursts are covered by one compact comment that counts the changes; player replies take priority. Normal AI turns can then discuss the supplied page/screen details more naturally, mixed with ordinary conversation.

Metadata sharing starts on; **window play starts off**. Turn on window play and explicitly grant a policy to a selected window or its app before companions can move anything. The settings list shows every locally detected eligible window; process paths stay local for matching policies. Model context uses opaque session IDs instead of HWNDs/process IDs.

- **Observe:** Ignore excludes the window from the native feed; App shares only its app name/state; Title adds title, class and geometry.
- **Control:** None; Nudge (at most 24 pixels per axis); Move; or Resize (also permits movement).
- **Limits:** travel radius from the original position, maximum size change, per-policy cooldown, global minimum cooldown, global actions per minute, and a user-idle delay. Travel/size limits cannot accumulate into unlimited drift. Moving/resizing a window yourself beyond its existing anchor makes the new bounds the next play anchor.
- **Scope:** a session-only policy for this window, or a saved policy for all windows from that exact executable path. A window override takes precedence.
- **Recovery:** Undo last move restores prior bounds where possible; Pause all window play stops further changes. An activity log shows recent requests.

Window play is deliberately more active: **0 Off, 1 Relaxed, 2 Playful, 3 Eager** controls local opportunities (Eager by default). Personality-driven local nudges/occasional permitted resizing supplement model-selected actions without extra API requests. Companions can approach and look at a window they play with. Your existing idle, cooldown, rate, travel and size limits remain authoritative; adjust those in Windows settings if you want more frequent activity. The controller rechecks permissions, window/process identity and current state immediately before an action. It preserves focus/stacking order, constrains changes to the current monitor work area, and skips maximized/minimized/fullscreen windows, owned dialogs, security surfaces, inaccessible identities and the house's own windows. Windows may refuse an asynchronous move. No close/launch, mouse, keyboard, file or content-editing actions exist. Window play is disabled during games and movie mode.

These policies govern the **native window feed and movement**. Firefox sharing and screenshot fallback have separate controls. Native titles are untrusted reference text and cannot grant themselves permissions; selected titles may be sent to Gemini during companion turns.

Native notifications use Microsoft's [SetWinEventHook](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwineventhook) without injecting into other apps. Inventory/movement use [EnumWindows](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-enumwindows), [GetWindowTextW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowtextw), [SetWindowPos](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos) and [GetLastInputInfo](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getlastinputinfo).

## Balls, physics and moods

Drag a housemate and release while moving to throw them. Gravity pulls them down, they bounce off the display bounds and collide with one another, transferring momentum. Physics uses short simulation steps to avoid fast throws passing through another ball. Accessories/faces rotate while thrown, then smoothly return upright after landing. Pickup and Stand still reset rotation. Each character has distinct held, airborne and impact expressions: Burt looks bewildered, Cody delighted, Victoria affronted before recovering her smirk, and Mika gently concerned. Landing squash, blinking and mouth shapes complement those expressions. **Settings → Social & physics** controls throwing/collisions, gravity, bounce, playful scuffles and the time between scuffles. **Stand still** freezes both travel and physics; manual placement still works. Movie chairs and poker seating suspend throwing.

Housemates can be calm, happy, annoyed or angry and see one another's current moods. An annoyed housemate can initiate a short cartoon squabble; two irritated friends may also trigger one naturally. They approach each other with bouncing stars, cool down and return to normal. Scuffles have a cooldown and never affect user windows, memories, allowances or health. They are disabled during games and movies and can be switched off entirely.

## Looking at something interesting

During an ordinary AI turn, a housemate may choose an interest from its current observation. Browser snapshots include up to 12 visible headings, links, buttons or labelled media, with their viewport positions. Gemini chooses a target by index; the app resolves its location. With screenshot fallback, Gemini can identify a point within the image instead.

The housemate walks beside the target, looks at it, points with a small arrow, and shows a small coloured marker while saying its line. The marker lets pointer input pass through. They don't click, move your mouse or type into another app. Gestures are cleared if the foreground window changes, moves/resizes, or the browser target metadata changes. Old single-share snapshots without current window geometry can be discussed but cannot position a character.

Browser placement estimates the content viewport below the browser toolbar; side panels, unusual browser chrome and display scaling can make pointing approximate. Movement stays on the primary display. Screenshot understanding and interest selection depend on Gemini and can be mistaken. Game turns don't choose screen interests. Local wandering and return-home animations work without model inference.

## Token allowances and sleep

Each character has a separate **chat** allowance (default 20,000 tokens). Games and debates bypass local allowances and record their provider usage in a separate games counter; even a companion with a spent chat allowance can join. Input, reply **and thinking** tokens count, including conversation context, personality instructions, memories and any image input. A token limit is an application allowance, not a currency spending cap.

Before each chat inference, the app calls Gemini's [`countTokens` endpoint](https://ai.google.dev/api/tokens) with the intended generation request, including system instructions and image parts. If the remaining allowance cannot fit the counted input and a minimum reply, the character goes home. Otherwise, `maxOutputTokens` is capped to fit. Gemini's reported `usageMetadata.totalTokenCount`, including thinking tokens, is reconciled after the response; if the provider exceeds its preflight allowance, automatic hangout stops. There is only one model turn in flight at a time. The default Flash-Lite model uses minimal thinking; Gemini 3 Flash/Pro models use low thinking, and Gemini 2.5 Flash models disable thinking to preserve room for short replies. Very small output budgets can still produce truncated JSON and pause hangout.

In **Settings → Housemates**, enter a new allowance (256–1,000,000) and click **Refill tokens** to reset that character's used count immediately. Otherwise, **used tokens decrease gradually while the character is asleep inside the house**, increasing available energy without changing its maximum allowance. Recovery defaults to **1,000 tokens per minute per sleeping companion**.

Right-click the house → **Sleep recovery** to choose Off, 100, 500, 1,000 or 5,000 tokens per minute, or enter a custom rate (0–1,000,000). Fractional ticks accumulate so low rates work smoothly. The rate and recovered counts are saved locally; recovery runs only while the app is open. Awake characters, those still walking home, and requests with tokens still reserved don't recover. Characters exhausted before a usable request could fit wait until enough tokens have recovered before automatically waking.

Recovery restores the app's local energy allowance; it does not refund provider charges. Recovering and waking again can lead to further paid API usage, so this allowance is not a lifetime spending cap. You cannot manually refill a character during its in-flight turn.

The allowance remaining for an in-flight request is reserved on disk before sending. On success, unused reservation is returned. If usage cannot be verified, a conservative reservation is charged and automatic hangout pauses. If the app is closed or crashes during a request, the entire remaining reservation is counted on restart because the provider may still have billed it. This favours stopping over silently overspending; explicit refill/reset is available. Usage reported by the provider remains authoritative for billing.

Game/debate requests keep normal short reply limits but do not reserve, spend or check the local chat allowance. Their reported usage appears under **games** in Housemates settings and persists across restarts. An interrupted game request is flagged as unknown provider usage at the next launch; it does not consume chat allowance. Provider billing and quota errors still apply. Leaving a game sends companions with spent chat allowances home to recover.

## Memories

Each character has its own notebook of up to 30 short memories. During ordinary conversation, a character can leave up to two notes in its own or another character's notebook. Notes include their author and time, so Cody can remember something Victoria said without losing the source.

The model is instructed to remember shared jokes, relationships, game outcomes and preferences explicitly volunteered by you. It is instructed not to memorise raw screen content, private identifiers or secret roles. Generated memories are observations and can be wrong. Inspect them with **Memory** and remove individual notes. Memory updates are disabled during games; the app records the public result when a game finishes.

Memories, allowances and usage are saved in `.local/house.json`, which is excluded from Git. Chat transcripts, browser snapshots and screenshots remain in memory. An app restart keeps memories and usage but sends everyone to sleep.

**Settings → Reset** restores all four characters, default allowances and memories, clears local conversation and the game, sends everyone home and turns screenshots off. It asks for confirmation in the app. Your API connection and extension pairing are kept. Reset cannot recall submitted requests or remove data already transmitted to a provider.

## Games

**Tic-tac-toe:** wake a housemate, right-click the house, choose **Play a game → Tic-tac-toe** and pick an opponent. With two or more awake, you can also watch the first two play each other. Click squares on your turn. The local engine validates turn order, occupied squares, wins and draws; a model's invalid move falls back to the first open square.

**Mafia:** the five players are you, Burt, Cody, Victoria and Mika, with one randomly assigned mafia member and four townsfolk. Participants wake automatically, even with spent local allowances. Everyone gets a discussion turn and a vote; ties eliminate nobody. At night the mafia secretly chooses one player to eliminate. The town wins by voting out the mafia; the mafia wins at parity. Eliminated players spectate. Your own role appears in the game window; each model receives only its own role. Night speech isn't published, and per-character token counters are hidden during Mafia to avoid revealing the actor. There are no doctor/detective roles in this five-player version.

Speak in the living room or click pass during your discussion turn. Vote/choose a night target in the game window. Game inference ignores local chat allowances and records separate game usage. Sending a player home ends the current game. Provider quotas, charges and service errors still apply. An API error ends the game and pauses automatic hangout rather than retrying paid requests repeatedly.

### Poker night

Right-click the house → **Play a game → Poker night**, or type **“play poker”** in chat. With a working API connection, all four housemates wake and sit with you around an animated table. Their desktop bodies reappear when you leave. Ordinary wandering and natural rest pause while the table is open. Movie mode ends when poker begins.

A full house is five-player **fixed-limit Texas hold'em with play chips** (three to five seats when someone sits out or you spectate): two private cards each, a shared flop/turn/river, 5/10 blinds, bets of 10 before/on the flop and 20 on the turn/river, with up to three raises per street. Click **Fold**, **Check**, **Call** or **Bet/Raise** on your turn. The app enforces turn order and legal bets, evaluates the best five-card hand, and splits tied pots. Illegal model actions fall back to checking or calling. Most poker actions are silent; a reveal, raise or occasional one-liner still gets a reaction. Short poker text types faster and does not hold up betting. Direct player questions get priority and never submit a betting action. Each new hand starts everyone with 1,000 chips and rotates the dealer; stacks don't carry between hands, so there are no all-ins or side pots.

Your own cards always appear to you. Each model gets only its own cards, the shared board, public actions and hands that have explicitly been shown. Each housemate decides whether to reveal its cards after its action, including a fold. Leave **Show my cards after my action** unchecked to keep yours private, check it before acting to reveal afterward, or click **Reveal my cards now**. A reveal is public for the rest of that hand and cannot be undone. Even at the end, the local engine can determine the winner without forcing anyone's cards face-up. You can still reveal afterward. **Deal next hand** clears all reveals and deals fresh cards.

Only the public game result becomes a memory. Game state and hands aren't saved between app launches. AI decisions and game banter ignore the local token allowance and add to the separate game-usage counter; dealing, evaluation and animations are local. Generated speech is instructed to keep unrevealed cards private; this is a social companion prototype rather than an adversarial secure multiplayer service.

### Housemate invitations and occasional sit-outs

Housemates may suggest a game themselves, with **Join**, **Watch them play** or **Not now**. If enabled in **Settings → Social & physics**, an unanswered 25-second invitation lets them start without the player. Invitations occur only while idle, with a working key and multiple awake friends, and are spaced many minutes apart. Turn off invitations or automatic starts independently. Game turns still use the provider and bypass local chat allowances.

Most games start immediately. Occasionally a friend briefly deliberates and opts to watch; enough remaining players can continue, otherwise the game is postponed. That friend stays visible on the desktop during poker. Deliberation can be disabled in settings. Spectator poker never exposes hidden cards; choose **Join the next hand/game** to participate after the current one ends.

### Debate night

Right-click the house → **Play a game → Debate a topic**, enter a topic, and all four companions join you for three rounds. Add your argument in the group chat on your turn or choose **Pass this round**. Burt asks literal questions, Cody makes a case, Victoria challenges it, and Mika seeks common ground; their personalities and the recent arguments shape their replies. Each speaker gets the floor in turn and can address a specific earlier point. Debate turns bypass local chat allowances, with usage recorded separately like other games.

## Movie mode

Type **“Everybody watch something with me”**, **“Let's watch a movie”** or **“Movie mode”** into chat. You can also toggle **Movie mode** in the house or character context menu. The invitation works without an API key: everyone with available energy gathers on little armchairs with popcorn. By default they sit in the bottom-left corner; **Movie seats** in the house menu selects any corner. When Stand still is on, an explicit movie invitation places them directly in their seats. You can drag an individual chair to another spot.

While watching, they stay seated and defer natural wandering/rest, except that exhausted companions still go home. Recovering housemates can rejoin when their sleep timer and energy permit it. Ending movie mode packs away the chairs and resumes ordinary behaviour. **Stop movie mode** or **“We're done watching”** exits; starting a game or choosing **Everyone home / pause** also ends it. Movie mode itself isn't resumed automatically after an app restart; the seat corner is remembered.

Movie conversations focus on the shared film/show/video. Automatic reactions are quieter and less frequent (roughly 60–100 seconds after a turn completes), and no automatic inference runs without a recent shared observation. Empty/quiet replies are allowed. Direct questions still receive responses from the awake companions. Uncheck **Automatic conversation** to watch without unsolicited reactions. Movie turns ignore wander/inspect/rest intents, and don't write plot details into durable memories.

Movie mode **does not switch on screen capture**. Enable **Screen snapshots** or share visible captions/text through the extension. With screenshot permission on, movie mode prefers video frames over browser controls. It binds to the first observed foreground window/title and pauses observations when you switch apps or pages, so unrelated content doesn't become movie commentary. Invite them again (or toggle mode off/on) to watch a different window/title.

This is periodic still-frame/caption awareness, not continuous video or audio listening. The characters are instructed not to invent scenes, dialogue, music, motion, future plot or spoilers. Player controls/title alone aren't a basis for scene reactions. Protected video may produce black screenshots. Live reaction quality depends on Gemini, a working key and API credits.

## Firefox extension

Reload the **0.5.0** add-on to enable the new event stream. With live updates enabled, non-private tab opens, closes, switches and navigation are delivered separately from page snapshots, including background tabs. The desktop queues a brief acknowledgement of each permitted change while awake; bursts can share a counted comment. Pausing sharing clears pending browser reactions. Private tabs are excluded, and internal/protected tabs contribute only generic events without their title, URL or page contents. Lifecycle notifications use Firefox's [Tabs events](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/tabs).

Requires Firefox desktop 140 or newer. This directory now contains a Firefox-native Manifest V3 extension using `browser` APIs and background scripts.

1. Start the updated desktop app. In Firefox open `about:debugging#/runtime/this-firefox`.
2. Click **Load Temporary Add-on** and select **extension/manifest.json**, or the packaged **dist/screen-squatters-firefox-0.5.0.xpi**.
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

Existing saves migrate Pip → Burt, Byte → Cody and Rex → Victoria, including chat/game usage, interrupted-request reservations, memory authors and name references. An existing canonical record takes precedence over its old name. Factory reset restores all current personalities.

## Tests

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node tests/extension.cjs
python tests/ui_smoke.py
python tests/windows_live.py
```

Core tests cover guaranteed/batched event coverage, old-name migrations, upright settling, spectator card privacy, rare sit-outs, native window permissions, idle/cooldown/identity guards, privacy, undo, physics/collisions, debate, unlimited game accounting, budgets, sleep recovery, frozen movement, movie commands/seats/prompts, crash reservations, memory isolation, reset, game rules, poker hand rankings/private views/optional reveals/chip conservation across 300 simulated hands, paced speech, role privacy, bridge authentication, stream ordering, metadata validation, snapshot selection and PNG encoding. Node tests use isolated Firefox API mocks for permissions, popup/background contracts, SPA navigation, continuous updates and text filtering. The UI smoke check uses a temporary house and random local port, mocks AI replies/movie frames, exercises games, movie mode, progressive transcript ordering, five-seat poker, debate, directed/group chat, four-housemate settings, game-budget exemptions and browser pause/late-message clearing, and captures only its own opaque conversation window to verify native PNG encoding. It closes its windows afterward. The native window integration test enumerates metadata locally and verifies bounded moves/resizes/undo only against a disposable child fixture window. No other apps are moved. No live AI API calls are made by the tests.

`python tools/preview_social.py` renders the character expression grid, poker table, settings and compact/expanded house fixture previews into `.local/`. It asks only its own opaque test windows to paint themselves through Windows `PrintWindow`, checks process ownership, and does not capture the desktop or use live AI.

`tests/firefox_live.py --web-ext-js PATH_TO_WEB_EXT_JS` additionally runs Mozilla's `web-ext` with installed Firefox in a disposable headless profile. It verifies real repeated updates while companions sleep, background-tab opening/closing, metadata/DOM changes, SPA navigation, visible captions, media state and private-field filtering against local fixture pages. It does not use your personal browser profile or Gemini key. Validate the extension with `web-ext lint --source-dir extension`.

To diagnose connectivity, run `python diagnose_gemini.py`. It prompts for a key with hidden input (never saved), then checks model availability and token counting. Add `--generate` to also make one short generation request, which may use API credits. `--model MODEL_ID` selects a different model. Diagnostic output includes HTTP codes and usage metadata, not credentials or conversation/page content.

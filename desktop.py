"""Screen Squatters: a home for four desktop companions. Python 3.10+, Windows."""
from collections import deque
from copy import deepcopy
import os
from pathlib import Path
import queue
import secrets
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from ai import DEFAULT_MODEL, companion_turn
from bridge import BridgeServer, BrowserFeed, PORT
from games import Mafia, TicTacToe, Debate
from poker import Poker
from poker_ui import PokerTable
from speech import SpeechLine
from house import CHARACTERS, House
from ball_art import draw_friend
from habitat import Habitat
from behaviour import interest_point
from cinema import movie_command
from window_world import WindowWorld, clean_options
from social import Social, throw_velocity
from desktop_settings import windows_panel, social_panel
from attention import Attention, screen_remark
from game_social import MINIMUM, KINDS, OFFERS, DECLINES, occasional_refusal
from screen import browser_snapshot_matches, capture_window, foreground, make_noactivate

BG, PANEL, FG, MUTED = "#171923", "#242738", "#f1edff", "#abaec7"
ACCENT, TRANSPARENT = "#c5b0ff", "#010203"


class ScreenSquatters:
    def __init__(self, root, data_dir=None, port=PORT, timers=True):
        self.root = root
        self.local = Path(data_dir) if data_dir else Path(__file__).resolve().parent / ".local"
        self.local.mkdir(parents=True, exist_ok=True)
        self.house = House(self.local / "house.json")
        self.windows = WindowWorld(self.house.options)
        self.social = Social(CHARACTERS,self.house.options)
        self.windows_busy = False
        self.windows_epoch = 0
        self.last_windows_poll = 0
        self.last_hook_stamp = 0
        self.window_notice = False
        self.last_window_notice = 0
        self.attention = Attention()
        self.browser_paused = {}
        self.user_epoch = 0
        self.last_mischief = 0
        self.next_game_offer = time.monotonic()+240
        self.invitation = None
        self.invite_window = None
        self.deferred_game = None
        self.last_deliberation = -1e9
        self.last_reactor = -1
        self.proposed_offer = None
        self.join_next_game = False
        self.autonomous_game = False
        self.game_done_at = 0
        self.key = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
        self.model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
        self.page = None
        self.page_time = 0
        self.browser_feed = BrowserFeed()
        self.observation = None
        self.observation_time = 0
        self.capture_busy = False
        self.capture_epoch = 0
        self.last_capture = 0
        self.last_capture_error = ""
        self.inbox = queue.Queue(maxsize=8)
        self.results = queue.Queue()
        self.conversation = []
        self.pending = deque()
        self.busy = False
        self.busy_name = None
        self.generation = 0
        self.scene = 0
        self.next_turn = time.monotonic() + 20
        self.last_speaker = -1
        self.cancelled = threading.Event()
        self.closing = False
        self.game = None
        self.game_window = None
        self.memory_windows = []
        self.frame = 0
        self.bubbles = {name: ("", 0) for name in CHARACTERS}
        self.speech_lines = {}
        self.deliveries = []
        self.delivery_id = 0
        self.poker_table = None
        token_path = self.local / "pairing-code.txt"
        self.token = token_path.read_text().strip() if token_path.exists() else ""
        if len(self.token) != 48:
            self.token = secrets.token_hex(24)
            token_path.write_text(self.token)
        try:
            self.server = BridgeServer(self.token, self.inbox, port=port)
        except OSError:
            raise RuntimeError("Port 17373 is busy. Quit the other Screen Squatters instance first.") from None
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        root.title("Screen Squatters | home")
        root.configure(bg=BG)
        # Keep font sizes and canvas geometry balanced on high-DPI Windows desktops.
        root.tk.call("tk", "scaling", 1.333333)
        root.protocol("WM_DELETE_WINDOW", self.quit)
        self.autonomy = tk.BooleanVar(value=True)
        self.stand_still = tk.BooleanVar(value=self.house.stand_still)
        self.recovery_rate = tk.IntVar(value=self.house.sleep_recovery_rate)
        self.movie_mode = tk.BooleanVar(value=False)
        self.movie_corner = tk.StringVar(value=self.house.movie_corner)
        self.movie_source_window = None
        self.movie_source_title = ""
        self.last_recovery_tick = time.monotonic()
        self.last_recovery_save = self.last_recovery_tick
        self.recovery_dirty = False
        self.previous_sleepers = set()
        self.intent_contexts = {}
        self.interest_sources = {}
        self.native_interests = {}
        self.hangout = tk.BooleanVar(value=True)
        self.recipient = tk.StringVar(value="Everyone")
        self.screen_enabled = tk.BooleanVar(value=False)
        self.capture_interval = tk.IntVar(value=30)
        self.status = tk.StringVar(value="Everyone's home. Wake someone up to hang out.")
        self.context_status = tk.StringVar(value="Screen capture OFF | no browser page shared")
        self.build_home()
        self.build_floaters()
        self.note("Welcome home. Burt, Cody, Victoria and Mika are asleep. Wake any combination of them; they can chat with you and with each other. Settings has your API key and browser pairing code.")
        if self.house.warning:
            self.note(self.house.warning)
        self.refresh()
        self.animate()
        self.windows.backend.set_monitoring(self.house.options['window_awareness'])
        if timers:
            root.after(100, self.poll)
            root.after(500, self.tick)

    def button(self, parent, text, command, accent=False, **kwargs):
        return tk.Button(parent, text=text, command=command, bg=ACCENT if accent else PANEL,
                         fg=BG if accent else FG, relief="flat", padx=kwargs.pop("padx", 10), pady=kwargs.pop("pady", 7),
                         activebackground="#ddd0ff", cursor="hand2", font=kwargs.pop("font", ("Segoe UI", 10)), **kwargs)

    def label(self, parent, text, **kwargs):
        return tk.Label(parent, text=text, bg=BG, fg=FG, font=("Segoe UI", 10), **kwargs)

    def build_home(self):
        self.habitat = Habitat(self, draw_friend)

    def build_floaters(self):
        self.floaters = {}
        for name in CHARACTERS:
            win = tk.Toplevel(self.root)
            win.withdraw()
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg=TRANSPARENT)
            if os.name == "nt":
                win.wm_attributes("-transparentcolor", TRANSPARENT)
            resident = self.world.residents[name]
            win.geometry(f"190x230+{int(resident.x)}+{int(resident.y)}")
            canvas = tk.Canvas(win, width=190, height=230, bg=TRANSPARENT, highlightthickness=0, cursor="hand2")
            canvas.pack()
            canvas.bind("<ButtonPress-1>", lambda e, n=name: self.drag_start(e, n))
            canvas.bind("<B1-Motion>", lambda e, n=name: self.drag_move(e, n))
            canvas.bind("<ButtonRelease-1>", lambda e, n=name: self.drag_end(e, n))
            canvas.bind("<Button-3>", lambda e, n=name: self.floater_menu(e, n))
            self.floaters[name] = (win, canvas)
            win.update_idletasks()
            make_noactivate(win.winfo_id())

    def show_home(self):
        self.root.deiconify()
        self.root.lift()
        self.habitat.open = True

    def show_chat(self, recipient="Everyone"):
        self.recipient.set(recipient)
        self.chat.deiconify()
        self.chat.lift()
        self.question.focus_set()

    def append(self, name, text, remember=True, blocking=None):
        self.transcript.configure(state="normal")
        self.transcript.insert("end", name + "\n", name)
        if name in CHARACTERS and text:
            line = SpeechLine(text, time.monotonic(),fast=isinstance(self.game,Poker))
            self.delivery_id += 1
            mark = 'speech_'+str(self.delivery_id)
            self.transcript.mark_set(mark,'end-1c')
            self.transcript.mark_gravity(mark,'left')
            self.transcript.insert('end','\n\n')
            self.transcript.mark_gravity(mark,'right')
            self.deliveries.append({'name':name,'line':line,'mark':mark,'count':0,
                                    'blocking':not isinstance(self.game,Poker) if blocking is None else blocking})
            self.speech_lines[name] = line
        else:
            self.transcript.insert("end", text + "\n\n")
        # Keep widgets and model context bounded even during long sessions.
        if int(self.transcript.index("end-1c").split(".")[0]) > 600:
            self.transcript.delete("1.0", "120.0")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")
        if remember:
            if name in CHARACTERS and not self.movie_mode.get():
                previous = next((line["speaker"] for line in reversed(self.conversation) if line["speaker"] in CHARACTERS and line["speaker"] != name), None)
                resident = self.world.residents[name]
                if previous and not resident.interest and self.house.agents[previous]["awake"]:
                    friend = self.world.residents[previous]
                    resident.gaze = (friend.x+95, friend.y+150)
            self.conversation.append({"speaker": name, "text": text[:2000]})
            self.conversation = self.conversation[-20:]
        if name in CHARACTERS and text:
            until = max(time.monotonic()+18, self.speech_lines[name].end+7)
            self.bubbles[name] = (text,until)
            self.speech_lines[name].bubble_until = until

    def dialogue_tick(self, now=None):
        now = time.monotonic() if now is None else now
        if not self.deliveries:
            return
        self.transcript.configure(state='normal')
        for delivery in list(self.deliveries):
            visible = delivery['line'].visible(now)
            if len(visible) > delivery['count']:
                self.transcript.insert(delivery['mark'],visible[delivery['count']:])
                delivery['count'] = len(visible)
            if now >= delivery['line'].end:
                self.transcript.mark_unset(delivery['mark'])
                self.deliveries.remove(delivery)
        self.transcript.configure(state='disabled')
        self.transcript.see('end')

    def bubble_state(self, name, now=None):
        now = time.monotonic() if now is None else now
        private = isinstance(self.game, Mafia) and self.game.phase == 'night' and not self.game.result
        if private:
            return '', False, False
        if self.busy_name == name:
            return '', True, False
        text, until = self.bubbles[name]
        if not text or until <= now:
            return '', False, False
        line = self.speech_lines.get(name)
        if not line or line.text != text or getattr(line,'bubble_until',None) != until:
            line = self.speech_lines[name] = SpeechLine(text,now)
            until = max(until,line.end+7)
            self.bubbles[name] = (text,until)
            line.bubble_until = until
        return line.page(now), line.typing(now), line.speaking(now)

    def speech_pending(self):
        return any(delivery.get('blocking',True) for delivery in self.deliveries)

    def note(self, text):
        self.append("House", text, False)

    def save(self):
        try:
            self.house.save()
            return True
        except OSError:
            self.hangout.set(False)
            self.pending.clear()
            self.cancel_game("Game ended because the token ledger could not be saved.")
            self.note("Couldn't save the house. Automatic hangout paused; check folder permissions.")
            return False

    def awake(self):
        return [name for name, agent in self.house.agents.items() if agent["awake"]]

    def refresh(self):
        self.server.awake = bool(self.awake())
        for name, agent in self.house.agents.items():
            toggle = self.cards[name]["toggle"]
            if toggle is not None and toggle.winfo_exists():
                toggle.configure(text="Go home" if agent["awake"] else "Wake up")
            resident = self.world.residents[name]
            if agent["awake"] and resident.mode == "home":
                self.world.wake(name, time.monotonic())
            elif not agent["awake"] and resident.mode not in {"home", "returning"}:
                self.world.rest(name, time.monotonic())
            state = "Watching" if agent["awake"] and self.movie_mode.get() else "Awake" if agent["awake"] else "Resting"
            energy = f"{state} | {agent['used']:,} / {agent['limit']:,} tokens used"
            energy += f" | games {agent['game_used']:,}"
            if agent["reserved"]:
                energy += " | turn reserved"
            if isinstance(self.game, Mafia) and not self.game.result:
                energy = "Token usage hidden until Mafia ends"
            self.cards[name]["energy"].set(energy)
            win = self.floaters[name][0]
            if resident.mode != "home" and not (isinstance(self.game,Poker) and name in self.game.players):
                win.deiconify()
            else:
                win.withdraw()

    def toggle(self, name, automatic=False):
        if self.house.agents[name]["awake"]:
            self.sleep(name)
        elif self.house.wake(name):
            if not automatic:
                self.world.paused = False
            self.world.wake(name, time.monotonic())
            self.note(name + (" decided to wake up and explore." if automatic else " woke up and came out of the house."))
            self.next_turn = time.monotonic() + (45 if self.movie_mode.get() else 2)
            if not self.key and not automatic:
                self.note("Preview mode: add an API key in Settings for conversations and AI game turns.")
            self.save()
            self.refresh()
        else:
            self.note(name + " needs a token refill, or is waiting for an in-flight turn to finish.")

    def sleep(self, name):
        self.house.sleep(name)
        self.world.rest(name, time.monotonic())
        if self.busy_name == name:
            self.cancelled.set()
        if self.game and not self.game.result and name in self.game.players:
            self.cancel_game("Game ended because " + name + " went home.")
        self.note(name + " went home to sleep.")
        if not self.awake():
            self.observation = None
            self.capture_epoch += 1
        self.save()
        self.refresh()

    def sleep_all(self):
        if self.movie_mode.get():
            self.set_movie_mode(False, quiet=True)
        self.world.paused = True
        self.cancelled.set()
        self.pending.clear()
        self.cancel_game("Everyone headed home.")
        for name in CHARACTERS:
            self.house.sleep(name)
            self.world.rest(name, time.monotonic())
        self.observation = None
        self.capture_epoch += 1
        self.save()
        self.refresh()
        self.note("Everyone is asleep. Screen capture and AI turns have stopped. A request already submitted may still finish and use its reserved tokens.")

    def refill(self, name):
        try:
            self.house.recharge(name, int(self.cards[name]["limit"].get()))
        except (ValueError, TypeError) as error:
            self.note(str(error) if "invalid literal" not in str(error) else "Enter a whole-number token allowance.")
            return
        self.world.residents[name].blocked = False
        self.save()
        self.refresh()
        self.note(name + " has a fresh token allowance. Wake them when you're ready.")

    def recover_sleep_tick(self, now=None):
        now = time.monotonic() if now is None else now
        elapsed = max(0, now-self.last_recovery_tick)
        self.last_recovery_tick = now
        sleepers = {name for name, agent in self.house.agents.items()
                    if not agent["awake"] and self.world.residents[name].mode == "home" and not agent["reserved"]}
        recovered = self.house.recover_sleep(elapsed, sleepers & self.previous_sleepers)
        self.previous_sleepers = sleepers
        for name in recovered:
            resident = self.world.residents[name]
            if resident.blocked and self.house.remaining(name) >= resident.wake_threshold:
                resident.blocked = False
        if recovered:
            self.recovery_dirty = True
            self.refresh()
        if self.recovery_dirty and now-self.last_recovery_save >= 15:
            if self.save():
                self.recovery_dirty = False
            self.last_recovery_save = now
        return recovered

    def set_recovery_rate(self, rate=None):
        if rate is None:
            rate = self.recovery_rate.get()
        if type(rate) is not int or not 0 <= rate <= 1_000_000:
            self.note("Choose a recovery rate from 0 to 1,000,000 tokens per minute.")
            return
        self.recover_sleep_tick()
        self.house.sleep_recovery_rate = rate
        self.recovery_rate.set(rate)
        self.save()

    def custom_recovery_rate(self):
        rate = simpledialog.askinteger("Sleep recovery", "Tokens recovered per sleeping companion per minute (0 = off):",
                                       initialvalue=self.recovery_rate.get(), minvalue=0, maxvalue=1_000_000, parent=self.root)
        if rate is not None:
            self.set_recovery_rate(rate)

    def stand_still_changed(self):
        self.house.stand_still = self.stand_still.get()
        for name, resident in self.world.residents.items():
            if resident.pending_speech:
                self.bubbles[name] = (resident.pending_speech, time.monotonic()+18)
                resident.pending_speech = ""
        self.world.freeze(self.stand_still.get())
        self.interest_sources.clear()
        self.save()

    def set_movie_corner(self):
        self.house.movie_corner = self.movie_corner.get()
        self.world.movie_corner = self.house.movie_corner
        if self.movie_mode.get():
            for name in self.awake():
                self.world.seat(name, time.monotonic(), immediate=self.stand_still.get())
        self.save()

    def set_movie_mode(self, enabled=None, quiet=False):
        enabled = self.movie_mode.get() if enabled is None else enabled
        self.scene += 1
        self.cancelled.set()
        self.pending.clear()
        self.movie_mode.set(enabled)
        self.intent_contexts.clear()
        self.interest_sources.clear()
        self.observation = None
        self.capture_epoch += 1
        self.last_image = 0
        self.movie_source_window = None
        self.movie_source_title = ""
        if enabled:
            self.cancel_game("Putting the game away for movie night.")
            self.world.movie_enabled = True
            self.world.movie_corner = self.movie_corner.get()
            self.world.paused = False
            lines = {"Burt": "Umm, I've got popcorn. Wait, are we starting?", "Cody": "Movie night. I'll keep the commentary down.", "Victoria": "Obviously I get the good seat.","Mika":"Shall we settle in? I've brought tea."}
            for name in CHARACTERS:
                resident = self.world.residents[name]
                if not self.house.agents[name]["awake"]:
                    if resident.blocked or not self.house.wake(name):
                        continue
                    self.world.wake(name, time.monotonic())
                self.world.seat(name, time.monotonic(), immediate=self.stand_still.get())
                resident.pending_speech = lines[name]
                if resident.mode == "seated":
                    self.bubbles[name] = (lines[name], time.monotonic()+12)
                    resident.pending_speech = ""
            self.status.set("Movie mode | quiet reactions to shared frames or captions")
            if not quiet:
                self.note("Movie night! Everyone with energy is taking a seat. Enable screen snapshots or share captions so they can follow along. Movie mode doesn't enable screen capture automatically.")
        else:
            self.world.end_movie(time.monotonic())
            self.status.set("Movie mode ended. Back to hanging out.")
            if not quiet:
                self.note("Movie mode ended. The chairs and popcorn are packed away.")
        self.next_turn = time.monotonic()+45
        self.save()
        self.refresh()

    def current_observation(self):
        now = time.monotonic()
        if self.observation and now-self.observation_time <= 35:
            return deepcopy(self.observation)
        maximum_age = 35 if self.movie_mode.get() else 300
        if self.page and not self.page.get("automatic") and now-self.page_time < maximum_age:
            if self.movie_mode.get() and self.movie_source_title and self.page.get("title", "").lower() not in self.movie_source_title.lower():
                return None
            return deepcopy(self.page)
        return None

    def autonomy_changed(self):
        if self.autonomy.get():
            self.world.paused = False
            for resident in self.world.residents.values():
                if resident.mode == "home":
                    resident.wake_at = time.monotonic()+self.world.rng.uniform(20, 60)

    def apply_intent(self, name, result):
        if result.activity in ('rest','wander','inspect'):
            self.native_interests.pop(name,None)
        if self.movie_mode.get() or not self.autonomy.get() or not self.house.agents[name]["awake"]:
            return
        resident = self.world.residents[name]
        if resident.picked_up or resident.mode == 'airborne':
            return
        if result.activity == "rest":
            self.sleep(name)
        elif self.stand_still.get():
            return
        elif result.activity == "wander":
            resident.mode, resident.goal = "walking", self.world.destination()
            resident.next_wander = time.monotonic()+35
        elif result.activity == "inspect":
            observation, at = self.intent_contexts.get(name, (None, 0))
            if not observation or time.monotonic()-at > 45:
                return
            # A past page/screenshot must never point into a different current app.
            window = foreground()
            if not window or window["hwnd"] != observation.get("window_id"):
                return
            if observation.get("kind") == "page" and not browser_snapshot_matches(window, observation, 0):
                return
            point = interest_point(observation, result.interest)
            if point and not (self.world.bounds[0] <= point[0] <= self.world.bounds[2] and self.world.bounds[1] <= point[1] <= self.world.bounds[3]):
                return
            if observation.get("kind") == "page" and self.page and observation.get("targets") != self.page.get("targets"):
                return
            if point:
                self.world.inspect(name, point, time.monotonic(), result.speech)
                self.interest_sources[name] = window["hwnd"]
                self.bubbles[name] = ("", 0)

    def validate_interests(self):
        active = [name for name, resident in self.world.residents.items() if resident.interest]
        if not active:
            return
        window = foreground()
        for name in active:
            resident = self.world.residents[name]
            if name in self.native_interests:
                key = self.native_interests[name]
                item = self.windows.windows.get(key)
                permitted = item and self.house.options['window_awareness'] and self.house.options['window_control'] and self.windows.rule(key)['observe']!='ignore' and self.windows.rule(key)['control']!='none'
                if not permitted or time.monotonic()>resident.interest_until:
                    resident.interest = resident.gaze = None
                    resident.mode,resident.goal = 'idle',None
                    self.native_interests.pop(name,None)
                else:
                    x,y = item['rect'][0]+20,item['rect'][1]+30
                    resident.interest,resident.gaze = (x,y,'a permitted window'),(x,y)
                continue
            snapshot = self.intent_contexts.get(name, ({}, 0))[0] or {}
            stale_page = snapshot.get("kind") == "page" and (
                not browser_snapshot_matches(window, snapshot, 0) or
                bool(self.page and snapshot.get("targets") != self.page.get("targets")))
            moved_window = bool(window and window.get("bounds") != snapshot.get("bounds"))
            if not window or window["hwnd"] != self.interest_sources.get(name) or stale_page or moved_window:
                resident.interest = resident.gaze = None
                if resident.mode in {"approaching", "interested"}:
                    resident.mode, resident.goal = "idle", None
                    if resident.pending_speech:
                        self.bubbles[name] = (resident.pending_speech, time.monotonic()+18)
                        resident.pending_speech = ""

    def clear_context(self):
        self.page = None
        self.observation = None
        self.capture_epoch += 1
        self.context_status.set("Screen context cleared | capture " + ("ON" if self.screen_enabled.get() else "OFF"))
        self.note("Cleared the current screen snapshot. Turn off browser following and screen capture to stop future snapshots. Already submitted requests cannot be recalled.")

    def show_settings(self):
        if hasattr(self, "settings") and self.settings.winfo_exists():
            self.settings.lift()
            return
        win = self.settings = tk.Toplevel(self.root)
        win.title("Screen Squatters | settings")
        win.configure(bg=BG)
        win.geometry(f"760x{min(760,self.root.winfo_screenheight()-80)}")
        notebook = ttk.Notebook(win)
        notebook.pack(fill="both", expand=True, padx=15, pady=15)
        connection, housemates, awareness, windows, social, reset = [tk.Frame(notebook, bg=BG, padx=18, pady=16) for _ in range(6)]
        for frame, title in ((connection, "Connection"), (housemates, "Housemates"), (awareness, "Screen"), (windows,'Windows'), (social,'Social & physics'), (reset, "Reset")):
            notebook.add(frame, text=title)
        def scrollable(frame):
            canvas = tk.Canvas(frame,bg=BG,highlightthickness=0)
            scrollbar = ttk.Scrollbar(frame,orient='vertical',command=canvas.yview)
            scrollbar.pack(side='right',fill='y')
            canvas.pack(side='left',fill='both',expand=True)
            canvas.configure(yscrollcommand=scrollbar.set)
            content = tk.Frame(canvas,bg=BG)
            item = canvas.create_window(0,0,window=content,anchor='nw')
            content.bind('<Configure>',lambda _e:canvas.configure(scrollregion=canvas.bbox('all')))
            canvas.bind('<Configure>',lambda event:canvas.itemconfigure(item,width=event.width))
            return content
        windows_panel(self,scrollable(windows))
        social_panel(self,scrollable(social))
        self.habitat.populate_housemates(housemates)
        def text(parent, value):
            tk.Label(parent, text=value, bg=BG, fg=FG, wraplength=480, justify="left", font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 10))
        text(connection, "Gemini API key (memory only, for this app session)")
        key = tk.Entry(connection, show="*", bg=PANEL, fg=FG, insertbackground=FG, relief="flat")
        key.insert(0, self.key)
        key.pack(fill="x", ipady=8, pady=(0, 14))
        text(connection, "Gemini model (JSON output, vision and token counting)")
        model = tk.Entry(connection, bg=PANEL, fg=FG, insertbackground=FG, relief="flat")
        model.insert(0, self.model)
        model.pack(fill="x", ipady=8, pady=(0, 14))
        text(connection, "Firefox pairing code: load extension/manifest.json at about:debugging, then paste this in the add-on popup and enable live updates.")
        code = tk.Entry(connection, bg=PANEL, fg=ACCENT, relief="flat")
        code.insert(0, self.token)
        code.configure(state="readonly", readonlybackground=PANEL)
        code.pack(fill="x", ipady=7)
        def copy_code():
            win.clipboard_clear()
            win.clipboard_append(self.token)
        self.button(connection, "Copy pairing code", copy_code).pack(anchor="w", pady=8)
        text(connection, "Chat uses local allowances. Games/debates ignore those limits and record separate usage; provider charges still apply. No API key is stored on disk or in the extension.")
        def save():
            self.key, self.model = key.get().strip(), model.get().strip() or DEFAULT_MODEL
            win.destroy()
            self.next_turn = time.monotonic() + 3
        self.button(connection, "Use for this session", save, True).pack(anchor="e", pady=8)
        text(awareness, "The Firefox extension can continuously update focused-page text, metadata, reading position and captions, even while everyone sleeps. It sends updates locally; AI requests still follow the normal conversation schedule.")
        text(awareness, "Optional screenshot fallback captures the foreground window periodically while at least one companion is awake. Fresh matching browser text is preferred. The house's own windows and Windows sign-in surfaces are skipped.")
        tk.Checkbutton(awareness, text="Enable periodic foreground-window screenshots", variable=self.screen_enabled,
                       command=self.awareness_changed, bg=BG, fg=FG, selectcolor=PANEL,
                       activebackground=BG, activeforeground=FG).pack(anchor="w", pady=12)
        row = tk.Frame(awareness, bg=BG)
        row.pack(fill="x", pady=8)
        tk.Label(row, text="Capture interval (seconds):", bg=BG, fg=FG).pack(side="left")
        tk.Spinbox(row, from_=15, to=300, increment=15, textvariable=self.capture_interval, width=6).pack(side="left", padx=10)
        text(awareness, "A snapshot may be sent to Google's Gemini API during the next conversation turn, including automatic hangout turns. Images stay in memory and are never saved to disk. Turn screenshots off before viewing anything private. This setting resets to OFF on app restart.")
        self.button(awareness, "Clear current snapshot", self.clear_context).pack(anchor="w", pady=10)
        text(reset, "Factory reset sends everyone home and removes all companions' memories, usage, chat and game. Window permissions and social/physics settings reset; window play and screenshots turn OFF. Your extension pairing and API connection are kept.")
        text(reset, "Requests already submitted to Gemini cannot be recalled. Reset does not delete provider-side data or undo API charges.")
        self.button(reset, "Reset every companion to factory settings", self.reset_all, True).pack(anchor="w", pady=16)

    def awareness_changed(self):
        self.capture_epoch += 1
        self.observation = None
        self.last_capture = 0
        self.context_status.set("Periodic screen capture " + ("ON | snapshots may be sent during AI turns" if self.screen_enabled.get() else "OFF"))

    def show_memories(self, name):
        win = tk.Toplevel(self.root)
        self.memory_windows.append(win)
        win.title(name + " | memory notebook")
        win.configure(bg=BG)
        win.geometry("570x410")
        tk.Label(win, text="Notes from friends are attributed observations, not verified facts.", bg=BG, fg=MUTED,
                 wraplength=520, font=("Segoe UI", 10)).pack(padx=15, pady=12)
        listing = tk.Listbox(win, bg=PANEL, fg=FG, selectbackground="#59516d", relief="flat", font=("Segoe UI", 10))
        listing.pack(fill="both", expand=True, padx=15)
        notes = list(self.house.agents[name]["memories"])
        for note in notes:
            listing.insert("end", f"{note['from']}: {note['text']}")
        if not notes:
            listing.insert("end", "No memories yet. Make some together.")
        def remove():
            selected = listing.curselection()
            if selected and notes:
                target = notes[selected[0]]
                live = self.house.agents[name]["memories"]
                if target in live:
                    live.remove(target)
                    self.save()
                win.destroy()
        self.button(win, "Forget selected note", remove).pack(pady=12)

    def reset_all(self):
        if not messagebox.askyesno("Factory reset", "Reset all companions, memories, allowances, window permissions and local chat?", parent=self.root):
            return
        self.world.paused = True
        for name in CHARACTERS:
            self.world.rest(name, time.monotonic(), immediate=True)
            self.world.residents[name].blocked = False
        self.intent_contexts.clear()
        self.interest_sources.clear()
        self.native_interests.clear()
        self.generation += 1
        self.scene += 1
        self.cancelled.set()
        self.pending.clear()
        self.game = None
        self.dismiss_invitation()
        self.deferred_game = None
        self.join_next_game = False
        self.attention.clear()
        self.user_epoch += 1
        self.close_game_window()
        self.screen_enabled.set(False)
        self.awareness_changed()
        self.page = None
        self.conversation.clear()
        for window in self.memory_windows:
            if window.winfo_exists():
                window.destroy()
        self.memory_windows.clear()
        try:
            self.house.reset()
        except OSError:
            self.note("Factory state was restored in memory, but it could not be saved. Check folder permissions before restarting.")
            self.refresh()
            return
        self.movie_mode.set(False)
        self.movie_source_window = None
        self.movie_source_title = ""
        self.world.end_movie(time.monotonic())
        self.recovery_rate.set(self.house.sleep_recovery_rate)
        self.stand_still.set(self.house.stand_still)
        self.world.freeze(self.stand_still.get())
        self.movie_corner.set(self.house.movie_corner)
        self.world.movie_corner = self.house.movie_corner
        self.previous_sleepers.clear()
        self.recovery_dirty = False
        self.bubbles = {name: ("", 0) for name in CHARACTERS}
        self.speech_lines.clear()
        for delivery in self.deliveries:
            self.transcript.mark_unset(delivery['mark'])
        self.deliveries.clear()
        self.social = Social(CHARACTERS,self.house.options)
        self.windows.overrides.clear()
        self.windows.anchors.clear()
        self.windows.undos.clear()
        self.windows.events.clear()
        self.windows_epoch += 1
        self.habitat.open = False
        self.windows.backend.set_monitoring(False)
        self.windows.backend.set_monitoring(self.house.options['window_awareness'])
        if getattr(self,'settings',None) and self.settings.winfo_exists():
            self.settings.destroy()
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        self.transcript.configure(state="disabled")
        for name in CHARACTERS:
            self.cards[name]["limit"].set(str(self.house.agents[name]["limit"]))
        self.refresh()
        self.note("Factory reset complete. Everyone is home, with fresh memories and allowances.")

    def send(self):
        text = self.question.get().strip()[:2000]
        if text.lower().strip(' .!') in ('poker', 'play poker', 'start poker', "let's play poker", 'lets play poker'):
            self.question.delete(0,'end')
            self.append('You',text)
            self.start_poker()
            return
        command = movie_command(text)
        if command:
            self.question.delete(0, "end")
            self.append("You", text)
            self.set_movie_mode(command == "start")
            return
        if not text:
            return
        if not self.awake():
            self.note("Wake someone up first.")
            return
        if not self.key:
            self.show_settings()
            return
        self.question.delete(0, "end")
        self.append("You", text)
        self.user_epoch += 1
        if self.deliveries:
            self.dialogue_tick(max(item['line'].end for item in self.deliveries)+.01)
        if self.game and not self.game.result:
            if isinstance(self.game, Mafia) and self.game.phase == "discussion" and self.game.actor == "You":
                self.game.act("You")
                self.render_game()
                return
            elif isinstance(self.game,Debate) and self.game.actor == 'You':
                self.game.act('You',text)
                self.render_game()
                return
        names = self.awake()
        recipient = self.recipient.get()
        names.sort(key=lambda name:name.lower() not in text.lower())
        if recipient != 'Everyone' and recipient not in names:
            self.note(recipient+' is asleep. Wake them for a directed reply.')
        self.pending = deque([recipient] if recipient in names else names if recipient == "Everyone" else [])
        if recipient == 'Everyone' and isinstance(self.game,Poker):
            self.pending = deque(list(self.pending)[:1])
        self.next_turn = time.monotonic()

    def request_turn(self, name, trigger, direct=False, chat_only=False):
        if self.busy or self.speech_pending() or not self.key or not self.house.agents[name]["awake"]:
            return
        self.busy, self.busy_name = True, name
        if direct and not trigger.startswith('PLAYER_MESSAGE'):
            trigger = 'PLAYER_MESSAGE: '+trigger
        self.cancelled = threading.Event()
        self.send_button.configure(state="normal")
        private_night = isinstance(self.game, Mafia) and self.game.phase == "night"
        self.status.set("Secret night action in progress..." if private_night else name + " is typing…")
        agent = self.house.agents[name]
        try:
            exempt = self.game is not None
            remaining = self.house.reserve(name, unlimited=exempt)
        except OSError:
            agent["reserved"] = 0
            self.busy, self.busy_name = False, None
            self.send_button.configure(state="normal")
            self.hangout.set(False)
            self.note("Cannot safely save the token reservation. No AI request was sent.")
            return
        generation, scene = self.generation, self.scene
        reply_epoch = self.user_epoch
        game = self.game.view(name) if self.game and name in self.game.players else self.game.public_view() if isinstance(self.game,Poker) else {'game':self.game.kind,'rule':'You are observing. React only to public chat; you have no private role or cards.'} if self.game else None
        if isinstance(self.game,Poker) and self.game.result:
            game = {'game':'Poker','result':self.game.result,'shown_cards':game['shown_cards'],
                    'rule':'The hand is over. React only to the public result; no betting or private cards.'}
        observation = self.current_observation() if not game else None
        self.intent_contexts[name] = (deepcopy(observation), time.monotonic())
        args = (self.key, self.model, name, deepcopy(agent["memories"]), deepcopy(self.conversation),
                self.awake(), trigger, remaining, observation, game, self.cancelled, self.movie_mode.get(),
                self.windows.context(),self.social.context())
        self.refresh()
        def work():
            result = companion_turn(*args)
            result.game_turn = exempt
            result.direct_reply,result.chat_only,result.reply_epoch = direct,chat_only,reply_epoch
            self.results.put(("turn", generation, scene, name, result))
        threading.Thread(target=work, daemon=True).start()

    def handle_turn(self, generation, scene, name, result):
        self.busy, self.busy_name = False, None
        self.send_button.configure(state="normal")
        if generation != self.generation:
            self.refresh()
            return
        active = self.house.agents[name]["awake"] and not self.cancelled.is_set() and scene == self.scene
        if (not result.game_turn or result.chat_only) and result.reply_epoch>=0 and result.reply_epoch != self.user_epoch:
            active = False
        self.house.settle(name, result.used, unlimited=result.game_turn)
        if result.error:
            self.note(name + ": " + result.error)
            self.bubbles[name] = (result.error[:180], time.monotonic()+22)
            self.hangout.set(False)
            self.pending.clear()
            self.cancel_game("Game paused after an AI error. Start a new game after fixing the connection.")
        elif result.exhausted:
            self.world.residents[name].blocked = True
            self.world.residents[name].wake_threshold = result.required_tokens or 1000
            self.house.sleep(name)
            self.note(name + " is out of energy for another turn and went home. They'll recover while sleeping; you can also refill their allowance.")
            if self.game and not self.game.result:
                self.cancel_game("Game ended: a player needs more tokens.")
        elif active:
            night = isinstance(self.game, Mafia) and self.game.phase == "night"
            if isinstance(self.game,Poker) and not result.direct_reply:
                new_reveal = result.reveal_cards and name not in self.game.revealed
                real_raise = result.poker_action == 'raise' and 'raise' in self.game.legal_actions(name)
                if not new_reveal and not real_raise and self.game.turn_number%4 != 0:
                    result.speech = ''
                result.speech = result.speech[:100]
            if result.speech and not night:
                self.append(name, result.speech,blocking=True if result.direct_reply else None)
            ordinary = not self.game and not self.movie_mode.get()
            event = self.social.react(name,result,self.world,self.awake(),time.monotonic(),allowed=ordinary) if not night else None
            if event:
                self.note(event)
            if ordinary and result.window_action:
                self.windows.apply(result.window_action)
            if ordinary and result.game_offer.get('game') in KINDS and time.monotonic()>=self.next_game_offer and not self.pending:
                self.proposed_offer = (name,result.game_offer['game'],str(result.game_offer.get('topic',''))[:300])
            target = result.social_action.get('target')
            if result.social_action.get('kind') == 'reply' and target in self.pending:
                self.pending.remove(target)
                self.pending.appendleft(target)
            if not self.game:
                self.apply_intent(name, result)
            # Never persist game secrets, including accidentally generated memory updates.
            if (not self.game or self.game.result) and not self.movie_mode.get():
                accepted = self.house.remember(name, result.memories)
                for target, _text in accepted:
                    self.note(name + " left a note in " + target + "'s memory.")
            if self.game and not self.game.result and not result.chat_only:
                self.apply_game_turn(name, result)
            elif isinstance(self.game,Poker) and result.chat_only and result.reveal_cards and name in self.game.players:
                self.game.reveal(name)
                self.render_game()
        if not result.game_turn and not self.house.remaining(name) and self.game and not self.game.result:
            self.cancel_game("Game ended: a player ran out of tokens.")
        if active and not result.game_turn and not result.exhausted and not self.house.remaining(name):
            self.world.residents[name].blocked = True
            self.world.residents[name].wake_threshold = min(self.house.agents[name]["limit"], 1000)
            self.note(name + " used their allowance and went home to sleep.")
        self.save()
        self.refresh()
        self.status.set("All quiet at home." if not self.awake() else "Automatic conversation paused" if not self.hangout.get() else "Movie mode | watching quietly" if self.movie_mode.get() else "Hanging out")
        self.next_turn = time.monotonic() + (.15 if self.pending else .45 if isinstance(self.game,Poker) and not self.game.result else 2 if self.game and not self.game.result else self.world.rng.uniform(60, 100) if self.movie_mode.get() else 25)

    def capture_tick(self):
        now = time.monotonic()
        if self.capture_busy or not self.awake() or now - self.last_capture < 5:
            return
        self.last_capture = now
        self.capture_busy = True
        epoch = self.capture_epoch
        page, age = deepcopy(self.page), now - self.page_time
        screenshots = self.screen_enabled.get()
        movie = self.movie_mode.get()
        source_window, source_title = self.movie_source_window, self.movie_source_title
        try:
            interval = max(15, min(300, int(self.capture_interval.get())))
        except (tk.TclError, ValueError):
            interval = 30
        capture_image = screenshots and now - getattr(self, "last_image", 0) >= interval
        if capture_image:
            self.last_image = now
        previous = deepcopy(self.observation)
        def work():
            try:
                window = foreground()
                wrong_movie_source = bool(movie and source_window is not None and window and (
                    window["hwnd"] != source_window or source_title.lower() not in window["title"].lower()))
                if wrong_movie_source:
                    observation = None
                elif browser_snapshot_matches(window, page, age) and not (movie and screenshots):
                    observation = {"kind": "page", **page, "bounds": window["bounds"], "window_id": window["hwnd"]}
                elif capture_image and window:
                    observation = capture_window(window)
                    if observation:
                        observation["window_id"] = window["hwnd"]
                elif screenshots and window and previous and previous.get("window_id") == window["hwnd"]:
                    observation = previous
                else:
                    observation = None
                self.results.put(("capture", epoch, observation, ""))
            except Exception as error:
                self.results.put(("capture", epoch, None, str(error)))
        threading.Thread(target=work, daemon=True).start()

    def update_options(self,values):
        cleaned = clean_options(values)
        self.house.options.clear()
        self.house.options.update(cleaned)
        self.windows.backend.set_monitoring(self.house.options['window_awareness'])
        self.windows_epoch += 1
        self.last_windows_poll = 0
        if not self.house.options['window_awareness']:
            self.windows.windows.clear()
            self.windows.events.clear()
            self.windows.seeded = False
            self.window_notice = False
        self.save()

    def windows_tick(self,now):
        if self.windows_busy or not self.house.options['window_awareness'] or now-self.last_windows_poll<2:
            return
        self.last_windows_poll = now
        self.windows_busy = True
        epoch = self.windows_epoch
        def collect():
            try:
                records = self.windows.backend.list_windows()
            except Exception:
                records = None
            self.results.put(('windows',epoch,records,now))
        threading.Thread(target=collect,daemon=True).start()

    def dismiss_invitation(self):
        if self.invite_window and self.invite_window.winfo_exists():
            self.invite_window.destroy()
        self.invite_window,self.invitation = None,None

    def offer_game(self,name,kind='Tic-tac-toe',topic=''):
        if not self.house.options['game_invites'] or not self.key or self.game or self.invitation or len(self.awake())<2 or name not in self.awake():
            return
        self.next_game_offer = time.monotonic()+self.world.rng.uniform(600,1000)
        self.invitation = {'starter':name,'kind':kind,'topic':topic,'deadline':time.monotonic()+25}
        self.append(name,OFFERS[name].format(game=kind),blocking=False)
        win = self.invite_window = tk.Toplevel(self.root)
        win.title('Screen Squatters | game invitation')
        win.configure(bg=BG)
        self.label(win,name+' suggests '+kind).pack(padx=20,pady=12)
        self.label(win,'Join in, watch, or leave it for later.').pack(padx=20)
        if self.house.options['autoplay_games']:
            self.label(win,'They will start without you after 25 seconds.').pack(padx=20,pady=4)
        self.label(win,'Housemate games use API tokens without local game limits.').pack(padx=20,pady=6)
        row = tk.Frame(win,bg=BG)
        row.pack(padx=20,pady=12)
        self.button(row,'Join',lambda:self.accept_invitation(True),True).pack(side='left',padx=4)
        self.button(row,'Watch them play',lambda:self.accept_invitation(False)).pack(side='left',padx=4)
        self.button(row,'Not now',self.dismiss_invitation).pack(side='left',padx=4)
        win.protocol('WM_DELETE_WINDOW',self.dismiss_invitation)
        win.update_idletasks()
        make_noactivate(win.winfo_id())

    def accept_invitation(self,join):
        if not self.invitation:
            return
        offer = dict(self.invitation)
        self.dismiss_invitation()
        names = self.awake()
        if offer['starter'] in names:
            names.remove(offer['starter']); names.insert(0,offer['starter'])
        players = (['You'] if join else [])+names
        kind = offer['kind']
        if len(players)<MINIMUM[kind]:
            kind = 'Tic-tac-toe'
        if len(players)<2:
            return
        if kind == 'Tic-tac-toe':
            game = TicTacToe(*players[:2])
        elif kind == 'Poker':
            game = Poker(players)
        elif kind == 'Mafia':
            game = Mafia(players)
        else:
            game = Debate(players,offer['topic'] or 'What makes a good friend?')
        self.autonomous_game = not join
        self.begin_game(game)

    def request_join_game(self):
        self.join_next_game = True
        self.note('You will join the next hand or game, after the current one finishes.')

    def scene_tick(self,now):
        if self.busy or self.pending or self.speech_pending():
            return
        if self.deferred_game:
            game,self.deferred_game = self.deferred_game,None
            self.begin_game(game)
            return
        if self.join_next_game and self.game and self.game.result:
            self.join_next_game = False
            kind,players,topic = self.game.kind,['You']+[p for p in self.game.players if p!='You'],getattr(self.game,'topic','')
            self.autonomous_game = False
            self.begin_game(Poker(players) if kind=='Poker' else Mafia(players) if kind=='Mafia' else Debate(players,topic) if kind=='Debate' else TicTacToe(*players[:2]),deliberate=False)
            return
        if self.invitation and not self.house.options['game_invites']:
            self.dismiss_invitation()
        if self.invitation and self.house.options['autoplay_games'] and now>=self.invitation['deadline']:
            self.accept_invitation(False)
            return
        if self.autonomous_game and self.game and self.game.result and now-self.game_done_at>20:
            self.cancel_game('The housemates put their game away.')
        names = self.awake()
        private = isinstance(self.game,Mafia) and self.game.phase=='night' and not self.game.result
        if names and self.house.options['screen_comments'] and not private and now-self.attention.last_spoken>=3:
            def allowed(event):
                return event.get('source') != 'native' or (self.house.options['window_awareness'] and self.windows.public(event['window'],event['_record']) is not None)
            changes = self.attention.take(allowed)
            if changes:
                self.last_reactor = (self.last_reactor+1)%len(names)
                self.append(names[self.last_reactor],screen_remark(names[self.last_reactor],changes,self.world.rng),blocking=not isinstance(self.game,Poker))
                self.attention.last_spoken = now
                return
        level = self.house.options['playfulness']
        interval = {0:1e9,1:30,2:14,3:7}[level]
        if names and not self.game and not self.movie_mode.get() and now-self.last_mischief>=interval:
            self.last_mischief = now
            actor = self.world.rng.choice(names)
            key = self.windows.play(actor,self.world.rng,now) if level else None
            if key and self.world.movement_enabled and self.autonomy.get():
                item = self.windows.windows[key]
                self.world.inspect(actor,(item['rect'][0]+20,item['rect'][1]+30,'a permitted window'),now)
                self.native_interests[actor] = key
        if names and not self.game and not self.movie_mode.get() and self.hangout.get() and now>=self.next_game_offer and len(names)>=2:
            starter = self.world.rng.choice(names)
            available = [kind for kind in KINDS if len(names)>=MINIMUM[kind]]
            preferred = {'Burt':'Tic-tac-toe','Cody':'Tic-tac-toe','Victoria':'Poker','Mika':'Debate'}[starter]
            kind = preferred if preferred in available and self.world.rng.random()<.7 else self.world.rng.choice(available)
            offer = self.proposed_offer or (starter,kind,'')
            self.proposed_offer = None
            self.offer_game(*offer)

    def tick(self):
        if self.closing:
            return
        now = time.monotonic()
        self.windows_tick(now)
        self.recover_sleep_tick(now)
        if self.movie_mode.get() and not self.world.paused:
            for name, resident in self.world.residents.items():
                if not self.house.agents[name]["awake"] and resident.mode == "home" and not resident.blocked and now >= resident.wake_at and self.house.remaining(name) > 0:
                    self.toggle(name, automatic=True)
        elif self.autonomy.get():
            eligible = [name for name in CHARACTERS if self.house.remaining(name) > 0]
            for action, name in self.world.due(now, self.awake(), eligible, busy=[self.busy_name, *self.pending],
                                               playing=bool(self.game and (not self.game.result or isinstance(self.game, Poker)))):
                if action == "wake":
                    self.toggle(name, automatic=True)
                else:
                    self.sleep(name)
        self.validate_interests()
        self.capture_tick()
        self.scene_tick(now)
        if not self.busy and not self.speech_pending() and self.key and now >= self.next_turn:
            private = isinstance(self.game,Mafia) and self.game.phase=='night' and not self.game.result
            while self.pending and self.pending[0] not in self.awake():
                asleep = self.pending.popleft()
                self.note(asleep+' needs to rest before replying. Their chat allowance can recover while they sleep.')
            if self.pending and not private:
                self.request_turn(self.pending.popleft(),'PLAYER_MESSAGE: Answer what the player just said before returning to other topics. Keep it brief and in character.',direct=True,chat_only=self.game is not None)
            elif self.game and not self.game.result:
                actor = self.game.actor
                if actor in self.awake():
                    self.request_turn(actor, "Take your game turn. Respond to the ongoing banter without revealing secrets.")
            else:
                while self.pending and self.pending[0] not in self.awake():
                    self.pending.popleft()
                if self.hangout.get() and self.awake():
                    ready = [name for name in self.awake() if not self.movie_mode.get() or self.world.residents[name].mode == "seated"]
                    if self.movie_mode.get() and not self.current_observation():
                        ready = []
                        self.next_turn = now+5
                    names = list(CHARACTERS)
                    for offset in range(1, len(names)+1):
                        index = (self.last_speaker + offset) % len(names)
                        if names[index] in ready:
                            self.last_speaker = index
                            notice = bool(self.window_notice and now-self.window_notice<60 and now-self.last_window_notice>20 and not self.movie_mode.get())
                            if notice:
                                self.window_notice = False
                                self.last_window_notice = now
                            self.request_turn(names[index], "React briefly to the recently opened window in desktop metadata, if interesting. Only use permitted window play; do not guess its contents." if notice else "Watch this moment quietly. Only react briefly if this frame or caption gives you something specific to react to; otherwise leave speech empty." if self.movie_mode.get() else "Hang out naturally. Reply to something a friend just said, include a quiet friend, or notice something in the supplied context. Silence is okay: keep it short.")
                            break
        self.root.after(500, self.tick)

    def queue_window_change(self,change):
        public = self.windows.public(change['window'],change['record'])
        if public:
            self.attention.add({'event':{'opened':'window-opened','closed':'window-closed','focused':'window-switched'}[change['event']],
                                'event_id':change['event_id'],'source':'native','window':change['window'],'_record':change['record'],
                                'app':public['app'],'title':public.get('title','')})

    def poll(self, reschedule=True):
        if self.closing:
            return
        for kind,record,stamp in self.windows.backend.drain_events():
            if self.house.options['window_awareness']:
                self.last_hook_stamp = max(self.last_hook_stamp,stamp)
                change = self.windows.native_change(kind,record,stamp)
                if change:
                    self.queue_window_change(change)
        try:
            while True:
                page = self.inbox.get_nowait()
                if page.get('kind') == 'browser-event':
                    if page.get('sequence',1)>self.browser_paused.get(page.get('session_id'),0) and page.get('session_id') not in self.browser_feed.retired:
                        self.attention.add(page)
                    continue
                if not self.browser_feed.accept(page):
                    continue
                if page.get("kind") == "browser-state":
                    if page['state']=='paused':
                        self.browser_paused[page.get('session_id')] = page.get('sequence',0)
                        self.attention.clear('browser')
                    self.page, self.page_time = None, 0
                    if self.observation and self.observation.get("kind") == "page":
                        self.observation = None
                    self.capture_epoch += 1
                    self.context_status.set("Firefox feed " + page["state"] + " | browser context cleared")
                    continue
                self.page, self.page_time = page, time.monotonic()
                self.context_status.set("Browser text received | " + page["title"][:65] + (" | following" if page.get("automatic") else " | shared snapshot"))
                if not page.get("automatic"):
                    self.note("A browser snapshot arrived. Awake housemates can react to it during their next turn.")
        except queue.Empty:
            pass
        try:
            while True:
                event = self.results.get_nowait()
                if event[0] == "turn":
                    self.handle_turn(*event[1:])
                elif event[0] == 'windows':
                    self.windows_busy = False
                    if event[1] == self.windows_epoch and self.house.options['window_awareness'] and event[2] is not None and (len(event)<4 or event[3]>=self.last_hook_stamp):
                        opened = self.windows.update(event[2])
                        for change in self.windows.changes:
                            self.queue_window_change(change)
                        if any(self.windows.public(key,self.windows.windows[key]) for key in opened):
                            now = time.monotonic()
                            self.window_notice = now
                            if self.hangout.get() and self.awake() and not self.game and not self.movie_mode.get() and now-self.last_window_notice>20:
                                self.next_turn = min(self.next_turn,now+5)
                        refresh = getattr(self,'window_settings_refresh',None)
                        if refresh:
                            refresh()
                else:
                    _, epoch, observation, error = event
                    self.capture_busy = False
                    if epoch != self.capture_epoch or not self.awake():
                        continue
                    self.observation, self.observation_time = observation, time.monotonic()
                    if self.movie_mode.get() and observation and self.movie_source_window is None and observation.get("window_id") is not None:
                        self.movie_source_window = observation["window_id"]
                        self.movie_source_title = observation.get("title", "")
                    if error and error != self.last_capture_error:
                        self.note("Screen awareness: " + error)
                        self.last_capture_error = error
                    if observation:
                        kind = "Browser text" if observation["kind"] == "page" else "SCREEN CAPTURE ON"
                        self.context_status.set(kind + " | " + observation.get("title", "")[:65] + " | held in memory")
                    elif self.screen_enabled.get():
                        self.context_status.set("SCREEN CAPTURE ON | waiting for an eligible foreground window")
        except queue.Empty:
            pass
        if reschedule:
            self.root.after(100, self.poll)

    def choose_ttt(self):
        if self.busy:
            self.note("Wait for the current turn before starting a game.")
            return
        names = self.awake()
        if not names:
            self.note("Wake at least one housemate to play.")
            return
        win = tk.Toplevel(self.root)
        win.title("Who is playing?")
        win.configure(bg=BG)
        for name in names:
            self.button(win, "You vs " + name, lambda n=name: (win.destroy(), self.start_ttt("You", n))).pack(fill="x", padx=20, pady=8)
        if len(names) >= 2:
            self.button(win, names[0] + " vs " + names[1] + " (watch)", lambda: (win.destroy(), self.start_ttt(*names[:2]))).pack(fill="x", padx=20, pady=8)

    def begin_game(self, game, deliberate=True):
        if self.busy or self.speech_pending():
            self.deferred_game = game
            self.note('The game is queued after this reply.')
            return
        if not self.key:
            self.show_settings()
            return
        self.dismiss_invitation()
        self.deferred_game = None
        if deliberate and self.house.options['game_deliberation'] and time.monotonic()-self.last_deliberation>120:
            self.last_deliberation = time.monotonic()
            declined = occasional_refusal(game.players,game.kind,self.world.rng)
            if declined:
                self.append(declined,DECLINES[declined],blocking=False)
                players = [player for player in game.players if player != declined]
                if len(players)<MINIMUM[game.kind]:
                    self.note('They would rather watch for now. You can invite them again later.')
                    return
                game = Poker(players) if isinstance(game,Poker) else Mafia(players) if isinstance(game,Mafia) else Debate(players,game.topic) if isinstance(game,Debate) else TicTacToe(*players)
        for player in game.players:
            if player in CHARACTERS and player not in self.awake():
                self.house.wake(player,ignore_limit=True)
                self.world.wake(player,time.monotonic())
        if self.movie_mode.get():
            self.set_movie_mode(False, quiet=True)
        self.scene += 1
        self.pending.clear()
        self.close_game_window()
        self.game = game
        self.next_turn = time.monotonic() + 1
        self.note(game.kind + " started. Local token limits are suspended; provider usage is still recorded.")
        self.refresh()
        self.render_game()

    def start_ttt(self, first, second):
        self.autonomous_game = False
        self.begin_game(TicTacToe(first, second))

    def start_mafia(self):
        self.autonomous_game = False
        self.begin_game(Mafia(["You", *CHARACTERS]))

    def start_poker(self):
        self.autonomous_game = False
        if self.busy or self.speech_pending():
            self.deferred_game = Poker(['You',*CHARACTERS])
            self.note('Poker is queued after this reply.')
            return
        if not self.key:
            self.show_settings()
            return
        self.begin_game(Poker(['You',*CHARACTERS]))

    def start_debate(self):
        self.autonomous_game = False
        topic = simpledialog.askstring('Debate night','What should we debate?',parent=self.root)
        if topic and topic.strip():
            self.begin_game(Debate(['You',*CHARACTERS],topic.strip()))

    def next_poker_hand(self):
        if isinstance(self.game,Poker) and self.game.result:
            players = list(self.game.players)
            if self.join_next_game and 'You' not in players:
                players.insert(0,'You')
            self.join_next_game = False
            self.begin_game(Poker(players,dealer=self.game.dealer+1),deliberate=False)

    def close_game_window(self):
        if self.game_window and self.game_window.winfo_exists():
            self.game_window.destroy()
        self.game_window = None
        self.poker_table = None

    def cancel_game(self, reason="Game ended."):
        self.dismiss_invitation()
        self.deferred_game = None
        self.join_next_game = False
        self.autonomous_game = False
        if self.game:
            self.scene += 1
            self.cancelled.set()
            self.game = None
            self.close_game_window()
            for name in self.awake():
                if not self.house.remaining(name):
                    self.house.sleep(name)
                    self.world.rest(name,time.monotonic())
            self.note(reason)

    def game_action(self, value=None):
        if not self.game or self.game.actor != "You":
            return
        try:
            if isinstance(self.game, TicTacToe):
                self.game.move("You", value)
            elif isinstance(self.game, Poker):
                action, reveal = value if isinstance(value,tuple) else (value,False)
                self.game.act('You',action,reveal=reveal is True)
            elif isinstance(self.game,Debate):
                self.game.act('You','I will listen this round.')
            else:
                self.game.act("You", value or "")
            self.next_turn = time.monotonic() + 1
            self.render_game()
        except ValueError as error:
            self.note(str(error))

    def apply_game_turn(self, name, result):
        if self.game.actor != name:
            return
        if isinstance(self.game, TicTacToe):
            legal = [i for i, cell in enumerate(self.game.board) if not cell]
            move = result.move
            if move not in legal:
                move = legal[0]
                self.note(name + " fumbled their move; the first open square was used.")
            self.game.move(name, move)
        elif isinstance(self.game,Poker):
            legal = self.game.legal_actions(name)
            action = result.poker_action
            if action not in legal:
                action = 'check' if 'check' in legal else 'call' if 'call' in legal else 'fold'
            self.game.act(name,action,reveal=result.reveal_cards)
        elif isinstance(self.game,Debate):
            self.game.act(name,result.speech)
        else:
            targets = [p for p in self.game.alive if p != name]
            target = result.vote if result.vote in targets else targets[0]
            self.game.act(name, target)
        self.render_game()

    def render_game(self):
        if not self.game:
            return
        if not self.game_window or not self.game_window.winfo_exists():
            self.game_window = tk.Toplevel(self.root)
            self.game_window.configure(bg=BG)
            self.game_window.protocol("WM_DELETE_WINDOW", self.cancel_game)
        win = self.game_window
        win.title("Screen Squatters | " + self.game.kind)
        if isinstance(self.game,Poker):
            if self.poker_table is None:
                self.poker_table = PokerTable(self,win,draw_friend)
            else:
                self.poker_table.refresh()
            self.announce_game_result()
            return
        for widget in win.winfo_children():
            widget.destroy()
        self.label(win, self.game.kind).pack(padx=20, pady=10)
        self.label(win, self.game.result or ("Your turn" if self.game.actor == "You" else "Waiting for a housemate...")).pack(padx=20, pady=5)
        if isinstance(self.game, TicTacToe):
            self.label(win, "X: " + self.game.players[0] + " | O: " + self.game.players[1]).pack()
            board = tk.Frame(win, bg=BG)
            board.pack(padx=20, pady=16)
            for i, mark in enumerate(self.game.board):
                button = self.button(board, mark or " ", lambda cell=i: self.game_action(cell), width=5, height=2)
                if mark or self.game.actor != "You":
                    button.configure(state="disabled")
                button.grid(row=i//3, column=i%3, padx=3, pady=3)
        elif isinstance(self.game,Debate):
            tk.Label(win,text=self.game.topic,bg=BG,fg=ACCENT,wraplength=460,font=('Segoe UI',14,'bold')).pack(padx=20,pady=12)
            self.label(win,f'Round {self.game.round} / {self.game.rounds}').pack()
            tk.Label(win,text='\n\n'.join(self.game.events[-5:]),bg=BG,fg=FG,wraplength=460,justify='left').pack(padx=20,pady=12)
            if self.game.actor == 'You':
                self.label(win,'Add your argument in group chat, or pass.').pack(padx=20)
                self.button(win,'Open group chat',self.show_chat).pack(pady=5)
                self.button(win,'Pass this round',self.game_action).pack(pady=5)
        else:
            view = self.game.view("You")
            self.label(win, "Your secret role: " + view["your_role"].upper() if 'You' in self.game.players else 'Watching the housemates').pack(pady=8)
            self.label(win, "Alive: " + ", ".join(self.game.alive)).pack(padx=20)
            tk.Label(win, text="\n".join(self.game.events[-5:]), bg=BG, fg=MUTED, wraplength=430, justify="left").pack(padx=20, pady=12)
            if self.game.actor == "You":
                if self.game.phase == "discussion":
                    self.label(win, "Say your piece in the living room, then end your turn.").pack(padx=20)
                    self.button(win, "Done talking / pass", self.game_action).pack(pady=10)
                else:
                    for target in view["targets"]:
                        self.button(win, ("Eliminate " if self.game.phase == "night" else "Vote for ") + target,
                                    lambda value=target: self.game_action(value)).pack(fill="x", padx=20, pady=4)
        if 'You' not in self.game.players:
            self.button(win,'Join the next game',self.request_join_game).pack(pady=5)
        self.button(win, "Leave game", self.cancel_game).pack(pady=12)
        self.announce_game_result()

    def announce_game_result(self):
        if self.game.result and not getattr(self.game, "announced", False):
            self.game.announced = True
            self.game_done_at = time.monotonic()
            self.append("House", self.game.result)
            for name in self.game.players:
                if name in CHARACTERS:
                    self.house.remember("House", [{"target": name, "text": self.game.kind + ": " + self.game.result}])
            self.save()

    def drag_start(self, event, name):
        win = self.floaters[name][0]
        self.drag = (event.x_root, event.y_root, win.winfo_x(), win.winfo_y())
        self.dragged = False
        self.drag_samples = deque([(time.monotonic(),event.x_root,event.y_root)],maxlen=8)
        self.world.residents[name].vx = self.world.residents[name].vy = 0
        self.world.residents[name].picked_up = True
        self.world.residents[name].spin = 0
        self.world.residents[name].held_until = float("inf")

    def drag_move(self, event, name):
        x, y, wx, wy = self.drag
        dx, dy = event.x_root-x, event.y_root-y
        if abs(dx)+abs(dy) > 5:
            self.dragged = True
        resident = self.world.residents[name]
        resident.x, resident.y = self.world.constrain(wx+dx, wy+dy)
        self.drag_samples.append((time.monotonic(),event.x_root,event.y_root))

    def drag_end(self, event, name):
        resident = self.world.residents[name]
        resident.picked_up = False
        resident.held_until = time.monotonic()+20
        if resident.mode != "returning":
            resident.mode, resident.goal = "seated" if self.movie_mode.get() else "idle", None
            resident.next_wander = time.monotonic()+25
        if self.dragged:
            now = time.monotonic()
            self.drag_samples.append((now,event.x_root,event.y_root))
            vx,vy = throw_velocity(self.drag_samples,now)
            self.world.throw(name,vx,vy,now)
        if not self.dragged:
            self.show_chat(name)

    def floater_menu(self, event, name):
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="Have a chat", command=lambda:self.show_chat(name))
        menu.add_command(label="Peek inside the house", command=self.show_home)
        menu.add_command(label="Send " + name + " to sleep", command=lambda: self.sleep(name))
        menu.add_command(label="Memories", command=lambda: self.show_memories(name))
        menu.add_checkbutton(label="Stand still (everyone)", variable=self.stand_still, command=self.stand_still_changed)
        menu.add_checkbutton(label="Movie mode", variable=self.movie_mode, command=self.set_movie_mode)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def animate(self):
        if self.closing:
            return
        self.frame += 1
        self.world.physics_enabled = self.house.options['physics']
        self.world.gravity = self.house.options['gravity']
        self.world.bounce = self.house.options['bounce']
        self.social.tick(self.world,time.monotonic())
        self.dialogue_tick()
        self.habitat.frame()
        if self.poker_table:
            self.poker_table.animate()
        active = any(resident.mode != "home" for resident in self.world.residents.values())
        fading = abs(self.habitat.reveal-(1 if self.habitat.open else 0)) > .01
        self.root.after(40 if active or fading or self.habitat.hover else 250, self.animate)

    def quit(self):
        self.windows.backend.set_monitoring(False)
        self.recover_sleep_tick()
        self.closing = True
        self.cancelled.set()
        # Pending reservations stay on disk if inference is still running.
        try:
            self.house.save()
        except OSError:
            pass
        threading.Thread(target=self.server.shutdown, daemon=True).start()
        self.server.server_close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    try:
        ScreenSquatters(root)
        root.mainloop()
    except Exception as error:
        root.withdraw()
        messagebox.showerror("Screen Squatters couldn't start", str(error))
        root.destroy()

"""Screen Squatters: a home for three desktop companions. Python 3.10+, Windows."""
from collections import deque
from copy import deepcopy
import math
import os
from pathlib import Path
import queue
import secrets
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from ai import DEFAULT_MODEL, companion_turn
from bridge import BridgeServer, PORT
from games import Mafia, TicTacToe
from house import CHARACTERS, House
from screen import browser_snapshot_matches, capture_window, foreground

BG, PANEL, FG, MUTED = "#171923", "#242738", "#f1edff", "#abaec7"
ACCENT, TRANSPARENT = "#c5b0ff", "#010203"


def draw_friend(canvas, name, x, y, scale=1, asleep=False, phase=0):
    color = CHARACTERS[name]["color"]
    bob = 0 if asleep else math.sin(phase / 10) * 3
    def box(a, b, c, d):
        return x+a*scale, y+(b+bob)*scale, x+c*scale, y+(d+bob)*scale
    canvas.create_oval(*box(-34, 42, 34, 53), fill="#343247", outline="")
    for foot in (-20, 11):
        canvas.create_oval(*box(foot, 28, foot+15, 47), fill=color, outline="#5f5574", width=2)
    canvas.create_oval(*box(-37, -15, -17, 9), fill=color, outline="")
    canvas.create_oval(*box(17, -15, 37, 9), fill=color, outline="")
    canvas.create_oval(*box(-29, -43, 29, 38), fill=color, outline="#5f5574", width=2)
    canvas.create_oval(*box(-20, -34, -5, -23), fill="#efedff", outline="")
    for eye in (-11, 11):
        if asleep or phase % 110 < 3:
            canvas.create_line(x+(eye-4)*scale, y+(-9+bob)*scale, x+(eye+4)*scale,
                               y+(-9+bob)*scale, fill=BG, width=2)
        else:
            canvas.create_oval(*box(eye-3, -15, eye+3, -5), fill=BG, outline="")
    if name == "Byte":
        for eye in (-12, 12):
            canvas.create_oval(*box(eye-10, -21, eye+10, 0), outline="#263f49", width=2)
        canvas.create_line(x-2*scale, y+(-10+bob)*scale, x+2*scale, y+(-10+bob)*scale, fill=BG, width=2)
    elif name == "Rex":
        points = [(-23, -38), (-27, -56), (-12, -47), (0, -63), (12, -47), (27, -56), (23, -38)]
        canvas.create_polygon(*[v for a, b in points for v in (x+a*scale, y+(b+bob)*scale)], fill="#f7d977", outline="#92733c", width=2)
        canvas.create_line(x+6*scale, y+(-24+bob)*scale, x+18*scale, y+(-28+bob)*scale, fill=BG, width=2)
    else:
        canvas.create_line(x, y+(-42+bob)*scale, x+3*scale, y+(-55+bob)*scale,
                           x+12*scale, y+(-56+bob)*scale, smooth=True, fill="#78618f", width=3)
    if asleep:
        canvas.create_text(x+30*scale, y-40*scale, text="z Z", fill=MUTED, font=("Segoe UI", max(8, int(11*scale))))
    else:
        canvas.create_arc(*box(-9, 0, 10, 16), start=195, extent=145, style="arc", outline=BG, width=2)


class ScreenSquatters:
    def __init__(self, root, data_dir=None, port=PORT, timers=True):
        self.root = root
        self.local = Path(data_dir) if data_dir else Path(__file__).resolve().parent / ".local"
        self.local.mkdir(parents=True, exist_ok=True)
        self.house = House(self.local / "house.json")
        self.key = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
        self.model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
        self.page = None
        self.page_time = 0
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
        token_path = self.local / "pairing-code.txt"
        self.token = token_path.read_text().strip() if token_path.exists() else ""
        if len(self.token) != 48:
            self.token = secrets.token_hex(24)
            token_path.write_text(self.token)
        try:
            self.server = BridgeServer(self.token, self.inbox, port=port)
        except OSError:
            raise RuntimeError("Port 17373 is busy. Quit the older Pip/Screen Squatters instance first.") from None
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        root.title("Screen Squatters | home")
        root.configure(bg=BG)
        # Keep font sizes and canvas geometry balanced on high-DPI Windows desktops.
        root.tk.call("tk", "scaling", 1.333333)
        root.geometry(f"{min(1020, root.winfo_screenwidth()-60)}x{min(750, root.winfo_screenheight()-100)}")
        root.minsize(880, 650)
        root.protocol("WM_DELETE_WINDOW", self.quit)
        self.hangout = tk.BooleanVar(value=True)
        self.screen_enabled = tk.BooleanVar(value=False)
        self.capture_interval = tk.IntVar(value=30)
        self.status = tk.StringVar(value="Everyone's home. Wake someone up to hang out.")
        self.context_status = tk.StringVar(value="Screen capture OFF | no browser page shared")
        self.build_home()
        self.build_floaters()
        self.note("Welcome home. Pip, Byte and Rex are asleep. Wake any combination of them; they can chat with you and with each other. Settings has your API key and browser pairing code.")
        if self.house.warning:
            self.note(self.house.warning)
        self.refresh()
        self.animate()
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
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=20, pady=(14, 6))
        tk.Label(header, text="screen squatters", bg=BG, fg=FG, font=("Segoe UI", 24, "bold")).pack(side="left")
        self.button(header, "Settings", self.show_settings).pack(side="right")
        self.button(header, "Everyone home", self.sleep_all).pack(side="right", padx=8)
        tk.Label(self.root, text="Three housemates. No grand purpose. Just a little company.", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=22, pady=(0, 10))
        # Reserve the bottom indicators before allocating the expanding main area.
        tk.Label(self.root, textvariable=self.status, bg=BG, fg=MUTED, anchor="w", padx=18,
                 pady=6, font=("Segoe UI", 9)).pack(side="bottom", fill="x")
        tk.Label(self.root, textvariable=self.context_status, bg=PANEL, fg=ACCENT, anchor="w", padx=18,
                 pady=6, font=("Segoe UI", 9)).pack(side="bottom", fill="x")
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        left = tk.Frame(body, bg=BG, width=340)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        self.sidebar = tk.Canvas(left, width=338, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(left, orient="vertical", command=self.sidebar.yview)
        scrollbar.pack(side="right", fill="y")
        self.sidebar.pack(side="left", fill="both", expand=True)
        self.sidebar.configure(yscrollcommand=scrollbar.set)
        contents = tk.Frame(self.sidebar, bg=BG)
        embedded = self.sidebar.create_window((0, 0), window=contents, anchor="nw")
        contents.bind("<Configure>", lambda _e: self.sidebar.configure(scrollregion=self.sidebar.bbox("all")))
        self.sidebar.bind("<Configure>", lambda e: self.sidebar.itemconfigure(embedded, width=e.width))
        self.home_canvas = tk.Canvas(contents, width=338, height=170, bg=BG, highlightthickness=0)
        self.home_canvas.pack(fill="x")
        self.cards = {}
        for name, info in CHARACTERS.items():
            card = tk.Frame(contents, bg=PANEL, padx=10, pady=6)
            card.pack(fill="x", pady=(0, 8))
            top = tk.Frame(card, bg=PANEL)
            top.pack(fill="x")
            tk.Label(top, text=name, bg=PANEL, fg=info["color"], font=("Segoe UI", 13, "bold")).pack(side="left")
            toggle = self.button(top, "Wake up", lambda n=name: self.toggle(n), font=("Segoe UI", 9), pady=4)
            toggle.pack(side="right")
            tk.Label(card, text=info["tagline"], bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")
            energy = tk.StringVar()
            tk.Label(card, textvariable=energy, bg=PANEL, fg=FG, font=("Segoe UI", 8)).pack(anchor="w", pady=(3, 0))
            controls = tk.Frame(card, bg=PANEL)
            controls.pack(fill="x", pady=(4, 0))
            limit = tk.StringVar(value=str(self.house.agents[name]["limit"]))
            tk.Entry(controls, textvariable=limit, width=9, bg=BG, fg=FG, insertbackground=FG, relief="flat", font=("Segoe UI", 9)).pack(side="left", ipady=3)
            self.button(controls, "Refill tokens", lambda n=name: self.refill(n), font=("Segoe UI", 9), pady=4, padx=6).pack(side="left", padx=4)
            self.button(controls, "Memory", lambda n=name: self.show_memories(n), font=("Segoe UI", 9), pady=4, padx=6).pack(side="right")
            self.cards[name] = {"toggle": toggle, "energy": energy, "limit": limit}
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        # Pack the composer before the expanding transcript so it never disappears.
        footer = tk.Frame(right, bg=BG)
        footer.pack(side="bottom", fill="x")
        compose = tk.Frame(footer, bg=BG)
        compose.pack(fill="x", pady=(8, 5))
        self.question = tk.Entry(compose, bg=PANEL, fg=FG, insertbackground=FG, relief="flat", font=("Segoe UI", 11))
        self.question.pack(side="left", fill="x", expand=True, ipady=10)
        self.question.bind("<Return>", lambda _event: self.send())
        self.send_button = self.button(compose, "Say it", self.send, True)
        self.send_button.pack(side="right", padx=(8, 0))
        games = tk.Frame(footer, bg=BG)
        games.pack(fill="x", pady=(3, 5))
        self.button(games, "Tic-tac-toe", self.choose_ttt).pack(side="left")
        self.button(games, "Mafia", self.start_mafia).pack(side="left", padx=6)
        self.button(games, "Clear screen context", self.clear_context).pack(side="right")
        tk.Checkbutton(footer, text="Let awake housemates hang out (AI turns use tokens)", variable=self.hangout,
                       bg=BG, fg=MUTED, selectcolor=PANEL, activebackground=BG, activeforeground=FG,
                       font=("Segoe UI", 9)).pack(anchor="w")
        tk.Label(right, text="THE LIVING ROOM", bg=BG, fg=ACCENT, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4, 8))
        self.transcript = scrolledtext.ScrolledText(right, height=8, bg="#1c1f2d", fg=FG, relief="flat",
                                                   wrap="word", font=("Segoe UI", 11), padx=12, pady=8, state="disabled")
        self.transcript.pack(fill="both", expand=True)
        for name, info in CHARACTERS.items():
            self.transcript.tag_configure(name, foreground=info["color"], spacing1=8)
        self.transcript.tag_configure("You", foreground="#eeeeff", spacing1=8)
        self.transcript.tag_configure("House", foreground=MUTED, spacing1=8)

    def build_floaters(self):
        self.floaters = {}
        for i, name in enumerate(CHARACTERS):
            win = tk.Toplevel(self.root)
            win.withdraw()
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg=TRANSPARENT)
            if os.name == "nt":
                win.wm_attributes("-transparentcolor", TRANSPARENT)
            win.geometry(f"190x230+{max(0, self.root.winfo_screenwidth()-220-i*195)}+{max(0,self.root.winfo_screenheight()-320)}")
            canvas = tk.Canvas(win, width=190, height=230, bg=TRANSPARENT, highlightthickness=0, cursor="hand2")
            canvas.pack()
            canvas.bind("<ButtonPress-1>", lambda e, n=name: self.drag_start(e, n))
            canvas.bind("<B1-Motion>", lambda e, n=name: self.drag_move(e, n))
            canvas.bind("<ButtonRelease-1>", lambda e: self.show_home() if not self.dragged else None)
            canvas.bind("<Button-3>", lambda e, n=name: self.floater_menu(e, n))
            self.floaters[name] = (win, canvas)

    def show_home(self):
        self.root.deiconify()
        self.root.lift()
        self.question.focus_set()

    def append(self, name, text, remember=True):
        self.transcript.configure(state="normal")
        self.transcript.insert("end", name + "\n", name)
        self.transcript.insert("end", text + "\n\n")
        # Keep widgets and model context bounded even during long sessions.
        if int(self.transcript.index("end-1c").split(".")[0]) > 600:
            self.transcript.delete("1.0", "120.0")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")
        if remember:
            self.conversation.append({"speaker": name, "text": text[:2000]})
            self.conversation = self.conversation[-20:]
        if name in CHARACTERS:
            self.bubbles[name] = (text[:180], time.monotonic() + 18)

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
            self.cards[name]["toggle"].configure(text="Go home" if agent["awake"] else "Wake up")
            energy = f"{'Awake' if agent['awake'] else 'At home'} | {agent['used']:,} / {agent['limit']:,} tokens"
            if agent["reserved"]:
                energy += " | turn reserved"
            if isinstance(self.game, Mafia) and not self.game.result:
                energy = "Token usage hidden until Mafia ends"
            self.cards[name]["energy"].set(energy)
            win = self.floaters[name][0]
            if agent["awake"]:
                win.deiconify()
            else:
                win.withdraw()

    def toggle(self, name):
        if self.house.agents[name]["awake"]:
            self.sleep(name)
        elif self.house.wake(name):
            self.note(name + " woke up and came out of the house.")
            self.next_turn = time.monotonic() + 2
            if not self.key:
                self.note("Preview mode: add an API key in Settings for conversations and AI game turns.")
            self.save()
            self.refresh()
        else:
            self.note(name + " needs a token refill, or is waiting for an in-flight turn to finish.")

    def sleep(self, name):
        self.house.sleep(name)
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
        self.cancelled.set()
        self.pending.clear()
        self.cancel_game("Everyone headed home.")
        for name in CHARACTERS:
            self.house.sleep(name)
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
        self.save()
        self.refresh()
        self.note(name + " has a fresh token allowance. Wake them when you're ready.")

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
        win.geometry("590x580")
        notebook = ttk.Notebook(win)
        notebook.pack(fill="both", expand=True, padx=15, pady=15)
        connection, awareness, reset = [tk.Frame(notebook, bg=BG, padx=18, pady=16) for _ in range(3)]
        for frame, title in ((connection, "Connection"), (awareness, "Screen awareness"), (reset, "Factory reset")):
            notebook.add(frame, text=title)
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
        text(connection, "Browser pairing code: load the extension folder in Chrome/Edge, then paste this in its popup.")
        code = tk.Entry(connection, bg=PANEL, fg=ACCENT, relief="flat")
        code.insert(0, self.token)
        code.configure(state="readonly", readonlybackground=PANEL)
        code.pack(fill="x", ipady=7)
        def copy_code():
            win.clipboard_clear()
            win.clipboard_append(self.token)
        self.button(connection, "Copy pairing code", copy_code).pack(anchor="w", pady=8)
        text(connection, "Awake companions use API tokens when chatting or playing. Their input + output usage counts toward separate allowances. No API key is stored on disk or in the extension.")
        def save():
            self.key, self.model = key.get().strip(), model.get().strip() or DEFAULT_MODEL
            win.destroy()
            self.next_turn = time.monotonic() + 3
        self.button(connection, "Use for this session", save, True).pack(anchor="e", pady=8)
        text(awareness, "The browser extension can share once, or follow the focused webpage after you enable its optional site access. It sends visible text, not the whole HTML document.")
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
        text(reset, "Factory reset sends everyone home and removes all three characters' memories, token usage, conversation and current game. Personalities and default allowances are restored. Screen capture turns OFF. Your extension pairing and API connection are kept.")
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
        if not messagebox.askyesno("Factory reset", "Reset all three companions, their memories, token allowances and local chat?", parent=self.root):
            return
        self.generation += 1
        self.scene += 1
        self.cancelled.set()
        self.pending.clear()
        self.game = None
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
        self.bubbles = {name: ("", 0) for name in CHARACTERS}
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        self.transcript.configure(state="disabled")
        for name in CHARACTERS:
            self.cards[name]["limit"].set(str(self.house.agents[name]["limit"]))
        self.refresh()
        self.note("Factory reset complete. Everyone is home, with fresh memories and allowances.")

    def send(self):
        if self.busy:
            self.status.set("One housemate is still speaking. Try again when their turn finishes.")
            return
        text = self.question.get().strip()[:2000]
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
        if self.game and not self.game.result:
            if isinstance(self.game, Mafia) and self.game.phase == "discussion" and self.game.actor == "You":
                self.game.act("You")
                self.render_game()
            return
        self.pending = deque(self.awake())
        self.next_turn = time.monotonic()

    def request_turn(self, name, trigger):
        if self.busy or not self.key or not self.house.agents[name]["awake"]:
            return
        self.busy, self.busy_name = True, name
        self.cancelled = threading.Event()
        self.send_button.configure(state="disabled")
        private_night = isinstance(self.game, Mafia) and self.game.phase == "night"
        self.status.set("Secret night action in progress..." if private_night else name + " is thinking...")
        agent = self.house.agents[name]
        try:
            remaining = self.house.reserve(name)
        except OSError:
            agent["reserved"] = 0
            self.busy, self.busy_name = False, None
            self.send_button.configure(state="normal")
            self.hangout.set(False)
            self.note("Cannot safely save the token reservation. No AI request was sent.")
            return
        generation, scene = self.generation, self.scene
        game = self.game.view(name) if self.game and not self.game.result else None
        observation = None
        now = time.monotonic()
        if not game:
            if self.observation and now - self.observation_time <= 35:
                observation = deepcopy(self.observation)
            elif self.page and not self.page.get("automatic") and now - self.page_time < 300:
                observation = deepcopy(self.page)
        args = (self.key, self.model, name, deepcopy(agent["memories"]), deepcopy(self.conversation),
                self.awake(), trigger, remaining, observation, game, self.cancelled)
        self.refresh()
        def work():
            result = companion_turn(*args)
            self.results.put(("turn", generation, scene, name, result))
        threading.Thread(target=work, daemon=True).start()

    def handle_turn(self, generation, scene, name, result):
        self.busy, self.busy_name = False, None
        self.send_button.configure(state="normal")
        if generation != self.generation:
            self.refresh()
            return
        active = self.house.agents[name]["awake"] and not self.cancelled.is_set() and scene == self.scene
        self.house.settle(name, result.used)
        if result.error:
            self.note(name + ": " + result.error)
            self.hangout.set(False)
            self.pending.clear()
            self.cancel_game("Game paused after an AI error. Start a new game after fixing the connection.")
        elif result.exhausted:
            self.house.sleep(name)
            self.note(name + " is out of energy for another turn and went home. Refill their allowance to wake them again.")
            if self.game and not self.game.result:
                self.cancel_game("Game ended: a player needs more tokens.")
        elif active:
            night = isinstance(self.game, Mafia) and self.game.phase == "night"
            if result.speech and not night:
                self.append(name, result.speech)
            # Never persist game secrets, including accidentally generated memory updates.
            if not self.game or self.game.result:
                accepted = self.house.remember(name, result.memories)
                for target, _text in accepted:
                    self.note(name + " left a note in " + target + "'s memory.")
            if self.game and not self.game.result:
                self.apply_game_turn(name, result)
        if not self.house.remaining(name) and self.game and not self.game.result:
            self.cancel_game("Game ended: a player ran out of tokens.")
        if active and not result.exhausted and not self.house.remaining(name):
            self.note(name + " used their allowance and went home to sleep.")
        self.save()
        self.refresh()
        self.status.set("All quiet at home." if not self.awake() else "Hanging out" if self.hangout.get() else "Automatic hangout paused")
        self.next_turn = time.monotonic() + (2 if self.pending or (self.game and not self.game.result) else 25)

    def capture_tick(self):
        now = time.monotonic()
        if self.capture_busy or not self.awake() or now - self.last_capture < 5:
            return
        self.last_capture = now
        self.capture_busy = True
        epoch = self.capture_epoch
        page, age = deepcopy(self.page), now - self.page_time
        screenshots = self.screen_enabled.get()
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
                if browser_snapshot_matches(window, page, age):
                    observation = {"kind": "page", **page}
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

    def tick(self):
        if self.closing:
            return
        self.capture_tick()
        now = time.monotonic()
        if not self.busy and self.key and now >= self.next_turn:
            if self.game and not self.game.result:
                actor = self.game.actor
                if actor in self.awake():
                    self.request_turn(actor, "Take your game turn. Respond to the ongoing banter without revealing secrets.")
            else:
                while self.pending and self.pending[0] not in self.awake():
                    self.pending.popleft()
                if self.pending:
                    self.request_turn(self.pending.popleft(), "React to the user and what your housemates just said. Don't repeat their answer.")
                elif self.hangout.get() and self.awake():
                    names = list(CHARACTERS)
                    for offset in range(1, 4):
                        index = (self.last_speaker + offset) % 3
                        if names[index] in self.awake():
                            self.last_speaker = index
                            self.request_turn(names[index], "Hang out naturally. React to your friends, riff on a joke, notice something in the supplied snapshot, or suggest something fun. Silence is okay: keep it short.")
                            break
        self.root.after(500, self.tick)

    def poll(self, reschedule=True):
        if self.closing:
            return
        try:
            while True:
                page = self.inbox.get_nowait()
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
                else:
                    _, epoch, observation, error = event
                    self.capture_busy = False
                    if epoch != self.capture_epoch or not self.awake():
                        continue
                    self.observation, self.observation_time = observation, time.monotonic()
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

    def begin_game(self, game):
        if self.busy:
            self.note("Wait for the current turn before starting a game.")
            return
        if not self.key:
            self.show_settings()
            return
        self.scene += 1
        self.pending.clear()
        self.game = game
        self.next_turn = time.monotonic() + 1
        self.note(game.kind + " started. AI game turns use each player's token allowance.")
        self.render_game()

    def start_ttt(self, first, second):
        self.begin_game(TicTacToe(first, second))

    def start_mafia(self):
        if len(self.awake()) != 3:
            self.note("Mafia needs all three housemates awake, plus you: four players.")
            return
        self.begin_game(Mafia(["You", *CHARACTERS]))

    def close_game_window(self):
        if self.game_window and self.game_window.winfo_exists():
            self.game_window.destroy()
        self.game_window = None

    def cancel_game(self, reason="Game ended."):
        if self.game:
            self.scene += 1
            self.cancelled.set()
            self.game = None
            self.close_game_window()
            self.note(reason)

    def game_action(self, value=None):
        if not self.game or self.game.actor != "You":
            return
        try:
            if isinstance(self.game, TicTacToe):
                self.game.move("You", value)
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
        else:
            view = self.game.view("You")
            self.label(win, "Your secret role: " + view["your_role"].upper()).pack(pady=8)
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
        self.button(win, "Leave game", self.cancel_game).pack(pady=12)
        if self.game.result and not getattr(self.game, "announced", False):
            self.game.announced = True
            self.append("House", self.game.result)
            for name in self.game.players:
                if name in CHARACTERS:
                    self.house.remember("House", [{"target": name, "text": self.game.kind + ": " + self.game.result}])
            self.save()

    def drag_start(self, event, name):
        win = self.floaters[name][0]
        self.drag = (event.x_root, event.y_root, win.winfo_x(), win.winfo_y())
        self.dragged = False

    def drag_move(self, event, name):
        x, y, wx, wy = self.drag
        dx, dy = event.x_root-x, event.y_root-y
        if abs(dx)+abs(dy) > 5:
            self.dragged = True
        self.floaters[name][0].geometry(f"+{max(0,wx+dx)}+{max(0,wy+dy)}")

    def floater_menu(self, event, name):
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="Open home", command=self.show_home)
        menu.add_command(label="Send " + name + " to sleep", command=lambda: self.sleep(name))
        menu.add_command(label="Memories", command=lambda: self.show_memories(name))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def animate(self):
        if self.closing:
            return
        self.frame += 1
        c = self.home_canvas
        c.delete("all")
        c.create_oval(14, 195, 328, 220, fill="#242332", outline="")
        c.create_polygon(22, 62, 169, 3, 316, 62, fill="#6a587f", outline="#a48dc1", width=2)
        c.create_rectangle(35, 62, 303, 200, fill="#302b40", outline="#a48dc1", width=2)
        c.create_rectangle(149, 140, 192, 200, fill="#6a587f", outline="")
        c.create_oval(180, 170, 185, 175, fill="#efd490", outline="")
        for i, name in enumerate(CHARACTERS):
            x = 78+i*91
            c.create_rectangle(x-32, 79, x+32, 137, fill="#443955", outline="#9d85b7", width=2)
            if not self.house.agents[name]["awake"]:
                draw_friend(c, name, x, 111, .48, True, self.frame)
            else:
                c.create_text(x, 108, text="out", fill=MUTED, font=("Segoe UI", 10))
        c.create_text(92, 170, text="home, sweet\nhome", fill="#d8c6ef", font=("Segoe UI", 9))
        c.scale("all", 0, 0, 1, .76)
        for name, (win, canvas) in self.floaters.items():
            if not self.house.agents[name]["awake"]:
                continue
            canvas.delete("all")
            text, until = self.bubbles[name]
            private_night = isinstance(self.game, Mafia) and self.game.phase == "night"
            if self.busy_name == name and not private_night:
                text, until = "hmm...", time.monotonic()+1
            if until > time.monotonic():
                canvas.create_rectangle(5, 2, 185, 98, fill=PANEL, outline="#554961", width=2)
                canvas.create_polygon(81, 98, 91, 109, 102, 98, fill=PANEL, outline="")
                canvas.create_text(95, 50, text=text[:150], width=161, fill=FG, font=("Segoe UI", 9))
            draw_friend(canvas, name, 95, 161, .95, False, self.frame)
            canvas.create_text(95, 218, text=name + " | click for home", fill=CHARACTERS[name]["color"], font=("Segoe UI", 9, "bold"))
        self.root.after(80, self.animate)

    def quit(self):
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

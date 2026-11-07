"""The small desktop house, cutaway rooms, optional conversation, and live residents."""
import math
import os
import time
import tkinter as tk
from tkinter import scrolledtext

from behaviour import World
from house import CHARACTERS
from screen import make_clickthrough, make_noactivate

BG, PANEL, FG, MUTED = "#171923", "#242738", "#f1edff", "#abaec7"
TRANSPARENT = "#010203"


class Habitat:
    width, height = 360, 320

    def __init__(self, app, painter):
        self.app, self.paint = app, painter
        root = app.root
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg=TRANSPARENT)
        if os.name == "nt":
            root.wm_attributes("-transparentcolor", TRANSPARENT)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"360x320+{max(0, sw-405)}+{max(0,sh-390)}")
        root.minsize(1, 1)
        self.canvas = tk.Canvas(root, width=360, height=320, bg=TRANSPARENT, highlightthickness=0, cursor="hand2")
        self.canvas.pack()
        self.open = False
        self.reveal = 0
        self.hover = False
        self.dragged = False
        self.canvas.bind("<ButtonPress-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.canvas.bind("<Button-3>", self.menu)
        self.canvas.bind("<Enter>", lambda _e: setattr(self, "hover", True))
        self.canvas.bind("<Leave>", lambda _e: setattr(self, "hover", False))
        root.bind("<Escape>", lambda _e: setattr(self, "open", False))
        root.update_idletasks()
        make_noactivate(root.winfo_id())
        self.world = World(CHARACTERS, (0, 0, sw, max(240, sh-55)), self.home_point(), now=time.monotonic())
        self.world.freeze(app.stand_still.get())
        self.world.movie_corner = app.movie_corner.get()
        app.world = self.world
        app.cards = {name: {"toggle": None, "energy": tk.StringVar(),
                            "limit": tk.StringVar(value=str(app.house.agents[name]["limit"]))} for name in CHARACTERS}
        self.markers = {}
        self.build_chat()
        self.last_frame = time.monotonic()

    def home_point(self):
        return self.app.root.winfo_x()+85, self.app.root.winfo_y()+60

    def press(self, event):
        root = self.app.root
        self.drag_origin = (event.x_root, event.y_root, root.winfo_x(), root.winfo_y())
        self.dragged = False

    def drag(self, event):
        x, y, wx, wy = self.drag_origin
        dx, dy = event.x_root-x, event.y_root-y
        if abs(dx)+abs(dy) > 5:
            self.dragged = True
        root = self.app.root
        px = max(0, min(root.winfo_screenwidth()-self.width, wx+dx))
        py = max(0, min(root.winfo_screenheight()-self.height-45, wy+dy))
        root.geometry(f"+{px}+{py}")

    def release(self, event):
        if self.dragged:
            return
        self.tap(event.x, event.y)

    def tap(self, x, y):
        if not self.open:
            self.open = True
        elif y < 104:
            self.open = False
        elif 110 <= y <= 223 and 43 <= x <= 317:
            name = list(CHARACTERS)[min(2, int((x-43)/92))]
            self.app.toggle(name)
        elif 225 <= y <= 278:
            self.app.show_chat()
        else:
            self.open = False

    def menu(self, event):
        app = self.app
        menu = tk.Menu(app.root, tearoff=False)
        menu.add_command(label="Close the front wall" if self.open else "Enter the house", command=lambda: setattr(self, "open", not self.open))
        menu.add_command(label="Have a chat", command=app.show_chat)
        menu.add_checkbutton(label="Movie mode", variable=app.movie_mode, command=app.set_movie_mode)
        corners = tk.Menu(menu, tearoff=False)
        for value in ("bottom-left", "bottom-right", "top-left", "top-right"):
            corners.add_radiobutton(label=value.replace("-", " ").title(), variable=app.movie_corner,
                                    value=value, command=app.set_movie_corner)
        menu.add_cascade(label="Movie seats", menu=corners)
        games = tk.Menu(menu, tearoff=False)
        games.add_command(label="Tic-tac-toe", command=app.choose_ttt)
        games.add_command(label="Mafia", command=app.start_mafia)
        menu.add_cascade(label="Play a game", menu=games)
        menu.add_separator()
        menu.add_command(label="Settings & memories", command=app.show_settings)
        menu.add_checkbutton(label="Autonomous life", variable=app.autonomy, command=app.autonomy_changed)
        menu.add_checkbutton(label="Stand still", variable=app.stand_still, command=app.stand_still_changed)
        recovery = tk.Menu(menu, tearoff=False)
        for rate in (0, 100, 500, 1000, 5000):
            recovery.add_radiobutton(label="Off" if not rate else f"{rate:,} tokens / minute", variable=app.recovery_rate,
                                     value=rate, command=app.set_recovery_rate)
        recovery.add_separator()
        recovery.add_command(label="Custom rate...", command=app.custom_recovery_rate)
        menu.add_cascade(label=f"Sleep recovery ({app.recovery_rate.get():,}/min)", menu=recovery)
        menu.add_checkbutton(label="Automatic conversation", variable=app.hangout)
        menu.add_checkbutton(label="Screen snapshots", variable=app.screen_enabled, command=app.awareness_changed)
        menu.add_command(label="Everyone home / pause", command=app.sleep_all)
        menu.add_separator()
        menu.add_command(label="Quit Screen Squatters", command=app.quit)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def build_chat(self):
        app = self.app
        win = app.chat = tk.Toplevel(app.root)
        win.withdraw()
        win.title("Screen Squatters | conversation")
        win.geometry("460x460")
        win.minsize(380, 330)
        win.configure(bg=BG)
        win.protocol("WM_DELETE_WINDOW", win.withdraw)
        header = tk.Frame(win, bg=BG)
        header.pack(fill="x", padx=16, pady=12)
        tk.Label(header, text="a little company", bg=BG, fg=FG, font=("Segoe UI", 17, "bold")).pack(side="left")
        app.button(header, "Settings", app.show_settings).pack(side="right")
        footer = tk.Frame(win, bg=BG)
        footer.pack(side="bottom", fill="x", padx=16, pady=(4, 12))
        compose = tk.Frame(footer, bg=BG)
        compose.pack(fill="x", pady=6)
        app.question = tk.Entry(compose, bg=PANEL, fg=FG, insertbackground=FG, relief="flat", font=("Segoe UI", 11))
        app.question.pack(side="left", fill="x", expand=True, ipady=9)
        app.question.bind("<Return>", lambda _e: app.send())
        app.send_button = app.button(compose, "Say it", app.send, True)
        app.send_button.pack(side="right", padx=(8, 0))
        tk.Label(footer, textvariable=app.status, bg=BG, fg=MUTED, wraplength=420,
                 justify="left", anchor="w", font=("Segoe UI", 9)).pack(fill="x", pady=4)
        app.transcript = scrolledtext.ScrolledText(win, height=5, bg=BG, fg=FG, relief="flat", wrap="word",
                                                  font=("Segoe UI", 11), padx=10, pady=5, state="disabled")
        app.transcript.pack(fill="both", expand=True, padx=10)
        for name, info in CHARACTERS.items():
            app.transcript.tag_configure(name, foreground=info["color"], spacing1=8)
        app.transcript.tag_configure("You", foreground=FG, spacing1=8)
        app.transcript.tag_configure("House", foreground=MUTED, spacing1=8)

    def populate_housemates(self, parent):
        app = self.app
        tk.Checkbutton(parent, text="Let them wander, wake and rest on their own", variable=app.autonomy, command=app.autonomy_changed,
                       bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG).pack(anchor="w", pady=(0, 8))
        for name, info in CHARACTERS.items():
            card = tk.Frame(parent, bg=PANEL, padx=10, pady=8)
            card.pack(fill="x", pady=5)
            top = tk.Frame(card, bg=PANEL)
            top.pack(fill="x")
            tk.Label(top, text=name+"  ·  "+info["tagline"], bg=PANEL, fg=info["color"], font=("Segoe UI", 10)).pack(side="left")
            toggle = app.button(top, "Wake up", lambda n=name: app.toggle(n), font=("Segoe UI", 9), pady=3)
            toggle.pack(side="right")
            app.cards[name]["toggle"] = toggle
            tk.Label(card, textvariable=app.cards[name]["energy"], bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=3)
            row = tk.Frame(card, bg=PANEL)
            row.pack(fill="x")
            tk.Entry(row, textvariable=app.cards[name]["limit"], bg=BG, fg=FG, insertbackground=FG,
                     relief="flat", width=10).pack(side="left", ipady=5)
            app.button(row, "Refill tokens", lambda n=name: app.refill(n), font=("Segoe UI", 9), pady=4).pack(side="left", padx=8)
            app.button(row, "Memory", lambda n=name: app.show_memories(n), font=("Segoe UI", 9), pady=4).pack(side="right")
        tk.Checkbutton(parent, text="Let awake housemates start conversations (uses API tokens)", variable=app.hangout,
                       bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG).pack(anchor="w", pady=8)
        app.button(parent, "Everyone home / pause", app.sleep_all).pack(anchor="w", pady=8)
        app.refresh()

    def draw_house(self):
        app, c = self.app, self.canvas
        c.delete("all")
        c.create_oval(14, 276, 347, 309, fill="#302d3c", outline="")
        c.create_rectangle(274, 37, 299, 93, fill="#ae7d72", outline="#dca792", width=2)
        c.create_rectangle(270, 34, 303, 42, fill="#e8c1a5", outline="")
        c.create_rectangle(36, 101, 324, 279, fill="#e5c7a1", outline="#6d5260", width=3)
        for i, name in enumerate(CHARACTERS):
            x = 43+i*92
            c.create_rectangle(x, 111, x+90, 218, fill=("#514760", "#3d5b60", "#68524e")[i], outline="#ddbc95", width=2)
            for py in (128, 153, 178):
                c.create_text(x+76, py, text="·", fill="#84718b", font=("Segoe UI", 14))
            c.create_rectangle(x+10, 176, x+79, 200, fill="#8a6b75", outline="#b18c8a", width=2)
            c.create_rectangle(x+12, 178, x+34, 192, fill="#eee0cb", outline="")
            c.create_line(x+12, 201, x+12, 210, x+76, 210, x+76, 201, fill="#b18c8a", width=3)
            resident = self.world.residents[name]
            if resident.mode == "home":
                self.paint(c, name, x+46, 157, .55, True, app.frame)
            else:
                c.create_text(x+46, 155, text="watching a movie" if app.movie_mode.get() else "out exploring", fill="#d3c0c1", font=("Segoe UI", 7))
            c.create_text(x+45, 123, text=name, fill=CHARACTERS[name]["color"], font=("Segoe UI", 9, "bold"))
        # A tiny living room: the sofa is the conversation entry point.
        c.create_oval(73, 254, 272, 273, fill="#b48c79", outline="")
        c.create_rectangle(83, 228, 167, 259, fill="#718b8c", outline="#4b6167", width=2)
        c.create_rectangle(80, 244, 171, 262, fill="#8eaa9f", outline="#4b6167", width=2)
        c.create_text(125, 246, text="say hi", fill="#213d43", font=("Segoe UI", 8))
        c.create_oval(212, 235, 266, 253, fill="#9f7561", outline="#76534b", width=2)
        c.create_line(225, 251, 222, 266, 253, 266, 252, 251, fill="#76534b", width=3)
        c.create_oval(232, 232, 244, 242, fill="#eee0c2", outline="")
        # Tk canvas stipples dissolve the front wall while revealing the rooms behind it.
        if self.reveal < .98:
            options = {} if self.reveal < .15 else {"stipple": "gray75" if self.reveal < .4 else "gray50" if self.reveal < .65 else "gray25"}
            c.create_rectangle(36, 101, 324, 279, fill="#9b706f", outline="#e4b69b", width=3, **options)
            if self.reveal < .4:
                for y in range(122, 278, 22):
                    c.create_line(38, y, 322, y, fill="#825b62", width=2)
                for x in (80, 244):
                    c.create_rectangle(x-24, 141, x+24, 189, fill="#f3d996", outline="#e8b995", width=4)
                    c.create_line(x, 142, x, 189, fill="#a77c77", width=3)
                    c.create_line(x-24, 165, x+24, 165, fill="#a77c77", width=3)
                c.create_rectangle(151, 208, 208, 279, fill="#5d536b", outline="#e2b597", width=3)
                c.create_oval(192, 243, 198, 249, fill="#f5d68b", outline="")
        c.create_polygon(20, 105, 180, 23, 340, 105, fill="#56516f", outline="#c39b9c", width=3)
        c.create_line(37, 100, 180, 35, 324, 100, fill="#77718c", width=2)
        c.create_text(180, 77, text="movie night" if app.movie_mode.get() else "screen squatters", fill="#f0d7bb", font=("Segoe UI", 10, "bold"))
        c.create_rectangle(150, 280, 210, 290, fill="#c79b7b", outline="")
        capture = app.screen_enabled.get() and bool(app.awake())
        browser = bool(app.awake() and app.page and time.monotonic()-app.page_time < 15)
        c.create_oval(309, 218, 319, 231, fill="#ffd778" if capture else "#91dfce" if browser else "#7d6b72", outline="#e6bea0")
        if capture or browser:
            c.create_text(291, 301, text="screen on" if capture else "browser on", fill="#f6d99d", font=("Segoe UI", 8))
        if self.hover:
            c.create_text(158, 304, text="tap a housemate · roof to close" if self.open else "click to enter · right-click for more",
                          fill="#dcc8b6", font=("Segoe UI", 8))

    def marker(self, name, resident):
        if name not in self.markers:
            win = tk.Toplevel(self.app.root)
            win.withdraw()
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg=TRANSPARENT)
            if os.name == "nt":
                win.wm_attributes("-transparentcolor", TRANSPARENT)
            c = tk.Canvas(win, width=50, height=50, bg=TRANSPARENT, highlightthickness=0)
            c.pack()
            self.markers[name] = (win, c)
            win.update_idletasks()
            make_clickthrough(win.winfo_id())
        win, c = self.markers[name]
        if resident.mode != "interested" or not resident.interest:
            win.withdraw()
            return
        x, y, _label = resident.interest
        win.geometry(f"50x50+{max(0,int(x-25))}+{max(0,int(y-25))}")
        c.delete("all")
        color = CHARACTERS[name]["color"]
        radius = 14+math.sin(self.app.frame/6)*3
        c.create_oval(25-radius, 25-radius, 25+radius, 25+radius, outline=color, width=2)
        c.create_line(25, 3, 25, 11, fill=color, width=2)
        c.create_line(25, 39, 25, 47, fill=color, width=2)
        c.create_line(3, 25, 11, 25, fill=color, width=2)
        c.create_line(39, 25, 47, 25, fill=color, width=2)
        if not win.winfo_viewable():
            win.deiconify()

    def frame(self):
        app = self.app
        now = time.monotonic()
        self.reveal += ((1 if self.open else 0)-self.reveal)*.24
        self.world.home = self.world.constrain(*self.home_point())
        for resident in self.world.residents.values():
            if resident.mode == "returning":
                resident.goal = self.world.home
        arrived = self.world.step(now-self.last_frame, now, autonomous=app.autonomy.get())
        self.last_frame = now
        for name in arrived:
            resident = self.world.residents[name]
            if resident.pending_speech:
                app.bubbles[name] = (resident.pending_speech[:180], now+18)
                resident.pending_speech = ""
        self.draw_house()
        for name, (win, canvas) in app.floaters.items():
            resident = self.world.residents[name]
            if resident.mode == "home":
                win.withdraw()
                if name in self.markers:
                    self.markers[name][0].withdraw()
                continue
            if (win.winfo_x(), win.winfo_y()) != (int(resident.x), int(resident.y)):
                win.geometry(f"+{int(resident.x)}+{int(resident.y)}")
            if not win.winfo_viewable():
                win.deiconify()
            canvas.delete("all")
            text, until = app.bubbles[name]
            private = getattr(app.game, "phase", None) == "night" and not app.game.result
            if app.busy_name == name and not private and not app.movie_mode.get():
                text, until = "hmm...", now+1
            if resident.mode == "returning":
                text, until = "heading home...", now+1
            if text and until > now:
                canvas.create_rectangle(5, 2, 185, 98, fill=PANEL, outline="#554961", width=2)
                canvas.create_polygon(81, 98, 91, 109, 102, 98, fill=PANEL, outline="")
                canvas.create_text(95, 50, text=text[:150], width=161, fill=FG, font=("Segoe UI", 9))
            gaze = (0, 0)
            if resident.gaze:
                dx, dy = resident.gaze[0]-(resident.x+95), resident.gaze[1]-(resident.y+150)
                distance = max(1, math.hypot(dx, dy))
                gaze = (dx/distance, dy/distance)
            self.paint(canvas, name, 95, 161, .95, False, app.frame, gaze=gaze,
                       pointing=resident.mode == "interested", walking=resident.mode in {"walking", "returning", "approaching", "settling"},
                       seated=resident.mode == "seated")
            self.marker(name, resident)

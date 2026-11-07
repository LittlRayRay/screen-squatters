"""Pip: a tiny Windows desktop companion. Run with Python 3.10+."""
import math
import os
from pathlib import Path
import queue
import secrets
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext

from ai import DEFAULT_MODEL, ask
from bridge import BridgeServer

BG = "#171923"
PANEL = "#232638"
FG = "#eff0ff"
MUTED = "#b0b5d1"
ACCENT = "#c5b0ff"
TRANSPARENT = "#010203"


class Pip:
    def __init__(self, root):
        self.root = root
        self.page = None
        self.history = []
        self.busy = False
        self.generation = 0
        self.frame = 0
        self.closing = False
        self.inbox = queue.Queue(maxsize=8)
        self.results = queue.Queue()
        self.key = os.environ.get("OPENAI_API_KEY", "")
        self.model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
        local = Path(__file__).resolve().parent / ".local"
        local.mkdir(exist_ok=True)
        token_path = local / "pairing-code.txt"
        self.token = token_path.read_text().strip() if token_path.exists() else ""
        if len(self.token) != 48:
            self.token = secrets.token_hex(24)
            token_path.write_text(self.token)
        try:
            self.server = BridgeServer(self.token, self.inbox)
        except OSError:
            root.withdraw()
            messagebox.showerror("Pip is already running?", "Port 17373 is busy. Close the other Pip window and try again.")
            root.destroy()
            return
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        root.title("Pip Â· desktop companion")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg=TRANSPARENT)
        if os.name == "nt":
            root.wm_attributes("-transparentcolor", TRANSPARENT)
        root.geometry(f"190x205+{root.winfo_screenwidth()-235}+{root.winfo_screenheight()-295}")
        self.canvas = tk.Canvas(root, width=190, height=205, bg=TRANSPARENT, highlightthickness=0, cursor="hand2")
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self.drag_start)
        self.canvas.bind("<B1-Motion>", self.drag_move)
        self.canvas.bind("<ButtonRelease-1>", self.drag_end)
        self.canvas.bind("<Button-3>", self.context_menu)
        self.menu = tk.Menu(root, tearoff=False)
        self.menu.add_command(label="Chat with Pip", command=self.show_chat)
        self.menu.add_command(label="Settings & pairing", command=self.show_settings)
        self.menu.add_separator()
        self.menu.add_command(label="Quit Pip", command=self.quit)
        self.build_chat()
        root.after(50, self.animate)
        root.after(100, self.poll)
        root.after(350, self.show_chat)

    def button(self, parent, text, command, accent=False):
        return tk.Button(parent, text=text, command=command, bg=ACCENT if accent else PANEL,
                         fg=BG if accent else FG, activebackground="#d9ccff", relief="flat",
                         borderwidth=0, padx=12, pady=8, cursor="hand2", font=("Segoe UI", 10))

    def build_chat(self):
        self.chat = tk.Toplevel(self.root)
        self.chat.withdraw()
        self.chat.title("Pip Â· a little company")
        self.chat.geometry("460x620")
        self.chat.minsize(410, 480)
        self.chat.configure(bg=BG)
        self.chat.protocol("WM_DELETE_WINDOW", self.chat.withdraw)
        header = tk.Frame(self.chat, bg=BG)
        header.pack(fill="x", padx=20, pady=(18, 10))
        tk.Label(header, text="pip", font=("Segoe UI", 27, "bold"), bg=BG, fg=ACCENT).pack(side="left")
        self.button(header, "Settings", self.show_settings).pack(side="right")
        tk.Label(self.chat, text="A small friend for whatever you're reading.", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=20)
        self.page_label = tk.Label(self.chat, text="No page shared yet Â· click the browser extension",
                                   bg=PANEL, fg=MUTED, padx=12, pady=12, wraplength=390,
                                   justify="left", anchor="w", font=("Segoe UI", 10))
        self.page_label.pack(fill="x", padx=20, pady=14)
        self.transcript = scrolledtext.ScrolledText(self.chat, bg=BG, fg=FG, relief="flat", height=6,
                                                   wrap="word", font=("Segoe UI", 11), padx=4,
                                                   insertbackground=FG, state="disabled")
        self.transcript.pack(fill="both", expand=True, padx=16)
        self.transcript.tag_configure("pip", foreground=ACCENT, spacing1=10)
        self.transcript.tag_configure("you", foreground="#9ce9d7", spacing1=10)
        self.transcript.tag_configure("note", foreground=MUTED, spacing1=8)
        actions = tk.Frame(self.chat, bg=BG)
        actions.pack(fill="x", padx=20, pady=8)
        self.button(actions, "Summarise page", lambda: self.send("Summarise this page in three clear points.", True)).pack(side="left")
        self.button(actions, "Forget page & chat", self.forget).pack(side="right")
        compose = tk.Frame(self.chat, bg=BG)
        compose.pack(fill="x", padx=20, pady=(0, 8))
        self.question = tk.Entry(compose, bg=PANEL, fg=FG, insertbackground=FG, relief="flat", font=("Segoe UI", 11))
        self.question.pack(side="left", fill="x", expand=True, ipady=10)
        self.question.bind("<Return>", lambda _e: self.send())
        self.send_button = self.button(compose, "Send", self.send, True)
        self.send_button.pack(side="right", padx=(8, 0))
        self.status = tk.StringVar(value="Page stays local until you send an AI question.")
        tk.Label(self.chat, textvariable=self.status, bg=BG, fg=MUTED, wraplength=420,
                 font=("Segoe UI", 9), anchor="w").pack(fill="x", padx=20, pady=(0, 14))
        self.append("pip", "Hey, I'm Pip! Drag me somewhere cosy. Click me to chat, or right-click for my menu.\n\nShare a page with my browser extension, then ask me about it. Open Settings to pair the extension and add an API key.")

    def append(self, who, text):
        self.transcript.configure(state="normal")
        self.transcript.insert("end", ("You" if who == "you" else "Pip" if who == "pip" else "Info") + "\n", who)
        self.transcript.insert("end", text + "\n\n")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def show_chat(self):
        self.chat.deiconify()
        self.chat.lift()
        self.question.focus_set()

    def show_settings(self):
        if hasattr(self, "settings") and self.settings.winfo_exists():
            self.settings.lift()
            return
        win = self.settings = tk.Toplevel(self.root)
        win.title("Pip Â· settings & pairing")
        win.configure(bg=BG)
        win.geometry("500x590")
        win.resizable(False, False)
        def label(text):
            tk.Label(win, text=text, bg=BG, fg=FG, wraplength=450, justify="left",
                     font=("Segoe UI", 10)).pack(anchor="w", padx=24, pady=(16, 6))
        label("1. Pair your Chrome / Edge extension")
        label("Load the extension folder, open its popup, then paste this code. This is a local pairing code, not an API key.")
        code = tk.Entry(win, bg=PANEL, fg=ACCENT, relief="flat", font=("Consolas", 10))
        code.insert(0, self.token)
        code.configure(state="readonly", readonlybackground=PANEL)
        code.pack(fill="x", padx=24, ipady=8)
        def copy():
            self.root.clipboard_clear()
            self.root.clipboard_append(self.token)
            copied.configure(text="Copied pairing code")
        copied = self.button(win, "Copy pairing code", copy)
        copied.pack(anchor="w", padx=24, pady=6)
        label("2. OpenAI API key (kept in memory for this session)")
        key = tk.Entry(win, show="*", bg=PANEL, fg=FG, insertbackground=FG, relief="flat")
        key.insert(0, self.key)
        key.pack(fill="x", padx=24, ipady=8)
        label("Model")
        model = tk.Entry(win, bg=PANEL, fg=FG, insertbackground=FG, relief="flat")
        model.insert(0, self.model)
        model.pack(fill="x", padx=24, ipady=8)
        label("Sending a question sends the shared page text and recent chat to OpenAI. API usage may incur charges. No page content or chat is saved to disk.")
        def save():
            self.key = key.get().strip()
            self.model = model.get().strip() or DEFAULT_MODEL
            win.destroy()
            self.status.set("AI ready." if self.key else "Preview mode Â· add an API key to chat.")
        self.button(win, "Save for this session", save, True).pack(anchor="e", padx=24, pady=12)

    def send(self, text=None, needs_page=False):
        if self.busy:
            return
        if needs_page and not self.page:
            self.append("note", "Share a page using the browser extension first.")
            return
        question = (text if text is not None else self.question.get()).strip()[:4000]
        if not question:
            return
        if not self.key:
            self.append("note", "The character and page sharing work without a key. Add an OpenAI API key in Settings to enable AI replies.")
            self.show_settings()
            return
        if text is None:
            self.question.delete(0, "end")
        self.append("you", question)
        self.busy = True
        self.send_button.configure(state="disabled")
        self.status.set("Pip is thinkingâ€¦")
        generation = self.generation
        key, model, page, history = self.key, self.model, self.page, list(self.history)
        def work():
            try:
                reply = ask(key, model, page, history, question)
                self.results.put((generation, question, reply, None))
            except Exception as error:
                self.results.put((generation, question, None, str(error)))
        threading.Thread(target=work, daemon=True).start()

    def clear_chat(self):
        self.generation += 1  # Discard any reply already in flight for an old page.
        self.history.clear()
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        self.transcript.configure(state="disabled")

    def forget(self):
        self.page = None
        self.clear_chat()
        self.page_label.configure(text="No page shared Â· the previous snapshot was cleared")
        self.append("pip", "Fresh start! I've cleared the page and our chat from this app. Any AI request already sent cannot be recalled.")

    def poll(self):
        if self.closing:
            return
        try:
            while True:
                page = self.inbox.get_nowait()
                self.page = page
                self.clear_chat()
                self.page_label.configure(text=f"SHARED {time.strftime('%H:%M')} Â· {page['title']}\n{page['url'][:80]}\n{len(page['text']):,} characters Â· snapshot")
                self.append("pip", "Got it! " + ("What would you like to know about this page?" if page["text"].strip() else "I couldn't find readable text here. This may be a canvas, PDF, or image-based page."))
                self.show_chat()
        except queue.Empty:
            pass
        try:
            while True:
                generation, question, reply, error = self.results.get_nowait()
                self.busy = False
                self.send_button.configure(state="normal")
                self.status.set("Page stays local until you send an AI question.")
                if generation == self.generation:
                    if error:
                        self.append("note", error)
                    else:
                        self.history.extend([{"role": "user", "content": question}, {"role": "assistant", "content": reply}])
                        self.history = self.history[-12:]
                        self.append("pip", reply)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def drag_start(self, event):
        self.drag = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())
        self.moved = False

    def drag_move(self, event):
        x, y, wx, wy = self.drag
        dx, dy = event.x_root-x, event.y_root-y
        if abs(dx) + abs(dy) > 5:
            self.moved = True
        self.root.geometry(f"+{max(0, wx+dx)}+{max(0, wy+dy)}")

    def drag_end(self, _event):
        if not self.moved:
            self.show_chat()

    def context_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def animate(self):
        if self.closing:
            return
        self.frame += 1
        c = self.canvas
        c.delete("all")
        bob = math.sin(self.frame / 12) * 4
        c.create_oval(42, 166, 150, 181, fill="#343247", outline="")
        c.create_oval(57, 135+bob, 87, 173+bob, fill="#a98adb", outline="#685481", width=2)
        c.create_oval(108, 135+bob, 138, 173+bob, fill="#a98adb", outline="#685481", width=2)
        c.create_oval(26, 99+bob, 60, 128+bob, fill=ACCENT, outline="#685481", width=2)
        c.create_oval(132, 94+bob, 165, 122+bob, fill=ACCENT, outline="#685481", width=2)
        c.create_oval(48, 32+bob, 144, 157+bob, fill=ACCENT, outline="#685481", width=3)
        c.create_oval(61, 45+bob, 88, 65+bob, fill="#decfff", outline="")
        c.create_line(95, 35+bob, 99, 20+bob, 110, 17+bob, fill="#685481", width=3, smooth=True)
        blink = self.frame % 100 in (0, 1, 2)
        for x in (77, 114):
            if blink:
                c.create_line(x-4, 86+bob, x+4, 86+bob, fill=BG, width=3)
            else:
                c.create_oval(x-4, 78+bob, x+4, 92+bob, fill=BG, outline="")
                c.create_oval(x-2, 80+bob, x, 83+bob, fill="white", outline="")
        c.create_oval(60, 95+bob, 76, 103+bob, fill="#e8a9cc", outline="")
        c.create_oval(116, 95+bob, 132, 103+bob, fill="#e8a9cc", outline="")
        if self.busy:
            c.create_oval(91, 105+bob, 101, 116+bob, fill=BG, outline="")
        else:
            c.create_arc(83, 97+bob, 109, 116+bob, start=195, extent=150, style="arc", outline=BG, width=3)
        c.create_text(95, 194, text="thinkingâ€¦" if self.busy else "pip Â· click to chat", fill="#b9a0eb", font=("Segoe UI", 9, "bold"))
        self.root.after(50, self.animate)

    def quit(self):
        self.closing = True
        threading.Thread(target=self.server.shutdown, daemon=True).start()
        self.server.server_close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    try:
        Pip(root)
        root.mainloop()
    except Exception as error:
        messagebox.showerror("Pip couldn't start", str(error))
        raise

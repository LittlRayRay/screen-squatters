"""Controlled desktop integration check. No live API calls or user screen captures."""
import base64
import os
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai import Turn
from desktop import ScreenSquatters
from games import Mafia
from screen import _libraries, capture_window

temporary = tempfile.TemporaryDirectory()
root = tk.Tk()
app = ScreenSquatters(root, data_dir=temporary.name, port=0, timers=False)
app.key = "test-only"

def pump():
    for _ in range(12):
        root.update()
        app.poll(reschedule=False)
        time.sleep(.02)

try:
    pump()
    assert app.question.winfo_viewable()
    assert app.question.winfo_rooty() + app.question.winfo_height() <= root.winfo_rooty() + root.winfo_height()
    assert app.send_button.winfo_viewable()
    for name in app.cards:
        assert app.cards[name]['toggle'].winfo_viewable()
    for name in app.house.agents:
        app.toggle(name)
    pump()
    assert len(app.awake()) == 3
    assert all(win.winfo_viewable() for win, _canvas in app.floaters.values())
    locations = [(win.winfo_x(), win.winfo_y()) for win, _ in app.floaters.values()]
    assert len(set(locations)) == 3, f"Floating characters overlap at startup: {locations}"
    app.inbox.put({"title": "Controlled test", "url": "https://example.com/", "text": "A test page.", "automatic": False})
    pump()
    assert "Controlled test" in app.context_status.get()
    with patch("desktop.companion_turn", return_value=Turn(speech="B-but I thought the moon was cheese!", used=500, memories=[{"target": "Byte", "text": "Pip thinks the moon is cheese."}])):
        app.request_turn("Pip", "Hang out")
        pump()
    assert app.house.agents["Pip"]["used"] == 500
    assert app.house.agents["Byte"]["memories"][0]["from"] == "Pip"
    assert "moon was cheese" in app.transcript.get("1.0", "end")
    app.start_ttt("You", "Byte")
    app.game_action(0)
    with patch("desktop.companion_turn", return_value=Turn(speech="Centre square, obviously.", used=400, move=4)):
        app.request_turn("Byte", "Play")
        pump()
    assert app.game.board[4] == "O"
    app.cancel_game()
    app.start_mafia()
    assert isinstance(app.game, Mafia)
    app.game_action()  # User passes discussion.
    with patch("desktop.companion_turn", return_value=Turn(speech="I trust nobody.", used=400)):
        app.request_turn("Pip", "Discuss")
        pump()
    assert "Pip" in app.game.spoken
    app.cancel_game()
    app.show_settings()
    pump()
    assert app.settings.winfo_viewable()
    app.settings.destroy()
    # Test native PNG capture ONLY if our controlled test window is foreground.
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes as wt
        root.lift()
        root.focus_force()
        pump()
        user, _gdi, _kernel = _libraries()
        hwnd = user.GetForegroundWindow()
        pid = wt.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == os.getpid():
            snapshot = capture_window({"hwnd": hwnd, "title": "Controlled test window"})
            assert base64.b64decode(snapshot["image"].split(",", 1)[1]).startswith(b"\x89PNG")
            print("Controlled native capture passed.")
        else:
            print("Native capture skipped: Windows kept another app foreground; no screenshot taken.")
    app.sleep_all()
    assert not app.awake()
    assert all(not win.winfo_viewable() for win, _canvas in app.floaters.values())
    old_generation = app.generation
    with patch("desktop.messagebox.askyesno", return_value=True):
        app.reset_all()
    assert app.generation > old_generation
    assert not app.house.agents["Byte"]["memories"]
    assert app.house.agents["Pip"]["used"] == 0
    app.handle_turn(old_generation, 0, "Pip", Turn(speech="STALE REPLY", used=500))
    assert "STALE REPLY" not in app.transcript.get("1.0", "end")
    assert app.house.agents["Pip"]["used"] == 0
    print("UI smoke passed: home/composer, three floating characters, page reception, cross-agent memory, charged AI turns, tic-tac-toe, Mafia, settings, sleep, reset and stale-reply isolation.")
finally:
    app.quit()
    temporary.cleanup()

"""Creates the actual Tk windows, exercises UI state, then closes them."""
from pathlib import Path
import sys
import time
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop import Pip

root = tk.Tk()
app = Pip(root)

def pump():
    for _ in range(12):
        root.update()
        time.sleep(.03)

try:
    pump()
    assert app.chat.winfo_viewable()
    # Catch pack-layout overflow, particularly with Windows display scaling.
    assert app.question.winfo_viewable()
    assert app.question.winfo_rooty() + app.question.winfo_height() <= app.chat.winfo_rooty() + app.chat.winfo_height()
    assert app.send_button.winfo_viewable()
    app.inbox.put({"title": "Smoke test article", "url": "https://example.com/", "text": "The moon orbits Earth."})
    pump()
    assert "Smoke test article" in app.page_label.cget("text")
    app.show_settings()
    pump()
    assert app.settings.winfo_viewable()
    app.settings.destroy()
    app.key = "test-only"
    with patch("desktop.ask", return_value="The moon orbits Earth."):
        app.send("What does the moon orbit?")
        pump()
    assert "The moon orbits Earth." in app.transcript.get("1.0", "end")
    assert len(app.history) == 2
    app.forget()
    assert app.page is None and not app.history
    # Replies arriving after forgetting cannot repopulate the transcript.
    app.results.put((app.generation - 1, "old question", "STALE REPLY", None))
    pump()
    assert "STALE REPLY" not in app.transcript.get("1.0", "end")
    print("UI smoke passed: window, animation, page reception, settings, mocked AI reply, forget, stale reply.")
finally:
    app.quit()

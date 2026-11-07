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
    assert root.overrideredirect()
    assert not app.chat.winfo_viewable(), "Only the house should open at launch"
    assert not app.habitat.open
    app.habitat.tap(180, 200)
    assert app.habitat.open
    app.habitat.tap(85, 160)
    assert app.house.agents['Pip']['awake']
    app.show_chat()
    pump()
    assert app.question.winfo_viewable()
    assert app.question.winfo_rooty() + app.question.winfo_height() <= app.chat.winfo_rooty() + app.chat.winfo_height()
    assert app.send_button.winfo_viewable()
    for name in app.house.agents:
        if not app.house.agents[name]['awake']:
            app.toggle(name)
    pump()
    assert len(app.awake()) == 3
    assert all(win.winfo_viewable() for win, _canvas in app.floaters.values())
    locations = [(win.winfo_x(), win.winfo_y()) for win, _ in app.floaters.values()]
    assert len(set(locations)) == 3, f"Floating characters overlap at startup: {locations}"
    app.inbox.put({"title": "Controlled test", "url": "https://example.com/", "text": "A test page.", "automatic": False})
    pump()
    assert "Controlled test" in app.context_status.get()
    session = '11111111-1111-4111-8111-111111111111'
    app.inbox.put({'title':'Firefox live','url':'https://example.com/','text':'Latest page',
                   'automatic':True,'session_id':session,'sequence':1})
    pump()
    app.observation = {'kind':'page','title':'Firefox live'}
    app.inbox.put({'kind':'browser-state','state':'paused','session_id':session,'sequence':3})
    app.inbox.put({'title':'Delayed page','url':'https://example.com/','text':'Old page',
                   'automatic':True,'session_id':session,'sequence':2})
    pump()
    assert app.page is None and app.observation is None, 'Pausing clears context and rejects late page updates'
    with patch("desktop.companion_turn", return_value=Turn(speech="B-but I thought the moon was cheese!", used=500, memories=[{"target": "Byte", "text": "Pip thinks the moon is cheese."}])):
        app.request_turn("Pip", "Hang out")
        pump()
    assert app.house.agents["Pip"]["used"] == 500
    assert app.house.agents["Byte"]["memories"][0]["from"] == "Pip"
    assert "moon was cheese" in app.transcript.get("1.0", "end")
    # Freeze translations without disabling chat, wake/sleep or manual placement.
    app.stand_still.set(True)
    app.stand_still_changed()
    positions = [(r.x,r.y) for r in app.world.residents.values()]
    for i in range(20):
        app.world.step(.1, time.monotonic()+i)
    assert positions == [(r.x,r.y) for r in app.world.residents.values()]
    # Movie invitations are local commands and work even before an API key is set.
    app.key = ''
    app.question.insert(0, 'Everybody watch something with me')
    app.send()
    pump()
    assert app.movie_mode.get() and app.world.movie_enabled
    assert all(r.mode == 'seated' for r in app.world.residents.values())
    assert len(set((r.x,r.y) for r in app.world.residents.values())) == 3
    assert not app.screen_enabled.get(), 'Movie mode must not silently enable screenshots'
    before = [(r.x,r.y) for r in app.world.residents.values()]
    app.apply_intent('Pip', Turn(activity='wander'))
    assert before == [(r.x,r.y) for r in app.world.residents.values()]
    # Movie capture prefers a frame to browser controls, while existing capture consent is on.
    browser = {'hwnd': 123, 'browser': True, 'title': 'Controlled test - Chrome', 'bounds':[0,0,800,600]}
    app.screen_enabled.set(True)
    with patch('desktop.foreground', return_value=browser), patch('desktop.capture_window', return_value={'kind':'image','title':'Controlled film frame','image':'data:image/png;base64,YWJj','bounds':[0,0,800,600]}) as screenshot:
        app.capture_tick()
        pump()
    assert screenshot.called
    assert app.observation['kind'] == 'image'
    assert app.movie_source_window == 123
    app.last_capture = app.last_image = 0
    with patch('desktop.foreground', return_value={**browser,'hwnd':456,'title':'A different app'}), patch('desktop.capture_window') as unrelated:
        app.capture_tick()
        pump()
    unrelated.assert_not_called()
    assert app.current_observation() is None
    app.key = 'test-only'
    app.next_turn = 0
    with patch.object(app.root, 'after'), patch.object(app, 'capture_tick'), patch.object(app, 'request_turn') as inferred:
        app.tick()
    inferred.assert_not_called()
    app.screen_enabled.set(False)
    app.question.insert(0, 'Stop movie mode')
    app.send()
    assert not app.movie_mode.get()
    app.stand_still.set(False)
    app.stand_still_changed()
    app.key = 'test-only'
    # A model-selected target moves the body beside the current observed window.
    app.intent_contexts['Pip'] = ({'kind':'image','window_id':123,'bounds':[0,0,800,600]}, time.monotonic())
    with patch('desktop.foreground', return_value={'hwnd':123,'bounds':[0,0,800,600]}):
        app.apply_intent('Pip', Turn(speech='Look at that!', activity='inspect', interest={'x':.5,'y':.5,'label':'A test drawing'}))
    assert app.world.residents['Pip'].mode == 'approaching'
    assert app.world.residents['Pip'].gaze == (400,300)
    with patch('desktop.foreground', return_value={'hwnd':456,'bounds':[0,0,800,600]}):
        app.validate_interests()
    assert app.world.residents['Pip'].interest is None
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
    notebook = app.settings.winfo_children()[0]
    notebook.select(1)
    pump()
    for name in app.cards:
        toggle = app.cards[name]['toggle']
        assert toggle.winfo_viewable()
        assert toggle.winfo_rooty()+toggle.winfo_height() <= app.settings.winfo_rooty()+app.settings.winfo_height()
    app.settings.destroy()
    # Test native PNG capture ONLY if our controlled test window is foreground.
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes as wt
        app.show_chat()
        app.chat.focus_force()
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
    assert app.world.paused
    for i in range(300):
        app.world.step(.15, time.monotonic()+i*.15, autonomous=False)
    pump()
    assert all(not win.winfo_viewable() for win, _canvas in app.floaters.values())
    # Only actual sleep inside the house repays local energy, never a pending turn.
    app.house.agents['Pip']['used'] = 1000
    app.world.residents['Pip'].blocked = True
    app.world.residents['Pip'].wake_threshold = 19500
    app.set_recovery_rate(600)
    app.previous_sleepers = {'Pip'}
    app.last_recovery_tick = 100
    app.last_recovery_save = 100
    app.recover_sleep_tick(160)
    assert app.house.agents['Pip']['used'] == 400
    assert not app.world.residents['Pip'].blocked
    old_generation = app.generation
    with patch("desktop.messagebox.askyesno", return_value=True):
        app.reset_all()
    assert app.generation > old_generation
    assert not app.house.agents["Byte"]["memories"]
    assert app.house.agents["Pip"]["used"] == 0
    app.handle_turn(old_generation, 0, "Pip", Turn(speech="STALE REPLY", used=500))
    assert "STALE REPLY" not in app.transcript.get("1.0", "end")
    assert app.house.agents["Pip"]["used"] == 0
    print("UI smoke passed: house/cutaway, sleep recovery, stand still, chat movie invite, seated companions, movie frame capture, screen interests, shared memory, games, pause and reset.")
finally:
    app.quit()
    temporary.cleanup()

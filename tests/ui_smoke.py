"""Controlled desktop integration check. No live API calls or user screen captures."""
import base64
import os
from pathlib import Path
import sys
import tempfile
import time
import threading
from types import SimpleNamespace
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai import Turn
from desktop import ScreenSquatters
from games import Mafia, Debate
from poker import Poker
from house import CHARACTERS
from screen import _libraries, capture_window

temporary = tempfile.TemporaryDirectory()
root = tk.Tk()
app = ScreenSquatters(root, data_dir=temporary.name, port=0, timers=False)
app.key = "test-only"
app.house.options["window_awareness"] = False
app.house.options.update(game_deliberation=False,game_invites=False,autoplay_games=False,screen_comments=False)
app.windows.backend.set_monitoring(False)

def pump():
    for _ in range(12):
        root.update()
        app.poll(reschedule=False)
        time.sleep(.02)

def finish_speech():
    if app.deliveries:
        app.dialogue_tick(max(item['line'].end for item in app.deliveries)+.1)

try:
    pump()
    assert root.overrideredirect()
    assert not app.chat.winfo_viewable(), "Only the house should open at launch"
    assert not app.habitat.open
    assert root.winfo_width() == 160, 'The closed house should be compact'
    app.habitat.tap(180, 200)
    assert app.habitat.open
    pump()
    assert root.winfo_width() == 360, 'Clicking expands the house'
    app.habitat.tap(85, 160)
    assert app.house.agents['Burt']['awake']
    app.show_chat()
    pump()
    assert app.question.winfo_viewable()
    assert app.question.winfo_rooty() + app.question.winfo_height() <= app.chat.winfo_rooty() + app.chat.winfo_height()
    assert app.send_button.winfo_viewable()
    for name in app.house.agents:
        if not app.house.agents[name]['awake']:
            app.toggle(name)
    pump()
    assert len(app.awake()) == len(CHARACTERS)
    assert all(win.winfo_viewable() for win, _canvas in app.floaters.values())
    locations = [(win.winfo_x(), win.winfo_y()) for win, _ in app.floaters.values()]
    assert len(set(locations)) == len(CHARACTERS), f"Floating characters overlap at startup: {locations}"
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
    with patch("desktop.companion_turn", return_value=Turn(speech="B-but I thought the moon was cheese!", used=500, memories=[{"target": "Cody", "text": "Burt thinks the moon is cheese."}])):
        app.request_turn("Burt", "Hang out")
        pump()
    assert app.house.agents["Burt"]["used"] == 500
    assert app.house.agents["Cody"]["memories"][0]["from"] == "Burt"
    app.append('Burt','Wait, the player is here.')
    assert 'Wait, the player is here.' not in app.transcript.get('1.0','end'), 'Fresh speech begins with a typing pause'
    app.append('You','I am listening.')
    finish_speech()
    assert "moon was cheese" in app.transcript.get("1.0", "end")
    transcript = app.transcript.get('1.0','end')
    assert transcript.index('moon was cheese') < transcript.index('I am listening.'), 'Typewriter text must stay with its original message'
    assert transcript.index('Wait, the player is here.') < transcript.index('I am listening.')
    # A player message is accepted during inference and takes priority over the old ambient reply.
    release = threading.Event()
    def delayed_turn(*_args):
        release.wait(5)
        return Turn(speech='STALE AMBIENT REPLY',used=30)
    with patch('desktop.companion_turn',side_effect=delayed_turn):
        app.request_turn('Burt','Ambient conversation')
        app.show_chat('Cody')
        app.question.insert(0,'Cody, what do you think?')
        app.send()
        assert list(app.pending) == ['Cody'] and app.busy
        assert app.send_button.cget('state') == 'normal'
        release.set()
        pump()
    assert 'STALE AMBIENT REPLY' not in app.transcript.get('1.0','end')
    def player_reply(*args):
        assert args[6].startswith('PLAYER_MESSAGE')
        assert args[4][-1]['text'] == 'Cody, what do you think?'
        return Turn(speech='Oh! I think we should try it.',used=40)
    app.next_turn = 0
    with patch('desktop.companion_turn',side_effect=player_reply):
        with patch.object(app.root,'after'),patch.object(app,'capture_tick'):
            app.tick()
        pump()
    finish_speech()
    assert 'I think we should try it' in app.transcript.get('1.0','end')
    pickup = SimpleNamespace(x_root=300,y_root=300)
    app.world.residents['Victoria'].spin = 130
    app.drag_start(pickup,'Victoria')
    assert app.world.residents['Victoria'].picked_up and app.world.residents['Victoria'].spin == 0
    app.drag_end(pickup,'Victoria')
    assert not app.world.residents['Victoria'].picked_up
    # Local permitted-window gestures survive normal foreground checks and stop on revocation.
    from test_desktop_world import record
    from window_world import clean_rule
    app.windows.update([record()])
    target = next(iter(app.windows.windows))
    app.windows.overrides[target] = clean_rule({'control':'nudge'})
    app.house.options['window_control'] = True
    app.house.options['window_awareness'] = True
    app.last_mischief = 0
    app.busy = True
    with patch.object(app.windows,'play',return_value=target),patch.object(app.world.rng,'choice',return_value='Cody'):
        app.scene_tick(time.monotonic())
    app.busy = False
    with patch('desktop.foreground',return_value=None):
        app.validate_interests()
    assert app.world.residents['Cody'].interest is not None
    app.windows.overrides[target] = clean_rule({'observe':'ignore'})
    app.validate_interests()
    assert app.world.residents['Cody'].interest is None
    app.house.options['window_control'] = False
    app.house.options['window_awareness'] = False
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
    assert len(set((r.x,r.y) for r in app.world.residents.values())) == len(CHARACTERS)
    assert not app.screen_enabled.get(), 'Movie mode must not silently enable screenshots'
    before = [(r.x,r.y) for r in app.world.residents.values()]
    app.apply_intent('Burt', Turn(activity='wander'))
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
    app.intent_contexts['Burt'] = ({'kind':'image','window_id':123,'bounds':[0,0,800,600]}, time.monotonic())
    with patch('desktop.foreground', return_value={'hwnd':123,'bounds':[0,0,800,600]}):
        app.apply_intent('Burt', Turn(speech='Look at that!', activity='inspect', interest={'x':.5,'y':.5,'label':'A test drawing'}))
    assert app.world.residents['Burt'].mode == 'approaching'
    assert app.world.residents['Burt'].gaze == (400,300)
    with patch('desktop.foreground', return_value={'hwnd':456,'bounds':[0,0,800,600]}):
        app.validate_interests()
    assert app.world.residents['Burt'].interest is None
    app.start_ttt("You", "Cody")
    app.game_action(0)
    with patch("desktop.companion_turn", return_value=Turn(speech="Centre square, obviously.", used=400, move=4)):
        app.request_turn("Cody", "Play")
        pump()
    assert app.game.board[4] == "O"
    finish_speech()
    app.cancel_game()
    app.start_mafia()
    assert isinstance(app.game, Mafia)
    app.game_action()  # User passes discussion.
    with patch("desktop.companion_turn", return_value=Turn(speech="I trust nobody.", used=400)):
        app.request_turn("Burt", "Discuss")
        pump()
    assert "Burt" in app.game.spoken
    finish_speech()
    previous_mood = app.social.moods['Burt']
    app.game.mafia,app.game.phase = 'Burt','night'
    with patch('desktop.companion_turn',return_value=Turn(speech='PRIVATE NIGHT SPEECH',emotion='angry',vote='You',used=1)):
        app.request_turn('Burt','Secret night action')
        pump()
    assert app.social.moods['Burt'] == previous_mood, 'Private Mafia actions must not leak through public mood animations'
    assert 'PRIVATE NIGHT SPEECH' not in app.transcript.get('1.0','end')
    app.cancel_game()
    # Poker uses the shared table, private hands, voluntary reveals and paced AI turns.
    app.start_poker()
    pump()
    assert isinstance(app.game,Poker) and app.poker_table is not None
    assert all(not win.winfo_viewable() for win,_ in app.floaters.values()), 'Housemates sit at the table instead of appearing twice'
    with patch('desktop.companion_turn',return_value=Turn(speech='Fine, I call.',used=100,poker_action='call',reveal_cards=True)):
        app.request_turn('Victoria','Play poker')
        pump()
    assert app.game.actor == 'Mika'
    finish_speech()
    with patch('desktop.companion_turn',return_value=Turn(used=100,poker_action='call')):
        app.request_turn('Mika','Play poker')
        pump()
    assert app.game.actor == 'You'
    assert app.game.view('Burt')['shown_cards'] == {'Victoria':app.game.hands['Victoria']}
    assert not app.busy, 'Poker AI turn finishes before the user acts'
    app.poker_table.reveal_on_action.set(True)
    app.poker_table.action('call')
    assert 'You' in app.game.revealed
    finish_speech()
    before_bet = app.game.current_bet
    app.show_chat('Burt')
    app.question.insert(0,'Burt, are you enjoying this?')
    app.send()
    app.next_turn = 0
    with patch('desktop.companion_turn',return_value=Turn(speech='Umm, yes! I think so.',used=20,poker_action='raise',reveal_cards=True)):
        with patch.object(app.root,'after'),patch.object(app,'capture_tick'):
            app.tick()
        pump()
    finish_speech()
    assert app.game.actor == 'Burt' and app.game.current_bet == before_bet, 'A direct poker chat reply must not submit a betting action'
    assert 'Burt' in app.game.revealed, 'A voluntary reveal in poker chat is allowed without betting'
    with patch('desktop.companion_turn',return_value=Turn(used=100,poker_action='invalid',reveal_cards=False)):
        app.request_turn('Burt','Play poker')
        pump()
    assert app.game.actor == 'Cody', 'An invalid model action uses a safe legal fallback'
    assert 'Burt' in app.game.revealed
    for widget in app.game_window.winfo_children():
        assert widget.winfo_viewable(), 'Poker controls must be visible'
        assert widget.winfo_rooty()+widget.winfo_height() <= app.game_window.winfo_rooty()+app.game_window.winfo_height()+1, 'Poker controls must fit in the window'
    while not app.game.result:
        actor = app.game.actor
        legal = app.game.legal_actions(actor)
        app.game.act(actor,'check' if 'check' in legal else 'call')
    app.render_game()
    dealer = app.game.dealer
    app.next_poker_hand()
    assert app.game.dealer == (dealer+1)%len(app.game.players) and not app.game.revealed
    app.cancel_game()
    pump()
    assert app.poker_table is None
    assert all(win.winfo_viewable() for win,_ in app.floaters.values())
    # Housemate-only poker exposes no private cards and the player can join the next hand.
    app.house.options['game_invites'] = True
    app.offer_game('Cody','Poker')
    assert app.invitation and app.invite_window.winfo_exists()
    app.accept_invitation(False)
    pump()
    assert 'You' not in app.game.players and len(app.game.players)==4
    assert not app.poker_table.show.winfo_viewable() and app.poker_table.join.winfo_viewable()
    while not app.game.result:
        actor = app.game.actor
        app.game.act(actor,'check' if 'check' in app.game.legal_actions(actor) else 'call')
    app.render_game()
    app.request_join_game()
    app.scene_tick(time.monotonic())
    assert 'You' in app.game.players and len(app.game.players)==5
    app.cancel_game()
    finish_speech()
    app.house.options['game_deliberation'] = True
    app.last_deliberation = -1e9
    with patch('desktop.occasional_refusal',return_value='Victoria'):
        app.start_poker()
    pump()
    assert 'Victoria' not in app.game.players
    assert app.floaters['Victoria'][0].winfo_viewable(), 'A friend who sits out stays on the desktop'
    app.cancel_game()
    app.house.options.update(game_deliberation=False,game_invites=False)
    finish_speech()
    app.house.options.update(game_invites=True,autoplay_games=True)
    app.offer_game('Cody','Tic-tac-toe')
    app.invitation['deadline'] = time.monotonic()-1
    app.scene_tick(time.monotonic())
    assert app.game and 'You' not in app.game.players and app.autonomous_game
    assert app.invitation is None
    app.cancel_game()
    app.house.options.update(game_invites=False,autoplay_games=False)
    finish_speech()
    app.house.options['screen_comments'] = True
    previous = app.transcript.get('1.0','end')
    app.attention.add({'event':'tab-opened','event_id':'fixture-open','source':'browser'})
    app.attention.add({'event':'tab-closed','event_id':'fixture-close','source':'browser'})
    app.scene_tick(time.monotonic()+5)
    assert not app.attention.pending
    finish_speech()
    assert app.transcript.get('1.0','end') == previous, 'Screen changes must never append canned event-log dialogue'
    app.house.options['screen_comments'] = False
    # Games still run after the local chat allowance is spent, and record separate usage.
    app.house.agents['Burt']['used'] = app.house.agents['Burt']['limit']
    app.house.sleep('Burt')
    app.world.rest('Burt',time.monotonic(),immediate=True)
    app.start_ttt('You','Burt')
    assert app.house.agents['Burt']['awake']
    app.game_action(0)
    def unlimited_turn(*args):
        assert args[7] is None, 'Game calls must bypass the local remaining-token allowance'
        return Turn(used=30000,move=4)
    with patch('desktop.companion_turn',side_effect=unlimited_turn):
        app.request_turn('Burt','Play past local allowance')
        pump()
    assert app.game.board[4] == 'O'
    assert app.house.agents['Burt']['used'] == app.house.agents['Burt']['limit']
    assert app.house.agents['Burt']['game_used'] >= 30000
    app.cancel_game()
    assert not app.house.agents['Burt']['awake'], 'Chat limits resume after leaving the game'
    with patch('desktop.simpledialog.askstring',return_value='Should we plant a garden?'):
        app.start_debate()
    assert isinstance(app.game,Debate) and len(app.game.players) == 5
    app.show_chat()
    assert app.recipient.get() == 'Everyone'
    app.question.insert(0,'I think we should grow vegetables.')
    app.send()
    assert app.game.actor == 'Burt'
    with patch('desktop.companion_turn',return_value=Turn(speech='Umm, what vegetables?',used=100)):
        app.request_turn('Burt','Debate')
        pump()
    assert app.game.actor == 'Cody'
    finish_speech()
    app.cancel_game()
    app.house.recharge('Burt',20000)
    app.toggle('Burt')
    app.show_chat('Mika')
    app.question.insert(0,'Hello, Mika.')
    app.send()
    assert list(app.pending) == ['Mika']
    app.pending.clear()
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
    notebook.select(3)
    pump()
    assert notebook.tab(3,'text') == 'Windows'
    notebook.select(4)
    pump()
    assert notebook.tab(4,'text') == 'Social & physics'
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
    app.house.agents['Burt']['used'] = 1000
    app.world.residents['Burt'].blocked = True
    app.world.residents['Burt'].wake_threshold = 19500
    app.set_recovery_rate(600)
    app.previous_sleepers = {'Burt'}
    app.last_recovery_tick = 100
    app.last_recovery_save = 100
    app.recover_sleep_tick(160)
    assert app.house.agents['Burt']['used'] == 400
    assert not app.world.residents['Burt'].blocked
    old_generation = app.generation
    with patch("desktop.messagebox.askyesno", return_value=True):
        app.reset_all()
    assert app.generation > old_generation
    assert not app.house.agents["Cody"]["memories"]
    assert app.house.agents["Burt"]["used"] == 0
    app.handle_turn(old_generation, 0, "Burt", Turn(speech="STALE REPLY", used=500))
    assert "STALE REPLY" not in app.transcript.get("1.0", "end")
    assert app.house.agents["Burt"]["used"] == 0
    print("UI smoke passed: player interruption priority, non-betting poker chat, spectator joining, sit-outs, screen reactions, permitted-window gestures/revocation, pickup states, renamed housemates, games, settings and reset.")
finally:
    app.quit()
    temporary.cleanup()

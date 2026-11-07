"""Offline judges' showcase. Real companion UI/physics/games, labelled staged dialogue.

Run with launch_demo.cmd. Uses a temporary house and only moves its own prop windows.
No Gemini requests, personal window enumeration, or screen captures are performed.
"""
import argparse
from copy import deepcopy
import random
import tempfile
import time
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from ai import Turn
from cinema import movie_comment_fallback
from desktop import ScreenSquatters, BG, PANEL, FG, MUTED, ACCENT
from games import TicTacToe, Mafia, Debate
from house import CHARACTERS, House
from poker import Poker
from social import Social
from window_world import WindowWorld, chaos_options


CHAPTERS = [
    ('A tiny home', 'Click the house to peel back the front wall. Each room belongs to a different housemate.', 12),
    ('Meet the housemates', 'Four distinct personalities, animated accessories, expressions, typing dots and natural speech bubbles.', 25),
    ('Friends, not assistants', 'Group chat, direct replies and shared memories. Type into the real chat; offline replies are intentionally scripted.', 26),
    ('Pick up, throw, bounce', 'Drag a housemate, then let go. Gravity, collisions, pickup faces and upright recovery use the real physics engine.', 23),
    ('A page catches their eye', 'A staged Firefox-style page feed supplies title, text, headings and a visible target. No screenshot or real browser is read.', 24),
    ('Window mischief', 'The real permission controller animates two demo-owned windows. Watch the housemates undo each other’s decorating. Try Undo or Pause.', 30),
    ('A tiny disagreement', 'Personality, moods and a harmless cartoon squabble. They can disagree and then make up.', 20),
    ('Tic-tac-toe', 'Cody invites you to play. Join, spectate, or decline. Real legal moves, wins and draws; disable Player autopilot to take your own turns.', 32),
    ('Poker night', 'Real fixed-limit Texas hold’em: hidden hands, betting, community cards, showdown and optional reveals. Quiet, quick banter.', 40),
    ('Mafia after dark', 'Real hidden roles, discussion, voting and private night actions. The offline player sees only their own game view.', 30),
    ('Debate club', 'Everyone has a turn and a different point of view. Switch off Player autopilot and add your own argument in group chat.', 30),
    ('Movie mode', 'Chairs, popcorn and focused company. This demo uses staged captions and an accelerated comment interval; the normal app uses 35 seconds.', 30),
    ('Rest and recharge', 'The local allowance sends an exhausted housemate home. Sleep gradually reduces usage at the user’s adjustable recovery rate.', 25),
    ('Your house, your rules', 'Explore the actual settings: window permissions, Chaos/Pause/Undo, physics, autonomous life, recovery, memory and factory reset.', 0),
]

INTRO = {
    'Burt': 'Umm, hello. I live in that room. I think. Wait, yes, that one.',
    'Cody': 'Hi! Four people and one house. That is almost one house each!',
    'Victoria': 'Victoria. I shall be handling the standards around here.',
    'Mika': 'Come in. There’s room for you too. I’ll put the tea on.',
}
DEBATE_LINES = {
    'Burt': 'Umm, if the popcorn is shared, can I have the bits nobody wants?',
    'Cody': 'Separate bowls! Then we can share our separate bowls. Wait.',
    'Victoria': 'One bowl, provided certain people learn to take a reasonable handful.',
    'Mika': 'A little bowl each, and a big one for refills. Everyone gets some.',
}


def demo_turn(name, trigger, conversation, game=None, movie=False):
    """Deterministic stand-in for generation; never makes a network request."""
    if game and game.get('game') == 'Poker':
        legal = game.get('legal_actions',[])
        return Turn(poker_action='check' if 'check' in legal else 'call' if 'call' in legal else 'fold',
                    reveal_cards=name=='Cody', used=18, speech='')
    if game and game.get('game') == 'Tic-tac-toe':
        legal = game['legal_cells']
        preferred = [4,0,2,6,8,1,3,5,7] if name!='Burt' else list(reversed(range(9)))
        return Turn(move=next(i for i in preferred if i in legal),used=22,
                    speech='Umm, this one looks free.' if name=='Burt' else 'Okay, your turn!')
    if game and game.get('game') == 'Mafia':
        targets = game.get('targets',[])
        return Turn(vote=targets[0] if targets else '',used=25,
                    speech={'Burt':'Umm, I forgot who we were suspicious of.',
                            'Cody':'I trust everyone. Is that bad for this game?',
                            'Victoria':'Cody, that is a spectacularly unhelpful defence.',
                            'Mika':'Let’s hear everyone before we decide.'}[name] if game['phase']=='discussion' else '')
    if game and game.get('game') == 'Debate':
        return Turn(speech=DEBATE_LINES[name],used=26)
    if movie:
        return Turn(speech=movie_comment_fallback(name,conversation),used=20)
    latest = next((line['text'] for line in reversed(conversation) if line['speaker']=='You'),'')
    if trigger.startswith('PLAYER_MESSAGE'):
        topic = latest.lower()
        if any(word in topic for word in ('remember','snack','popcorn')):
            return Turn(speech={'Burt':'Umm, yes. Popcorn. I wrote that down this time.',
                                'Cody':'Popcorn! I remembered because I want some.',
                                'Victoria':'Yes, darling. Your snack preferences have been noted.',
                                'Mika':'We’ll remember popcorn for movie night.'}[name],used=30,
                        memories=[{'target':'Mika','text':'The demo visitor asked us to remember popcorn for movie night.'}])
        return Turn(speech={'Burt':'Umm, I heard you. I’m still trying to work out my answer.',
                            'Cody':'Oh! I’m glad you came to hang out with us.',
                            'Victoria':'You have my attention, darling. Do make yourself comfortable.',
                            'Mika':'I’m listening. It’s nice having everyone here.'}[name],used=25)
    return Turn(speech=INTRO[name],used=20)


class DemoWindows:
    """A strictly owned-window backend: no native enumeration or personal app access."""
    def __init__(self, root):
        self.root = root
        self.props = {}
        self.hooks = []

    def add(self, window, title):
        window.update_idletasks()
        key = window.winfo_id()
        self.props[key] = (window,title)
        return key

    def set_monitoring(self, enabled):
        pass

    def drain_events(self):
        return []

    def idle_seconds(self):
        return 100

    def inspect(self, hwnd):
        if hwnd not in self.props:
            return None
        window,title = self.props[hwnd]
        if not window.winfo_exists() or window.state()=='withdrawn':
            return None
        x,y,w,h = window.winfo_x(),window.winfo_y(),window.winfo_width(),window.winfo_height()
        return {'hwnd':hwnd,'pid':1,'started':1,'path':'demo-owned/'+str(hwnd),
                'app':'DEMO prop','title':title,'class':'DemoOwnedWindow',
                'rect':[x,y,x+w,y+h],'work':[0,0,self.root.winfo_screenwidth(),self.root.winfo_screenheight()-50],
                'state':{'zoomed':'maximized','iconic':'minimized'}.get(window.state(),'normal'),
                'foreground':False,'movable':window.state()=='normal','playable':True,'resizable':True}

    def list_windows(self):
        return [record for hwnd in self.props if (record:=self.inspect(hwnd))]

    def position(self, record, rect):
        if record['hwnd'] not in self.props:
            return False
        window,_ = self.props[record['hwnd']]
        window.geometry(f'{rect[2]-rect[0]}x{rect[3]-rect[1]}+{rect[0]}+{rect[1]}')
        return True

    def set_state(self, record, state):
        if record['hwnd'] not in self.props or state not in ('restore','maximize','minimize'):
            return False
        self.props[record['hwnd']][0].state({'restore':'normal','maximize':'zoomed','minimize':'iconic'}[state])
        return True


class DemoApp(ScreenSquatters):
    def __init__(self,root,directory):
        house = House(Path(directory)/'house.json')
        house.options.update(window_awareness=False,window_control=False)
        house.save()
        super().__init__(root,data_dir=directory,port=0,timers=False)
        self.key = 'offline-demo-no-network'
        self.world.rng = random.Random(7)
        self.autonomy.set(False)
        self.hangout.set(False)
        self.house.options.update(game_deliberation=False,game_invites=False,autoplay_games=False,screen_comments=False)
        self.windows.backend.set_monitoring(False)
        self.owned_windows = DemoWindows(root)
        self.windows = WindowWorld(self.house.options,self.owned_windows)
        self.director = None
        self.demo_pending = None

    def request_turn(self,name,trigger,direct=False,chat_only=False):
        if self.busy or self.speech_pending() or name not in self.awake():
            return
        self.busy,self.busy_name = True,name
        self.cancelled.clear()
        self.status.set(name+' is typing… [offline demo]')
        self.house.reserve(name,unlimited=self.game is not None)
        view = self.game.view(name) if self.game and name in self.game.players else None
        result = demo_turn(name,trigger,deepcopy(self.conversation),None if direct else view,self.movie_mode.get() and not direct)
        result.game_turn = self.game is not None
        result.direct_reply,result.chat_only,result.reply_epoch = direct,chat_only,self.user_epoch
        generation,scene = self.generation,self.scene
        def finish():
            self.demo_pending = None
            if not self.closing:
                self.handle_turn(generation,scene,name,result)
        self.demo_pending = self.root.after(650,finish)

    def capture_tick(self):
        # Only the director's explicitly staged page/captions can supply context.
        pass

    def windows_tick(self,now):
        if self.house.options['window_awareness']:
            self.windows.update(self.owned_windows.list_windows())

    def validate_interests(self):
        # Demo targets are registered prop windows, never the user's foreground app.
        pass

    def current_observation(self):
        return self.observation

    def show_settings(self):
        super().show_settings()
        self.settings.title('DEMO ONLY | Settings — temporary save, offline replies')
        self.settings.geometry('+450+35')

    def quit(self):
        if self.director:
            self.director.closed = True
        super().quit()


class DemoDirector:
    def __init__(self,app):
        self.app,self.root = app,app.root
        app.director = self
        self.closed = False
        self.chapter = -1
        self.epoch = 0
        self.elapsed = 0
        self.playing = False
        self.autoplayer = tk.BooleanVar(value=True)
        self.events = []
        self.passed = set()
        self.panel = tk.Toplevel(self.root)
        self.panel.title('Screen Squatters | Judges’ demo')
        self.panel.configure(bg=BG)
        self.panel.attributes('-topmost',True)
        self.panel.geometry(f'410x{min(790,self.root.winfo_screenheight()-90)}+24+24')
        self.panel.minsize(380,580)
        self.panel.protocol('WM_DELETE_WINDOW',app.quit)
        self.panel.bind('<space>',lambda event:self.toggle_play() if event.widget==self.panel else None)
        tk.Label(self.panel,text='SCREEN SQUATTERS',bg=BG,fg=ACCENT,font=('Segoe UI',19,'bold')).pack(anchor='w',padx=20,pady=(18,4))
        tk.Label(self.panel,text='JUDGES’ SHOWCASE · OFFLINE / STAGED',bg=BG,fg=MUTED,font=('Segoe UI',9,'bold')).pack(anchor='w',padx=20)
        tk.Label(self.panel,text='Real UI, physics, memory and game rules.\nScripted replies / feed; simulated token counters.\nOnly demo-owned windows move. No API charges.',bg=PANEL,fg=FG,
                 justify='left',padx=12,pady=10,font=('Segoe UI',10)).pack(fill='x',padx=20,pady=12)
        self.heading = tk.StringVar()
        self.description = tk.StringVar()
        self.status = tk.StringVar()
        tk.Label(self.panel,textvariable=self.heading,bg=BG,fg=FG,font=('Segoe UI',15,'bold'),anchor='w').pack(fill='x',padx=20)
        tk.Label(self.panel,textvariable=self.description,bg=BG,fg=MUTED,wraplength=355,justify='left',anchor='nw',height=5).pack(fill='x',padx=20,pady=8)
        chapter_frame = tk.Frame(self.panel,bg=BG)
        chapter_frame.pack(fill='both',expand=True,padx=20)
        chapter_scroll = tk.Scrollbar(chapter_frame)
        chapter_scroll.pack(side='right',fill='y')
        self.chapter_list = tk.Listbox(chapter_frame,bg=PANEL,fg=FG,selectbackground='#51416e',relief='flat',font=('Segoe UI',10),height=8,exportselection=False,
                                       yscrollcommand=chapter_scroll.set)
        chapter_scroll.configure(command=self.chapter_list.yview)
        for i,(title,_,_) in enumerate(CHAPTERS):
            self.chapter_list.insert('end',f'{i+1:02d}  {title}')
        self.chapter_list.pack(side='left',fill='both',expand=True)
        self.chapter_list.bind('<<ListboxSelect>>',self.select_chapter)
        row = tk.Frame(self.panel,bg=BG)
        row.pack(fill='x',padx=20,pady=(12,5))
        app.button(row,'‹ Back',lambda:self.go(self.chapter-1)).pack(side='left')
        self.play_button = app.button(row,'▶ Start tour',self.toggle_play,True)
        self.play_button.pack(side='left',padx=7)
        app.button(row,'Next ›',lambda:self.go(self.chapter+1)).pack(side='left')
        row2 = tk.Frame(self.panel,bg=BG)
        row2.pack(fill='x',padx=20,pady=5)
        app.button(row2,'Replay scene',lambda:self.go(self.chapter)).pack(side='left')
        app.button(row2,'Open chat',app.show_chat).pack(side='left',padx=5)
        app.button(row2,'Settings',app.show_settings).pack(side='left')
        tk.Checkbutton(self.panel,text='Player autopilot (off = judges play)',variable=self.autoplayer,bg=BG,fg=FG,selectcolor=PANEL,
                       activebackground=BG,activeforeground=FG).pack(anchor='w',padx=20,pady=4)
        self.action_button = app.button(self.panel,'Try this feature',self.action,True)
        self.action_button.pack(fill='x',padx=20,pady=5)
        row3 = tk.Frame(self.panel,bg=BG)
        row3.pack(fill='x',padx=20,pady=4)
        app.button(row3,'Pause windows',app.pause_window_play).pack(side='left')
        app.button(row3,'Undo move',app.windows.undo).pack(side='left',padx=5)
        tk.Label(self.panel,textvariable=self.status,bg=BG,fg=MUTED,wraplength=360,justify='left').pack(anchor='w',padx=20,pady=(6,12))
        self.browser = self.prop('DEMO · Firefox-style page',520,320,460,80)
        self.notes = self.prop('DEMO · Shared notes',420,240,650,420)
        self.browser_body = self.prop_text(self.browser)
        self.notes_body = self.prop_text(self.notes)
        self.browser.withdraw(); self.notes.withdraw()
        self.root.after(200,self.pulse)
        self.go(0)

    def prop(self,title,width,height,x,y):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.configure(bg=PANEL)
        sw,sh = self.root.winfo_screenwidth(),self.root.winfo_screenheight()
        win.geometry(f'{min(width,sw-50)}x{min(height,sh-80)}+{min(x,max(0,sw-width-20))}+{min(y,max(0,sh-height-60))}')
        tk.Label(win,text='STAGED DEMO CONTENT · NOT YOUR BROWSER',bg='#51416e',fg=FG,pady=7,font=('Segoe UI',9,'bold')).pack(fill='x')
        win.protocol('WM_DELETE_WINDOW',win.withdraw)
        self.app.owned_windows.add(win,title)
        return win

    def prop_text(self,window):
        text = tk.Label(window,text='',bg=PANEL,fg=FG,font=('Segoe UI',13),justify='left',anchor='nw',padx=18,pady=18,wraplength=440)
        text.pack(fill='both',expand=True)
        window.bind('<Configure>',lambda event:text.configure(wraplength=max(170,window.winfo_width()-40)) if event.widget==window else None)
        return text

    def select_chapter(self,_event):
        selected = self.chapter_list.curselection()
        if selected and selected[0]!=self.chapter:
            self.go(selected[0])

    def toggle_play(self):
        self.playing = not self.playing
        self.play_button.configure(text='Ⅱ Pause tour' if self.playing else '▶ Resume tour')

    def later(self,seconds,fn):
        self.events.append([self.elapsed+seconds,fn])

    def say(self,name,text):
        self.app.append(name,text)

    def wake_all(self):
        now = time.monotonic()
        for i,name in enumerate(CHARACTERS):
            agent = self.app.house.agents[name]
            agent['used'] = min(agent['used'],agent['limit']//2)
            agent['awake'] = True
            resident = self.app.world.residents[name]
            resident.blocked = False
            self.app.world.wake(name,now)
            resident.x,resident.y = self.app.world.constrain(450+i*160,self.root.winfo_screenheight()-260)
            resident.mode = 'idle'
            resident.goal = None
            resident.interest = resident.gaze = None
            resident.spin = 0
            resident.rest_at = now+3600
        self.app.refresh()

    def finish_speech(self):
        if self.app.deliveries:
            self.app.dialogue_tick(max(item['line'].end for item in self.app.deliveries)+.1)

    def go(self,index):
        if not 0<=index<len(CHAPTERS):
            self.playing = False
            return
        app = self.app
        self.epoch += 1
        if app.demo_pending:
            self.root.after_cancel(app.demo_pending)
            app.demo_pending = None
        app.busy,app.busy_name = False,None
        for agent in app.house.agents.values():
            agent['reserved'] = 0
            agent['game_pending'] = False
        self.finish_speech()
        app.pending.clear()
        app.cancel_game('Moving to the next demo scene.')
        if app.movie_mode.get():
            app.set_movie_mode(False,quiet=True)
        app.pause_window_play()
        app.hangout.set(False)
        app.social = Social(CHARACTERS,app.house.options)
        app.stand_still.set(False); app.stand_still_changed()
        app.observation = None
        self.browser.withdraw(); self.notes.withdraw()
        for win in app.memory_windows:
            if win.winfo_exists(): win.destroy()
        app.memory_windows.clear()
        if getattr(app,'settings',None) and app.settings.winfo_exists(): app.settings.destroy()
        self.chapter,self.elapsed,self.events = index,0,[]
        title,description,_duration = CHAPTERS[index]
        self.heading.set(f'{index+1:02d} / {len(CHAPTERS):02d}  {title}')
        self.description.set(description)
        self.chapter_list.selection_clear(0,'end'); self.chapter_list.selection_set(index); self.chapter_list.see(index)
        self.passed.add(index)
        self.action_button.configure(text={0:'Open / close house',3:'Throw Burt again',5:'More window mischief',6:'Start a tiny squabble',
                                           11:'Next movie caption',12:'Show a minute of recovery',13:'Factory reset demo (confirm)'}.get(index,'Try / replay this feature'))
        if index:
            self.wake_all()
            app.show_chat()
            app.chat.geometry(f'500x{min(430,self.root.winfo_screenheight()-100)}+{min(450,max(0,self.root.winfo_screenwidth()-510))}+50')
        self.enter_scene(index)
        self.status.set('Tour ready. Press Start, or jump to any chapter.')

    def enter_scene(self,index):
        app = self.app
        if index==0:
            app.sleep_all(); app.chat.withdraw(); app.habitat.open = False
            self.later(3,lambda:setattr(app.habitat,'open',True))
        elif index==1:
            app.habitat.open = True
            for i,(name,line) in enumerate(INTRO.items()): self.later(i*5,lambda n=name,t=line:self.say(n,t))
        elif index==2:
            self.say('You','Remember that I like popcorn for movie night.')
            self.later(2,lambda:app.request_turn('Mika','PLAYER_MESSAGE: remember popcorn',direct=True))
            self.later(7,lambda:self.say('Burt','Umm, I wrote it down. Wait, Mika wrote it down for me.'))
            self.later(13,lambda:self.say('Victoria','A historic breakthrough in household administration.'))
            self.later(18,lambda:app.show_memories('Mika'))
        elif index==3:
            self.say('Cody','Oh! Try picking us up. Burt, maybe brace yourself.')
            self.later(4,self.throw)
            self.later(11,lambda:self.say('Burt','Uhh, I was over there a second ago.'))
        elif index==4:
            self.page_scene()
        elif index==5:
            self.window_scene()
        elif index==6:
            self.squabble()
        elif index in (7,8,9,10):
            game = TicTacToe('You','Burt') if index==7 else Poker(['You',*CHARACTERS],rng=random.Random(17)) if index==8 else Mafia(['You',*CHARACTERS],rng=random.Random(9)) if index==9 else Debate(['You',*CHARACTERS],'Should movie-night popcorn be shared?',rounds=2)
            app.begin_game(game,deliberate=False)
            if index==7:
                app.cancel_game('First, an invitation from a housemate.')
                app.house.options['game_invites'] = True
                app.offer_game('Cody','Tic-tac-toe')
                self.later(6,lambda:self.join_demo_invitation())
            if app.game_window: app.game_window.geometry('+450+45')
            if index==8: self.say('Victoria','Real chips? No? Very well. I shall win the pretend ones.')
        elif index==11:
            app.set_movie_mode(True)
            self.movie_frame()
            self.later(4,lambda:self.say('Cody','He came back for the little robot. I’m glad.'))
            self.later(12,lambda:self.say('Victoria','Finally, someone in this film with decent manners.'))
            self.later(19,self.movie_frame)
            self.later(22,lambda:self.say('Burt','Umm, okay, I think I know which robot it is now.'))
        elif index==12:
            agent = app.house.agents['Burt']
            agent['used'] = agent['limit']
            app.sleep('Burt')
            app.world.rest('Burt',time.monotonic(),immediate=True)
            app.house.sleep_recovery_rate = 600
            app.recovery_rate.set(600)
            self.say('Mika','He’s having a rest. We’ll keep his popcorn here.')
            self.later(4,self.recharge)
            self.later(12,lambda:app.show_memories('Mika'))
        else:
            app.show_settings()
            self.say('Mika','That’s our little house. You’re welcome to stay a while.')
            self.playing = False
            self.play_button.configure(text='▶ Resume tour')

    def page_scene(self):
        self.browser.deiconify()
        self.browser_body.configure(text='Volcano Club\n\nWhy do plates move?\nA plate boundary is where two tectonic plates meet.\n\n[Visible target] A diagram of a subduction zone\n\nMetadata: title, headings, text, visible targets\nFeed: staged Firefox extension payload')
        now = time.monotonic()
        self.app.inbox.put({'title':'Volcano Club — demo page','url':'https://example.com/volcano-club',
                            'text':'A plate boundary is where two tectonic plates meet.','headings':['Why do plates move?'],
                            'targets':[{'label':'subduction diagram','x':.5,'y':.65}],
                            'viewport':{'width':520,'height':320},'automatic':True})
        self.app.poll(reschedule=False)
        self.app.context_status.set('DEMO: staged Firefox-style metadata received; no browser inspected')
        x,y = self.browser.winfo_x()+200,self.browser.winfo_y()+190
        self.app.world.inspect('Burt',(x,y,'subduction diagram'),now)
        self.say('Burt','Umm, slab pull is a major driver of plate motion. Wait, did someone want the popcorn?')
        self.later(9,lambda:self.say('Cody','You know all that but you got lost walking out of your bedroom?'))

    def window_scene(self):
        self.browser.deiconify(); self.notes.deiconify()
        self.browser_body.configure(text='A very rearrangeable demo window\n\nWatch the desktop companions move, wobble and resize me.\n\nOnly these demo-owned props are registered.\nYour actual apps are outside this demo.')
        self.notes_body.configure(text='House rules\n\nVictoria: everything aligned.\nMika: a little more room, please.\nCody: what if it bounced?\nBurt: umm, which window?')
        self.app.house.options.update(chaos_options(self.app.house.options))
        self.app.windows.update(self.app.owned_windows.list_windows())
        self.say('Victoria','That window is crooked. Give me a moment.')
        self.later(2,lambda:self.stunt('Victoria'))
        self.later(9,lambda:self.stunt('Cody'))
        self.later(10,lambda:self.say('Cody','I made room! Oh. You had just put it there.'))
        self.later(17,lambda:self.stunt('Mika'))
        self.later(24,lambda:self.stunt('Burt'))

    def stunt(self,name='Burt'):
        self.app.windows.update(self.app.owned_windows.list_windows())
        key = self.app.windows.play(name,self.app.world.rng)
        if key:
            item = self.app.windows.windows[key]
            self.app.world.inspect(name,(item['rect'][0]+30,item['rect'][1]+40,'a demo window'),time.monotonic())

    def squabble(self):
        app = self.app
        now = time.monotonic()
        for i,name in enumerate(('Cody','Victoria')):
            resident = app.world.residents[name]
            resident.x,resident.y = app.world.constrain(550+i*100,self.root.winfo_screenheight()-270)
            resident.mode = 'idle'
        self.say('Victoria','Cody, stop moving the window I have just straightened.')
        result = Turn(emotion='annoyed',social_action={'kind':'scuffle','target':'Cody'})
        self.later(3,lambda:app.social.react('Victoria',result,app.world,app.awake(),time.monotonic()))
        self.later(9,lambda:self.say('Cody','Okay, okay! I thought you wanted more space.'))
        self.later(14,lambda:self.say('Mika','There. One window each. Peace restored.'))

    def throw(self):
        self.app.world.throw('Burt',1000,-600,time.monotonic())

    def join_demo_invitation(self):
        if self.app.invitation:
            self.finish_speech()
            self.app.accept_invitation(True)
            if self.app.game_window: self.app.game_window.geometry('+450+45')

    def recharge(self):
        before = self.app.house.agents['Burt']['used']
        self.app.house.recover_sleep(60,['Burt'])
        after = self.app.house.agents['Burt']['used']
        self.app.note(f'DEMO: advanced the recovery clock by one minute: Burt’s usage {before} → {after}. Real recovery uses elapsed time.')
        self.app.refresh()

    def movie_frame(self):
        self.browser.deiconify()
        self.browser_body.configure(text='STAGED MOVIE FRAME · The Little Robot\n\nA traveller returns to the station for a forgotten robot.\n\nCaption: “I wasn’t going to leave you behind.”\n\nThis is authored demo context, not a live film or audio feed.')
        self.app.observation = {'kind':'page','title':'The Little Robot — staged caption',
                                'text':'A traveller returns to collect a forgotten robot. Caption: I wasn’t going to leave you behind.',
                                'url':'https://example.com/demo-film','bounds':[0,0,800,600]}
        self.app.observation_time = time.monotonic()

    def action(self):
        if self.chapter==0: self.app.habitat.open = not self.app.habitat.open
        elif self.chapter==3: self.throw()
        elif self.chapter==5: self.stunt()
        elif self.chapter==6: self.squabble()
        elif self.chapter==11: self.movie_frame()
        elif self.chapter==12: self.recharge()
        elif self.chapter==13: self.app.reset_all()
        else: self.go(self.chapter)

    def player_turn(self):
        game = self.app.game
        if not game or game.result or game.actor!='You' or not self.autoplayer.get(): return
        if isinstance(game,Poker): self.app.game_action(('check' if 'check' in game.legal_actions('You') else 'call',game.phase=='river'))
        elif isinstance(game,TicTacToe): self.app.game_action(next(i for i in [0,4,8,2,6,1,3,5,7] if not game.board[i]))
        elif isinstance(game,Debate):
            game.act('You','I vote for a bowl each, with extra popcorn in the middle.')
            self.app.render_game(); self.app.next_turn = time.monotonic()+1
        else: self.app.game_action(game.view('You')['targets'][0] if game.phase!='discussion' else None)

    def pulse(self):
        if self.closed or self.app.closing: return
        self.app.poll(reschedule=False)
        self.app.windows_tick(time.monotonic())
        self.app.recover_sleep_tick()
        if self.playing:
            self.elapsed += .2
            for event in list(self.events):
                if self.elapsed>=event[0]:
                    self.events.remove(event); event[1]()
            duration = CHAPTERS[self.chapter][2]
            self.status.set(f'{len(self.passed)} / {len(CHAPTERS)} chapters visited · {max(0,int(duration-self.elapsed))}s to next scene · Offline, no API charges')
            if duration and self.elapsed>=duration:
                self.go(self.chapter+1)
        if not self.app.busy and not self.app.speech_pending():
            if self.app.pending:
                name = self.app.pending.popleft()
                self.app.request_turn(name,'PLAYER_MESSAGE: demo visitor',direct=True,chat_only=self.app.game is not None)
            elif self.playing and self.app.game and not self.app.game.result and time.monotonic()>=self.app.next_turn:
                self.player_turn()
                if self.app.game and self.app.game.actor in self.app.awake():
                    self.app.request_turn(self.app.game.actor,'Take your game turn.')
        self.root.after(200,self.pulse)


def smoke_test(director):
    """Exercise the showcase without a browser, provider or personal window backend."""
    app = director.app
    app.root.update()
    assert director.action_button.winfo_y()+director.action_button.winfo_height()<director.panel.winfo_height(), 'Presenter controls must fit the screen'
    for index in range(len(CHAPTERS)):
        director.go(index)
        for _ in range(3): app.root.update()
        for _when,callback in list(director.events):
            callback()
            deadline = time.monotonic()+3
            while app.demo_pending and time.monotonic()<deadline:
                app.root.update()
                time.sleep(.01)
            assert not app.demo_pending, 'Offline reply did not finish'
            director.finish_speech()
        director.events.clear()
        if index==2:
            assert any('popcorn' in note['text'] for note in app.house.agents['Mika']['memories'])
        if index==4:
            assert app.page['title']=='Volcano Club — demo page'
        if index==5:
            assert len(app.windows.windows)==2
            director.stunt('Burt')
            assert app.windows.play_history
            target = next(iter(app.windows.windows))
            assert not app.windows.apply({'target':target,'kind':'close'})
            app.windows.animate(time.monotonic()+3)
            app.root.update()
            assert app.windows.undo()
        if index in (7,8,9,10):
            if index==7: director.join_demo_invitation()
            for _ in range(180):
                game = app.game
                if game.result: break
                if game.actor=='You': director.player_turn()
                else:
                    actor = game.actor
                    result = demo_turn(actor,'Play',[],game.view(actor))
                    app.apply_game_turn(actor,result)
                app.root.update_idletasks()
            assert app.game.result, f'{app.game.kind} did not complete'
        if index==12:
            before = app.house.agents['Burt']['used']; director.recharge()
            assert app.house.agents['Burt']['used']<before
    assert isinstance(app.windows.backend,DemoWindows)
    assert app.local!=Path(__file__).resolve().parent/'.local'
    print('Judges demo smoke passed: 14 chapters, isolated save, staged page feed, owned-window play/undo/close rejection, all four complete games, movie mode and recovery. No API requests.')
    app.quit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke-test',action='store_true')
    parser.add_argument('--autoplay',action='store_true',help='Start the guided tour immediately')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='screen-squatters-demo-') as directory:
        root = tk.Tk()
        try:
            app = DemoApp(root,directory)
            director = DemoDirector(app)
            if args.smoke_test:
                from unittest.mock import patch
                with patch('ai.post',side_effect=AssertionError('Demo must not contact Gemini')), \
                     patch('desktop.capture_window',side_effect=AssertionError('Demo must not capture the screen')):
                    smoke_test(director)
            else:
                if args.autoplay: director.toggle_play()
                root.mainloop()
        except Exception as error:
            if args.smoke_test:
                root.destroy()
                raise
            messagebox.showerror('Screen Squatters demo',str(error),parent=root)
            root.destroy()


if __name__=='__main__':
    main()

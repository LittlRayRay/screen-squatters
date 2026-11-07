"""The shared poker table. Opponent cards come only from the public view."""
import tkinter as tk
from house import CHARACTERS
from visuals import rounded, speech_bubble

BG, PANEL, FG, MUTED = '#171923', '#242738', '#f1edff', '#abaec7'
SUITS = {'C':'♣','D':'♦','H':'♥','S':'♠'}


class PokerTable:
    def __init__(self, app, window, painter):
        self.app, self.window, self.painter = app, window, painter
        height = min(710,window.winfo_screenheight()-80)
        self.canvas_height = height-310
        window.geometry(f'740x{height}')
        window.resizable(False, False)
        tk.Label(window,text='poker night',bg=BG,fg=FG,font=('Segoe UI',18,'bold')).pack(pady=(12,0))
        tk.Label(window,text="Just-for-fun chips · fixed-limit Texas hold'em",bg=BG,fg=MUTED).pack()
        self.canvas = tk.Canvas(window,width=720,height=self.canvas_height,bg=BG,highlightthickness=0)
        self.canvas.pack(padx=10)
        self.status = tk.StringVar()
        tk.Label(window,textvariable=self.status,bg=BG,fg=FG,wraplength=700,font=('Segoe UI',10)).pack()
        self.actions = tk.Frame(window,bg=BG)
        self.actions.pack(pady=8)
        self.reveal_on_action = tk.BooleanVar(value=False)
        self.reveal_row = tk.Frame(window,bg=BG)
        self.reveal_row.pack()
        self.choice = tk.Checkbutton(self.reveal_row,text='Show my cards after my action',variable=self.reveal_on_action,
                                     bg=BG,fg=FG,selectcolor=PANEL,activebackground=BG,activeforeground=FG)
        self.choice.pack(side='left')
        self.show = app.button(self.reveal_row,'Reveal my cards now',self.reveal)
        self.show.pack(side='left',padx=8)
        self.events = tk.StringVar()
        tk.Label(window,textvariable=self.events,bg=BG,fg=MUTED,wraplength=690,font=('Segoe UI',9)).pack(pady=7)
        self.leave = app.button(window,'Leave table',app.cancel_game)
        self.leave.pack(pady=(0,8))
        self.refresh()

    def action(self, action):
        self.app.game_action((action,self.reveal_on_action.get()))
        self.reveal_on_action.set(False)

    def reveal(self):
        self.app.game.reveal('You')
        self.refresh()

    def refresh(self):
        game = self.app.game
        self.status.set(game.result or (f"{game.phase.title()} · Your turn" if game.actor == 'You' else f'{game.phase.title()} · {game.actor} is choosing'))
        self.events.set('\n'.join(game.events[-2:]))
        for widget in self.actions.winfo_children():
            widget.destroy()
        if game.result:
            self.app.button(self.actions,'Deal next hand · fresh 1,000 chips each',self.app.next_poker_hand,True).pack()
        else:
            for action in game.legal_actions('You'):
                label = {'fold':'Fold','check':'Check','call':f'Call {game.current_bet-game.bets["You"]}',
                         'raise':f'{"Bet" if not game.current_bet else "Raise"} {game.increment}'}[action]
                self.app.button(self.actions,label,lambda value=action:self.action(value),True).pack(side='left',padx=5)
        revealed = 'You' in game.revealed
        self.show.configure(state='disabled' if revealed else 'normal',text='Your cards are public' if revealed else 'Reveal my cards now')
        self.choice.configure(state='disabled' if revealed else 'normal')
        self.animate()

    def cards(self, cards, x, y, small=False):
        w, h = (30,42) if small else (40,56)
        for i, card in enumerate(cards):
            left = x+i*(w+5)
            rounded(self.canvas,left+2,y+3,left+w+2,y+h+3,radius=5,fill='#102824',outline='')
            rounded(self.canvas,left,y,left+w,y+h,radius=5,fill='#f6f0df' if card else '#453e68',outline='#e7cda4' if card else '#9185bf')
            if card:
                self.canvas.create_text(left+w/2,y+h/2,text=card[0].replace('T','10')+'\n'+SUITS[card[1]],
                                        fill='#b04156' if card[1] in 'DH' else '#26323c',font=('Segoe UI',10 if small else 12,'bold'))
            else:
                self.canvas.create_text(left+w/2,y+h/2,text='✦',fill='#b3a8dc',font=('Segoe UI',16))

    def animate(self):
        app, c, game = self.app, self.canvas, self.app.game
        if not c.winfo_exists() or not game:
            return
        c.delete('all')
        view = game.view('You')
        c.create_oval(137,102,583,328,fill='#0d111c',outline='')
        c.create_oval(132,92,588,318,fill='#62463d',outline='#ad8870',width=4)
        c.create_oval(147,107,573,303,fill='#215b52',outline='#408378',width=2)
        c.create_oval(161,119,559,291,outline='#729b80',dash=(3,6))
        c.create_text(360,175,text=f'POT  {game.pot if not game.result else game.awarded_pot}',fill='#f1d596',font=('Segoe UI',13,'bold'))
        self.cards(game.board,250,207)
        for i in range(len(game.board),5):
            rounded(c,250+i*45,207,290+i*45,263,radius=5,outline='#427d6e',fill='#245c52')
        seats = {'You':(360,325,320,300),'Burt':(72,190,150,150),'Byte':(360,54,327,108),'Rex':(648,190,500,150)}
        if len(game.players) == 5:
            seats.update(Burt=(72,190,155,183),Byte=(240,48,207,125),Rex=(480,48,447,125),Mika=(648,190,500,183))
        latest = app.busy_name or max((name for name in CHARACTERS if app.bubble_state(name)[0]),
                                     key=lambda name:app.speech_lines[name].start,default=None)
        for player in game.players:
            x,y,cx,cy = seats[player]
            color = CHARACTERS[player]['color'] if player in CHARACTERS else '#f1edff'
            if player == game.actor:
                c.create_oval(x-45,y-53,x+45,y+38,outline=color,width=2,dash=(4,4))
            if player in CHARACTERS:
                _text, typing, speaking = app.bubble_state(player)
                self.painter(c,player,x,y,.55,phase=app.frame+list(CHARACTERS).index(player)*17,
                             seated=True,popcorn=False,talking=speaking,gaze=((360-x)/400,(210-y)/400))
            else:
                c.create_text(x,y+24,text='your hand',fill=color,font=('Segoe UI',10))
            label = player+(' · folded' if player not in game.active else '')+(' · dealer' if game.players[game.dealer] == player else '')
            c.create_text(x,y+46,text=label,fill=color,font=('Segoe UI',9,'bold'))
            c.create_text(x,y+61,text=f'{game.stacks[player]} chips · in {game.bets[player]}',fill=MUTED,font=('Segoe UI',8))
            cards = view['your_cards'] if player == 'You' else view['shown_cards'].get(player,['',''])
            self.cards(cards,cx,cy,small=True)
            if player in CHARACTERS:
                text,typing,_speaking = app.bubble_state(player)
                if (text or typing) and (len(game.players) == 4 or player == latest):
                    bx,by = (275,0) if len(game.players) == 5 else {'Burt':(3,3),'Byte':(462,3),'Rex':(537,267)}[player]
                    speech_bubble(c,player,text,bx,by,width=175,color=color,typing=typing,phase=app.frame)
        c.create_text(360,400,text='Cards stay hidden unless their owner chooses to show them.',fill=MUTED,font=('Segoe UI',8))
        if self.canvas_height != 410:
            c.scale('all',0,0,1,self.canvas_height/410)

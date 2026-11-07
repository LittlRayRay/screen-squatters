"""User controls for metadata, window permissions, physics and social events."""
import tkinter as tk
from tkinter import ttk
from window_world import clean_options, clean_rule

BG,PANEL,FG,MUTED = '#171923','#242738','#f1edff','#abaec7'


def check(parent,label,variable):
    tk.Checkbutton(parent,text=label,variable=variable,bg=BG,fg=FG,selectcolor=PANEL,
                   activebackground=BG,activeforeground=FG).pack(anchor='w',pady=3)


def spin(parent,label,variable,low,high,increment=1):
    row = tk.Frame(parent,bg=BG)
    row.pack(fill='x',pady=3)
    tk.Label(row,text=label,bg=BG,fg=FG).pack(side='left')
    tk.Spinbox(row,from_=low,to=high,increment=increment,textvariable=variable,width=7).pack(side='right')


def windows_panel(app,parent):
    options = app.house.options
    enabled = tk.BooleanVar(value=options['window_awareness'])
    control = tk.BooleanVar(value=options['window_control'])
    idle = tk.StringVar(value=str(options['window_idle_seconds']))
    cooldown = tk.StringVar(value=str(options['window_cooldown']))
    rate = tk.StringVar(value=str(options['window_actions_per_minute']))
    check(parent,'Share native window metadata with the housemates',enabled)
    check(parent,'Allow window play on explicitly permitted windows/apps',control)
    tk.Label(parent,text='Titles, app names and geometry only; no screenshots or window contents.\nSelected metadata may go to Gemini during normal conversation turns.',
             bg=BG,fg=MUTED,justify='left',wraplength=590).pack(anchor='w',pady=4)
    spin(parent,'Wait for user idle (seconds)',idle,0,120)
    spin(parent,'Minimum cooldown per window (seconds)',cooldown,5,600)
    spin(parent,'Maximum actions per minute, across all agents',rate,1,30)
    def save_global():
        try:
            values = dict(options,window_awareness=enabled.get(),window_control=control.get(),
                          window_idle_seconds=float(idle.get()),window_cooldown=float(cooldown.get()),
                          window_actions_per_minute=int(rate.get()))
        except ValueError:
            app.note('Enter numeric window limits.')
            return
        app.update_options(values)
        idle.set(str(options['window_idle_seconds']))
        cooldown.set(str(options['window_cooldown']))
        rate.set(str(options['window_actions_per_minute']))
        refresh()
    app.button(parent,'Save window controls',save_global,True).pack(anchor='w',pady=5)
    listing = ttk.Treeview(parent,columns=('app','title','policy'),show='headings',height=5,selectmode='browse')
    for column,width in [('app',110),('title',300),('policy',120)]:
        listing.heading(column,text=column.title())
        listing.column(column,width=width,minwidth=60)
    listing.pack(fill='x',pady=5)
    values = {'observe':tk.StringVar(value='title'),'control':tk.StringVar(value='none'),
              'distance':tk.StringVar(value='48'),'size':tk.StringVar(value='40'),'cooldown':tk.StringVar(value='30')}
    row = tk.Frame(parent,bg=BG)
    row.pack(fill='x')
    for key,choices in [('observe',('ignore','app','title')),('control',('none','nudge','move','resize'))]:
        tk.Label(row,text=key.title()+':',bg=BG,fg=FG).pack(side='left',padx=(0,5))
        ttk.Combobox(row,textvariable=values[key],values=choices,state='readonly',width=9).pack(side='left',padx=(0,12))
    spin(parent,'Maximum travel from original position (px per axis)',values['distance'],1,600)
    spin(parent,'Maximum size change from original size (px)',values['size'],0,400)
    spin(parent,'This policy cooldown (seconds)',values['cooldown'],5,600)
    scope = tk.StringVar(value='This window (this session)')
    ttk.Combobox(parent,textvariable=scope,values=('This window (this session)','All windows of this app (saved)'),state='readonly').pack(fill='x',pady=4)
    status = tk.StringVar(value='Choose a window. Nudge is capped at 24px; resize also permits movement.')
    def selected(_event=None):
        selection = listing.selection()
        if selection and selection[0] in app.windows.windows:
            for key,value in app.windows.rule(selection[0]).items():
                values[key].set(str(value))
    listing.bind('<<TreeviewSelect>>',selected)
    def apply():
        selection = listing.selection()
        if not selection or selection[0] not in app.windows.windows:
            status.set('Select an open window first.')
            return
        key = selection[0]
        try:
            rule = clean_rule({name:float(value.get()) if name in ('distance','size','cooldown') else value.get() for name,value in values.items()})
        except ValueError:
            status.set('Enter numeric distance, size and cooldown limits.')
            return
        if scope.get().startswith('All'):
            path = app.windows.windows[key]['path']
            if not path:
                status.set('App identity unavailable. Use a session window policy.')
                return
            options['window_rules'][path] = rule
            app.windows.overrides.pop(key,None)
            app.save()
        else:
            app.windows.overrides[key] = rule
        for name,value in rule.items():
            values[name].set(str(value))
        status.set(f"Applied: {rule['observe']} / {rule['control']}, travel {rule['distance']}px, size {rule['size']}px. Global play must also be enabled.")
        refresh()
    buttons = tk.Frame(parent,bg=BG)
    buttons.pack(fill='x',pady=5)
    app.button(buttons,'Apply policy',apply,True).pack(side='left')
    app.button(buttons,'Undo last move',lambda:status.set('Undo requested.' if app.windows.undo() else 'Nothing eligible to undo.')).pack(side='left',padx=5)
    def pause():
        control.set(False)
        options['window_control'] = False
        app.save()
        status.set('All window play paused.')
    app.button(buttons,'Pause all window play',pause).pack(side='left')
    tk.Label(parent,textvariable=status,bg=BG,fg=MUTED,wraplength=590,justify='left').pack(anchor='w')
    activity = tk.StringVar()
    tk.Label(parent,textvariable=activity,bg=BG,fg=MUTED,wraplength=590,justify='left').pack(anchor='w',pady=5)
    def refresh():
        if not listing.winfo_exists():
            return
        activity.set('Recent window play:\n'+'\n'.join(list(app.windows.audit)[-3:]) if app.windows.audit else 'No window play this session.')
        keys = set(app.windows.windows)
        for key in listing.get_children():
            if key not in keys:
                listing.delete(key)
        for key,item in app.windows.windows.items():
            rule = app.windows.rule(key)
            row_values = (item['app'],item['title'],rule['observe']+' / '+rule['control'])
            if listing.exists(key):
                listing.item(key,values=row_values)
            else:
                listing.insert('', 'end',iid=key,values=row_values)
    app.window_settings_refresh = refresh
    refresh()


def social_panel(app,parent):
    options = app.house.options
    physics = tk.BooleanVar(value=options['physics'])
    scuffles = tk.BooleanVar(value=options['scuffles'])
    gravity = tk.StringVar(value=str(options['gravity']))
    bounce = tk.StringVar(value=str(options['bounce']))
    cooldown = tk.StringVar(value=str(options['scuffle_cooldown']))
    check(parent,'Throwing, gravity, bouncing and ball collisions',physics)
    spin(parent,'Gravity (pixels / second²)',gravity,100,2400,100)
    spin(parent,'Bounce (0 = soft, 0.9 = springy)',bounce,0,.9,.05)
    check(parent,'Allow playful cartoon scuffles when annoyed',scuffles)
    spin(parent,'Minimum time between scuffles (seconds)',cooldown,20,600,10)
    tk.Label(parent,text='Drag a housemate and release while moving to throw them.\nStand still freezes travel and physics; manual dragging still works.\nScuffles are local cartoon bumps/stars, disabled during games and movies.',
             bg=BG,fg=MUTED,justify='left',wraplength=580).pack(anchor='w',pady=15)
    def save():
        try:
            updated = dict(options,physics=physics.get(),scuffles=scuffles.get(),gravity=float(gravity.get()),
                           bounce=float(bounce.get()),scuffle_cooldown=float(cooldown.get()))
        except ValueError:
            app.note('Enter numeric physics and social limits.')
            return
        app.update_options(updated)
    app.button(parent,'Save social & physics settings',save,True).pack(anchor='w',pady=10)
    tk.Label(parent,text='Everyone is the default chat audience. Choose a name in chat for a directed reply.\nDebate night: right-click the house → Play a game → Debate a topic.\nLocal token limits are ignored during games and debate; provider charges still apply.',
             bg=BG,fg=FG,justify='left',wraplength=580).pack(anchor='w',pady=15)

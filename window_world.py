"""Window metadata and bounded opt-in window play. Never sends input or closes apps."""
from collections import deque
import ctypes
from ctypes import wintypes as wt
import math
import os
import queue
import time

DEFAULTS = {'window_awareness':True,'window_control':False,'window_idle_seconds':3,
            'window_cooldown':30,'window_actions_per_minute':3,'window_rules':{},
            'physics':True,'gravity':900,'bounce':.62,'scuffles':True,'scuffle_cooldown':90}
DEFAULTS.update(playfulness=3,screen_comments=True,game_invites=True,autoplay_games=True,game_deliberation=True)
DEFAULTS.update(window_scope='selected',play_during_activities=False)


def chaos_options(options):
    return clean_options(dict(options,window_scope='all',window_control=True,window_awareness=True,
                              playfulness=4,window_idle_seconds=0,window_cooldown=5,
                              window_actions_per_minute=12,window_rules={},play_during_activities=True))


def number(value, default, low, high):
    return min(high,max(low,value)) if type(value) in (int,float) and math.isfinite(value) else default


def clean_rule(value):
    value = value if isinstance(value,dict) else {}
    return {'observe':value.get('observe') if value.get('observe') in ('ignore','app','title') else 'title',
            'control':value.get('control') if value.get('control') in ('none','nudge','move','resize') else 'none',
            'distance':int(number(value.get('distance'),48,1,600)),
            'size':int(number(value.get('size'),40,0,400)),
            'cooldown':int(number(value.get('cooldown'),30,5,600))}


def clean_options(value):
    result = dict(DEFAULTS,window_rules={})
    if not isinstance(value,dict):
        return result
    for key in ('window_awareness','window_control','physics','scuffles','screen_comments','game_invites','autoplay_games','game_deliberation','play_during_activities'):
        if type(value.get(key)) is bool:
            result[key] = value[key]
    for key,low,high in [('window_idle_seconds',0,120),('window_cooldown',5,600),
                         ('window_actions_per_minute',1,30),('gravity',100,2400),
                         ('bounce',0,.9),('scuffle_cooldown',20,600)]:
        result[key] = number(value.get(key),result[key],low,high)
    result['playfulness'] = int(number(value.get('playfulness'),3,0,4))
    result['window_scope'] = 'all' if value.get('window_scope')=='all' else 'selected'
    rules = value.get('window_rules')
    if isinstance(rules,dict):
        result['window_rules'] = {path.casefold():clean_rule(rule) for path,rule in list(rules.items())[:200]
                                  if isinstance(path,str) and 0 < len(path) < 1024}
    result['window_actions_per_minute'] = int(result['window_actions_per_minute'])
    return result


class NativeWindows:
    def __init__(self):
        self.available = os.name == 'nt'
        self.hooks = []
        self.native_events = queue.Queue()
        self.hook_records = {}
        if not self.available:
            return
        from screen import _libraries
        self.user,self.gdi,self.kernel = _libraries()
        self.dwm = ctypes.WinDLL('dwmapi')
        self.callback = ctypes.WINFUNCTYPE(wt.BOOL,wt.HWND,wt.LPARAM)
        signatures = [
            (self.user,'EnumWindows',[self.callback,wt.LPARAM],wt.BOOL),
            (self.user,'IsWindowVisible',[wt.HWND],wt.BOOL),
            (self.user,'IsIconic',[wt.HWND],wt.BOOL),
            (self.user,'IsZoomed',[wt.HWND],wt.BOOL),
            (self.user,'GetClassNameW',[wt.HWND,wt.LPWSTR,ctypes.c_int],ctypes.c_int),
            (self.user,'GetWindow',[wt.HWND,wt.UINT],wt.HWND),
            (self.user,'GetAncestor',[wt.HWND,wt.UINT],wt.HWND),
            (self.user,'GetWindowLongPtrW',[wt.HWND,ctypes.c_int],ctypes.c_ssize_t),
            (self.user,'SetWindowPos',[wt.HWND,wt.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wt.UINT],wt.BOOL),
            (self.user,'MonitorFromWindow',[wt.HWND,wt.DWORD],wt.HANDLE),
            (self.dwm,'DwmGetWindowAttribute',[wt.HWND,wt.DWORD,ctypes.c_void_p,wt.DWORD],ctypes.c_long),
            (self.kernel,'GetProcessTimes',[wt.HANDLE,*([ctypes.POINTER(wt.FILETIME)]*4)],wt.BOOL),
            (self.kernel,'GetTickCount',[],wt.DWORD),
        ]
        for library,name,args,result in signatures:
            fn = getattr(library,name)
            fn.argtypes,fn.restype = args,result

    def inspect(self, hwnd):
        if not self.available or not self.user.IsWindowVisible(hwnd) or self.user.GetAncestor(hwnd,2) != hwnd:
            return None
        pid = wt.DWORD()
        self.user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        if not pid.value or pid.value == os.getpid():
            return None
        cloaked = wt.DWORD()
        if self.dwm.DwmGetWindowAttribute(hwnd,14,ctypes.byref(cloaked),4) == 0 and cloaked.value:
            return None
        title,klass = ctypes.create_unicode_buffer(512),ctypes.create_unicode_buffer(128)
        self.user.GetWindowTextW(hwnd,title,512)
        self.user.GetClassNameW(hwnd,klass,128)
        if not title.value or klass.value in ('Progman','WorkerW','Shell_TrayWnd','Shell_SecondaryTrayWnd'):
            return None
        rect = wt.RECT()
        if not self.user.GetWindowRect(hwnd,ctypes.byref(rect)):
            return None
        path,started = '',0
        process = self.kernel.OpenProcess(0x1000,False,pid.value)
        if process:
            try:
                buffer,length = ctypes.create_unicode_buffer(2048),wt.DWORD(2048)
                if self.kernel.QueryFullProcessImageNameW(process,0,buffer,ctypes.byref(length)):
                    path = buffer.value.casefold()
                stamps = [wt.FILETIME() for _ in range(4)]
                if self.kernel.GetProcessTimes(process,*[ctypes.byref(item) for item in stamps]):
                    started = (stamps[0].dwHighDateTime << 32) | stamps[0].dwLowDateTime
            finally:
                self.kernel.CloseHandle(process)
        executable = path.rsplit('\\',1)[-1]
        if executable in ('lockapp.exe','logonui.exe','credentialuibroker.exe','consent.exe','winlogon.exe','dwm.exe'):
            return None
        class MonitorInfo(ctypes.Structure):
            _fields_ = [('cbSize',wt.DWORD),('monitor',wt.RECT),('work',wt.RECT),('flags',wt.DWORD)]
        self.user.GetMonitorInfoW.argtypes,self.user.GetMonitorInfoW.restype = [wt.HANDLE,ctypes.POINTER(MonitorInfo)],wt.BOOL
        info = MonitorInfo()
        info.cbSize = ctypes.sizeof(info)
        if not self.user.GetMonitorInfoW(self.user.MonitorFromWindow(hwnd,2),ctypes.byref(info)):
            return None
        state = 'minimized' if self.user.IsIconic(hwnd) else 'maximized' if self.user.IsZoomed(hwnd) else 'normal'
        fullscreen = rect.left <= info.monitor.left and rect.top <= info.monitor.top and rect.right >= info.monitor.right and rect.bottom >= info.monitor.bottom
        style = self.user.GetWindowLongPtrW(hwnd,-16)
        playable = bool(path and started)
        movable = playable and state == 'normal' and not fullscreen and not self.user.GetWindow(hwnd,4) and klass.value != '#32770'
        return {'hwnd':int(hwnd),'pid':pid.value,'started':started,'path':path,'app':executable or klass.value,
                'title':title.value[:180],'class':klass.value,'rect':[rect.left,rect.top,rect.right,rect.bottom],
                'work':[info.work.left,info.work.top,info.work.right,info.work.bottom], 'state':state,
                'foreground':self.user.GetForegroundWindow() == hwnd,'movable':movable,'playable':playable,'resizable':bool(style & 0x40000)}

    def list_windows(self):
        if not self.available:
            return []
        records = []
        @self.callback
        def collect(hwnd,_param):
            try:
                item = self.inspect(hwnd)
                if item:
                    records.append(item)
            except (OSError,ValueError):
                pass
            return True
        if not self.user.EnumWindows(collect,0):
            raise OSError('Window enumeration unavailable')
        self.hook_records.update({item['hwnd']:dict(item) for item in records})
        return records

    def set_monitoring(self,enabled):
        if not self.available:
            return
        if enabled and self.hooks:
            return
        self.user.UnhookWinEvent.argtypes,self.user.UnhookWinEvent.restype = [wt.HANDLE],wt.BOOL
        for hook in self.hooks:
            self.user.UnhookWinEvent(hook)
        self.hooks = []
        self.drain_events()
        if not enabled:
            self.hook_records.clear()
            return
        event_callback = ctypes.WINFUNCTYPE(None,wt.HANDLE,wt.DWORD,wt.HWND,wt.LONG,wt.LONG,wt.DWORD,wt.DWORD)
        @event_callback
        def receive(_hook,event,hwnd,object_id,child_id,_thread,_stamp):
            if not hwnd or object_id != 0 or child_id != 0:
                return
            try:
                if event in (0x8001,0x8003):
                    if event==0x8003 and self.user.IsIconic(hwnd):
                        return
                    record = self.hook_records.pop(int(hwnd),None)
                    kind = 'closed'
                else:
                    record = self.inspect(hwnd)
                    kind = 'focused' if event == 3 else 'opened'
                    if record:
                        self.hook_records[int(hwnd)] = dict(record)
                if record:
                    self.native_events.put((kind,dict(record),time.monotonic()))
            except (OSError,ValueError):
                pass
        self.event_callback = receive  # Keep the native callback alive for the hook lifetime.
        self.user.SetWinEventHook.argtypes,self.user.SetWinEventHook.restype = [wt.DWORD,wt.DWORD,wt.HMODULE,event_callback,wt.DWORD,wt.DWORD,wt.DWORD],wt.HANDLE
        for first,last in ((3,3),(0x8001,0x8003)):
            hook = self.user.SetWinEventHook(first,last,None,receive,0,0,2)  # out-of-context, skip this process
            if hook:
                self.hooks.append(hook)

    def drain_events(self):
        events = []
        try:
            while True:
                events.append(self.native_events.get_nowait())
        except queue.Empty:
            return events

    def idle_seconds(self):
        class LastInput(ctypes.Structure):
            _fields_ = [('size',wt.UINT),('tick',wt.DWORD)]
        info = LastInput(ctypes.sizeof(LastInput),0)
        self.user.GetLastInputInfo.argtypes,self.user.GetLastInputInfo.restype = [ctypes.POINTER(LastInput)],wt.BOOL
        return ((self.kernel.GetTickCount()-info.tick)&0xffffffff)/1000 if self.user.GetLastInputInfo(ctypes.byref(info)) else 0

    def position(self, record, rect):
        x,y,right,bottom = map(int,rect)
        # Preserve focus and stacking order. ASYNC prevents a hung app blocking ours.
        return bool(self.user.SetWindowPos(record['hwnd'],None,x,y,right-x,bottom-y,0x0010|0x0004|0x0200|0x4000))

    def set_state(self,record,state):
        commands = {'restore':4,'maximize':3,'minimize':7}
        if state not in commands:
            return False
        self.user.ShowWindowAsync.argtypes,self.user.ShowWindowAsync.restype = [wt.HWND,ctypes.c_int],wt.BOOL
        return bool(self.user.ShowWindowAsync(record['hwnd'],commands[state]))


def identity(record):
    return record['hwnd'],record['pid'],record['started'],record['path']


class WindowWorld:
    def __init__(self, options, backend=None):
        self.options = options
        self.backend = backend or NativeWindows()
        self.windows = {}
        self.overrides = {}
        self.events = deque(maxlen=16)
        self.audit = deque(maxlen=12)
        self.actions = deque()
        self.last_action = {}
        self.anchors = {}
        self.undos = deque(maxlen=20)
        self.serial = 0
        self.seeded = False
        self.last_update = 0
        self.changes = []
        self.event_serial = 0
        self.aliases = {}
        self.closed_identities = set()
        self.animations = []
        self.status = 'Window play has not run yet.'

    def update(self, records):
        self.changes = []
        self.last_update = time.monotonic()
        opened = []
        updated = {}
        for item in records:
            key = self.aliases.get(identity(item))
            if key is None:
                self.serial += 1
                key = 'w'+str(self.serial)
                self.aliases[identity(item)] = key
            if key not in self.windows:
                self.closed_identities.discard(identity(item))
                if self.seeded:
                    opened.append(key)
                    self.emit({'event':'opened','window':key,'record':dict(item),'time':time.monotonic()})
            elif item['foreground'] and not self.windows[key]['foreground']:
                self.emit({'event':'focused','window':key,'record':dict(item),'time':time.monotonic()})
            updated[key] = dict(item,id=key)
        for key,item in self.windows.items():
            if key not in updated:
                self.closed_identities.add(identity(item))
                self.emit({'event':'closed','window':key,'record':item,'time':time.monotonic()})
                self.anchors.pop(key,None)
        self.windows = updated
        self.seeded = True
        return opened

    def emit(self,event):
        self.event_serial += 1
        event['event_id'] = f'native:{self.event_serial}'
        self.events.append(event)
        self.changes.append(event)

    def native_change(self,kind,record,stamp):
        key = self.aliases.get(identity(record))
        if kind=='closed' and identity(record) in self.closed_identities:
            return None
        if key is None:
            self.serial += 1
            key = 'w'+str(self.serial)
            self.aliases[identity(record)] = key
        elif key in self.windows and (kind == 'opened' or (kind=='focused' and self.windows[key]['foreground'])):
            return None
        if kind == 'closed':
            self.closed_identities.add(identity(record))
            self.windows.pop(key,None)
            self.anchors.pop(key,None)
        else:
            self.closed_identities.discard(identity(record))
            if kind=='focused':
                for item in self.windows.values():
                    item['foreground'] = False
                record = dict(record,foreground=True)
            self.windows[key] = dict(record,id=key)
        event = {'event':kind,'window':key,'record':dict(record),'time':stamp}
        self.emit(event)
        self.last_update = max(self.last_update,stamp)
        return event

    def play(self,name,rng,now=None):
        if self.animations:
            return None
        candidates = [key for key,item in self.windows.items() if (self.public(key,item) or {}).get('allowed')]
        if not candidates:
            self.status = 'Window play is off.' if not self.options.get('window_control') else 'No permitted ordinary app windows are available.'
        rng.shuffle(candidates)
        for key in candidates:
            chaos = self.options.get('playfulness',3)>=4
            amount = min(self.rule(key)['distance'],180) if chaos else min(self.rule(key)['distance'],65)
            dx,dy = rng.choice((-amount,amount)),rng.choice((-amount//2,amount//2))
            if name == 'Mika':
                dx,dy = amount//2,-amount//3
            elif name == 'Victoria':
                dx,dy = rng.choice((-amount,amount)),0
            action = {'target':key,'dx':dx,'dy':dy}
            if self.rule(key)['control']=='resize' and rng.random()<(.6 if chaos else .3):
                action.update(dw=rng.choice((-96,96)),dh=rng.choice((-48,48)))
            if chaos:
                item = self.windows[key]
                width,height = item['rect'][2]-item['rect'][0],item['rect'][3]-item['rect'][1]
                if width>.9*(item['work'][2]-item['work'][0]) or height>.9*(item['work'][3]-item['work'][1]):
                    action.update(dw=-128,dh=-96)
            if chaos and self.options.get('window_scope')=='all' and rng.random()<.08:
                action['kind'] = 'maximize'
            if self.apply(action,now,animated=True,shake=chaos and name in ('Burt','Cody')):
                return key
        return None

    def rule(self, key, record=None):
        record = record or self.windows.get(key,{})
        default = {'control':'resize','distance':280,'size':160,'cooldown':5} if self.options.get('window_scope')=='all' else {}
        return clean_rule(self.overrides.get(key,self.options.get('window_rules',{}).get(record.get('path',''),default)))

    def public(self, key, item):
        rule = self.rule(key,item)
        if rule['observe'] == 'ignore':
            return None
        data = {'id':key,'app':item['app'],'state':item['state'],'foreground':item['foreground']}
        if rule['observe'] == 'title':
            data.update(title=item['title'][:100],bounds=list(item['rect']),window_class=item['class'])
        can_play = item['movable'] or (self.options.get('window_scope')=='all' and item.get('playable',False))
        if self.options.get('window_control') and can_play and rule['control'] != 'none':
            data['allowed'] = {'control':rule['control'],'distance':min(rule['distance'],24) if rule['control']=='nudge' else rule['distance'],
                               'resize':rule['size'] if rule['control']=='resize' and (item['resizable'] or self.options.get('window_scope')=='all') else 0}
        return data

    def context(self):
        if not self.options.get('window_awareness') or time.monotonic()-self.last_update > 10:
            return None
        items = sorted(self.windows.items(),key=lambda pair:not pair[1]['foreground'])
        windows = [data for key,item in items if (data := self.public(key,item))]
        events = []
        for event in self.events:
            if time.monotonic()-event['time'] > 60:
                continue
            data = self.public(event['window'],event['record'])
            if data:
                events.append({'event':event['event'],'window':data})
        return {'windows':windows[:20],'total_visible':len(windows),'events':events[-5:],
                'source':'Native Windows metadata, no screenshot or window contents.'}

    def blocked(self,message):
        self.status = message
        return False

    def apply(self, action, now=None, animated=False, shake=False, manual=False):
        now = time.monotonic() if now is None else now
        if not self.options.get('window_awareness') or not self.options.get('window_control') or not isinstance(action,dict):
            return self.blocked('Window play is switched off.')
        kind = action.get('kind','move')
        if kind not in ('move','restore','maximize','minimize'):
            return self.blocked('That window operation is unavailable. Closing is never allowed.')
        key = action.get('target')
        if not isinstance(key,str) or key not in self.windows:
            return self.blocked('The target window is no longer available.')
        record,rule = self.windows[key],self.rule(key)
        if rule['observe'] == 'ignore' or rule['control'] == 'none':
            return self.blocked('This window is excluded by its policy.')
        if not manual and self.backend.idle_seconds() < self.options.get('window_idle_seconds',3):
            return self.blocked('Waiting for the configured user-idle delay.')
        cooldown = max(rule['cooldown'],self.options.get('window_cooldown',30))
        if not manual and now-self.last_action.get(key,-1e9) < cooldown:
            return self.blocked('Waiting for this window’s cooldown.')
        while self.actions and now-self.actions[0] >= 60:
            self.actions.popleft()
        rate = self.options.get('window_actions_per_minute',3)
        if not manual and (len(self.actions)>=rate or (self.options.get('playfulness')==4 and self.actions and now-self.actions[-1]<60/rate)):
            return self.blocked('Waiting for the configured action-rate limit.')
        live = self.backend.inspect(record['hwnd'])
        all_windows = self.options.get('window_scope')=='all'
        if not live or identity(live) != identity(record) or not (live['movable'] or (all_windows and live.get('playable',False))):
            return self.blocked('The window is protected or cannot currently be moved.')
        if live['state'] != 'normal' and kind=='move':
            kind = 'restore'
        if kind != 'move':
            if not all_windows or not hasattr(self.backend,'set_state'):
                return self.blocked('State changes need all-window play enabled.')
            wanted = {'restore':'normal','maximize':'maximized','minimize':'minimized'}[kind]
            if live['state']==wanted or not self.backend.set_state(live,kind):
                return self.blocked('No state change was needed or the app declined it.')
            self.record_action(key,live,now,f'{kind} requested')
            return True
        deltas = [action.get(key,0) for key in ('dx','dy','dw','dh')]
        if any(type(value) not in (int,float) or not math.isfinite(value) for value in deltas):
            return False
        dx,dy,dw,dh = deltas
        if (dw or dh) and (rule['control'] != 'resize' or (not live['resizable'] and not all_windows)):
            return False
        anchor = self.anchors.get(key,live['rect'])
        limit = min(24,rule['distance']) if rule['control']=='nudge' else rule['distance']
        left,top,right,bottom = live['work']
        x,y,r,b = live['rect']
        if (abs(x-anchor[0]) > limit or abs(y-anchor[1]) > limit or
            abs((r-x)-(anchor[2]-anchor[0])) > rule['size'] or abs((b-y)-(anchor[3]-anchor[1])) > rule['size']):
            anchor = list(live['rect'])
            self.anchors.pop(key,None)
        dx,dy = max(-limit,min(limit,dx)),max(-limit,min(limit,dy))
        dw,dh = max(-rule['size'],min(rule['size'],dw)),max(-rule['size'],min(rule['size'],dh))
        width = min(right-left,max(min(240,anchor[2]-anchor[0]),min(anchor[2]-anchor[0]+rule['size'],max(anchor[2]-anchor[0]-rule['size'],r-x+dw)))) if dw else r-x
        height = min(bottom-top,max(min(160,anchor[3]-anchor[1]),min(anchor[3]-anchor[1]+rule['size'],max(anchor[3]-anchor[1]-rule['size'],b-y+dh)))) if dh else b-y
        if width>right-left or height>bottom-top:
            if rule['control']!='resize' or (not live['resizable'] and not all_windows):
                return self.blocked('The window cannot fit on its monitor without resize permission.')
            width,height = min(width,right-left),min(height,bottom-top)
        nx = min(right-width,max(left,min(anchor[0]+limit,max(anchor[0]-limit,x+dx))))
        ny = min(bottom-height,max(top,min(anchor[1]+limit,max(anchor[1]-limit,y+dy))))
        rect = [int(nx),int(ny),int(nx+width),int(ny+height)]
        if abs(rect[0]-x)>limit or abs(rect[1]-y)>limit or abs(width-(r-x))>rule['size'] or abs(height-(b-y))>rule['size']:
            return self.blocked('The requested change exceeds the window’s limits.')
        if rect == live['rect']:
            return self.blocked('This window is already at its travel/size limit.')
        if animated:
            self.animations.append({'key':key,'identity':identity(live),'origin':list(live['rect']),
                                    'target':rect,'start':now,'duration':1.1 if shake else .7,'shake':shake,
                                    'distance':limit,'size':rule['size']})
        elif not self.backend.position(live,rect):
            return self.blocked('The app refused the move.')
        self.anchors.setdefault(key,list(live['rect']))
        self.record_action(key,live,now,f'animated move/resize within {limit}px' if animated else f'move/resize within {limit}px')
        return True

    def record_action(self,key,live,now,description):
        self.undos.append((identity(live),list(live['rect']),live['state']))
        self.last_action[key] = now
        self.actions.append(now)
        self.status = f"{live['app']}: {description}"
        self.audit.append(self.status)

    def animate(self,now=None):
        now = time.monotonic() if now is None else now
        for animation in list(self.animations):
            key = animation['key']
            rule = self.rule(key)
            live = self.backend.inspect(animation['identity'][0])
            allowed = self.options.get('window_control') and self.options.get('window_awareness') and rule['observe']!='ignore' and rule['control']!='none'
            resize = animation['target'][2]-animation['target'][0] != animation['origin'][2]-animation['origin'][0] or animation['target'][3]-animation['target'][1] != animation['origin'][3]-animation['origin'][1]
            if resize and rule['control']!='resize':
                allowed = False
            limit = min(24,rule['distance']) if rule['control']=='nudge' else rule['distance']
            if not allowed or not live or identity(live)!=animation['identity'] or live['state']!='normal' or limit<animation['distance'] or rule['size']<animation['size']:
                self.animations.remove(animation)
                continue
            t = max(0,min(1,(now-animation['start'])/animation['duration']))
            progress = (1-math.cos(t*math.pi*3))/2 if animation['shake'] else t*t*(3-2*t)
            rect = [round(a+(b-a)*progress) for a,b in zip(animation['origin'],animation['target'])]
            if not self.backend.position(live,rect):
                self.animations.remove(animation)
                continue
            if key in self.windows:
                self.windows[key]['rect'] = list(rect)
            if t>=1:
                self.animations.remove(animation)

    def undo(self):
        self.animations.clear()
        while self.undos:
            target,rect,state = self.undos.pop()
            live = self.backend.inspect(target[0])
            if live and identity(live) == target and (live['movable'] or live.get('playable',False)):
                if state != 'normal':
                    return self.backend.set_state(live,{'maximized':'maximize','minimized':'minimize'}[state])
                if live['state']!='normal' and not self.backend.set_state(live,'restore'):
                    continue
                left,top,right,bottom = live['work']
                width,height = min(rect[2]-rect[0],right-left),min(rect[3]-rect[1],bottom-top)
                x,y = max(left,min(right-width,rect[0])),max(top,min(bottom-height,rect[1]))
                return self.backend.position(live,[x,y,x+width,y+height])
        return False

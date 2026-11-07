"""Window metadata and bounded opt-in window play. Never sends input or closes apps."""
from collections import deque
import ctypes
from ctypes import wintypes as wt
import math
import os
import time

DEFAULTS = {'window_awareness':True,'window_control':False,'window_idle_seconds':3,
            'window_cooldown':30,'window_actions_per_minute':3,'window_rules':{},
            'physics':True,'gravity':900,'bounce':.62,'scuffles':True,'scuffle_cooldown':90}


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
    for key in ('window_awareness','window_control','physics','scuffles'):
        if type(value.get(key)) is bool:
            result[key] = value[key]
    for key,low,high in [('window_idle_seconds',0,120),('window_cooldown',5,600),
                         ('window_actions_per_minute',1,30),('gravity',100,2400),
                         ('bounce',0,.9),('scuffle_cooldown',20,600)]:
        result[key] = number(value.get(key),result[key],low,high)
    rules = value.get('window_rules')
    if isinstance(rules,dict):
        result['window_rules'] = {path.casefold():clean_rule(rule) for path,rule in list(rules.items())[:200]
                                  if isinstance(path,str) and 0 < len(path) < 1024}
    result['window_actions_per_minute'] = int(result['window_actions_per_minute'])
    return result


class NativeWindows:
    def __init__(self):
        self.available = os.name == 'nt'
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
        if not self.available or not self.user.IsWindowVisible(hwnd):
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
        movable = bool(path and started and state == 'normal' and not fullscreen and not self.user.GetWindow(hwnd,4) and klass.value != '#32770')
        return {'hwnd':int(hwnd),'pid':pid.value,'started':started,'path':path,'app':executable or klass.value,
                'title':title.value[:180],'class':klass.value,'rect':[rect.left,rect.top,rect.right,rect.bottom],
                'work':[info.work.left,info.work.top,info.work.right,info.work.bottom], 'state':state,
                'foreground':self.user.GetForegroundWindow() == hwnd,'movable':movable,'resizable':bool(style & 0x40000)}

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
        return records

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

    def update(self, records):
        self.last_update = time.monotonic()
        opened = []
        old = {identity(item):key for key,item in self.windows.items()}
        updated = {}
        for item in records:
            key = old.get(identity(item))
            if key is None:
                self.serial += 1
                key = 'w'+str(self.serial)
                if self.seeded:
                    opened.append(key)
                    self.events.append({'event':'opened','window':key,'record':dict(item),'time':time.monotonic()})
            elif item['foreground'] and not self.windows[key]['foreground']:
                self.events.append({'event':'focused','window':key,'record':dict(item),'time':time.monotonic()})
            updated[key] = dict(item,id=key)
        for key,item in self.windows.items():
            if key not in updated:
                self.events.append({'event':'closed','window':key,'record':item,'time':time.monotonic()})
                self.anchors.pop(key,None)
        self.windows = updated
        self.seeded = True
        return opened

    def rule(self, key, record=None):
        record = record or self.windows.get(key,{})
        return clean_rule(self.overrides.get(key,self.options.get('window_rules',{}).get(record.get('path',''),{})))

    def public(self, key, item):
        rule = self.rule(key,item)
        if rule['observe'] == 'ignore':
            return None
        data = {'id':key,'app':item['app'],'state':item['state'],'foreground':item['foreground']}
        if rule['observe'] == 'title':
            data.update(title=item['title'][:100],bounds=list(item['rect']),window_class=item['class'])
        if self.options.get('window_control') and item['movable'] and rule['control'] != 'none':
            data['allowed'] = {'control':rule['control'],'distance':min(rule['distance'],24) if rule['control']=='nudge' else rule['distance'],
                               'resize':rule['size'] if rule['control']=='resize' and item['resizable'] else 0}
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

    def apply(self, action, now=None):
        now = time.monotonic() if now is None else now
        if not self.options.get('window_awareness') or not self.options.get('window_control') or not isinstance(action,dict):
            return False
        key = action.get('target')
        if not isinstance(key,str) or key not in self.windows:
            return False
        record,rule = self.windows[key],self.rule(key)
        if rule['observe'] == 'ignore' or rule['control'] == 'none':
            return False
        if self.backend.idle_seconds() < self.options.get('window_idle_seconds',3):
            return False
        cooldown = max(rule['cooldown'],self.options.get('window_cooldown',30))
        if now-self.last_action.get(key,-1e9) < cooldown:
            return False
        while self.actions and now-self.actions[0] >= 60:
            self.actions.popleft()
        if len(self.actions) >= self.options.get('window_actions_per_minute',3):
            return False
        live = self.backend.inspect(record['hwnd'])
        if not live or identity(live) != identity(record) or not live['movable']:
            return False
        deltas = [action.get(key,0) for key in ('dx','dy','dw','dh')]
        if any(type(value) not in (int,float) or not math.isfinite(value) for value in deltas):
            return False
        dx,dy,dw,dh = deltas
        if (dw or dh) and (rule['control'] != 'resize' or not live['resizable']):
            return False
        anchor = self.anchors.get(key,live['rect'])
        limit = min(24,rule['distance']) if rule['control']=='nudge' else rule['distance']
        left,top,right,bottom = live['work']
        x,y,r,b = live['rect']
        if x < left or y < top or r > right or b > bottom:
            return False
        if (abs(x-anchor[0]) > limit or abs(y-anchor[1]) > limit or
            abs((r-x)-(anchor[2]-anchor[0])) > rule['size'] or abs((b-y)-(anchor[3]-anchor[1])) > rule['size']):
            anchor = list(live['rect'])
            self.anchors.pop(key,None)
        dx,dy = max(-limit,min(limit,dx)),max(-limit,min(limit,dy))
        dw,dh = max(-rule['size'],min(rule['size'],dw)),max(-rule['size'],min(rule['size'],dh))
        width = min(right-left,max(min(240,anchor[2]-anchor[0]),min(anchor[2]-anchor[0]+rule['size'],max(anchor[2]-anchor[0]-rule['size'],r-x+dw)))) if dw else r-x
        height = min(bottom-top,max(min(160,anchor[3]-anchor[1]),min(anchor[3]-anchor[1]+rule['size'],max(anchor[3]-anchor[1]-rule['size'],b-y+dh)))) if dh else b-y
        nx = min(right-width,max(left,min(anchor[0]+limit,max(anchor[0]-limit,x+dx))))
        ny = min(bottom-height,max(top,min(anchor[1]+limit,max(anchor[1]-limit,y+dy))))
        rect = [int(nx),int(ny),int(nx+width),int(ny+height)]
        if rect == live['rect']:
            return False
        if not self.backend.position(live,rect):
            return False
        self.anchors.setdefault(key,list(live['rect']))
        self.undos.append((identity(live),list(live['rect'])))
        self.last_action[key] = now
        self.actions.append(now)
        self.audit.append(f"{record['app']}: requested move/resize within {limit}px")
        return True

    def undo(self):
        while self.undos:
            target,rect = self.undos.pop()
            live = self.backend.inspect(target[0])
            if live and identity(live) == target and live['movable']:
                left,top,right,bottom = live['work']
                width,height = min(rect[2]-rect[0],right-left),min(rect[3]-rect[1],bottom-top)
                x,y = max(left,min(right-width,rect[0])),max(top,min(bottom-height,rect[1]))
                return self.backend.position(live,[x,y,x+width,y+height])
        return False

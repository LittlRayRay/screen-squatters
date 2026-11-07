"""Native integration: inspect/move/resize/undo ONLY a disposable child fixture window."""
import json
import ctypes
from ctypes import wintypes as wt
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from window_world import NativeWindows, WindowWorld, clean_options, clean_rule, chaos_options

CHILD = '''
import ctypes,json,tkinter as tk,threading,sys
from ctypes import wintypes as wt
root=tk.Tk()
root.title('Screen Squatters owned window fixture')
root.geometry('480x300+100+100')
tk.Label(root,text='Disposable window-control fixture. No personal data.',padx=30,pady=30).pack()
root.update()
user=ctypes.WinDLL('user32')
user.GetAncestor.argtypes,user.GetAncestor.restype=[wt.HWND,wt.UINT],wt.HWND
print(json.dumps({'hwnd':int(user.GetAncestor(root.winfo_id(),2))}),flush=True)
threading.Thread(target=lambda:(sys.stdin.readline(),root.after(0,root.destroy)),daemon=True).start()
root.mainloop()
'''


def wait_rect(backend,hwnd,predicate):
    deadline = time.monotonic()+3
    while time.monotonic()<deadline:
        record = backend.inspect(hwnd)
        if record and predicate(record['rect']):
            return record
        time.sleep(.04)
    raise AssertionError('Fixture window did not reach its expected position')


def wait_state(backend,hwnd,state):
    deadline = time.monotonic()+3
    while time.monotonic()<deadline:
        current = backend.inspect(hwnd)
        if current and current['state']==state:
            return current
        time.sleep(.04)
    raise AssertionError('Fixture did not reach its expected window state')


def main():
    backend = NativeWindows()
    backend.set_monitoring(True)
    user = backend.user
    user.PeekMessageW.argtypes,user.PeekMessageW.restype = [ctypes.POINTER(wt.MSG),wt.HWND,wt.UINT,wt.UINT,wt.UINT],wt.BOOL
    def pump_events():
        deadline = time.monotonic()+.35
        while time.monotonic()<deadline:
            message = wt.MSG()
            while user.PeekMessageW(ctypes.byref(message),None,0,0,1):
                pass
            time.sleep(.01)
        return backend.drain_events()
    process = subprocess.Popen([sys.executable,'-c',CHILD],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                               creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:
        info = json.loads(process.stdout.readline())
        initial_events = pump_events()
        record = backend.inspect(info['hwnd'])
        assert record and record['pid'] == process.pid, 'Only our child fixture can be targeted'
        assert any(kind in ('opened','focused') and item['pid']==process.pid for kind,item,_stamp in initial_events), 'Native WinEvent hooks must notice the fixture'
        assert any(item['hwnd'] == info['hwnd'] for item in backend.list_windows()), 'Native top-level enumeration must find the fixture'
        assert record['movable'] and record['resizable']
        original = list(record['rect'])
        options = clean_options({'window_idle_seconds':0,'window_cooldown':5})
        world = WindowWorld(options,backend)
        world.update([record])  # Never enumerate or move any other user's windows.
        key = next(iter(world.windows))
        assert not world.apply({'target':key,'dx':20},100), 'Default policy must forbid moves'
        options['window_control'] = True
        world.overrides[key] = clean_rule({'control':'nudge','distance':24,'cooldown':5})
        assert world.apply({'target':key,'dx':999},100)
        moved = wait_rect(backend,info['hwnd'],lambda rect:rect[0] == original[0]+24)
        assert moved['rect'][1:] == [original[1],original[2]+24,original[3]]
        assert world.undo()
        wait_rect(backend,info['hwnd'],lambda rect:rect == original)
        # All-window chaos must handle real maximized apps and visibly animate geometry.
        assert backend.set_state(record,'maximize')
        maximized = wait_state(backend,info['hwnd'],'maximized')
        chaos = WindowWorld(chaos_options({}),backend)
        chaos.update([maximized])
        chaos_key = next(iter(chaos.windows))
        assert not chaos.apply({'target':chaos_key,'kind':'close'},100)
        assert chaos.apply({'target':chaos_key,'dx':100},100)
        restored = wait_state(backend,info['hwnd'],'normal')
        start = time.monotonic()
        assert chaos.apply({'target':chaos_key,'dx':140,'dy':70,'dw':80},start,animated=True,shake=True)
        target = list(chaos.animations[0]['target'])
        while chaos.animations:
            chaos.animate()
            time.sleep(.025)
        wait_rect(backend,info['hwnd'],lambda rect:rect == target)
        assert target != restored['rect']
        assert chaos.undo()
        wait_rect(backend,info['hwnd'],lambda rect:rect == restored['rect'])
        assert chaos.undo()
        wait_state(backend,info['hwnd'],'maximized')
        backend.set_state(record,'restore')
        wait_state(backend,info['hwnd'],'normal')
        world.overrides[key] = clean_rule({'control':'resize','size':32,'cooldown':5})
        assert world.apply({'target':key,'dw':999,'dh':999},106)
        wait_rect(backend,info['hwnd'],lambda rect:rect == [original[0],original[1],original[2]+32,original[3]+32])
        assert world.undo()
        wait_rect(backend,info['hwnd'],lambda rect:rect == original)
        process.communicate(input='close\n',timeout=5)
        assert any(kind=='closed' and item['pid']==process.pid for kind,item,_stamp in pump_events()), 'Hook must report the fixture closing'
        print('Native window test passed: hooks, nudge, resize, all-window chaos, maximized restore, animated shake, undo/state recovery and closing rejection; only the disposable fixture was moved.')
    finally:
        if process.poll() is None:
            process.terminate()
        process.communicate(timeout=5)
        pump_events()
        backend.set_monitoring(False)


if __name__ == '__main__':
    main()

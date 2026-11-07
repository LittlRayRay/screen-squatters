"""Native integration: inspect/move/resize/undo ONLY a disposable child fixture window."""
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from window_world import NativeWindows, WindowWorld, clean_options, clean_rule

CHILD = '''
import ctypes,json,tkinter as tk
from ctypes import wintypes as wt
root=tk.Tk()
root.title('Screen Squatters owned window fixture')
root.geometry('480x300+100+100')
tk.Label(root,text='Disposable window-control fixture. No personal data.',padx=30,pady=30).pack()
root.update()
user=ctypes.WinDLL('user32')
user.GetAncestor.argtypes,user.GetAncestor.restype=[wt.HWND,wt.UINT],wt.HWND
print(json.dumps({'hwnd':int(user.GetAncestor(root.winfo_id(),2))}),flush=True)
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


def main():
    process = subprocess.Popen([sys.executable,'-c',CHILD],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                               creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:
        info = json.loads(process.stdout.readline())
        backend = NativeWindows()
        record = backend.inspect(info['hwnd'])
        assert record and record['pid'] == process.pid, 'Only our child fixture can be targeted'
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
        world.overrides[key] = clean_rule({'control':'resize','size':32,'cooldown':5})
        assert world.apply({'target':key,'dw':999,'dh':999},106)
        wait_rect(backend,info['hwnd'],lambda rect:rect == [original[0],original[1],original[2]+32,original[3]+32])
        assert world.undo()
        wait_rect(backend,info['hwnd'],lambda rect:rect == original)
        print('Native window test passed: own child metadata, default denial, bounded nudge, resize and undo; no screenshots or other app movement.')
    finally:
        if process.poll() is None:
            process.terminate()
        process.communicate(timeout=5)


if __name__ == '__main__':
    main()

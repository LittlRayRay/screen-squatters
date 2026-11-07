"""Render only this process's opaque fixture windows. No AI calls or personal data."""
import ctypes
from ctypes import wintypes as wt
from pathlib import Path
import sys
import struct
import tempfile
import time
import tkinter as tk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from desktop import ScreenSquatters, draw_friend
from screen import _libraries, png_rgb
from visuals import speech_bubble


def snapshot(window,path):
    window.attributes('-topmost',True)
    window.lift()
    for _ in range(15):
        window.update()
        time.sleep(.03)
    user,_gdi,_kernel = _libraries()
    user.GetAncestor.argtypes, user.GetAncestor.restype = [wt.HWND,wt.UINT],wt.HWND
    user.PrintWindow.argtypes, user.PrintWindow.restype = [wt.HWND,wt.HDC,wt.UINT],wt.BOOL
    hwnd = user.GetAncestor(window.winfo_id(),2)
    pid = wt.DWORD()
    user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    import os
    if pid.value != os.getpid():
        raise RuntimeError('Preview window is not owned by this process')
    title = ctypes.create_unicode_buffer(256)
    user.GetWindowTextW(hwnd,title,256)
    if title.value != window.title():
        raise RuntimeError('Unexpected preview window title')
    # Ask our own opaque window to paint itself; never copy pixels from the desktop.
    rect = wt.RECT()
    if not user.GetWindowRect(hwnd,ctypes.byref(rect)):
        raise RuntimeError('Could not locate preview')
    width,height = rect.right-rect.left,rect.bottom-rect.top
    assert 0 < width < 2000 and 0 < height < 2000
    dc = user.GetDC(hwnd)
    memory = _gdi.CreateCompatibleDC(dc)
    bitmap = _gdi.CreateCompatibleBitmap(dc,width,height)
    previous = _gdi.SelectObject(memory,bitmap)
    try:
        if not user.PrintWindow(hwnd,memory,2):
            raise RuntimeError('Own-window rendering failed')
        _gdi.SelectObject(memory,previous)
        header = struct.pack('<IiiHHIIiiII',40,width,-height,1,32,0,width*height*4,0,0,0,0)
        info = ctypes.create_string_buffer(header+b'\0'*12)
        pixels = ctypes.create_string_buffer(width*height*4)
        if _gdi.GetDIBits(memory,bitmap,0,height,pixels,info,0) != height:
            raise RuntimeError('Could not read preview render')
        rgb = bytearray(width*height*3)
        rgb[0::3],rgb[1::3],rgb[2::3] = pixels.raw[2::4],pixels.raw[1::4],pixels.raw[0::4]
        path.write_bytes(png_rgb(width,height,rgb))
    finally:
        _gdi.SelectObject(memory,previous)
        _gdi.DeleteObject(bitmap)
        _gdi.DeleteDC(memory)
        user.ReleaseDC(hwnd,dc)
    print(path)


def main():
    local = ROOT/'.local'
    local.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='social-preview-',dir=local) as directory:
        assert Path(directory).resolve().is_relative_to(local.resolve())
        root = tk.Tk()
        app = ScreenSquatters(root,data_dir=directory,port=0,timers=False)
        try:
            app.key = 'fixture-only'
            app.house.options['window_awareness'] = False
            app.stand_still.set(True)
            app.stand_still_changed()
            app.start_poker()
            while app.game.phase == 'preflop' or app.game.actor != 'You':
                legal = app.game.legal_actions(app.game.actor)
                app.game.act(app.game.actor,'check' if 'check' in legal else 'call')
            app.game.reveal('Rex')
            app.render_game()
            app.busy_name = 'Byte'
            root.withdraw()
            snapshot(app.game_window,local/'poker-preview.png')
            app.busy_name = None
            app.cancel_game()
            for win,_canvas in app.floaters.values():
                win.withdraw()
            preview = tk.Toplevel(root)
            preview.title('Screen Squatters | animation preview')
            preview.geometry('820x320')
            canvas = tk.Canvas(preview,width=820,height=320,bg='#171923',highlightthickness=0)
            canvas.pack()
            for name,x in [('Burt',105),('Byte',310),('Rex',515),('Mika',720)]:
                draw_friend(canvas,name,x,215,1.1,phase=25,walking=name=='Byte',talking=name=='Burt')
                canvas.create_text(x,288,text=name,fill='#f1edff',font=('Segoe UI',11,'bold'))
            speech_bubble(canvas,'Burt','Umm, wait, do I put these cards down now?',x=15,y=24,width=180)
            speech_bubble(canvas,'Rex','',x=425,y=24,width=180,color='#ffc18d',typing=True,phase=25)
            snapshot(preview,local/'speech-preview.png')
            preview.destroy()
            gallery = tk.Toplevel(root)
            gallery.title('Screen Squatters | compact and expanded house')
            gallery.configure(bg='#171923')
            gallery.geometry('620x390')
            tk.Label(gallery,text='click the small house to enter',bg='#171923',fg='#f1edff',font=('Segoe UI',13)).pack(pady=12)
            row = tk.Frame(gallery,bg='#171923')
            row.pack()
            for resident in app.world.residents.values():
                resident.mode = 'home'
            original_canvas,original_reveal = app.habitat.canvas,app.habitat.reveal
            for opened in (False,True):
                panel = tk.Canvas(row,width=360 if opened else 160,height=320 if opened else 143,bg='#171923',highlightthickness=0)
                panel.pack(side='left',padx=10)
                app.habitat.canvas = panel
                app.habitat.reveal = 1 if opened else 0
                app.habitat.draw_house()
                if not opened:
                    panel.scale('all',0,0,160/360,160/360)
            app.habitat.canvas,app.habitat.reveal = original_canvas,original_reveal
            snapshot(gallery,local/'house-preview.png')
            gallery.destroy()
            app.house.options['window_awareness'] = True
            app.windows.update([{'hwnd':0,'pid':0,'started':0,'path':'c:\\fixtures\\editor.exe','app':'editor.exe',
                                 'title':'Example document (fixture)','class':'Fixture','rect':[100,100,600,500],
                                 'work':[0,0,1600,900],'state':'normal','foreground':False,'movable':False,'resizable':False}])
            app.show_settings()
            app.settings.winfo_children()[0].select(3)
            snapshot(app.settings,local/'windows-settings-preview.png')
        finally:
            app.quit()


if __name__ == '__main__':
    main()

"""Windows foreground-window snapshots, encoded in memory without dependencies."""
import base64
import ctypes
from ctypes import wintypes as wt
import os
import struct
import zlib


def png_rgb(width, height, rgb):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    rows = b"".join(b"\0" + rgb[row * width * 3:(row + 1) * width * 3] for row in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 5)) + chunk(b"IEND", b""))


def _libraries():
    if os.name != "nt":
        raise RuntimeError("Screen awareness currently supports Windows only.")
    user = ctypes.WinDLL("user32", use_last_error=True)
    gdi = ctypes.WinDLL("gdi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = [
        (user, "GetForegroundWindow", [], wt.HWND),
        (user, "GetWindowThreadProcessId", [wt.HWND, ctypes.POINTER(wt.DWORD)], wt.DWORD),
        (user, "GetWindowTextW", [wt.HWND, wt.LPWSTR, ctypes.c_int], ctypes.c_int),
        (user, "GetWindowRect", [wt.HWND, ctypes.POINTER(wt.RECT)], wt.BOOL),
        (user, "GetDC", [wt.HWND], wt.HDC),
        (user, "ReleaseDC", [wt.HWND, wt.HDC], ctypes.c_int),
        (kernel, "OpenProcess", [wt.DWORD, wt.BOOL, wt.DWORD], wt.HANDLE),
        (kernel, "QueryFullProcessImageNameW", [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)], wt.BOOL),
        (kernel, "CloseHandle", [wt.HANDLE], wt.BOOL),
        (gdi, "CreateCompatibleDC", [wt.HDC], wt.HDC),
        (gdi, "CreateCompatibleBitmap", [wt.HDC, ctypes.c_int, ctypes.c_int], wt.HBITMAP),
        (gdi, "SelectObject", [wt.HDC, wt.HANDLE], wt.HANDLE),
        (gdi, "DeleteObject", [wt.HANDLE], wt.BOOL),
        (gdi, "DeleteDC", [wt.HDC], wt.BOOL),
        (gdi, "SetStretchBltMode", [wt.HDC, ctypes.c_int], ctypes.c_int),
        (gdi, "StretchBlt", [wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.DWORD], wt.BOOL),
        (gdi, "GetDIBits", [wt.HDC, wt.HBITMAP, wt.UINT, wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.UINT], ctypes.c_int),
    ]
    for lib, name, args, result in signatures:
        function = getattr(lib, name)
        function.argtypes, function.restype = args, result
    return user, gdi, kernel


def foreground():
    user, _gdi, kernel = _libraries()
    hwnd = user.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wt.DWORD()
    user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == os.getpid():
        return None
    title = ctypes.create_unicode_buffer(512)
    user.GetWindowTextW(hwnd, title, len(title))
    executable = ""
    process = kernel.OpenProcess(0x1000, False, pid.value)
    if process:
        try:
            path = ctypes.create_unicode_buffer(2048)
            length = wt.DWORD(len(path))
            if kernel.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(length)):
                executable = path.value.rsplit("\\", 1)[-1].lower()
        finally:
            kernel.CloseHandle(process)
    if executable in {"lockapp.exe", "logonui.exe", "credentialuibroker.exe"}:
        return None
    return {"hwnd": hwnd, "title": title.value, "executable": executable,
            "browser": executable in {"chrome.exe", "msedge.exe", "brave.exe", "firefox.exe", "opera.exe"}}


def capture_window(window):
    user, gdi, _kernel = _libraries()
    if user.GetForegroundWindow() != window["hwnd"]:
        return None
    rect = wt.RECT()
    if not user.GetWindowRect(window["hwnd"], ctypes.byref(rect)):
        raise RuntimeError("Couldn't locate the foreground window.")
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if not 0 < width <= 16000 or not 0 < height <= 16000:
        return None
    scale = min(1, 1024 / max(width, height))
    out_w, out_h = max(1, int(width * scale)), max(1, int(height * scale))
    dc = user.GetDC(None)
    memory = gdi.CreateCompatibleDC(dc)
    bitmap = gdi.CreateCompatibleBitmap(dc, out_w, out_h)
    if not dc or not memory or not bitmap:
        if bitmap:
            gdi.DeleteObject(bitmap)
        if memory:
            gdi.DeleteDC(memory)
        if dc:
            user.ReleaseDC(None, dc)
        raise RuntimeError("Windows could not create a screen snapshot.")
    previous = gdi.SelectObject(memory, bitmap)
    try:
        gdi.SetStretchBltMode(memory, 4)
        if not gdi.StretchBlt(memory, 0, 0, out_w, out_h, dc, rect.left, rect.top, width, height, 0x00CC0020):
            raise RuntimeError("Windows could not capture this window.")
        gdi.SelectObject(memory, previous)
        header = struct.pack("<IiiHHIIiiII", 40, out_w, -out_h, 1, 32, 0, out_w * out_h * 4, 0, 0, 0, 0)
        info = ctypes.create_string_buffer(header + b"\0" * 12)
        pixels = ctypes.create_string_buffer(out_w * out_h * 4)
        if gdi.GetDIBits(memory, bitmap, 0, out_h, pixels, info, 0) != out_h:
            raise RuntimeError("Windows could not read the screen snapshot.")
        raw = pixels.raw
        rgb = bytearray(out_w * out_h * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = raw[2::4], raw[1::4], raw[0::4]
        image = png_rgb(out_w, out_h, rgb)
        return {"kind": "image", "title": window["title"],
                "image": "data:image/png;base64," + base64.b64encode(image).decode("ascii")}
    finally:
        gdi.SelectObject(memory, previous)
        gdi.DeleteObject(bitmap)
        gdi.DeleteDC(memory)
        user.ReleaseDC(None, dc)


def browser_snapshot_matches(window, page, age):
    return bool(window and window["browser"] and page and age < 15
                and page.get("title") and page["title"].lower() in window["title"].lower())

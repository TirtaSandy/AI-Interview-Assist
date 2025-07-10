import ctypes
import sys
import platform
from ctypes import wintypes, c_long, c_longlong, c_void_p

if ctypes.sizeof(c_void_p) == ctypes.sizeof(c_long):
    LONG_PTR = c_long
else:
    LONG_PTR = c_longlong

WDA_NONE = 0x00000000
WDA_EXCLUDEFROMCAPTURE_WIN10 = 0x00000002
WDA_EXCLUDEFROMCAPTURE_WIN11 = 0x00000011

GWL_EXSTYLE = -20
GWL_STYLE   = -16
WS_CHILD    = 0x40000000

WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW  = 0x00040000
WS_EX_LAYERED    = 0x00080000

HWND_TOPMOST       = -1
HWND_NOTOPMOST     = -2
SWP_NOMOVE         = 0x0002
SWP_NOSIZE         = 0x0001
SWP_FRAMECHANGED   = 0x0020

LWA_ALPHA = 0x00000002

DWMWA_EXCLUDED_FROM_CAPTURE = 23
DWMWA_CLOAK = 13

class PrivacyEngine:
    def __init__(self, hwnd, logger):
        self.hwnd = hwnd
        self.logger = logger
        self.user32 = ctypes.windll.user32
        self.dwmapi = ctypes.windll.dwmapi

        self._hide_taskbar_flag = False
        self._hide_screen_flag = False

        self._setup_prototypes()

        try:
            style = self.user32.GetWindowLongPtrW(self.hwnd, GWL_STYLE)
            if style & WS_CHILD:
                parent = self.user32.GetParent(self.hwnd)
                if parent:
                    self.logger.debug(f"Child HWND {self.hwnd} -> using parent {parent}")
                    self.hwnd = parent
        except Exception as e:
            self.logger.error(f"Could not get parent window: {e}", exc_info=True)


    def _setup_prototypes(self):
        self.user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.GetWindowLongPtrW.restype  = LONG_PTR
        self.user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
        self.user32.SetWindowLongPtrW.restype  = LONG_PTR
        self.user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
        self.user32.SetWindowDisplayAffinity.restype  = wintypes.BOOL
        self.user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.DWORD, wintypes.BYTE, wintypes.DWORD]
        self.user32.SetLayeredWindowAttributes.restype  = wintypes.BOOL
        self.user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.INT, wintypes.INT, wintypes.INT, wintypes.INT, wintypes.UINT]
        self.user32.SetWindowPos.restype  = wintypes.BOOL
        self.dwmapi.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        self.dwmapi.DwmSetWindowAttribute.restype  = c_long
        self.user32.GetParent.argtypes = [wintypes.HWND]
        self.user32.GetParent.restype = wintypes.HWND

    def _get_affinity_flag(self):
        try:
            build = sys.getwindowsversion().build
        except Exception:
            build = int(platform.version().split('.')[-1])
        return WDA_EXCLUDEFROMCAPTURE_WIN11 if build >= 22000 else WDA_EXCLUDEFROMCAPTURE_WIN10

    def _normalize_window_styles(self):
        ex = self.user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
        new_ex = ex

        if self._hide_screen_flag and (ex & WS_EX_TOOLWINDOW):
            new_ex &= ~WS_EX_TOOLWINDOW
        if not self._hide_screen_flag and not self._hide_taskbar_flag and not (ex & WS_EX_APPWINDOW):
            new_ex |= WS_EX_APPWINDOW

        if new_ex != ex:
            self.user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, new_ex)
            self.user32.SetWindowPos(self.hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_FRAMECHANGED)
            self.logger.debug(f"Normalized styles: 0x{new_ex:08X}")

    def _ensure_layered(self):
        ex = self.user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
        if not (ex & WS_EX_LAYERED):
            self.user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED)
            self.user32.SetLayeredWindowAttributes(self.hwnd, 0, 255, LWA_ALPHA)
            self.user32.SetWindowPos(self.hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_FRAMECHANGED)
            self.logger.debug(f"Applied WS_EX_LAYERED to {self.hwnd}")

    def set_display_affinity(self, hide: bool):
        self._hide_screen_flag = hide
        affinity = self._get_affinity_flag() if hide else WDA_NONE
        if not (self._hide_screen_flag and self._hide_taskbar_flag):
            self._normalize_window_styles()
        self._ensure_layered()

        if self.user32.SetWindowDisplayAffinity(self.hwnd, affinity):
            state = 'hidden from' if hide else 'visible to'
            self.logger.info(f"Window is now {state} screen capture.")
        else:
            err = ctypes.get_last_error()
            self.logger.error(f"SetWindowDisplayAffinity failed (E={err})")

    def set_taskbar_visibility(self, hide: bool):
        self._hide_taskbar_flag = hide
        ex = self.user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
        new_ex = (ex | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW if hide else (ex & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
        if new_ex != ex:
            self.user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, new_ex)
            self.user32.SetWindowPos(self.hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_FRAMECHANGED)
            msg = 'hidden from' if hide else 'visible on'
            self.logger.info(f"Window is now {msg} the taskbar.")

    def set_always_on_top(self, on_top: bool):
        flag = HWND_TOPMOST if on_top else HWND_NOTOPMOST
        if self.user32.SetWindowPos(self.hwnd, flag, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE):
            state = 'enabled' if on_top else 'disabled'
            self.logger.info(f"Always-on-top {state}.")
        else:
            self.logger.error("Failed to set topmost.")

    def set_transparency(self, percent: float):
        try:
            alpha = int(255 * (percent / 100.0))
            ex = self.user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
            if not (ex & WS_EX_LAYERED):
                self.user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED)
            self.user32.SetLayeredWindowAttributes(self.hwnd, 0, alpha, LWA_ALPHA)
            self.logger.info(f"Transparency set to {percent:.0f}%.")
        except Exception as e:
            self.logger.error(f"Failed to set transparency: {e}")
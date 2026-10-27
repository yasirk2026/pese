"""Local Windows account binding. No environment variable can select another SID."""
import hashlib
import os


def account_binding():
    if os.name != "nt":
        # Source tests only; packaged desktop/isolated inference remain Windows.
        identity = "uid:" + str(os.getuid())
    else:
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        security = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        security.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
        security.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        security.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        token = wintypes.HANDLE()
        if not security.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
            raise OSError("Cannot establish local Windows account identity")
        try:
            size = wintypes.DWORD()
            security.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
            data = ctypes.create_string_buffer(size.value)
            if not security.GetTokenInformation(token, 1, data, size, ctypes.byref(size)):
                raise OSError("Cannot read local account identity")
            sid = ctypes.cast(data, ctypes.POINTER(ctypes.c_void_p))[0]
            text = wintypes.LPWSTR()
            if not security.ConvertSidToStringSidW(sid, ctypes.byref(text)):
                raise OSError("Cannot bind local account")
            try: identity = "windows-sid:" + text.value
            finally: kernel.LocalFree(ctypes.cast(text, ctypes.c_void_p))
        finally: kernel.CloseHandle(token)
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()

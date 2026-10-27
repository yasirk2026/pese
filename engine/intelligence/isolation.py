"""Bounded subprocess inference: timeout kills native hangs; no thread timeout."""
import json
import os
import subprocess
import threading
import time


def working_set(process):
    if os.name != "nt":
        return 0  # On other platforms a deployment-specific limiter is required.
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
             "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    if not ctypes.windll.psapi.GetProcessMemoryInfo(wintypes.HANDLE(int(process._handle)),
                                                  ctypes.byref(counters), counters.cb):
        raise OSError("Cannot inspect worker memory")
    return counters.PeakWorkingSetSize


def infer_process(command, payload, *, timeout_seconds=2.0, memory_bytes=256*1024*1024):
    if os.name != "nt":
        raise RuntimeError("No verified memory limiter for this platform")
    stop = threading.Event()
    exceeded = threading.Event()
    peak = [0]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    def monitor():
        while not stop.is_set() and process.poll() is None:
            try:
                peak[0] = max(peak[0], working_set(process))
                if peak[0] > memory_bytes:
                    exceeded.set()
                    process.kill()
                    return
            except OSError:
                if process.poll() is None:
                    exceeded.set()
                    process.kill()
                return
            stop.wait(.01)
    watcher = threading.Thread(target=monitor, daemon=True)
    watcher.start()
    start = time.perf_counter()
    try:
        data = json.dumps(payload, allow_nan=False).encode()
        if len(data) > 65536:
            raise ValueError("Inference input budget exceeded")
        output, _ = process.communicate(data, timeout=timeout_seconds)
        if exceeded.is_set() or process.returncode != 0 or len(output) > 65536:
            raise RuntimeError("Inference crashed or exceeded resource/output budget")
        result = json.loads(output)
        return result, {"latency_ms": (time.perf_counter()-start)*1000, "peak_bytes": peak[0]}
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate()
        stop.set()
        watcher.join(timeout=.1)

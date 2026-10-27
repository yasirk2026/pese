"""Killable resident inference and cancellable bounded training subprocesses."""
import json
import os
from pathlib import Path
from queue import Queue,Empty
import subprocess
import sys
from threading import Event,Lock,Thread
import time
from ..isolation import working_set


class ResidentInference:
    def __init__(self):
        self.process=None;self.key=None;self.lock=Lock();self.sequence=0;self.responses=Queue(maxsize=2)
        self.monitor_stop=Event();self.peak=0

    def close(self):
        process=self.process;self.process=None;self.key=None;self.monitor_stop.set()
        if process:
            if process.poll() is None:process.kill()
            try:process.wait(timeout=1)
            except subprocess.TimeoutExpired:pass
            for pipe in (process.stdin,process.stdout):
                if pipe:
                    try:pipe.close()
                    except OSError:pass

    def _start(self,key):
        self.close();self.responses=Queue(maxsize=2);self.monitor_stop=Event();self.peak=0
        process=subprocess.Popen([sys.executable,"-B","-u",str(Path(__file__).with_name("process_worker.py")),"inference"],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        self.process=process;self.key=key
        responses=self.responses;stop=self.monitor_stop
        def read():
            try:
                while not stop.is_set():
                    line=process.stdout.readline(65537)
                    if not line or len(line)>65536:break
                    responses.put_nowait(json.loads(line))
            except Exception:pass
            finally:
                try:responses.put_nowait({"worker_error":True})
                except Exception:pass
        def monitor():
            while not stop.wait(.01) and process.poll() is None:
                try:
                    self.peak=max(self.peak,working_set(process))
                    if self.peak>384*1024*1024:process.kill();return
                except OSError:return
        Thread(target=read,daemon=True).start();Thread(target=monitor,daemon=True).start()

    def __call__(self,command,payload):
        if os.name!="nt":raise RuntimeError("Windows memory isolation required")
        if not self.lock.acquire(blocking=False):raise RuntimeError("Inference worker busy")
        try:
            key=(payload["checkpoint_hash"],payload["tokenizer_hash"])
            cold=self.process is None or self.process.poll() is not None or key!=self.key
            if cold:self._start(key)
            self.sequence+=1;request={**payload,"request_id":self.sequence}
            raw=json.dumps(request,allow_nan=False).encode()+b"\n"
            if len(raw)>65536:raise ValueError("Input budget exceeded")
            start=time.perf_counter()
            self.process.stdin.write(raw);self.process.stdin.flush()
            response=self.responses.get(timeout=5 if cold else .15)
            if response.get("request_id")!=self.sequence or "scores" not in response:raise RuntimeError("Inference failed")
            return response["scores"],{"latency_ms":(time.perf_counter()-start)*1000,"cold":cold,"peak_bytes":self.peak,
                                       "execution":"resident_cpu"}
        except Exception:
            self.close();raise
        finally:self.lock.release()


def run_training(payload,cancel,timeout=180):
    operation=payload.get("operation","training")
    if operation not in ("training","evaluation"):raise ValueError("Unsupported local job operation")
    process=subprocess.Popen([sys.executable,"-B","-u",str(Path(__file__).with_name("process_worker.py")),operation],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    result=Queue(maxsize=1)
    def communicate():
        try:result.put(process.communicate(json.dumps(payload).encode()))
        except Exception:result.put((b"",None))
    Thread(target=communicate,daemon=True).start();start=time.monotonic();peak=0
    try:
        while process.poll() is None:
            if cancel.is_set():raise InterruptedError("Training cancelled")
            if time.monotonic()-start>timeout:raise TimeoutError("Training wall budget")
            peak=max(peak,working_set(process))
            if peak>512*1024*1024:raise MemoryError("Training memory budget")
            cancel.wait(.02)
        stdout,_=result.get(timeout=2)
        if process.returncode or len(stdout)>65536:raise RuntimeError("Training worker failed")
        response=json.loads(stdout);response["peak_bytes"]=peak;return response
    finally:
        if process.poll() is None:process.kill()
        try:process.wait(timeout=2)
        except subprocess.TimeoutExpired:pass

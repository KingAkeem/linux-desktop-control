"""Live failure tests using only disposable fixture windows and isolated test state."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from Xlib import X, XK, display
from Xlib.ext import xtest
from linux_desktop_control.server import Bridge
from linux_desktop_control.backend import DesktopError, runtime_dir

ROOT=Path(__file__).resolve().parents[1]


def fixture(path):
    process=subprocess.Popen([sys.executable,str(ROOT/'tests/fixture.py'),str(path)])
    for _ in range(100):
        if path.exists(): return process,json.loads(path.read_text())
        time.sleep(.05)
    raise AssertionError('Fixture failed')


def fails(fn, text):
    try: fn()
    except DesktopError as exc: assert text in str(exc), str(exc)
    else: raise AssertionError('Expected failure')


def run():
    with tempfile.TemporaryDirectory(prefix='desktop-safety-test-') as temp:
        os.environ['XDG_RUNTIME_DIR']=temp
        os.environ['XDG_STATE_HOME']=temp
        first,state=fixture(Path(temp)/'first.json')
        b=Bridge()
        second=None
        try:
            wid=state['window_id']
            b.call('start',{'task':'Test desktop safety in a disposable app','window_id':wid})
            other=Bridge()
            try: fails(lambda:other.call('start',{'task':'Test exclusivity','window_id':wid}),'already running')
            finally: other.close()
            # A failed second controller must not stop the first.
            assert b.call('status')['active']
            second,other_state=fixture(Path(temp)/'second.json')
            time.sleep(.2)
            fails(lambda:b.call('action',{'kind':'key','keys':['Return']}),'focus')
            second.terminate();second.wait();second=None
            b.call('select',{'window_id':wid})
            # Global emergency shortcut is exercised with synthetic test input.
            d=display.Display()
            codes=[d.keysym_to_keycode(k) for k in (XK.XK_Control_L,XK.XK_Alt_L,XK.XK_Escape)]
            for code in codes: xtest.fake_input(d,X.KeyPress,code)
            for code in reversed(codes): xtest.fake_input(d,X.KeyRelease,code)
            d.sync()
            time.sleep(.2)
            assert b.call('status')['stop_latched']
            fails(lambda:b.call('start',{'task':'Verify Stop cannot be bypassed','window_id':wid}),'latched')
            b.call('stop')
            d.close()
            print(json.dumps({'result':'passed','checks':['exclusive sessions','failed contender leaves owner intact','focus theft','global Stop hotkey','Stop latch cannot be reset by MCP']}))
        finally:
            b.close()
            for p in (first,second):
                if p and p.poll() is None: p.terminate();p.wait(timeout=3)


def crash_test():
    with tempfile.TemporaryDirectory(prefix='desktop-crash-test-') as temp:
        os.environ['XDG_RUNTIME_DIR']=temp
        os.environ['XDG_STATE_HOME']=temp
        first,state=fixture(Path(temp)/'fixture.json')
        b=Bridge()
        try:
            b.call('start',{'task':'Test crash recovery in disposable app','window_id':state['window_id']})
            shot=b.call('capture')['metadata']
            x,y,w,h=state['widgets']['area']
            errors=[]
            def drag():
                try: b.call('action',{'kind':'drag','capture_id':shot['capture_id'],'x':x+80,'y':y+70,'end_x':x+500,'end_y':y+70,'duration':3})
                except DesktopError as exc: errors.append(str(exc))
            thread=threading.Thread(target=drag)
            thread.start()
            time.sleep(.3)
            b.process.kill()
            thread.join(timeout=3)
            b.close()
            assert errors
            d=display.Display()
            assert not d.screen().root.query_pointer().mask & X.Button1Mask
            assert (runtime_dir()/'stopped').exists()
            d.close()
            print(json.dumps({'result':'passed','checks':['controller crash interrupts action','held mouse button released','crash latches Stop']}))
        finally:
            b.close()
            if first.poll() is None: first.terminate();first.wait(timeout=3)


if __name__=='__main__':
    run()
    crash_test()

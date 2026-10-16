"""Explicit live desktop test. Only sends input to this script's disposable GTK app."""
import asyncio
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]


async def run(state_path, env):
    params = StdioServerParameters(command=str(ROOT/'launch'), env=env)
    async with Client(params) as client:
        listed = await client.list_tools()
        names = [t.name for t in listed.tools]
        assert len(names)==7, names
        async def call(name, **args):
            response=await client.call_tool(name,args)
            if response.is_error:
                raise AssertionError(f'{name}: '+str(response.content))
            return response
        def data(response):
            return json.loads(next(c.text for c in response.content if c.type=='text'))
        def state(): return json.loads(state_path.read_text())
        await call('desktop_status')
        windows=data(await call('desktop_windows'))
        wid=state()['window_id']
        assert any(w['window_id']==wid for w in windows)
        await call('desktop_start',task='Verify the disposable desktop test app',window_id=wid)
        async def capture(): return data(await call('desktop_capture'))['metadata']
        async def at(widget, kind='click', **kw):
            meta=await capture()
            x,y,w,h=state()['widgets'][widget]
            return await call('desktop_action',kind=kind,capture_id=meta['capture_id'],x=x+w//2,y=y+h//2,**kw)
        await at('entry')
        await call('desktop_action',kind='type',text='Hello Desktop 123!')
        assert state()['text']=='Hello Desktop 123!', state()
        await call('desktop_action',kind='key',keys=['Ctrl','a'])
        await call('desktop_action',kind='paste',text='Linux desktop ✓ café 日本語')
        await asyncio.sleep(.15)
        assert state()['text']=='Linux desktop ✓ café 日本語', state()['text']
        await at('button')
        assert state()['clicks']>=1
        await at('button',kind='double_click')
        assert state()['double_clicks']>=1, state()['double_clicks']
        await at('scroll',kind='scroll',steps=5)
        assert state()['scroll']>0
        meta=await capture()
        x,y,w,h=state()['widgets']['area']
        await call('desktop_action',kind='drag',capture_id=meta['capture_id'],x=x+80,y=y+70,end_x=x+300,end_y=y+90,duration=.5)
        assert state()['drag_events']>0
        # Screenshot is an actual MCP ImageContent, not a path or a claim of success.
        shot=await call('desktop_capture')
        png=next(c.data for c in shot.content if c.type=='image')
        (ROOT/'output').mkdir(exist_ok=True)
        (ROOT/'output/live-demo.png').write_bytes(base64.b64decode(png))
        # Stop interrupts a long drag and releases its held button.
        meta=await capture()
        pending=asyncio.create_task(client.call_tool('desktop_action',{'kind':'drag','capture_id':meta['capture_id'],'x':x+80,'y':y+70,'end_x':x+500,'end_y':y+90,'duration':3}))
        await asyncio.sleep(.25)
        await call('desktop_stop')
        interrupted=await pending
        assert interrupted.is_error
        await asyncio.sleep(.15)
        assert not state()['drag_held']
        await call('desktop_start',task='Verify typing cancellation in the test app',window_id=wid)
        await at('entry')
        pending=asyncio.create_task(client.call_tool('desktop_action',{'kind':'type','text':'x'*180}))
        await asyncio.sleep(.25)
        await call('desktop_stop')
        interrupted=await pending
        assert interrupted.is_error
        await asyncio.sleep(.15)
        assert len(state()['text'])<180
        # Closing our fixture verifies target closure without affecting other apps.
        await call('desktop_start',task='Verify target closure handling',window_id=wid)
        await client.call_tool('desktop_action',{'kind':'key','keys':['Alt','F4']})
        # The window manager may finish closing after the action returns.
        for _ in range(40):
            remaining=data(await call('desktop_windows'))
            if not any(w['window_id']==wid for w in remaining):
                break
            await asyncio.sleep(.05)
        else:
            raise AssertionError('Fixture did not close within two seconds')
        closed=await client.call_tool('desktop_capture',{})
        assert closed.is_error
        await call('desktop_stop')
        print(json.dumps({'result':'passed','tools':names,'checks':['MCP discovery','MCP image content','focus','ASCII typing','Unicode clipboard paste','click','double click','scroll','drag','Stop during drag','Stop during typing','target closure']}))


def main():
    with tempfile.TemporaryDirectory(prefix='desktop-control-test-') as temporary:
        env=dict(os.environ)
        # Isolate only test control state. This never resets the production Stop latch.
        env['XDG_RUNTIME_DIR']=temporary
        env['XDG_STATE_HOME']=temporary
        state_path=Path(temporary)/'fixture.json'
        fixture=subprocess.Popen([sys.executable,str(ROOT/'tests/fixture.py'),str(state_path)],env=env)
        try:
            for _ in range(100):
                if state_path.exists(): break
                time.sleep(.05)
            assert state_path.exists(),'Fixture failed to start'
            asyncio.run(run(state_path,env))
        finally:
            if fixture.poll() is None:
                fixture.terminate()
                fixture.wait(timeout=3)


if __name__=='__main__': main()

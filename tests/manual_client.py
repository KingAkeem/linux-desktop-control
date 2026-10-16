"""Interactive MCP client for a single, explicitly selected visible application.

Screenshots are saved only by this diagnostic client, not by the MCP server.
"""
import asyncio
import base64
import json
import os
from pathlib import Path
import sys
from mcp import Client, StdioServerParameters

ROOT=Path(__file__).resolve().parents[1]


async def main():
    title=sys.argv[1]
    output=ROOT/'output/manual'
    output.mkdir(parents=True,exist_ok=True)
    async with Client(StdioServerParameters(command=str(ROOT/'launch'),env=dict(os.environ))) as client:
        async def call(name,args):
            response=await client.call_tool(name,args)
            text=next((c.text for c in response.content if c.type=='text'),'{}')
            if response.is_error:
                print(json.dumps({'error':text}),flush=True)
                return None
            value=json.loads(text)
            for c in response.content:
                if c.type=='image':
                    path=output/(value.get('metadata',{}).get('capture_id','capture')+'.png')
                    path.write_bytes(base64.b64decode(c.data))
                    value['image_path']=str(path)
            print(json.dumps({'tool':name,'result':value}),flush=True)
            return value
        response=await client.call_tool('desktop_windows',{})
        windows=json.loads(next(c.text for c in response.content if c.type=='text'))
        matches=[w for w in windows if w['title']==title]
        if len(matches)!=1:
            print(json.dumps({'error':'Expected exactly one matching window','match_count':len(matches)}),flush=True)
            return
        wid=matches[0]['window_id']
        started=await call('desktop_start',{'task':'Inspect the explicitly selected application with the interactive test client','window_id':wid})
        if started is None: return
        await call('desktop_capture',{})
        print('Ready for JSON: {"tool":"desktop_action","args":{"kind":"key","keys":["Escape"]}} or quit',flush=True)
        try:
            while True:
                line=await asyncio.to_thread(sys.stdin.readline)
                if not line or line.strip()=='quit':break
                req=json.loads(line)
                await call(req['tool'],req.get('args',{}))
        finally:
            await call('desktop_stop',{})


if __name__=='__main__':asyncio.run(main())

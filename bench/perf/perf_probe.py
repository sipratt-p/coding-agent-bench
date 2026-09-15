#!/usr/bin/env python3
"""Decode + prefill + concurrency probe for an OpenAI-compatible endpoint.
Usage: perf_probe.py <base_url> <model> [tag]
Prints: single-stream decode t/s, prefill t/s at ~32k, aggregate at C=4/16.
"""
import json,sys,time,urllib.request
from concurrent.futures import ThreadPoolExecutor
BASE=sys.argv[1]; MODEL=sys.argv[2]; TAG=sys.argv[3] if len(sys.argv)>3 else MODEL
URL=BASE.rstrip("/")+"/chat/completions"
def call(prompt,max_tokens,ignore_eos=False):
    b={"model":MODEL,"messages":[{"role":"user","content":prompt}],"max_tokens":max_tokens,"temperature":1.0}
    if ignore_eos: b["ignore_eos"]=True
    r=urllib.request.Request(URL,data=json.dumps(b).encode(),headers={"Content-Type":"application/json"})
    t=time.time(); d=json.loads(urllib.request.urlopen(r,timeout=3600).read()); dt=time.time()-t
    return d["usage"],dt
print(f"== {TAG}")
u,dt=call("Say OK",16); print(f"  warmup ok ({u['completion_tokens']} tok)")
u,dt=call("Count slowly from 1 to 200, one number per line.",512,True)
print(f"  decode single: {u['completion_tokens']/dt:.1f} tok/s ({u['completion_tokens']} tok in {dt:.1f}s)")
long="\n".join(f"Line {i}: the quick brown fox #{i} jumps over the lazy dog and files a report." for i in range(1700))
u,dt=call(long+"\n\nReply with just the word OK.",8)
print(f"  prefill: {u['prompt_tokens']} tok in {dt:.1f}s = {u['prompt_tokens']/dt:.0f} tok/s")
for C in (4,16):
    t=time.time()
    with ThreadPoolExecutor(C) as ex:
        rs=list(ex.map(lambda _: call("Count slowly from 1 to 200, one number per line.",512,True),range(C)))
    dt=time.time()-t; tot=sum(u["completion_tokens"] for u,_ in rs)
    print(f"  C={C}: {tot/dt:.0f} tok/s aggregate ({tot/dt/C:.1f}/req)")

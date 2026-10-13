import json,struct,re,collections,statistics as st
F=23.976
x=open('drp/x/SeqContainer/4a3ed434-36d5-4c72-b247-201fe1c5066b.xml').read()
fps={}
for n,h in re.findall(r'<Name>([^<]*)</Name>(?:(?!</Sm2Ti).)*?<MediaFrameRate>([0-9a-f]*)<',x,re.S):
    if len(h)>=16: fps[n]=round(struct.unpack('<d',bytes.fromhex(h[:16]))[0],3)
T=json.load(open('timeline.json'))
tr={t['kind'][0]+str(t['idx']):t['clips'] for t in T}
def tc(f):
    s=(f-86400)/F; return f"{int(s//3600)}:{int(s%3600//60):02d}:{s%60:05.2f}"
R=[(7*3600+45*60,7*3600+46*60+30),(7*3600+48*60,7*3600+51*60),(7*3600+51*60+30,7*3600+55*60+30),(7*3600+56*60,7*3600+59*60+30),(8*3600,8*3600+2*60+30),(8*3600+3*60,8*3600+5*60+30)]
allshots=[]
for i,(a,b) in enumerate(R):
    a=86400+a*F; b=86400+b*F
    print(f"\n######## EDIT {i+1}")
    for k in ['A2','A1','A3','A4']:
        for c in tr[k]:
            if a<=c['start']<b and k=='A2': print('  MUSIC',k,c['name'],tc(c['start']),f"{c['dur']/F:.1f}s src_in={int(c['inp'] or 0)/F/60:.2f}min" )
    # visible shot timeline: topmost of V5? no V5 = adjustment. visible = highest of V4,V3,V1
    ev=set()
    for k in ['V1','V3','V4','V5']:
        for c in tr[k]:
            if a<=c['start']<b: ev.add(c['start']); ev.add(c['start']+c['dur'])
    ev=sorted(ev); shots=[]
    for s,e in zip(ev,ev[1:]):
        m=(s+e)/2; top=None
        for k in ['V4','V3','V1']:
            for c in tr[k]:
                if c['start']<=m<c['start']+c['dur']: top=(k,c['name']); break
            if top: break
        adj=any(c['start']<=m<c['start']+c['dur'] for c in tr['V5'])
        if top:
            if shots and shots[-1][2]==top and shots[-1][1]==s: shots[-1][1]=e; shots[-1][3]|=adj
            else: shots.append([s,e,top,adj])
        else: shots.append([s,e,('GAP',''),adj])
    for s,e,top,adj in shots:
        print(f"  {tc(s)} {(e-s)/F:5.2f}s {top[0]:3} {top[1]:12} fps={fps.get(top[1])} {'FX' if adj else ''}")
    d=[(e-s)/F for s,e,t,_ in shots if t[0]!='GAP']; allshots+=d
    print(f"  shots={len(d)} total={sum(d):.1f}s median={st.median(d):.2f}s")
print("\nALL median",st.median(allshots),"mean",st.mean(allshots),"quantiles",[round(q,2) for q in st.quantiles(allshots,n=10)])

import sys, struct, xml.etree.ElementTree as ET, collections, json
root = ET.fromstring(open(sys.argv[1],encoding="utf-8").read().replace("::","__").encode())
def fr(h):
    try: return struct.unpack('>d', bytes.fromhex(h[:16]))[0]
    except: return None
out=[]
for kind in ['VideoTrackVec','AudioTrackVec']:
    vec=root.find(kind)
    for ti,el in enumerate(vec.findall('Element')):
        tr=el.find('Sm2TiTrack')
        items=tr.find('Items')
        clips=[]
        for it in items.findall('Element'):
            c=it[0]
            g=lambda t:(c.find(t).text if c.find(t) is not None else None)
            clips.append(dict(type=c.tag,name=g('Name'),start=int(g('Start') or 0),dur=int(g('Duration') or 0),
              inp=g('In'),path=g('MediaFilePath'),fps=fr(g('MediaFrameRate') or ''),
              effects=bool(c.find('EffectFiltersBA') is not None and c.find('EffectFiltersBA').text)))
        out.append(dict(kind=kind,idx=ti+1,clips=sorted(clips,key=lambda x:x['start'])))
json.dump(out,open(sys.argv[2],'w'),indent=1)
for t in out:
    cl=t['clips']
    types=collections.Counter(c['type'] for c in cl)
    print(t['kind'],t['idx'],len(cl),dict(types), 'span',(cl[0]['start'],cl[-1]['start']+cl[-1]['dur']) if cl else '')

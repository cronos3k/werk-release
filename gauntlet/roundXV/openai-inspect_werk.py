#!/usr/bin/env python3
"""Inspect, verify, list, and extract crate-v1.werk.

Rules are transcribed only from MANIFEST.json and spec/ in the package.
No source or binary from loaders/ is imported or executed.
"""
from __future__ import annotations
import argparse, binascii, hashlib, json, time, zipfile
from pathlib import Path
from typing import Any

class WerkError(Exception): pass

def strict_json(raw: bytes, name: str) -> Any:
    if raw.startswith(b'\xef\xbb\xbf'): raise WerkError(f'{name}: forbidden JSON BOM')
    def hook(pairs):
        out={}
        for k,v in pairs:
            if k in out: raise WerkError(f'{name}: duplicate JSON key {k!r}')
            out[k]=v
        return out
    def bad(v): raise WerkError(f'{name}: non-finite JSON number {v}')
    try: return json.loads(raw.decode('utf-8'), object_pairs_hook=hook, parse_constant=bad)
    except (UnicodeDecodeError,json.JSONDecodeError) as e: raise WerkError(f'{name}: bad UTF-8 JSON: {e}') from e

def canon(v):
    return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def safe_name(n):
    p=n.split('/')
    return bool(n) and not n.startswith(('/','\\')) and '\\' not in n and '..' not in p and ':' not in p[0]

# Ed25519 verification, from spec/MINI-SPECS.md section 12.
P=2**255-19
D=(-121665*pow(121666,P-2,P))%P
L=2**252+27742317777372353535851937790883648493
I=pow(2,(P-1)//4,P)
ID=(0,1,1,0)
def decode_point(s):
    if len(s)!=32: raise ValueError('point length')
    q=int.from_bytes(s,'little'); sign=q>>255; y=q&((1<<255)-1)
    if y>=P: raise ValueError('non-canonical y')
    y2=y*y%P; u=(y2-1)%P; v=(D*y2+1)%P
    x=u*pow(v,3,P)*pow(u*pow(v,7,P)%P,(P-5)//8,P)%P
    if v*x*x%P==(-u)%P: x=x*I%P
    if v*x*x%P!=u or (x==0 and sign): raise ValueError('bad point')
    if (x&1)!=sign: x=P-x
    return x,y,1,x*y%P
B=decode_point((4*pow(5,P-2,P)%P).to_bytes(32,'little'))
def padd(a,b):
    x1,y1,z1,t1=a; x2,y2,z2,t2=b
    aa=(y1-x1)*(y2-x2)%P; bb=(y1+x1)*(y2+x2)%P
    c=t1*(2*D)*t2%P; d=z1*2*z2%P
    e=(bb-aa)%P; f=(d-c)%P; g=(d+c)%P; h=(bb+aa)%P
    return e*f%P,g*h%P,f*g%P,e*h%P
def smul(n,p):
    r=ID
    while n:
        if n&1: r=padd(r,p)
        p=padd(p,p); n>>=1
    return r
def peq(a,b): return a[0]*b[2]%P==b[0]*a[2]%P and a[1]*b[2]%P==b[1]*a[2]%P
def edverify(pk,msg,sig):
    if len(pk)!=32 or len(sig)!=64: return False
    rb=sig[:32]; s=int.from_bytes(sig[32:],'little')
    if s>=L: return False
    try: a=decode_point(pk); r=decode_point(rb)
    except ValueError: return False
    k=int.from_bytes(hashlib.sha512(rb+pk+msg).digest(),'little')%L
    return peq(smul(8,smul(s,B)),smul(8,padd(r,smul(k,a))))
def crypto_selftest():
    assert sha(b'abc')=='ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    pk=bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
    sig=bytes.fromhex('e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b')
    assert edverify(pk,b'',sig)

class Audit:
    def __init__(self): self.checks=[]; self.errors=[]
    def check(self,cat,item,declared,computed):
        ok=declared==computed
        self.checks.append(dict(category=cat,item=item,declared=declared,computed=computed,ok=ok))
        if not ok: self.errors.append(f'{cat}: {item}: declared {declared!r}, computed {computed!r}')
        return ok
    def require(self,ok,msg):
        if not ok: self.errors.append(msg)

CONVENTIONS={
'endianness':'le','units_per_meter':1.0,'length_unit':'metre','angle_unit':'radian',
'time_unit':'second','mass_unit':'kilogram','up_axis':'y','forward_axis':'-z',
'right_axis':'+x','handedness':'right','winding':'ccw','quat_order':'wxyz',
'oct_encoding_pole':'y','sh_l1_order':['dc','y','z','x'],'color_space_default':'srgb',
'uv_origin':'top-left','alignment_bytes':16,'text_encoding':'utf-8','id_case':'kebab-case',
'hash_algorithm':'sha256','signature_algorithm':'ed25519'}

def count_hash_fields(v, keys={'sha256','input_hash','spec_sha256'}):
    if isinstance(v,dict): return sum((1 if k in keys else 0)+count_hash_fields(x,keys) for k,x in v.items())
    if isinstance(v,list): return sum(count_hash_fields(x,keys) for x in v)
    return 0

def active(node,audit):
    found=[v for v in node.get('versions',[]) if v.get('v')==node.get('active')]
    audit.require(len(found)==1,f"node {node.get('node_id')!r} has invalid active version")
    return found[0] if len(found)==1 else None

def verify_signature(raw,manifest_raw,a):
    d=strict_json(raw,'SIGNATURE.json'); actual=sha(manifest_raw); handled=0; valid=True
    valid &= a.check('signature-manifest-sha256','top-level',d.get('manifest_sha256'),actual); handled+=1
    chain=d.get('chain',[])
    a.require(isinstance(chain,list) and bool(chain),'signature chain missing/empty')
    prev=None
    for i,e in enumerate(chain):
        a.require(e.get('index')==i,f'signature index mismatch at {i}')
        expected='0'*64 if prev is None else sha(prev.encode())
        valid &= a.check('signature-prev-entry-sha256',f'chain[{i}]',e.get('prev_entry_sha256'),expected); handled+=1
        if i==len(chain)-1:
            valid &= a.check('signature-manifest-sha256',f'chain[{i}]',e.get('manifest_sha256'),actual)
        handled+=1
        signer=e.get('signer',{})
        msg='\n'.join(['werk-sig/1',str(e.get('manifest_sha256','')),str(e.get('prev_entry_sha256','')),
                       str(e.get('signed_at','')),str(signer.get('uri','')),str(signer.get('kind',''))]).encode()
        try: ok=edverify(bytes.fromhex(e['public_key']),msg,bytes.fromhex(e['signature']))
        except (KeyError,TypeError,ValueError): ok=False
        valid &= a.check('ed25519-signature',f'chain[{i}]',True,ok)
        prev=e.get('signature','')
    if chain: a.require(d.get('manifest_sha256')==chain[-1].get('manifest_sha256'),'signature anchors disagree')
    discovered=count_hash_fields(d,{'manifest_sha256','prev_entry_sha256','sha256'})
    a.require(discovered==handled,f'signature hash coverage {handled}/{discovered}')
    return ('signed-and-valid' if valid and discovered==handled else 'present-and-invalid'),handled

def make_listing(m,order):
    lines=['# Container contents and node graph','',
      f"Entity: **{m['entity']['name']}** — {m['entity']['summary']}",'',
      f"Profile: `{m['profile']}`. Archive entries: {len(order)}.",'',
      'Meanings are the active versions’ own notes. `requires` is a hard dependency; `enhances` adds a feature without making its target mandatory.','',
      f"Primary mesh node: `{m.get('primary',{}).get('mesh')}`. Primary sound node: `{m.get('primary',{}).get('sound')}`.",'','## Nodes','']
    for n in m['nodes']:
        v=next((x for x in n['versions'] if x.get('v')==n.get('active')),None)
        lines += [f"### `{n['node_id']}` — `{n['type']}`",'']
        if v is None: lines += ['Invalid active version.','']; continue
        lines += [f"Active version {v['v']}. Meaning: {v['note']}",'','Files:','']
        for f in v['files']:
            meta=', '.join(x for x in (f.get('role'),f.get('media_type')) if x)
            suffix=f'; {meta}' if meta else ''
            lines.append(f"- `{f['path']}` — {f['size']} bytes; sha256 `{f['sha256']}`{suffix}")
        lines += ['','Edges:','']
        if n.get('edges'):
            for e in n['edges']:
                role=f" ({e['role']})" if e.get('role') else ''
                lines.append(f"- `{e['kind']}`{role} → `{e['to']}`")
        else: lines.append('- None.')
        lines.append('')
    lines += ['## Physical archive order','']+[f'{i}. `{name}`' for i,name in enumerate(order,1)]+['']
    return '\n'.join(lines)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('container',nargs='?',default='crate-v1.werk')
    ap.add_argument('--mesh-out',default='primary_mesh.glb'); ap.add_argument('--sound-out',default='primary_sound.wav')
    ap.add_argument('--listing-out',default='CONTENTS.md'); ap.add_argument('--audit-out',default='verification.json')
    args=ap.parse_args(); t0=time.perf_counter(); crypto_selftest(); a=Audit()
    with zipfile.ZipFile(args.container,'r') as z:
        infos=z.infolist(); a.require(len({i.filename for i in infos})==len(infos),'duplicate archive name')
        payload={}
        for info in infos:
            a.require(safe_name(info.filename),f'unsafe archive path {info.filename!r}')
            a.require(info.compress_type==zipfile.ZIP_STORED,f'non-store entry {info.filename}')
            a.require(not(info.flag_bits&8),f'data descriptor on {info.filename}')
            try: b=z.read(info)
            except (zipfile.BadZipFile,RuntimeError) as e: a.errors.append(f'archive read failure {info.filename}: {e}'); continue
            payload[info.filename]=b
            a.check('archive-crc32',info.filename,f'{info.CRC:08x}',f'{binascii.crc32(b)&0xffffffff:08x}')
    t1=time.perf_counter()
    if 'MANIFEST.json' not in payload: raise WerkError('MANIFEST.json missing')
    rawm=payload['MANIFEST.json']; m=strict_json(rawm,'MANIFEST.json'); handled=0
    a.require(m.get('werk',{}).get('major')==1,'unsupported werk major')
    a.require(m.get('profile')=='3d-entity/1','unsupported profile')
    a.require(m.get('container',{}).get('zip_compression')=='store','manifest compression is not store')
    for k,v in CONVENTIONS.items(): a.check('convention',k,m.get('conventions',{}).get(k),v)
    nodes=m.get('nodes',[]); ids=[]; owners={}; declared=set(); specpaths=set()
    for ni,n in enumerate(nodes):
        nid=n.get('node_id'); a.require(isinstance(nid,str) and nid not in ids,f'duplicate/invalid node {nid!r}'); ids.append(nid)
        seen=set()
        for vi,v in enumerate(n.get('versions',[])):
            vn=v.get('v'); a.require(isinstance(vn,int) and vn not in seen,f'duplicate/invalid version in {nid}'); seen.add(vn)
            for fi,f in enumerate(v.get('files',[])):
                p=f.get('path'); label=f'nodes[{ni}].versions[{vi}].files[{fi}] {p}'; handled+=1
                if not isinstance(p,str) or p not in payload: a.errors.append(f'declared file missing: {p}'); continue
                a.require(owners.get(p) in (None,nid),f'{p} owned by two nodes'); owners[p]=nid; declared.add(p)
                if p.startswith('spec/'): specpaths.add(p)
                a.check('manifest-file-size',label,f.get('size'),len(payload[p]))
                a.check('manifest-file-sha256',label,f.get('sha256'),sha(payload[p]))
            if 'input_hash' in v:
                handled+=1; h=hashlib.sha256(); ok=True
                for p in v.get('input_files',[]):
                    if p not in payload: a.errors.append(f'input_hash file missing: {p}'); ok=False; break
                    h.update(hashlib.sha256(payload[p]).digest())
                if ok: h.update(canon(v.get('input_params',{}))); a.check('input-hash',f'{nid} v{vn}',v['input_hash'],h.hexdigest())
            if 'spec_sha256' in v:
                handled+=1; h=hashlib.sha256(); paths=[]
                for mapname in ('schemas','layouts'):
                    p=m.get(mapname,{}).get(n.get('type'))
                    if p: paths.append(p)
                for p in sorted(set(paths),key=lambda x:x.encode()): h.update(p.encode()+b'\n'+hashlib.sha256(payload[p]).digest()+b'\n')
                a.check('version-spec-sha256',f'{nid} v{vn}',v['spec_sha256'],h.hexdigest())
        active(n,a)
    idset=set(ids)
    for n in nodes:
        for e in n.get('edges',[]):
            a.require(e.get('kind') in ('requires','enhances'),f"bad edge kind from {n.get('node_id')}")
            a.require(e.get('to') in idset,f"edge target missing: {e.get('to')}")
    actual=set(payload)-{'MANIFEST.json','SIGNATURE.json'}
    a.require(actual==declared,f'reachability mismatch undeclared={sorted(actual-declared)} missing={sorted(declared-actual)}')
    lic=m.get('license',{}); lp=lic.get('file'); handled+=1
    if lp in payload: a.check('license-sha256',lp,lic.get('sha256'),sha(payload[lp]))
    else: a.errors.append('license missing')
    h=hashlib.sha256(); handled+=1
    for p in sorted(specpaths,key=lambda x:x.encode()): h.update(p.encode()+b'\n'+hashlib.sha256(payload[p]).digest()+b'\n')
    a.check('global-spec-sha256','spec/ aggregate',m.get('spec_sha256'),h.hexdigest())
    discovered=count_hash_fields(m); a.require(handled==discovered,f'manifest hash coverage {handled}/{discovered}')
    provenance_hashes=0
    for n in nodes:
        if n.get('type')!='core.provenance': continue
        v=active(n,a)
        if not v: continue
        for f in v.get('files',[]):
            d=strict_json(payload[f['path']],f['path'])
            for ri,run in enumerate(d.get('runs',[])):
                for ci,c in enumerate(run.get('consumed',[])):
                    p=c.get('path'); provenance_hashes+=1
                    if p in payload: a.check('provenance-consumed-sha256',f'runs[{ri}].consumed[{ci}] {p}',c.get('sha256'),sha(payload[p]))
                    else: a.errors.append(f'provenance path missing: {p}')
    sigstate='absent'; sighashes=0
    if 'SIGNATURE.json' in payload: sigstate,sighashes=verify_signature(payload['SIGNATURE.json'],rawm,a)
    t2=time.perf_counter()
    byid={n['node_id']:n for n in nodes}; prim=m.get('primary',{}); extracted={}
    mesh=byid.get(prim.get('mesh')); sound=byid.get(prim.get('sound'))
    a.require(mesh is not None,'primary mesh node missing'); a.require(sound is not None,'primary sound node missing')
    if mesh:
        v=active(mesh,a); fs=[] if not v else [f for f in v['files'] if str(f.get('path','')).lower().endswith('.glb')]
        a.require(len(fs)==1,'primary mesh does not have exactly one GLB')
        if len(fs)==1 and sha(payload[fs[0]['path']])==fs[0]['sha256']:
            Path(args.mesh_out).write_bytes(payload[fs[0]['path']]); extracted['mesh']=dict(node_id=mesh['node_id'],source_path=fs[0]['path'],output_path=args.mesh_out,declared_sha256=fs[0]['sha256'],computed_sha256=sha(payload[fs[0]['path']]),size=len(payload[fs[0]['path']]))
    if sound:
        v=active(sound,a); fs=[] if not v else [f for f in v['files'] if f.get('role')=='best' and f.get('media_type')=='audio/wav']
        a.require(len(fs)==1,'primary sound does not have exactly one best WAV')
        if len(fs)==1 and sha(payload[fs[0]['path']])==fs[0]['sha256']:
            Path(args.sound_out).write_bytes(payload[fs[0]['path']]); extracted['sound']=dict(node_id=sound['node_id'],source_path=fs[0]['path'],output_path=args.sound_out,declared_sha256=fs[0]['sha256'],computed_sha256=sha(payload[fs[0]['path']]),size=len(payload[fs[0]['path']]))
    Path(args.listing_out).write_text(make_listing(m,[i.filename for i in infos]),encoding='utf-8',newline='\n')
    t3=time.perf_counter(); counts={}
    for c in a.checks:
        q=counts.setdefault(c['category'],{'checked':0,'passed':0}); q['checked']+=1; q['passed']+=int(c['ok'])
    result={'success':not a.errors and set(extracted)=={'mesh','sound'},'signature_state':sigstate,'archive_entries':len(infos),'node_count':len(nodes),
      'current_package_sha256_declarations':handled+sighashes+provenance_hashes,'manifest_hash_declarations_discovered':discovered,'manifest_hash_declarations_handled':handled,
      'signature_hash_declarations_handled':sighashes,'payload_hash_declarations_handled':provenance_hashes,'archive_read_order':[i.filename for i in infos],
      'category_counts':counts,'errors':a.errors,'extraction':extracted,'timing_seconds':{'open_read_crc':t1-t0,'verify_graph_hashes_signature':t2-t1,'extract_and_write':t3-t2,'total':t3-t0},'checks':a.checks}
    Path(args.audit_out).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    print(f"Entity: {m['entity']['name']} ({len(nodes)} nodes, {len(infos)} entries)"); print(f'Signature: {sigstate}')
    for k,v in sorted(counts.items()): print(f"{k}: {v['passed']}/{v['checked']} passed")
    print('All structural checks and declared current-package hashes passed.' if not a.errors else 'ERRORS:\n- '+'\n- '.join(a.errors))
    for k,v in extracted.items(): print(f"Extracted {k}: {v['source_path']} -> {v['output_path']} sha256={v['computed_sha256']}")
    print(f'Node listing: {args.listing_out}\nMachine-readable audit: {args.audit_out}')
    return 0 if result['success'] else 1

if __name__=='__main__':
    try: raise SystemExit(main())
    except (WerkError,zipfile.BadZipFile,AssertionError) as e: print(f'container failure: {e}'); raise SystemExit(2)

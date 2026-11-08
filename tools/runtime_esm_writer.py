"""Minimal runtime-only Bethesda ESM text patch writer, no legacy dataset deps.

Only targets fields verified by exact original bytes, FormID, record type,
subrecord occurrence, and EditorID. All GRUP nesting, FormIDs, record flags,
and untouched subrecords stay intact. Used only on user-owned local files.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import hashlib,struct,zlib

HEADER=struct.Struct('<4sIIIII')
FIELD=struct.Struct('<4sH')
MAX_RECORD=64*1024*1024
ALLOWED_TEXT={b'FULL',b'DESC',b'BTXT',b'ITXT',b'UNAM',b'RNAM',
              b'NNAM',b'NAM1',b'TNAM',b'DNAM',b'CNAM',b'SHRT',b'FNAM'}


def sha256(path:Path)->str:
    digest=hashlib.sha256()
    with path.open('rb') as inp:
        for chunk in iter(lambda:inp.read(8*1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()


def patch_subrecords(data:bytes,fid:int,typ:str,plan:dict,editor_ids:dict,seen:set,
                     *,allow_changed:bool=False):
    offset=0;count=Counter();out=bytearray();modified=0;found_edid=None
    local_seen=set();local_skipped={};candidates=set()
    while offset<len(data):
        start=offset
        if offset+6>len(data):raise ValueError('Truncated subrecord')
        tag,n=FIELD.unpack_from(data,offset);offset+=6
        wide=False
        if tag==b'XXXX':
            if n!=4 or offset+10>len(data):raise ValueError('Invalid extended subrecord')
            n=struct.unpack_from('<I',data,offset)[0];offset+=4
            tag,_unused=FIELD.unpack_from(data,offset);offset+=6
            wide=True
        if offset+n>len(data):raise ValueError('Subrecord overrun')
        before=data[offset:offset+n];offset+=n
        idx=count[tag];count[tag]+=1
        if tag==b'EDID':
            try:found_edid=before.rstrip(b'\0').decode('ascii').casefold()
            except UnicodeError:raise ValueError('Invalid EditorID in target')
        key=(fid,typ,tag.decode('ascii','replace'),idx)
        if key not in plan:
            out.extend(data[start:offset]);continue
        candidates.add(key)
        original_sha256,translated=plan[key]
        if tag not in ALLOWED_TEXT or key in seen or key in local_seen:
            raise ValueError(f'Text field alignment mismatched: {key}')
        if hashlib.sha256(before).hexdigest()!=original_sha256:
            if not allow_changed:raise ValueError(f'Text field alignment mismatched: {key}')
            local_skipped[key]='original_text_changed'
            out.extend(data[start:offset])
            continue
        if not translated.endswith(b'\0') or b'\0' in translated[:-1]:
            raise ValueError(f'Invalid translated text NUL terminator: {key}')
        try:target=translated[:-1].decode('utf-8')
        except UnicodeError:raise ValueError(f'Invalid translated text UTF-8: {key}')
        if '\ufffd' in target or not any('\uac00'<=c<='\ud7a3' for c in target):
            raise ValueError(f'Non-Korean or damaged translation: {key}')
        local_seen.add(key);modified+=1
        if wide or len(translated)>65535:
            out.extend(FIELD.pack(b'XXXX',4)+struct.pack('<I',len(translated)))
            out.extend(FIELD.pack(tag,0))
        else:
            out.extend(FIELD.pack(tag,len(translated)))
        out.extend(translated)
    # This check is per-record rather than fuzzy global text replacement.
    expected_edid=editor_ids.get((fid,typ))
    if found_edid!=expected_edid:
        if not allow_changed:
            raise ValueError(f'EditorID mismatch: {typ}:{fid:08X}: {found_edid!r} != {expected_edid!r}')
        # A reused FormID is NOT proof of identical content. Preserve the whole
        # incoming record instead of applying any of its apparently matching text.
        return data,0,{key:'editor_id_changed' for key in candidates}
    seen.update(local_seen)
    return bytes(out),modified,local_skipped


def write_copy(source:Path,dest:Path,plan:dict,editor_ids:dict,*,allow_changed:bool=False)->dict:
    if source.resolve()==dest.resolve() or dest.exists():
        raise ValueError('Original source or existing output cannot be overwritten')
    entries={(fid,typ) for fid,typ,tag,idx in plan}
    seen=set();visited=set();stat=Counter();record_types=Counter();skipped={}
    total=source.stat().st_size
    with source.open('rb') as inp,dest.open('w+b') as out:
        pos=0;groups=[]
        while pos<total:
            while groups and groups[-1][0]==pos:
                end,output_begin=groups.pop()
                size=out.tell()-output_begin
                if size>0xFFFFFFFF:raise ValueError('GRUP overflow')
                out.seek(output_begin+4);out.write(struct.pack('<I',size));out.seek(output_begin+size)
                stat['groups_closed']+=1
            if groups and pos>groups[-1][0]:raise ValueError('GRUP overflow source')
            header=inp.read(24)
            if len(header)!=24:raise ValueError('Truncated record header')
            tag,n,flags,fid,revision,version=HEADER.unpack(header)
            if tag==b'GRUP':
                if n<24 or pos+n>total or groups and pos+n>groups[-1][0]:
                    raise ValueError('GRUP boundary invalid')
                groups.append((pos+n,out.tell()))
                out.write(header);pos+=24;stat['groups']+=1
                continue
            if n>MAX_RECORD or pos+24+n>total or groups and pos+24+n>groups[-1][0]:
                raise ValueError('Record boundary invalid')
            typ=tag.decode('ascii','replace');stat['records']+=1
            record_types[typ]+=1
            if (fid,typ) not in entries:
                out.write(header)
                remaining=n
                while remaining:
                    buf=inp.read(min(remaining,8*1024*1024))
                    if not buf:raise ValueError('Truncated unchanged record')
                    out.write(buf);remaining-=len(buf)
                pos+=24+n
                continue
            if (fid,typ) in visited:
                raise ValueError(f'Duplicate target record FormID/type: {typ}:{fid:08X}')
            visited.add((fid,typ))
            raw=inp.read(n)
            if len(raw)!=n:raise ValueError('Truncated text record')
            zipped=bool(flags & 0x00040000)
            if zipped:
                if len(raw)<4:raise ValueError('Compressed record missing size')
                uncompressed=struct.unpack_from('<I',raw)[0]
                unpacked=zlib.decompress(raw[4:])
                if len(unpacked)!=uncompressed:raise ValueError('Compressed record content wrong size')
            else:unpacked=raw
            changed,count,not_applied=patch_subrecords(
                unpacked,fid,typ,plan,editor_ids,seen,allow_changed=allow_changed)
            skipped.update(not_applied)
            if count:
                stat['changed_records']+=1;stat['changed_fields']+=count
                raw=struct.pack('<I',len(changed))+zlib.compress(changed) if zipped else changed
                header=HEADER.pack(tag,len(raw),flags,fid,revision,version)
            out.write(header);out.write(raw);pos+=24+n
        while groups and groups[-1][0]==pos:
            end,output_begin=groups.pop()
            size=out.tell()-output_begin
            out.seek(output_begin+4);out.write(struct.pack('<I',size));out.seek(output_begin+size)
            stat['groups_closed']+=1
        if groups or pos!=total:raise ValueError('Unclosed GRUP')
        if not allow_changed and seen!=plan.keys():
            raise ValueError(f'Canonical fields not all applied: {len(plan)-len(seen)} remaining')
    stat['original_bytes']=total;stat['translated_bytes']=dest.stat().st_size
    stat['unmatched_fields']=len(plan)-len(seen)
    reasons=Counter(skipped.get(key,'record_or_field_missing') for key in plan.keys()-seen)
    examples=[{'formid':f'{key[0]:08X}','type':key[1],'field':key[2],
               'index':key[3],'reason':skipped.get(key,'record_or_field_missing')}
              for key in sorted(plan.keys()-seen)[:50]]
    result=dict(stat)
    result['changed_fields']=stat['changed_fields']
    result['changed_records']=stat['changed_records']
    result['record_type_counts']=dict(record_types)
    result['unmatched_reasons']=dict(reasons)
    result['unmatched_examples']=examples
    return result


def inspect_structure(path:Path)->dict:
    """Independently parse emitted record/group boundaries, without reading assets."""
    total=path.stat().st_size;pos=0;groups=[];counts=Counter();records=0;group_count=0
    with path.open('rb') as stream:
        while pos<total:
            while groups and groups[-1]==pos:groups.pop()
            if groups and pos>groups[-1]:raise ValueError('Emitted GRUP overrun')
            raw=stream.read(24)
            if len(raw)!=24:raise ValueError('Emitted record header truncated')
            tag,size,*_=HEADER.unpack(raw)
            if tag==b'GRUP':
                if size<24 or pos+size>total or groups and pos+size>groups[-1]:
                    raise ValueError('Emitted GRUP boundary invalid')
                groups.append(pos+size);pos+=24;group_count+=1
                continue
            if size>MAX_RECORD or pos+24+size>total or groups and pos+24+size>groups[-1]:
                raise ValueError('Emitted record boundary invalid')
            counts[tag.decode('ascii','replace')]+=1
            stream.seek(size,1);pos+=24+size;records+=1
        while groups and groups[-1]==pos:groups.pop()
        if groups or pos!=total:raise ValueError('Emitted GRUP not closed')
    return {'records':records,'groups':group_count,'record_type_counts':dict(counts)}

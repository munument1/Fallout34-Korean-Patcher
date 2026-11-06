from __future__ import annotations
import csv, gzip, json, re, struct, zlib
from collections import Counter, defaultdict
from pathlib import Path
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
esm=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fo3\staging\Data\Fallout34.esm')
candidate=root/'data'/'fo3'/'translation_candidates.jsonl.gz'
targets=defaultdict(list)
with gzip.open(candidate,'rt',encoding='utf-8') as f:
    for line in f:
        row=json.loads(line)
        targets[int(row['target_formid'],16)].append(row)
def iter_fields(raw):
    off=0
    extended=0
    while off+6<=len(raw):
        typ,size=struct.unpack_from('<4sH',raw,off);off+=6
        if typ==b'XXXX':
            if size!=4 or off+4>len(raw):break
            extended=struct.unpack_from('<I',raw,off)[0];off+=4
            continue
        n=extended or size;extended=0
        if off+n>len(raw):break
        yield typ.decode('ascii','replace'),raw[off:off+n]
        off+=n
def text_guess(buf):
    if not buf: return ''
    if b'\x00' in buf[:-1]:return '' # avoid binary
    raw=buf.rstrip(b'\0')
    if not raw or len(raw)>65536:return ''
    for codec in ('utf-8','cp1252'):
        try:
            text=raw.decode(codec)
            if all(ch.isprintable() or ch in '\r\n\t' for ch in text):return text
        except UnicodeError:pass
    return ''
count_records=0;hits=0;matched_exact=0;field_match=0;failed=0
bytype=Counter(); examples=[]
target_info=[]
end=esm.stat().st_size
with esm.open('rb') as f:
    off=0
    while off<end:
        f.seek(off)
        hdr=f.read(24)
        if len(hdr)!=24:raise Exception('truncated header')
        typ,size,flags,fid,rev,misc=struct.unpack('<4sIIIII',hdr)
        if typ==b'GRUP':
            if size<24 or off+size>end:raise Exception(f'bad GRUP {off} {size}')
            off+=24
            continue
        if size>16*1024*1024 or off+24+size>end:raise Exception(f'bad record {off} {size}')
        count_records+=1
        if fid in targets:
            hits+=1
            f.seek(off+24)
            blob=f.read(size)
            if flags&0x00040000:
                want=struct.unpack_from('<I',blob)[0]
                blob=zlib.decompress(blob[4:])
                if len(blob)!=want:raise Exception('inflation mismatch')
            text_fields=defaultdict(list)
            for tag,data in iter_fields(blob):
                t=text_guess(data)
                if t:text_fields[tag].append(t)
            for row in targets[fid]:
                bytype[row['record_type']]+=1
                if row['field'] in text_fields:
                    field_match+=1
                    if row['english'] in text_fields[row['field']]:
                        matched_exact+=1
                        if len(examples)<7:
                            examples.append({'target':f'{fid:08X}','type':row['record_type'],'field':row['field'],'english':row['english'][:120],'korean':row['korean'][:120],'match':'exact'})
                    else:
                        if len(examples)<15:
                            examples.append({'target':f'{fid:08X}','type':row['record_type'],'field':row['field'],'english':row['english'][:110],'esm_fields':[x[:110] for x in text_fields[row['field']][:3]],'match':'field_exists_english_diff'})
                elif len(examples)<15:
                    examples.append({'target':f'{fid:08X}','type':row['record_type'],'field':row['field'],'english':row['english'][:110],'available_fields':list(text_fields)[:15],'match':'missing_field'})
        off+=24+size
result={'esm_records_scanned':count_records,'target_unique_ids':len(targets),'target_records_seen':hits,'candidate_rows':sum(map(len,targets.values())),'fields_present_rows':field_match,'english_exact_field_matches':matched_exact,'record_type_distribution':dict(bytype.most_common()),'samples':examples,'note':'Field matching is not a complete parser for text encodings; any mismatch needs separate QA.'}
(root/'data'/'fo3'/'esm_field_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('RESULT',json.dumps({k:v for k,v in result.items() if k not in ('samples','record_type_distribution')},ensure_ascii=True),flush=True)
print('SAMPLES',json.dumps(examples,ensure_ascii=True),flush=True)

"""Inspect SWF embedded fonts, no assets modified. CWS/FWS SWF tag parser."""
from pathlib import Path
import argparse,struct,zlib,collections,json,hashlib


def swf_tags(path):
    """Yield (tag type, original contents SHA-256) for strict non-font audit."""
    data=path.read_bytes()
    if data[:3]==b'CWS':blob=data[:8]+zlib.decompress(data[8:])
    elif data[:3]==b'FWS':blob=data
    else:raise ValueError('Not a supported SWF')
    if struct.unpack_from('<I',data,4)[0]!=len(blob):raise ValueError('Invalid expanded SWF size')
    nbits=blob[8]>>3
    p=8+(5+4*nbits+7)//8+4
    while p<len(blob):
        taglen=struct.unpack_from('<H',blob,p)[0];p+=2
        code=taglen>>6;n=taglen&63
        if n==63:n=struct.unpack_from('<I',blob,p)[0];p+=4
        chunk=blob[p:p+n];p+=n
        yield code,hashlib.sha256(chunk).hexdigest(),chunk[:2]
        if code==0:break


def parse_swf(path):
    data=path.read_bytes()
    if data[:3]==b'CWS':blob=data[:8]+zlib.decompress(data[8:])
    elif data[:3]==b'FWS':blob=data
    else:raise ValueError('Not a supported SWF')
    declared=struct.unpack_from('<I',data,4)[0]
    if len(blob)!=declared:raise ValueError(f'Expanded SWF size wrong {len(blob)} != {declared}')
    nbits=blob[8]>>3
    rectlen=(5+4*nbits+7)//8
    p=8+rectlen+4
    fonts=[];types=collections.Counter()
    while p<len(blob):
        taglen=struct.unpack_from('<H',blob,p)[0];p+=2
        code=taglen>>6;n=taglen&0x3f
        if n==63:n=struct.unpack_from('<I',blob,p)[0];p+=4
        chunk=blob[p:p+n];p+=n
        types[code]+=1
        if code in (10,48,75,91):
            rec={'tag':code,'bytes':len(chunk),'font_id':struct.unpack_from('<H',chunk)[0]}
            if code in (48,75):
                flags=chunk[2];namelen=chunk[4]
                rec['flags']=flags
                rec['font_name']=chunk[5:5+namelen].decode('latin1','replace')
                rec['number_of_glyphs']=struct.unpack_from('<H',chunk,5+namelen)[0]
                rec['wide_code']=bool(flags&4)
                rec['wide_offsets']=bool(flags&8)
                if code==75 and rec['number_of_glyphs']:
                    start=7+namelen
                    k=rec['number_of_glyphs']
                    sz=4 if rec['wide_offsets'] else 2
                    if sz==4:
                        codeoff=struct.unpack_from('<I',chunk,start+sz*k)[0]
                    else:
                        codeoff=struct.unpack_from('<H',chunk,start+sz*k)[0]
                    table=start+codeoff
                    if table+2*k>len(chunk):
                        rec['code_table_error']=f'{table}+{2*k} > {len(chunk)}'
                    else:
                        charset=set(struct.unpack_from('<'+str(k)+'H',chunk,table))
                        rec['korean_syllable_glyphs']=sum(0xAC00<=cp<=0xD7A3 for cp in charset)
                        rec['full_hangul_coverage']=rec['korean_syllable_glyphs']==11172
                        rec['missing_glyphs_in_sample']=[c for c in '겍갹괜뾋뷁긔귁걟갉긁삶쮸힣' if ord(c) not in charset]
                        rec['present_glyphs_in_sample']=[c for c in '겍갹괜뾋뷁긔귁걟갉긁삶쮸힣' if ord(c) in charset]
            elif code==91:
                flags=chunk[2];name=chunk[3:].split(b'\0')[0]
                rec['flags']=flags
                rec['font_name']=name.decode('latin1','replace')
                rec['font4_has_embedded_font_data']=bool(flags&4)
                rec['embedded_font_bytes']=len(chunk)-4-len(name)
            fonts.append(rec)
        if code==0:break
    return {'filename':path.name,'swf_version':data[3],'uncompressed_bytes':len(blob),'font_tags':fonts,'tag_counts':dict(types)}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('path',type=Path)
    args=p.parse_args()
    for f in args.path.rglob('*.swf'):
        try:res=parse_swf(f)
        except Exception as ex:print('ERROR',f,ex);continue
        print(json.dumps(res,ensure_ascii=False,indent=2))

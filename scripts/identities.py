"""Validate owner-defined global colors, exact aliases, bindings and PNG symbols."""
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib
import unicodedata
from aggregate import require


def normalize(text):
    value = text.replace('’',"'").replace('‘',"'").replace('–','-').replace('—','-')
    value = ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c))
    return ' '.join(value.split())


def validate_png(raw):
    require(len(raw)<=2_000_000 and raw[:8]==b'\x89PNG\r\n\x1a\n','Invalid or oversized PNG')
    offset=8;header=None;payload=bytearray();ended=False
    while offset+12<=len(raw):
        size=struct.unpack('>I',raw[offset:offset+4])[0]
        tag=raw[offset+4:offset+8];end=offset+8+size
        require(end+4<=len(raw),'Truncated PNG')
        chunk=raw[offset+8:end];crc=struct.unpack('>I',raw[end:end+4])[0]
        require(zlib.crc32(tag+chunk)&0xffffffff==crc,'Corrupt PNG chunk')
        if header is None:
            require(tag==b'IHDR' and size==13,'Missing PNG header')
            width,height,depth,kind,compression,filtering,interlace=struct.unpack('>IIBBBBB',chunk)
            require(0<width<=4096 and 0<height<=4096,'Invalid PNG dimensions')
            require(kind in (0,2,3,4,6) and depth in (1,2,4,8,16) and compression==0 and filtering==0 and interlace in (0,1),'Invalid PNG header')
            header=(width,height)
        elif tag==b'IHDR':raise ValueError('Duplicate PNG header')
        if tag==b'IDAT':payload.extend(chunk)
        offset=end+4
        if tag==b'IEND':
            require(size==0 and offset==len(raw),'Invalid PNG ending');ended=True;break
    require(header is not None and ended and payload,'Incomplete PNG')
    decompressor=zlib.decompressobj()
    maximum=(header[0]*8+64)*header[1]+1024
    pixels=decompressor.decompress(payload,maximum+1)
    require(len(pixels)<=maximum and decompressor.eof and not decompressor.unused_data,'Invalid PNG pixel stream')


def compile_registry(source, public):
    require(isinstance(source,dict) and source.get('schemaVersion')==1 and isinstance(source.get('entities'),list), 'Invalid identity registry')
    require(len(source['entities'])<=5000,'Too many identities')
    entities=[];ids=set();aliases=set();bindings=set()
    for item in source['entities']:
        require(isinstance(item,dict),'Invalid entity')
        entity={key:item[key] for key in ['id','label','shortLabel','kind','colorHex','aliases','bindings']}
        require(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}',entity['id']) and entity['id'] not in ids,'Invalid or duplicate identity ID')
        ids.add(entity['id'])
        require(isinstance(entity['label'],str) and entity['label'].strip(),'Missing label')
        require(isinstance(entity['shortLabel'],str) and 1<=len(entity['shortLabel'])<=12,'Invalid short label')
        require(entity['kind'] in ['party','coalition'],'Invalid entity kind')
        require(re.fullmatch(r'[0-9a-fA-F]{6}',entity['colorHex']),'Color must be six hexadecimal digits without #')
        require(isinstance(entity['aliases'],list) and isinstance(entity['bindings'],list),'Missing alias or binding arrays')
        for alias in entity['aliases']:
            require(isinstance(alias,str),'Invalid alias')
            key=normalize(alias)
            require(key and len(key)<=500 and key not in aliases,'Ambiguous or duplicate alias')
            aliases.add(key)
        for binding in entity['bindings']:
            require(isinstance(binding,dict),'Invalid binding')
            key=(binding.get('electionID'),binding.get('resultID'))
            require(all(isinstance(v,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,199}',v) for v in key) and key not in bindings,'Duplicate or invalid result binding')
            bindings.add(key)
        if item.get('symbolPath') is not None:
            path=item['symbolPath']
            require(isinstance(path,str) and re.fullmatch(r'symbols/[a-zA-Z0-9_-]+\.png',path),'Symbol must be a PNG inside public/symbols')
            raw=(public/path).read_bytes()
            validate_png(raw)
            entity['symbolPath']=path
            entity['symbolSHA256']=hashlib.sha256(raw).hexdigest()
        elif item.get('symbolSHA256') is not None:
            raise ValueError('Symbol hash without image')
        entities.append(entity)
    result=dict(schemaVersion=1,entities=entities)
    require(len(json.dumps(result,ensure_ascii=False).encode())<=1_000_000,'Identity registry too large')
    return result


def candidate_catalog(elections):
    names={}
    for election in elections:
        for territory in election['territories']:
            for row in territory['results']:
                key=row['name'];entry=names.setdefault(key,dict(sourceName=key,bindings=[]))
                binding=dict(electionID=election['id'],resultID=row['id'])
                if binding not in entry['bindings']:entry['bindings'].append(binding)
    return dict(schemaVersion=1,candidates=[names[k] for k in sorted(names)])

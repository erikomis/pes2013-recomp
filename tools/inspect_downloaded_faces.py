#!/usr/bin/env python3
"""Read-only inventory of downloaded PES PC face packs; no PS3 conversion."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib


def inspect(path):
    rows=[]
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            if entry.is_dir():continue
            row={'name':entry.filename,'bytes':entry.file_size}
            if entry.file_size > 32*1024*1024:
                row['status']='size_limit';rows.append(row);continue
            data=archive.read(entry)
            row['sha256']=hashlib.sha256(data).hexdigest()
            if len(data)>=16 and data[:8]==bytes.fromhex('0001015745535953'):
                declared=struct.unpack_from('<I',data,12)[0]
                if declared>32*1024*1024:raise ValueError('Oversized WESYS payload')
                dec=zlib.decompressobj();raw=dec.decompress(data[16:],declared+1)
                if len(raw)!=declared or not dec.eof:
                    raise ValueError('Invalid compressed payload')
                row['format']='WESYS PC compressed';row['dds_headers']=[]
                row['trailing_bytes']=len(dec.unused_data)
                at=raw.find(b'DDS ')
                while at>=0:
                    if at+128<=len(raw) and struct.unpack_from('<I',raw,at+4)[0]==124:
                        height,width=struct.unpack_from('<II',raw,at+12)
                        row['dds_headers'].append({'offset':at,'width':width,'height':height,
                                                  'fourcc':raw[at+84:at+88].decode('ascii','replace')})
                    at=raw.find(b'DDS ',at+4)
            rows.append(row)
    return {'archive':path.name,'files':rows,'ps3_compatible':None,'installed':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path);args=parser.parse_args()
    packs=[]
    for path in sorted(args.directory.glob('*2026.zip')):
        try:packs.append(inspect(path))
        except (ValueError,zipfile.BadZipFile,zlib.error) as exc:
            packs.append({'archive':path.name,'error':str(exc)})
    print(json.dumps({'packs':packs,'note':'DDS header inventory only; names and PS3 conversion unverified'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()

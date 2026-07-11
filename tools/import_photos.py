#!/usr/bin/env python3
from pathlib import Path
from PIL import Image, ImageOps
import json, re, sys, csv

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'incoming'
FULL=ROOT/'assets'/'photos'/'full'
THUMB=ROOT/'assets'/'photos'/'thumb'
OUT=ROOT/'assets'/'gallery-data.js'
EXT={'.jpg','.jpeg','.png','.webp','.tif','.tiff'}

def slug(s):
    s=re.sub(r'[^a-zA-Z0-9_-]+','-',s).strip('-').lower()
    return s or 'photo'

def category(i,name):
    n=name.lower()
    if any(x in n for x in ('portrait','портрет','индив')): return 'portraits'
    if any(x in n for x in ('friend','друз','group','групп')): return 'friends'
    return ['class','friends','portraits'][i%3]

def main():
    if not SRC.exists(): SRC.mkdir()
    files=sorted([p for p in SRC.rglob('*') if p.suffix.lower() in EXT])
    if not files:
        print('В папке incoming нет JPG/PNG/WebP. Скопируйте фотографии и запустите снова.')
        return 2
    FULL.mkdir(parents=True,exist_ok=True); THUMB.mkdir(parents=True,exist_ok=True)
    for p in list(FULL.glob('*'))+list(THUMB.glob('*')): p.unlink()
    result=[]
    for i,p in enumerate(files):
        name=f'{i+1:03d}-{slug(p.stem)}.webp'
        try:
            with Image.open(p) as im:
                im=ImageOps.exif_transpose(im).convert('RGB')
                full=im.copy(); full.thumbnail((2200,2200),Image.Resampling.LANCZOS)
                full.save(FULL/name,'WEBP',quality=86,method=6)
                thumb=im.copy(); thumb.thumbnail((900,900),Image.Resampling.LANCZOS)
                thumb.save(THUMB/name,'WEBP',quality=79,method=6)
                result.append({'id':name[:-5],'title':f'Кадр {i+1:02d}','category':category(i,p.stem),'thumb':f'assets/photos/thumb/{name}','full':f'assets/photos/full/{name}','alt':'Фотография учеников 4 «Е» класса'})
                print(f'[{i+1}/{len(files)}] {p.name}')
        except Exception as e: print('Ошибка:',p,e)
    OUT.write_text('window.ALBUM_PHOTOS = '+json.dumps(result,ensure_ascii=False,indent=2)+';\n',encoding='utf-8')
    print(f'Готово: {len(result)} фотографий. Откройте index.html или опубликуйте папку на GitHub Pages.')
    return 0
if __name__=='__main__': raise SystemExit(main())

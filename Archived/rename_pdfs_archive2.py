import argparse, csv, re
import os
import shutil
import math
from pathlib import Path
from datetime import datetime
import pymupdf
import pytesseract
from PIL import Image, ImageOps
from pytesseract import Output
BASE = Path(__file__).resolve().parent

def filename_from_name(name):
    stem = re.sub(r'\s+', ' ', name.strip())
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', stem)[:150].strip(' .')
    if not stem:
        raise ValueError('Empty filename')
    return stem + '.pdf'

def extract(source, args):
    with pymupdf.open(source) as doc:
        if doc.needs_pass or not doc.page_count:
            raise ValueError('Encrypted or empty PDF')
        pix = doc[0].get_pixmap(dpi=args.dpi, colorspace=pymupdf.csRGB, alpha=False)
        image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    image = image.rotate(args.rotate, expand=True)
    w,h = image.size
    a,b,c,d = args.roi
    crop = ImageOps.autocontrast(ImageOps.grayscale(image.crop((round(a*w),round(b*h),round(c*w),round(d*h)))))
    crop.save(args.debug_dir / (source.stem + '_crop.png'))
    config = '--psm 6'
    # Language directory is configured through the subprocess environment.
    # Do not add a quoted --tessdata-dir to pytesseract's config string.
    data = pytesseract.image_to_data(crop,lang=args.lang,config=config,output_type=Output.DICT,timeout=args.timeout)
    lines={}
    for i,word in enumerate(data['text']):
        if word.strip():
            key=tuple(data[k][i] for k in ('block_num','par_num','line_num'))
            lines.setdefault(key,[]).append((word.strip(),float(data['conf'][i])))
    found=[]
    for words in lines.values():
        if not re.fullmatch(r'name[:.]?',words[0][0],re.I):
            continue
        name=' '.join(t for t,_ in words[1:])
        scores=[s for _,s in words[1:] if s>=0]
        if len(name.split())>=2 and all(c.isalpha() or c in " '-’" for c in name) and scores:
            found.append((name,min(scores)))
    if len(found)!=1:
        raise ValueError(f'Expected one Name field; found {len(found)}')
    return found[0]

def main():
    p=argparse.ArgumentParser(description='OCR employee Name field and rename PDFs with spaces')
    p.add_argument('folder',type=Path)
    p.add_argument('--apply',action='store_true')
    p.add_argument('--rotate',type=int,choices=(0,90,180,270),default=90)
    p.add_argument('--roi',type=float,nargs=4,default=(.60,.04,.95,.20))
    p.add_argument('--dpi',type=int,default=300)
    p.add_argument('--timeout',type=float,default=30)
    p.add_argument('--lang',default='eng')
    p.add_argument('--min-confidence',type=float,default=80)
    p.add_argument('--tesseract',type=Path)
    p.add_argument('--tessdata',type=Path)
    p.add_argument('--debug-dir',type=Path,default=BASE/'debug')
    args=p.parse_args()
    a,b,c,d=args.roi
    if not args.folder.is_dir(): p.error('Input folder not found')
    if not (0<=a<c<=1 and 0<=b<d<=1): p.error('Invalid ROI')
    if args.dpi<=0 or not math.isfinite(args.min_confidence) or not 0<=args.min_confidence<=100:
        p.error('Invalid DPI or confidence')
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        p.error('Timeout must be a positive finite number')
    if not re.fullmatch(r'[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*', args.lang):
        p.error('Invalid language specification')
    if args.apply and os.name != 'nt':
        p.error('Apply mode is Windows-only to preserve no-overwrite rename semantics')
    bundled = BASE / 'tools' / 'tesseract' / 'tesseract.exe'
    executable = args.tesseract
    if executable is None:
        executable = bundled if bundled.is_file() else shutil.which('tesseract')
    if not executable:
        p.error('Tesseract not found. Provide tools/tesseract runtime or --tesseract PATH')
    executable = Path(executable).resolve()
    if not executable.is_file():
        p.error(f'Tesseract executable not found: {executable}')
    pytesseract.pytesseract.tesseract_cmd = str(executable)
    if args.tessdata is None:
        sibling = executable.parent / 'tessdata'
        prefix = os.environ.get('TESSDATA_PREFIX')
        if sibling.is_dir():
            args.tessdata = sibling
        elif prefix:
            args.tessdata = Path(prefix)
        else:
            p.error('Language directory not found. Supply --tessdata PATH')
    args.tessdata = args.tessdata.resolve()
    if not args.tessdata.is_dir():
        p.error(f'Language directory not found: {args.tessdata}')
    for language in args.lang.split('+'):
        model = args.tessdata / (language + '.traineddata')
        if not model.is_file() or model.stat().st_size == 0:
            p.error(f'Missing or empty language model: {model}')
    os.environ['TESSDATA_PREFIX'] = str(args.tessdata)
    try:
        version = pytesseract.get_tesseract_version()
        # Exercise model loading, not just executable version reporting.
        pytesseract.image_to_data(
            Image.new('RGB', (300, 100), 'white'),
            lang=args.lang, config='--psm 6', timeout=args.timeout,
            output_type=Output.DICT,
        )
    except Exception as exc:
        p.error(f'Tesseract startup/model check failed: {exc}')
    print(f'Tesseract: {version}')
    print(f'Language data: {args.tessdata}')
    try:
        args.debug_dir.mkdir(parents=True, exist_ok=True)
        log = args.debug_dir / ('rename_log_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.csv')
        log_handle = log.open('x', newline='', encoding='utf-8-sig')
        writer = csv.DictWriter(log_handle, fieldnames=['original','employee','confidence','proposed','status'])
        writer.writeheader()
        log_handle.flush()
        os.fsync(log_handle.fileno())
    except OSError as exc:
        p.error(f'Cannot create audit log: {exc}')
    files=sorted(f for f in args.folder.iterdir() if f.is_file() and f.suffix.lower()=='.pdf')
    occupied={f.name.casefold() for f in args.folder.iterdir()}
    rows=[]
    for source in files:
        row=dict(original=source.name,employee='',confidence='',proposed='',status='')
        try:
            name,confidence=extract(source,args)
            target=source.with_name(filename_from_name(name))
            row.update(employee=name,confidence=round(confidence,1),proposed=target.name)
            key=target.name.casefold()
            if confidence<args.min_confidence: row['status']='REVIEW: low OCR confidence'
            elif key==source.name.casefold(): row['status']='Already named'
            elif key in occupied: row['status']='SKIP: filename collision'
            else:
                if args.apply:
                    if target.exists():
                        raise FileExistsError(f'Destination already exists: {target.name}')
                    source.rename(target)
                row['status']='Renamed' if args.apply else 'DRY RUN'
                occupied.add(key)
        except Exception as exc: row['status']=f'ERROR: {exc}'
        rows.append(row)
        writer.writerow(row)
        log_handle.flush()
        os.fsync(log_handle.fileno())
        print(f"{row['original']} -> {row['proposed'] or '(none)'} [{row['status']}]")
    log_handle.close()
    print(f'Processed {len(files)} PDF(s). Audit log: {log}')
    return 1 if any(r['status'].startswith(('ERROR:', 'REVIEW:', 'SKIP:')) for r in rows) else 0

if __name__ == '__main__':
    raise SystemExit(main())

"""Template-based employee-name OCR with position-independent field matching."""
import argparse
import csv
import io
import math
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import pymupdf
from PIL import Image, ImageOps

BASE = Path(__file__).resolve().parent


def filename_from_name(name):
    name = re.sub(r"\s+", " ", name.strip())
    if not name or len(name) > 150:
        raise ValueError("Empty or excessively long employee name")
    if re.search(r'[<>:"/\\|?*\x00-\x1f]', name):
        raise ValueError("Invalid filename characters in OCR name")
    return name.strip(" .") + ".pdf"


def valid_name(name):
    words = name.split()
    return (len(words) >= 2 and all(any(c.isalpha() for c in w) for w in words)
            and all(c.isalpha() or c in " '-’" for c in name))


def run_ocr(image, args, folder, tag, psm):
    path = folder / (tag + ".png")
    image.save(path)
    command = [str(args.tesseract), str(path), "stdout", "--tessdata-dir",
               str(args.tessdata), "-l", args.lang, "--psm", str(psm), "tsv"]
    result = subprocess.run(command, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=args.timeout,
                            creationflags=0x08000000 if os.name == "nt" else 0)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Tesseract failed")
    (folder / (tag + ".tsv")).write_text(result.stdout, encoding="utf-8")
    tokens = []
    for row in csv.DictReader(io.StringIO(result.stdout), delimiter="\t"):
        if row.get("level") != "5" or not row.get("text", "").strip():
            continue
        token = {k: int(row[k]) for k in ("left", "top", "width", "height")}
        token.update(text=row["text"].strip(), confidence=float(row["conf"]))
        tokens.append(token)
    return tokens


def locate_names(tokens):
    """Match the Name anchor to right-hand words by geometry, not OCR line IDs."""
    candidates = []
    for label in tokens:
        if label["text"].strip(":.").casefold() != "name":
            continue
        right_edge = label["left"] + label["width"]
        center = label["top"] + label["height"] / 2
        words = []
        for token in tokens:
            if token["left"] < right_edge or token is label:
                continue
            other_center = token["top"] + token["height"] / 2
            overlap = min(label["top"] + label["height"], token["top"] + token["height"]) - max(label["top"], token["top"])
            if overlap >= .35 * min(label["height"], token["height"]) and abs(other_center-center) <= .65 * max(label["height"], token["height"]):
                words.append(token)
        words.sort(key=lambda t: t["left"])
        name = " ".join(t["text"] for t in words)
        if valid_name(name):
            confidence = min(t["confidence"] for t in words)
            if confidence >= 0:
                candidates.append((name, confidence))
    return candidates


def extract(source, args, folder):
    with pymupdf.open(source) as doc:
        if doc.needs_pass or not doc.page_count:
            raise ValueError("Encrypted or empty PDF")
        pix = doc[0].get_pixmap(dpi=args.dpi, colorspace=pymupdf.csRGB, alpha=False)
        original = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    angles = [args.rotate]
    if args.auto_rotate:
        angles += [angle for angle in (0, 90, 180, 270) if angle != args.rotate]
    all_found = []
    for angle in angles:
        image = original.rotate(angle, expand=True)
        w, h = image.size
        regions = [tuple(args.roi), (0.35, 0.0, 1.0, 0.40)]
        regions = list(dict.fromkeys(regions))
        for index, region in enumerate(regions):
            a,b,c,d = region
            crop = image.crop((round(a*w), round(b*h), round(c*w), round(d*h)))
            crop = ImageOps.autocontrast(ImageOps.grayscale(crop))
            for psm in (6, 11):
                tag = f"rotation_{angle}_region_{index}_psm_{psm}"
                tokens = run_ocr(crop, args, folder, tag, psm)
                for name, confidence in locate_names(tokens):
                    all_found.append((name, confidence, tag))
        # Stop at an orientation only if it provides one acceptable name.
        eligible = [entry for entry in all_found if entry[1] >= args.min_confidence]
        if len({entry[0].casefold() for entry in eligible}) == 1:
            break
    eligible = [entry for entry in all_found if entry[1] >= args.min_confidence]
    if len({entry[0].casefold() for entry in eligible}) > 1:
        raise ValueError("Conflicting high-confidence names; inspect OCR TSV files")
    if eligible:
        return max(eligible, key=lambda entry: entry[1])
    if all_found:
        return max(all_found, key=lambda entry: entry[1])
    raise ValueError("No valid Name field across position/segmentation attempts; inspect debug crops and TSV")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder", type=Path)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--rotate", type=int, choices=(0,90,180,270), default=90)
    p.add_argument("--auto-rotate", action="store_true")
    p.add_argument("--roi", type=float, nargs=4, default=(.55,.04,.95,.20))
    p.add_argument("--dpi", type=int, default=300)
    p.add_argument("--timeout", type=float, default=30)
    p.add_argument("--lang", default="eng")
    p.add_argument("--min-confidence", type=float, default=80)
    p.add_argument("--tesseract", type=Path)
    p.add_argument("--tessdata", type=Path)
    p.add_argument("--debug-dir", type=Path, default=BASE/"debug")
    args = p.parse_args()
    a,b,c,d = args.roi
    if not args.folder.is_dir(): p.error("Input folder not found")
    if not (0<=a<c<=1 and 0<=b<d<=1): p.error("Invalid ROI")
    if args.dpi<=0 or not math.isfinite(args.timeout) or args.timeout<=0: p.error("Invalid DPI/timeout")
    if not math.isfinite(args.min_confidence) or not 0<=args.min_confidence<=100: p.error("Invalid confidence")
    if not re.fullmatch(r"[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*",args.lang): p.error("Invalid language")
    if args.apply and os.name != "nt": p.error("Apply mode is Windows-only for no-overwrite rename behavior")
    bundled = BASE/"tools"/"tesseract"/"tesseract.exe"
    executable = args.tesseract or (bundled if bundled.is_file() else shutil.which("tesseract"))
    if not executable: p.error("Tesseract executable not found")
    args.tesseract = Path(executable).resolve()
    if not args.tesseract.is_file(): p.error("Invalid Tesseract executable")
    args.tessdata = (args.tessdata or args.tesseract.parent/"tessdata").resolve()
    for language in args.lang.split("+"):
        model = args.tessdata/(language+".traineddata")
        if not model.is_file() or model.stat().st_size==0: p.error(f"Missing/empty model: {model}")
    try:
        args.debug_dir.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory() as temporary:
            run_ocr(Image.new("RGB",(300,100),"white"),args,Path(temporary),"startup",6)
    except Exception as exc: p.error(f"Startup/model check failed: {exc}")
    run_dir = args.debug_dir/ datetime.now().strftime("run_%Y%m%d_%H%M%S_%f")
    run_dir.mkdir()
    files = sorted(f for f in args.folder.iterdir() if f.is_file() and f.suffix.lower()==".pdf")
    occupied = {f.name.casefold() for f in args.folder.iterdir()}
    log = run_dir/"rename_log.csv"
    failures = 0
    with log.open("x",newline="",encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle,fieldnames=["original","employee","confidence","proposed","status","ocr_attempt","debug_folder"])
        writer.writeheader(); handle.flush(); os.fsync(handle.fileno())
        for index, source in enumerate(files):
            folder = run_dir/f"file_{index+1:04d}"
            folder.mkdir()
            row = dict(original=source.name,employee="",confidence="",proposed="",status="",ocr_attempt="",debug_folder=str(folder))
            try:
                name, confidence, attempt = extract(source,args,folder)
                target = source.with_name(filename_from_name(name))
                row.update(employee=name,confidence=round(confidence,1),proposed=target.name,ocr_attempt=attempt)
                key = target.name.casefold()
                if confidence<args.min_confidence: row["status"]="REVIEW: low OCR confidence"
                elif key==source.name.casefold(): row["status"]="Already named"
                elif key in occupied: row["status"]="SKIP: filename collision"
                else:
                    if args.apply:
                        if target.exists(): raise FileExistsError("Destination already exists")
                        # Journal intention before the filesystem operation.
                        planned=dict(row,status="RENAME PLANNED")
                        writer.writerow(planned); handle.flush(); os.fsync(handle.fileno())
                        source.rename(target)
                    row["status"]="Renamed" if args.apply else "DRY RUN"
                    occupied.add(key)
            except Exception as exc: row["status"]=f"ERROR: {exc}"
            if row["status"].startswith(("ERROR:","REVIEW:","SKIP:")): failures+=1
            writer.writerow(row); handle.flush(); os.fsync(handle.fileno())
            print(f"{source.name} -> {row['proposed'] or '(none)'} [{row['status']}]")
    print(f"Processed {len(files)} files; {failures} need review. Audit log: {log}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

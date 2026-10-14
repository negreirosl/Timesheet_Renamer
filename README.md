# PDF Employee Renamer — OCR timesheet renamer and department sorter

A small, local Windows command-line tool. It renders the first page of each
PDF in `input/`, runs Tesseract OCR on a configurable region, extracts the
employee name and designation, then renames the file and moves it into a
department folder.

Outputs clean Proper Case filenames (e.g., `Lucas Negreiros Ferreira.pdf`),
classifies employees into departments via a designation-to-department lookup
(`department_library.json`), and sorts processed files into structured
subfolders.

No frontend, database, or web server required.

## What it does

1. Reads each `.pdf` directly in `input/` (no subfolder scanning).
2. Renders page 1 at the configured DPI, optionally rotates it, and OCRs a
   configurable region (plus a fallback region) using Tesseract.
3. Extracts the **Name** and **Position/Designation** fields by locating the
   labels and reading the words to their right on the same line.
4. Normalizes the name to Proper Case and builds the target filename
   `<Employee Name>.pdf`.
5. Classifies the department by looking up the (normalized, lowercase)
   designation in `department_library.json`.
6. In dry-run mode, writes a preview to the audit CSV without touching files.
7. In apply mode (after typing `yes`), renames each PDF and **moves** it into
   `input/Timesheets/<DEPARTMENT>/`:

   - `input/Timesheets/ADM`
   - `input/Timesheets/MAINT`
   - `input/Timesheets/MAR`
   - `input/Timesheets/PROD`
   - `input/Timesheets/REVIEW` — routing location for low-confidence names,
     unknown designations, filename collisions, and processing errors.

   The full audit log lives at `debug/run_<timestamp>/rename_log.csv`, and each
   file also gets a numbered debug folder under that same run directory holding
   the crop images and raw OCR TSV output used to produce its result.

## Requirements

- Windows (apply mode is Windows-only; dry-run works on any OS).
- A Python interpreter and a project-local `venv` (created by setup, below).
- The Tesseract OCR runtime — executable, required DLLs, and
  `tessdata/eng.traineddata`. Not bundled; see "Tesseract" below.
- Python packages: `pymupdf`, `pillow` (see `requirements.txt`).

The script calls `tesseract.exe` directly via `subprocess` and parses TSV
output itself. `pytesseract` is **not used** by the current code; if you see
it referenced in an old snapshot or copy, that predates the current
subprocess-based implementation.

## Setup (internet required)

Double-click `SetupEnvironment.bat`. It creates the local `venv` when absent,
then installs the dependencies from `requirements.txt` and runs `pip check`.
Rerunning setup installs/checks requirements in that same environment.

Base Python detection tries the parent workspace
`WinPython\python\python.exe`, then a project-local
`WinPython\python\python.exe`, then a known workspace path. If your WinPython
distribution uses another directory name, pass the interpreter explicitly:

```
SetupEnvironment.bat -PythonExe "FULL PATH TO python.exe"
```

## Tesseract

Two supported options:

1. **Bundled runtime**: place the complete OCR runtime (executable, DLLs, and
   `tessdata/eng.traineddata`) in `tools/tesseract/`. This folder is
   gitignored; populate it locally. See `tools/README.txt` for the expected
   layout.
2. **External runtime**: install Tesseract normally and either add it to
   `PATH` or pass the executable path explicitly.

External-runtime example:

```
dry_run.bat --tesseract "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

Use the same `--tesseract` option on `apply_rename.bat`.

## Workflow

1. Run `SetupEnvironment.bat`.
2. Provide the Tesseract runtime and run `SanityCheck.bat` to verify the
   environment (Python imports, Tesseract executable, and `eng` language data).
3. Put **copies** of PDFs directly in `input/`.
4. Run `dry_run.bat` to preview extracted names, designations, and department
   classifications without modifying anything.
5. Review the audit CSV and debug crops. Fix calibration (below) if needed.
6. Run `apply_rename.bat` and type `yes` to rename and move files into
   `input/Timesheets/<DEPARTMENT>/`.

The run launchers use the project's `venv` Python directly; no activation
required. They do not install dependencies at startup.

## Calibration

First page only; fixed layout and rotation per invocation; no folder watching.

- Default rotation is 90 degrees counterclockwise for the supplied sideways
  preview. Use `--rotate 0` if the PDF already renders upright.
- Default ROI: `0.55 0.04 0.95 0.20` (fractions of page size after rotation,
  top-left origin). Keep the Name and Designation labels together on the same
  OCR line.

```
dry_run.bat --rotate 0 --roi 0.55 0.04 0.95 0.20
```

Repeat the same options on `apply_rename.bat` after verifying the crop.

## Behavior and safeguards

- Names are normalized to Proper Case automatically. A valid name must have
  at least two words.
- The script keeps the highest-confidence name candidate across all attempted
  regions and rotations; it does not leave conflicting candidates for review
  when at least one passes validation.
- Low-confidence names, unknown designations, filename collisions, and errors
  are routed to `input/Timesheets/REVIEW/` — they are moved there, not left
  in place.
- PDF contents are not rewritten; only filenames change and files are moved.
- Debug crops and TSV output contain personal data; secure them.
- Do not run concurrent jobs or change the input folder while processing.
- No automatic undo. Use copies and retain the audit logs.

## Customizing the department library

`department_library.json` maps a designation (lowercase, after normalization)
to a department code. To add a new designation, add a key like:

```json
"new designation title": "DEPT"
```

Valid department codes are `ADM`, `MAINT`, `MAR`, `PROD`, and `REVIEW`.
Designations that match no entry are classified as `UNKNOWN` and routed to
`REVIEW/` in apply mode.

A few designations are aliased in code before lookup (e.g., "control room
operator" → `cro`, "scaffolder" → `scaffolder/gpo`, "production operator" →
`production technician`). Only the aliases themselves live in code; adding an
ordinary new designation requires only a JSON edit.

## Archived versions

`Archived/` holds development snapshots from earlier iterations of this
project (including versions that used the `pytesseract` wrapper before the
current direct-subprocess design). They are historical only and not part of
the workflow; `rename_pdfs.py` at the repository root is the authoritative
script.

## Validation

Python syntax, filename normalization, department library lookup, and archive
integrity were checked. Runtime, OCR binaries, venv, and sample PDFs are not
bundled.

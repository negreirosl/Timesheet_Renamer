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
2. Renders page 1 at the configured DPI, applies the configured rotation
   (optionally trying all four orientations with `--auto-rotate`), and OCRs a
   configurable region plus a fallback region using Tesseract.
3. Extracts the **Name** and **Position/Designation** fields by locating each
   label and reading the words to its right; matching uses vertical alignment,
   not Tesseract's line grouping.
4. Normalizes the name to Proper Case and builds the target filename
   `<Employee Name>.pdf`.
5. Classifies the department by looking up the (normalized, lowercase)
   designation in `department_library.json`.
6. In dry-run mode, writes a preview to the audit CSV. Source PDFs are left
   unchanged; audit logs, debug crops, and OCR TSV output are still written.
7. In apply mode, renames each PDF and **moves** it into
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

- Windows. Apply mode is explicitly Windows-only, and the supplied launchers
  are Windows-specific.
- A Python interpreter and a project-local `venv` (created by setup, below).
- The Tesseract OCR runtime — executable, required DLLs, and
  `tessdata/eng.traineddata`. Not included in the repository; see "Tesseract"
  below.

Setup currently installs `pymupdf`, `pillow`, and `pytesseract` from
`requirements.txt`. The active renamer calls `tesseract.exe` directly via
`subprocess` and parses the TSV output itself, so it does **not** use
`pytesseract`; the supplied `SanityCheck.ps1` still imports it as part of its
environment check. References to `pytesseract` in old snapshots under
`Archived/` predate the current direct-subprocess design.

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

## Portable runtime setup

This project needs two portable runtimes. Neither is included in the
repository, and neither needs to be installed into Windows — both are
extracted into folders and run from there.

### WinPython (Python interpreter)

1. Download a WinPython release from
   <https://github.com/winpython/winpython/releases> — the "dot" (minimal)
   64-bit build is sufficient. The distribution is a 7-Zip self-extracting
   archive or a plain zip.
2. Extract it anywhere; the folder is self-contained and portable. This
   setup was developed with Python 3.13.13 under
   `C:\Radio Room\crew_dashboard\WinPython`.
3. Find the interpreter you extracted:

   ```
   python -c "import sys; print(sys.executable)"
   ```

4. `SetupEnvironment.bat` tries a few known locations automatically (a
   `WinPython` folder next to the project, one inside the project, and the
   `crew_dashboard` path above). If yours is elsewhere, pass it
   explicitly:

   ```
   SetupEnvironment.bat -PythonExe "FULL PATH TO python.exe"
   ```

   The base interpreter is only used once, to create the project-local
   `venv`; everything after that runs from the venv.

### Tesseract OCR (OCR engine)

1. Download the Windows installer from the UB Mannheim builds page:
   <https://github.com/UB-Mannheim/tesseract/wiki>. This project uses
   build `tesseract-ocr-w64-setup-5.5.3.20260724.exe`.
2. Extract the installer with 7-Zip (right-click the `.exe` → 7-Zip →
   Open archive → Extract) instead of running it. This is how the
   runtime in `tools\tesseract` was produced — no installation required.
3. Place the complete extracted runtime in `tools\tesseract\`, keeping
   its layout intact:

   ```
   tools/tesseract/
       tesseract.exe
       ...runtime DLLs and resources...
       tessdata/
           eng.traineddata
           configs/tsv
   ```

   Copy the whole folder, not just `tesseract.exe` — the DLLs and
   `tessdata` (including `configs/tsv`, which the script's `tsv` output
   mode needs) must sit alongside the executable.
4. The project checks `tools\tesseract\tesseract.exe` first, then falls
   back to Tesseract on `PATH`. `SanityCheck.bat` verifies the runtime
   and English language data.

Notes: `tools/` is gitignored, so the Tesseract runtime is not part of
the repository. The WinPython distribution normally lives outside this
project (shared with the crew dashboard workspace). Extracting the
runtimes does not make `SetupEnvironment.bat` offline — it still
downloads the Python packages from `requirements.txt`.

## Tesseract

Two supported options:

1. **User-provided project-local runtime**: place the complete OCR runtime
   (executable, DLLs, and `tessdata/eng.traineddata`) in `tools/tesseract/`.
   This folder is gitignored; a fresh clone does not contain it — populate it
   locally.
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
   environment (Python imports, dependency consistency, Tesseract executable,
   and `eng` language availability). External runtime:
   `SanityCheck.bat -Tesseract "FULL PATH TO tesseract.exe"`.
3. Put **copies** of PDFs directly in `input/`.
4. Run `dry_run.bat` to preview extracted names, designations, and department
   classifications. Source PDFs are not modified; audit logs and debug output
   are written.
5. Review the audit CSV and debug crops. Fix calibration (below) if needed.
6. Run `apply_rename.bat` and type `yes` at its prompt to rename and move files
   into `input/Timesheets/<DEPARTMENT>/`. Invoking the script directly with
   `python rename_pdfs.py input --apply` bypasses that prompt.

The run launchers use the project's `venv` Python directly; no activation
required. They do not install dependencies at startup.

## Calibration

First page only; fixed layout and rotation per invocation; no folder watching.

- Default rotation is 90 degrees counterclockwise for the supplied sideways
  preview. Use `--rotate 0` if the PDF already renders upright.
- Default ROI: `0.55 0.04 0.95 0.20` (fractions of page size after rotation,
  top-left origin). Include the Name and Position/Designation fields in the
  crop; each value should appear to the right of its label, and matching uses
  vertical alignment rather than Tesseract's line grouping.

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
  are routed to `input/Timesheets/REVIEW/` where possible. Routing is best-effort:
  if the REVIEW destination already exists, the source PDF can remain in
  `input/`.
- The audit CSV's post-move status is built from the classified department,
  even when a low-confidence or collision case was actually routed to REVIEW;
  treat it as a classification record, not a guaranteed statement of the
  file's final location.
- PDF contents are not rewritten; only filenames change and files are moved.
- Debug crops and TSV output contain personal data; secure them.
- Do not run concurrent jobs or change the input folder while processing.
- No automatic undo. Use copies and retain the audit logs.

## Customizing the department library

`department_library.json` maps a designation (lowercase, after normalization)
to a department code. To add a new designation, add a key like:

```json
{
  "new designation title": "MAINT"
}
```

Add the entry inside the existing JSON object (keeping commas correct).

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

## Validation scope

`SanityCheck.bat` covers Python imports, dependency consistency, the Tesseract
executable, and English language availability. It does not validate OCR
accuracy or crop calibration — verify those with a dry run and the debug
crops. Runtime, OCR binaries, venv, and sample PDFs are not included in the
repository.

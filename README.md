# PDF Employee Renamer & Department Classifier - Windows / WinPython

Outputs clean Proper Case filenames (e.g., `Lucas Negreiros Ferreira.pdf`), classifies employees into departments using an optimized zero-latency lookup library (`department_library.json`), and automatically sorts and moves processed files into structured department subfolders.

No frontend, Flask, database, or web server required.

## Placement
Extract PDF_Employee_Renamer under C:\Radio Room\crew_dashboard.
This creates a SEPARATE PDF_Employee_Renamer\venv and does not alter the
crew dashboard venv or its requirements. Ensure `department_library.json` is placed in the root directory alongside `rename_pdfs.py`.

## Setup (internet required)
Double-click SetupEnvironment.bat. It creates the local environment when absent,
then installs the three dependencies from requirements.txt and runs pip check.
Rerunning setup installs/checks requirements in that same environment.
No recycle, offline, freeze, lock-file, or destructive rebuild mode is included.

Base Python detection tries the parent workspace WinPython\python\python.exe,
a project-local WinPython\python\python.exe, then the known workspace path.
This interpreter location comes from your example setup; it is not verified on
this computer. If your WinPython distribution uses another directory name:
1. In Command Prompt, run:
    call "C:\Radio Room\crew_dashboard\WinPython\scripts\activate.bat"
    python -c "import sys; print(sys.executable)"
2. Use the printed path:
    SetupEnvironment.bat -PythonExe "FULL PATH TO python.exe"
The activate.bat path is NOT the interpreter executable.

## Tesseract
Not bundled. Put the complete OCR runtime (executable, DLLs and
 tessdata/eng.traineddata) in tools/tesseract, or add Tesseract to PATH.
External executable example:
dry_run.bat --tesseract "C:\Program Files\Tesseract-OCR\tesseract.exe"
Use the same --tesseract option on apply_rename.bat.

## Workflow & Automated Sorting
1. Run SetupEnvironment.bat.
2. Provide Tesseract runtime and run SanityCheck.bat.
   External runtime: SanityCheck.bat -Tesseract "FULL PATH TO tesseract.exe"
3. Put COPIES of PDFs directly in `input` (no subfolder scanning).
4. Run dry_run.bat to inspect extracted names, designations, department classifications, and debug crops via the CSV audit log.
5. Run apply_rename.bat and type `yes` to rename files and **automatically move them** into structured subfolders under `Timesheets`:
   - `Timesheets/ADM`
   - `Timesheets/MAINT`
   - `Timesheets/MAR`
   - `Timesheets/PROD`
   - `Timesheets/REVIEW` (Routing location for low confidence, unknown departments, or errors).

The run launchers use the project's venv Python directly; no activation required.
They do not install dependencies at startup.

## Crop calibration and limits
First page only; fixed layout and rotation per invocation; no folder watching.
Default rotation is 90 degrees COUNTERCLOCKWISE for the supplied sideways preview.
Use --rotate 0 if the PDF already renders upright.
Default ROI: 0.55 0.04 0.95 0.20, an initial estimate.
Coordinates are fractions of page size AFTER rotation, top-left origin.
Keep the Name and Designation labels together on the same OCR line.
Example: dry_run.bat --rotate 0 --roi 0.55 0.04 0.95 0.20
Repeat the same options on apply_rename.bat after verifying the crop.
Names are normalized to Proper Case (Title Case) automatically. Names must have at least two words. 
Missing/ambiguous fields, low confidence, unknown department classifications, and filename collisions are safely routed to the `REVIEW` folder. Confidence is only a screening heuristic.
PDF contents are not rewritten. Debug files contain personal data; secure them.
Do not run concurrent jobs or change the input folder while processing.
No automatic undo. Use copies and retain audit logs.

## Validation
Python syntax, filename normalization, department library lookup, and archive integrity were checked. Runtime, OCR binaries, venv, and sample PDFs are not bundled.
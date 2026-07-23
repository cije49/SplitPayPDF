# Building SplitPayPDF_Portable

Copy-and-run distribution: target machines need **no Python, no pip, no admin
rights, no internet**. Everything is prepared once on a build machine.

## How it works

The bundle is based on the official **Python embeddable distribution**
(a plain ZIP from python.org, no installer, fully relocatable). Two additions
are made at build time:

1. **tkinter + Tcl/Tk** are copied in from the build machine's normal Python
   install (the embeddable ZIP does not include them).
2. Dependencies from `requirements.txt` (`pymupdf`, `ttkbootstrap`,
   `tkinterdnd2`) are installed with `pip install --target` into the bundle's
   `Lib\site-packages` — pip runs only on the build machine.

The launcher `Run_SplitPayPDF.cmd` starts `python\python.exe app\SplitPayPDF.py`
with paths relative to its own location. No `.exe` is created or packed.

## Build machine prerequisites

- Windows, internet access
- 64-bit Python 3.10+ installed from **python.org** with the default
  "tcl/tk and IDLE" option (the Windows Store Python will not work —
  the script checks and tells you)

## Build

From the repository root:

```
powershell -ExecutionPolicy Bypass -File .\build_portable.ps1
```

Output: `SplitPayPDF_Portable\` next to the script (roughly 100–150 MB; the
bulk is PyMuPDF and the bundled Tcl/Tk). Options:

```
-OutputDir D:\somewhere\SplitPayPDF_Portable   # different output location
-PythonExe C:\Python312\python.exe             # pick a specific build Python
-EmbedZip  C:\dl\python-3.12.10-embed-amd64.zip # offline build (pre-downloaded,
                                                # must match build Python version)
```

The script ends with a smoke test (`import fitz, tkinter, ttkbootstrap,
tkinterdnd2` using the bundled runtime). If that fails the build aborts.

## Verify, then distribute

1. On the build machine: double-click `SplitPayPDF_Portable\Run_SplitPayPDF.cmd`,
   run a SAFE-mode split on a test PDF.
2. ZIP the whole folder and distribute (network share is best — avoids
   Mark-of-the-Web/SmartScreen prompts that email/browser downloads get).
3. Users: extract fully, double-click `Run_SplitPayPDF.cmd`. See
   `README_PORTABLE.txt` (users) and `IT_SECURITY_NOTES.txt` (IT review)
   inside the bundle.

## Resulting structure

```
SplitPayPDF_Portable/
├── Run_SplitPayPDF.cmd      launcher (plain text)
├── README_PORTABLE.txt      user instructions
├── IT_SECURITY_NOTES.txt    for IT/security review
├── app/                     SplitPayPDF.py + splitpay_core.py + README, LICENSE, requirements.txt
├── python/                  embeddable CPython + tcl/tk + site-packages
├── data/                    optional user workspace (not required by the app)
└── logs/                    optional; the real app log is %APPDATA%\SplitPayPDF\
```

## Notes / limitations

- 64-bit Windows 10/11 targets only (matches the bundled runtime).
- Settings/schemas/log remain per-user in `%APPDATA%\SplitPayPDF` — unchanged
  app behavior; nothing is written into the portable folder or Program Files.
- Rebuild the bundle whenever `SplitPayPDF.py`, `splitpay_core.py` or
  `requirements.txt` changes.
- If the company blocks `python.exe` by policy (AppLocker/WDAC, not ASR),
  this approach won't help — test on one company machine first.

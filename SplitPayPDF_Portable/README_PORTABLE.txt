SplitPayPDF Portable
====================

HOW TO USE
----------
1. Copy the ENTIRE "SplitPayPDF_Portable" folder to your computer
   (for example to your Desktop or D:\Tools). If you received it as a
   ZIP file, extract it fully first - do not run it from inside the ZIP.
2. Double-click "Run_SplitPayPDF.cmd".
3. The app window opens. A black console window stays open in the
   background while the app runs - this is normal, just leave it.

That's it. No installation, no Python setup, no admin rights,
no internet connection needed.

RULES
-----
- Do NOT move or delete files inside this folder (especially the
  "python" and "app" subfolders). Move/copy the whole folder only.
- You can rename or move the whole folder freely.

FOLDERS
-------
  app\      the application itself
  python\   the bundled Python runtime (do not touch)
  data\     optional workspace for your input/output PDFs
  logs\     optional folder for exported logs

Your settings, saved schemas and the app log are stored per-user in:
  %APPDATA%\SplitPayPDF
(so several people can use the same shared copy of the folder).

IF IT DOESN'T START
-------------------
- If Windows shows "protected your PC" (SmartScreen) on the ZIP or
  .cmd file: right-click the downloaded ZIP -> Properties -> Unblock,
  then extract again.
- If the console window shows an error, take a screenshot of it or
  copy the text - it tells us exactly what went wrong.
- App log file: %APPDATA%\SplitPayPDF\app_log.txt

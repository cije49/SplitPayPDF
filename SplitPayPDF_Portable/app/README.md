# SplitPayPDF

SplitPayPDF is a Windows desktop application for splitting, managing, and processing PDF files.  
It features a clean ttkbootstrap UI, intuitive help popups, and multiple PDF utilities built into a single tool.

---

# 📑 Table of Contents

- [✨ Features](#-features)
  - [PDF Splitter](#pdf-splitter)
  - [Advanced Debug & Schema-Based Naming System](#advanced-debug--schema-based-naming-system)
  - [PDF Tools](#pdf-tools)
- [📸 Screenshots](#-screenshots)
- [🛠️ Requirements](#️-requirements)
- [📥 Installation](#-installation)
- [🚀 Packaging / Building EXE](#-packaging--building-exe)
- [📂 Folder Structure](#-folder-structure)
- [📜 License](#-license)

---

## ✨ Features

### **PDF Splitter**
- Split PDFs by:
  - Page ranges  
  - Every N pages  
  - Specific lists of pages  
- Auto-rename duplicate output files  
- Intuitive progress dialogs  
- Support for Unicode paths

---

### **Advanced Debug & Schema-Based Naming System**

SplitPayPDF includes a powerful **debug reading mode** that displays each parsed line of a PDF as:

```
[LINE x] <content>
```

This allows users to inspect document structure and build custom **naming schemas** for:

- Employee folders  
- Output PDF filenames  
- Automated organization  

When debug mode is disabled, the app will automatically:

- Extract naming information  
- Generate or match employee folders  
- Save each split PDF into the correct destination  

Additional features:

- Schemas can be **saved** and **loaded**  
- All schemas & logs are stored in **APPDATA**  
- A **`!manual_review`** folder is automatically created for failed naming extractions  
- An **audit log** records all steps (toggle option planned)

---

## **PDF Tools**
- PDF → CSV extraction using PyMuPDF + pandas  
- Page counting  
- PDF metadata extraction  
- Basic PDF merging and splitting  
- Clean UI with contextual help popups  

---

## 📸 Screenshots

### Main Interface  
![Main UI](images/main_ui.png)

### Debug Mode  
![Debug Mode](images/debug_mode.png)

### Schema Builder  
![Schema Builder](images/schema_builder.png)

### Demo  
![Demo GIF](images/demo.gif)

---

## 🛠️ Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

Your `requirements.txt` should contain:

```
pymupdf>=1.24.0
ttkbootstrap>=1.10.1
tkinterdnd2>=0.4.0
```

(`tkinter` is part of the Python standard library. `ttkbootstrap` and
`tkinterdnd2` are optional at runtime — the app falls back to the classic
theme and no drag-and-drop if they are missing.)

---

## 📥 Installation

### Option 1 — Run from source

1. Install Python 3.10+  
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python SplitPayPDF.py
   ```

### Option 2 — Portable folder (no install, no admin, no pip on target)

For locked-down environments (e.g. Defender ASR blocking .exe files), build a
copy-and-run folder with a bundled Python runtime:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_portable.ps1
```

Users just copy `SplitPayPDF_Portable\` and double-click `Run_SplitPayPDF.cmd`.
See [BUILD_PORTABLE.md](BUILD_PORTABLE.md) for details.

---

## 🚀 Packaging / Building EXE

To build a standalone Windows executable:

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Build with:
   ```bash
   pyinstaller --noconfirm SplitPayPDF.spec
   ```
3. Output EXE will be located in:
   ```
   dist/SplitPayPDF/SplitPayPDF.exe
   ```

---

## 📂 Folder Structure

```
SplitPayPDF/
│
├── SplitPayPDF.py
├── SplitPayPDF.spec
├── requirements.txt
├── README.md
├── LICENSE
├── .gitignore
│
├── images/
│   ├── main_ui.png
│   ├── debug_mode.png
│   ├── schema_builder.png
│   └── demo.gif
│
└── dist/
    └── SplitPayPDF.exe
```

---

## 📜 License

This project is open-source under the MIT License.  
See the `LICENSE` file for full details.

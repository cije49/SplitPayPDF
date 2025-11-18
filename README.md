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
PyPDF2>=3.0.0
ttkbootstrap>=1.10.1
Pillow>=10.0.0
pandas>=2.0.0
pymupdf>=1.24.0
```

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

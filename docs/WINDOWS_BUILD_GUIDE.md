# Windows Build Guide - Crypto Tax Pro

This guide outlines the requirements and steps to compile the Crypto Tax Pro desktop application into a standalone Windows executable (`.exe`).

## 1. Prerequisites

Before building, ensure your system meets the following requirements:

### A. Python Environment
* **Python 3.12+**: Ensure Python is installed and added to your PATH.
* **Virtual Environment**: It is highly recommended to use the project's virtual environment (`.venv`).

### B. Development Tools
* **Visual Studio Build Tools**: 
    - Download from [visualstudio.microsoft.com](https://visualstudio.microsoft.com/downloads/).
    - During installation, select the **"Desktop development with C++"** workload.
    - Ensure the **MSVC v143 - VS 2022 C++ x64/x86 build tools** and **Windows 11 SDK** (or Windows 10) are checked.
* **Flutter SDK**:
    - Flet relies on Flutter for the GUI engine.
    - Download from [docs.flutter.dev](https://docs.flutter.dev/get-started/install/windows).
    - Add the `flutter/bin` directory to your system's PATH.

### C. Libraries
The project requires several Python packages. Install them using:
```powershell
pip install -r requirements.txt
```

---

## 2. Building the Application

The build process is managed by the `flet` CLI tool. It will package the Python logic, the Flet/Flutter UI, and all dependencies into a single folder.

### Step 1: Install Flet CLI
Ensure you have the latest version of flet:
```powershell
pip install flet --upgrade
```

### Step 2: Run the Build Command
Open a terminal in the project root directory and run:

```powershell
flet build windows --main app/main_gui.py
```

**Parameters explained:**
* `build windows`: Specifies the target platform.
* `--main app/main_gui.py`: Points to the entry point of the GUI application.

### Step 3: Optimization (Optional)
To create a cleaner build without specific console windows appearing in the background:
```powershell
flet build windows --main app/main_gui.py --product "Crypto Tax Pro" --description "Desktop crypto tax calculator"
```

---

## 3. Distribution

Once the command finishes successfully:

1. Navigate to the `build/windows` directory.
2. You will find a folder containing `crypto_tax_pro.exe` (or similar name based on your project settings).
3. **Important**: When sharing the app, you must share the **entire folder**, as it contains required DLLs and assets.

---

## 4. Troubleshooting

* **"MSVC not found"**: Ensure you installed the C++ workload in Visual Studio and restarted your terminal.
* **"Flutter not in PATH"**: Verify that running `flutter --version` works in your terminal.
* **ModuleNotFoundError**: Ensure you are running the build command from within the activated virtual environment where all dependencies are installed.

[![Twitter URL](https://img.shields.io/twitter/url/https/twitter.com/deanthecoder.svg?style=social\&label=Follow%20%40deanthecoder)](https://twitter.com/deanthecoder)

# DTC.Installer

A cross-platform Python script for packaging .NET applications with a single command.
Works seamlessly as a Git submodule or standalone folder inside your project.

## Requirements

* **Python 3.9+**
* **Inno Setup 6** (standard install makes `ISCC.exe` available on PATH)
* **.NET SDK** matching your target project (used by `dotnet publish`)

## Quick Start

1. Add this repository as a submodule in your .NET project:

   ```bash
   git submodule add https://github.com/deanthecoder/DTC.Installer.git Installer
   ```

   *(Alternatively, copy the files manually into an `Installer/` folder.)*

2. From the app root, run:

   ```bash
   python Installer/pack.py
   ```

   The first run generates a `packaging.json` configuration and exits.

3. Edit `packaging.json` to verify or adjust details such as product name, company, and project path.

4. Run the same command again to build and package your app:

   ```bash
   python Installer/pack.py
   ```

5. Retrieve the generated installer from `dist/win/`.
   To include version tags in the filename, tag your repo before building:

   ```bash
   git tag v1.0.0
   ```

Re-run step 4 any time you need a new build — existing configuration will be reused.

---

### Optional Enhancements

* **Auto-icon detection:**
  The script can automatically locate your app’s icon at `Assets/app.ico` (and `app.icns` on macOS), warning if missing.
* **Cross-platform ready:**
  Windows packaging uses Inno Setup; macOS and Linux support are planned.

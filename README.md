[![Twitter URL](https://img.shields.io/twitter/url/https/twitter.com/deanthecoder.svg?style=social\&label=Follow%20%40deanthecoder)](https://twitter.com/deanthecoder)

# DTC.Installer

A cross-platform Python script for packaging .NET applications with a single command.
Works seamlessly as a Git submodule or standalone folder inside your project.

## Requirements

* **Python 3.9+**
* **Inno Setup 6** (standard install makes `ISCC.exe` available on PATH)
* **.NET SDK** matching your target project (used by `dotnet publish`)
* **macOS tooling:** DMG generation runs on macOS and uses the built-in `hdiutil` command

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

3. Edit `packaging.json` to verify or adjust details such as product name, company, executable name, and project path.

4. Run the same command again to build and package your app:

   ```bash
   python Installer/pack.py
   ```

5. Retrieve the generated installer(s) from `dist/win/` and `dist/mac/` (for macOS builds).
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
  Windows installers use Inno Setup; macOS drag-and-drop DMGs are generated automatically, and Linux support is planned.

### Executable name

You can specify a top-level `Executable` (without `.exe`) to avoid repeating it in each platform section:

```json
{
  "Executable": "MyApp",
  "Win": {
    "Executable": "MyApp.exe"
  },
  "Mac": {
    "Executable": "MyApp"
  }
}
```

If you omit the per‑platform values, Windows packaging appends `.exe` automatically and macOS strips it if present.

### macOS Packaging

The generated `packaging.json` includes a `Mac` section with sensible defaults:

- Builds both Apple Silicon (`osx-arm64`) and Intel (`osx-x64`) runtimes.
- Produces drag-and-drop `.dmg` files under `dist/mac/`, each containing the app bundle and an `Applications` shortcut.
- Uses `Installer/templates/Info.plist` as the bundle manifest; customise icons, identifiers, or metadata by editing the `Mac` section.

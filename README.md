[![Twitter URL](https://img.shields.io/twitter/url/https/twitter.com/deanthecoder.svg?style=social&label=Follow%20%40deanthecoder)](https://twitter.com/deanthecoder)

# DTC.Installer

**DTC.Installer** is a cross‑platform packaging helper for .NET applications.
It is designed to live *inside* your repo (often as a Git submodule) and give you
a single, repeatable command to produce installable artifacts for Windows and macOS.

The goal is not to replace platform‑native tooling, but to *orchestrate it consistently*
with minimal configuration and sensible defaults.

---

## What it does

At a high level, the tool:

- Locates your `.csproj` automatically (or uses an explicit path if provided)
- Runs `dotnet publish` with the correct runtime(s)
- Generates installers using platform‑native tools
- Produces clean, versioned output in a predictable `dist/` layout
- Persists all configuration in a single `packaging.json` file

Once configured, packaging your app is a **one‑command operation**.

---

## Supported platforms

### Windows
- Uses **Inno Setup 6** (`ISCC.exe`) to build a `.exe` installer
- Handles versioning, icons, metadata, and install layout
- Automatically appends `.exe` where required

### macOS
- Builds **both Apple Silicon and Intel** runtimes by default
- Produces drag‑and‑drop **`.dmg` installers**
- Generates a proper `.app` bundle with `Info.plist`
- Automatically creates a bundle identifier if missing
- Includes an `Applications` shortcut inside the DMG

(Linux support is intentionally deferred but the structure allows it to be added cleanly.)

---

## Requirements

- **Python 3.9+**
- **.NET SDK** matching your target project
- **Inno Setup 6** (Windows packaging only)
- **macOS:** built‑in `hdiutil` (no extra installs required)

---

## Quick start

1. Add the installer to your repo (recommended as a submodule):

   ```bash
   git submodule add https://github.com/deanthecoder/DTC.Installer.git Installer
   ```

   *(Or copy it directly into an `Installer/` folder.)*

2. From your repo root, run:

   ```bash
   python Installer/pack.py
   ```

3. On first run, the script:
   - Scans for a `.csproj`
   - Infers sensible defaults (product name, company, bundle ID, etc.)
   - Writes a `packaging.json`
   - Exits without building

4. Review and tweak `packaging.json` as needed.

5. Run the same command again to build installers:

   ```bash
   python Installer/pack.py
   ```

---

## Configuration: `packaging.json`

All behaviour is driven by a single config file.

### Common fields

- `Product` – Display name of the application
- `Company` – Company / publisher name
- `Project` – Relative path to the `.csproj` (optional if auto‑detected)
- `Executable` – Base executable name (without `.exe`)
- `Version` – Optional override; otherwise inferred from Git tags

### Windows section

```json
"Win": {
  "Icon": "Assets/app.ico",
  "Publisher": "My Company Ltd"
}
```

- `.exe` is added automatically if omitted
- Missing icons generate warnings, not hard failures

### macOS section

```json
"Mac": {
  "Icon": "Assets/app.icns",
  "BundleIdentifier": "com.mycompany.myapp"
}
```

Defaults applied automatically if fields are missing:

- `BundleIdentifier` → derived from Company + Product
- Runtime targets → `osx-arm64` and `osx-x64`
- `Info.plist` → generated from template

---

## Output layout

Generated files are written to:

```
dist/
 ├─ win/
 │   └─ MyApp‑Setup‑1.2.0.exe
 └─ mac/
     ├─ MyApp‑1.2.0‑arm64.dmg
     └─ MyApp‑1.2.0‑x64.dmg
```

Version numbers are taken from the nearest Git tag:

```bash
git tag v1.2.0
```

If no tag is present, a safe fallback version is used.

---

## Design notes

- **Idempotent:** Re‑running the script reuses existing configuration
- **Submodule‑friendly:** No global installs, no repo pollution
- **Fail‑soft:** Missing optional assets emit warnings, not crashes
- **Explicit over magic:** Defaults are written into `packaging.json`, not hidden

---

## Typical workflow

```bash
# once
python Installer/pack.py
# edit packaging.json

# every release
git tag v1.3.0
python Installer/pack.py
```

That’s it.

---

## License
See [LICENSE](LICENSE) for details.
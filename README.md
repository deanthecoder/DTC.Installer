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

   To build with a one-off version without editing `packaging.json`, pass it on
   the command line:

   ```bash
   python Installer/pack.py --version 1.2
   ```

---

## Configuration: `packaging.json`

All behaviour is driven by a single config file.

### Common fields

- `Product` – Display name of the application
- `Company` – Company / publisher name
- `Project` – Relative path to the `.csproj` (optional if auto‑detected)
- `Executable` – Base executable name (without `.exe`)
- `Version` – Default package version; can be overridden for a single run with `--version`

### Windows section

```json
"Win": {
  "Icon": "Assets/app.ico",
  "Publisher": "My Company Ltd"
}
```

- `.exe` is added automatically if omitted
- Missing icons generate warnings, not hard failures
- `InstallOpenAL` (default `false`) includes `external/oalinst.exe` as `3rdParty/oalinst.exe` and runs it silently during install when enabled
- `ShowRunOnStartupTask` (default `false`) shows an unchecked installer task that can add the app to the current user's Windows startup registry key

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
python Installer/pack.py

# one-off release version
python Installer/pack.py --version 1.2
```

That’s it.

---

## GitHub Actions

The installer repo also provides a reusable workflow at:

```yaml
deanthecoder/DTC.Installer/.github/workflows/installers.yml@main
```

GitHub only discovers workflows from the parent repository's own
`.github/workflows` folder, so a submodule workflow will not run automatically
just because the submodule is checked out. Add a small wrapper workflow to each
product repo instead:

```yaml
name: Installers

on:
  workflow_dispatch:
    inputs:
      version:
        description: "Installer version, e.g. 0.1"
        required: true
        default: "0.1"
        type: string
      build_windows:
        description: "Build the Windows installer."
        required: true
        default: true
        type: boolean
      build_macos:
        description: "Build the macOS DMGs."
        required: true
        default: true
        type: boolean
      create_tag:
        description: "Create v-prefixed tag after successful builds."
        required: true
        default: true
        type: boolean

jobs:
  installers:
    permissions:
      contents: write
    uses: deanthecoder/DTC.Installer/.github/workflows/installers.yml@main
    with:
      version: ${{ inputs.version }}
      build_windows: ${{ inputs.build_windows }}
      build_macos: ${{ inputs.build_macos }}
      create_tag: ${{ inputs.create_tag }}
```

The reusable workflow checks out the caller repository with submodules enabled,
runs `Installer/pack.py --version ...`, and uploads:

- `dist/win/*.exe` from a Windows runner.
- `dist/mac/*.dmg` from a macOS runner.

When `create_tag` is enabled, the workflow also creates an annotated
`v<version>` tag after the selected installer builds pass. Existing tags are not
overwritten.

---

## License
See [LICENSE](LICENSE) for details.

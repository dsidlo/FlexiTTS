# App Delivery Recommendations

## Which app builder/bundeler to use?

What is the best or most popular way of creating a single bundled file for app delivery such as snap, flatpak, or appimage, given an electron app that uses a bundled python server that will work on linux, mac and windows?

### Recommendations:

There is no single Snap/Flatpak/AppImage-style file that runs on Linux, macOS, and Windows. Those three formats are Linux-only. The usual solution is one packaging pipeline that emits a **native artifact per OS**, with the Python server shipped as a sidecar binary.

#### What people actually use

The dominant stack for this architecture is:

1. Freeze the Python server with **PyInstaller** (or bundle a standalone CPython with **python-build-standalone** if you need `pip`/plugins at runtime).
2. Package the Electron app with **electron-builder** and copy the Python tree in via `extraResources`.
3. Start the server from the main process with `child_process.spawn`.

electron-builder is still the most common choice when you care about installers and Linux “one file” formats. Electron officially recommends **Electron Forge** for new apps; it can produce similar artifacts, but electron-builder has broader target support (NSIS, portable exe, DMG, AppImage, Snap, Flatpak, etc.) and a simpler `extraResources` story.

PyInstaller does **not** cross-compile well. Build the Python sidecar on each target OS/arch in CI. AppImages also need a Linux host or the `electronuserland/builder` Docker image.

#### Linux: AppImage vs Snap vs Flatpak

For an Electron + local Python server, **AppImage is the best match** to “single bundled file”:

| Format | Single file? | Install? | Sandbox | Fit for a bundled Python server |
|---|---|---|---|---|
| **AppImage** | Yes | No | No (by default) | Best. Drop-in portable binary. electron-builder default Linux target. |
| **Snap** | Sort of (`.snap`) | Yes (`snapd`) | Yes | Fine if you want Snap Store + auto-updates. Confinement often needs extra plugs (`network`, `home`, sometimes `process-control`). |
| **Flatpak** | Possible as a `.flatpak` bundle | Yes | Yes | Most popular *desktop* format via Flathub in 2026, but more friction for a sidecar process, and electron-builder’s Flatpak output is a standalone bundle, not a Flathub repo listing. |

electron-builder’s own guidance: AppImage first for universal no-install Linux; Snap if you want the Snap Store; Flatpak if you specifically want a sandboxed desktop app.

For *users* on Fedora/Mint/Steam Deck, Flatpak/Flathub is the more common *install* channel. For *you shipping one downloadable file from GitHub Releases*, AppImage is still the straightforward choice.

#### Other platforms (the real “cross-platform” answer)

Ship these as the counterparts:

- **Windows:** NSIS `.exe` installer (default, most popular). Add `portable` if you want a no-install USB-style binary.
- **macOS:** signed + notarized `.dmg` (universal if you support Intel + Apple Silicon).
- **Linux:** AppImage as the portable file; optionally also Snap and/or `.deb`/`.rpm`.

That is what “one bundled app that works on Linux, Mac, and Windows” means in practice: three (or more) artifacts from one config, not one file.

#### How to wire the Python server

Do **not** put the Python executable inside the asar. Use `extraResources` so it lands next to the app as a real file you can exec.

```json
{
  "build": {
    "extraResources": [
      {
        "from": "python-dist/${os}/${arch}",
        "to": "python",
        "filter": ["**/*"]
      }
    ],
    "win": { "target": ["nsis", "portable"] },
    "mac": { "target": ["dmg"] },
    "linux": { "target": ["AppImage"] }
  }
}
```

Then spawn it from the main process:

```js
const { spawn } = require('child_process');
const path = require('path');
const { app } = require('electron');

const pythonDir = app.isPackaged
  ? path.join(process.resourcesPath, 'python')
  : path.join(__dirname, 'python-dist', process.platform, process.arch);

const bin = process.platform === 'win32' ? 'server.exe' : 'server';
const child = spawn(path.join(pythonDir, bin), ['--port', '8765'], {
  stdio: 'pipe',
  windowsHide: true,
});
```

Prefer PyInstaller **`--onedir`** over `--onefile` for a long-lived server: faster start, fewer AV false positives, no extract-to-temp race. `--onefile` is closer to “one file” but worse as a sidecar.

If the backend needs a real Python (plugins, `pip install` at runtime), bundle **python-build-standalone** instead of freezing, as Datasette Desktop did.

#### Practical recommendation

- **Default shipping set:** Windows NSIS + macOS DMG + Linux AppImage.
- **Linux extra:** Snap only if you want the Snap Store; Flatpak/Flathub only if Linux desktop store presence matters more than a single-file download.
- **Python:** per-platform PyInstaller `--onedir` in `extraResources`, spawned from Electron main.
- **CI:** matrix of `windows-latest`, `macos-latest` (and optionally Intel), `ubuntu-latest` (or electron-builder Docker). Build Python first, then electron-builder on that same runner.

That combination is the most popular, least surprising path for an Electron app with a bundled Python server. Snap and Flatpak are distribution *channels* on Linux, not a cross-platform packaging strategy.

## Why ElectronBuilder over ElectronForge?

Tell me more about Electron-Forge and why the older Electron-Builder is still recommended. What are the issues facing Electron-Forge?

Electron Forge is the official, first-party *workflow*. electron-builder is the unofficial, battle-tested *packager*. They solve overlapping problems with different philosophies, which is why “official” and “recommended for shipping” still diverge.

### What Electron Forge actually is

Forge is an orchestration layer around Electron’s own tools:

- `@electron/packager` — turn source into a platform folder (`.app`, `resources/`, etc.)
- `@electron/osx-sign`, `electron-winstaller`, makers for DMG/ZIP/Squirrel/deb/rpm/Flatpak/Snap
- plugins for Webpack or Vite
- publishers for GitHub, S3, etc.

You get a project scaffold (`npx create-electron-app`), a dev loop (`npm start`), then `package` → `make` → `publish`. Config lives in `forge.config.js` as plugins + makers + publishers. The pitch is: one pipeline from `create` to release, and new Electron features (ASAR integrity, universal macOS builds) land in Forge first because it uses first-party modules.

That is real. For a greenfield *pure JS* Electron app, Forge is the paved road Electron wants you on.

#### Why electron-builder is still the production default

Builder is not a scaffold. You bring your own bundler (or none). It takes a built app and emits installers, signs them, publishes them, and generates update metadata for `electron-updater`.

The reasons it stays recommended, especially for an Electron + Python sidecar:

**1. Installer surface area is larger and more mature.**  
Builder ships NSIS, NSIS-Web, portable exe, MSI, AppX/MSIX, DMG, PKG, MAS, AppImage, Snap, Flatpak, deb, rpm, and archives from one config. Forge’s first-party Windows default is still **Squirrel.Windows**, not NSIS. Squirrel works, but it is the older Windows updater model (Setup.exe + `.nupkg` + `RELEASES`), with hyphen-in-name quirks, `--squirrel-*` spawn events you must handle, and no first-class `electron-updater` support. Teams regularly migrate Forge Squirrel → builder NSIS just to get `downloadUpdate()` / `quitAndInstall()` and delta updates.

**2. Auto-update is the real differentiator.**  
- Forge path: Electron’s built-in `autoUpdater` + Squirrel.Mac / Squirrel.Windows. Fine if you host a static feed (S3 + `RELEASES` / `releases.json`). Weak if you want GitHub Releases, generic HTTPS, AppImage updates, NSIS deltas, or one API on all three OSes.
- Builder path: `electron-updater` with GitHub, S3, generic, etc., plus AppImage and NSIS updaters.

electron-builder’s own Forge maker wrappers say this explicitly: publishing, auto-update, and code signing from those makers are incomplete; if you need them, use builder as the primary tool.

**3. Config is one declarative blob.**  
`extraResources`, `asarUnpack`, per-OS targets, publish providers, signing env vars — all in `package.json` / `electron-builder.yml`. For a Python tree that must *not* go inside the asar, that mapping is obvious. Forge can do the same via `packagerConfig.extraResource`, but sidecar + multi-format + updates is several packages and hooks instead of one file.

**4. Ecosystem gravity.**  
electron-builder is ~14–15k GitHub stars vs Forge ~7.1k; it has been the default answer on Stack Overflow and in CI examples for a decade. Most “how do I ship a binary next to Electron” snippets assume builder’s `extraResources` / `process.resourcesPath`. That matters when you hit an edge case at 2am.

**5. Builder is a tool; Forge wants to own the app.**  
Forge plugins expect to compile main/renderer (Vite/Webpack). That is great until you have a frozen Python distro, native addons, or a custom build graph. Builder does not care how you produced `dist/`. It packages what you point at.

#### Issues facing Electron Forge

These are the recurring ones, not random GitHub noise.

**Thin makers on unmaintained installers.**  
`@electron-forge/maker-flatpak` sits on `@malept/electron-installer-flatpak`, last released May 2021. Documented configs fail against current freedesktop SDKs (pinned zypak from 2021 still wants `clang++`, which the SDK does not ship). Failures surface as `flatpak-builder failed with status code 1`. The RPM maker has a similar “upstream installer stale since 2023” problem. Forge documents these as first-party makers; the implementations underneath are not kept current.

**Windows packaging is the weak spot.**  
Default Squirrel.Windows is awkward for modern consumer apps (no wizard-style NSIS options, App User Model ID rules, first-run locks, spaces in names). Maker-MSIX has open bugs around config being ignored. Builds on Windows are often described as slow or “stuck.” Production teams that care about Windows UX tend to leave Forge’s Windows maker.

**Plugin regressions around bundling.**  
`@electron-forge/plugin-vite` 7.5+ had a widely reported prune bug: runtime deps missing (`electron-updater`, `electron-log`) *or* the packaged app ballooning from ~260 MB to ~1.1 GB because `node_modules` was not filtered. That class of bug — “the framework decided what to ship” — is exactly what hurts a Python sidecar, because the sidecar is extra files the plugin does not understand.

**Abstraction cost.**  
`package` / `make` hide packager + maker + rebuild. When something hangs, you debug a stack of scoped packages. Builder’s `DEBUG=electron-builder` is ugly but one process. Forge docs are good for the happy path and thinner once you leave it.

**Squirrel.Mac / built-in updater fragility.**  
Electron’s own updater has had regressions (Mantle deserialization breaking ShipIt, helper-app path issues, “update already downloaded” races). Those are Electron bugs, not Forge bugs, but Forge *steers you onto that updater*. Builder steers you onto `electron-updater`, which has its own bugs but a larger user base and GitHub-Releases-shaped workflow.

**Heavier install / native rebuild always in the tree.**  
`@electron/rebuild` / `node-gyp` come along even if you have no native modules. That bites locked-down corporate npm environments.

**Linux “one file” is not first-class the way it is in builder.**  
Forge can emit AppImage/Snap, including via electron-builder’s *maker wrappers* — but those wrappers do not give you builder’s publish + updater + signing pipeline. For AppImage + `electron-updater`, people still end up running builder.

**Universal macOS is easier to misconfigure.**  
It works, but `targetArch` / packagerConfig placement and native-module fat binaries are a frequent source of “make failed” threads. Builder’s `--universal` path is equally picky, just more documented in one place.

Forge is not abandoned — v7.11 is current, v8 is in alpha as of mid-2026 — but its value is *integration*, not *installer completeness*.

#### How this maps to your Electron + Python app

| Concern | Forge | electron-builder |
|---|---|---|
| Official Electron docs / templates | Yes | Community |
| Vite/Webpack dev loop | Built-in plugins | Bring your own |
| Bundle a PyInstaller tree | `packagerConfig.extraResource` | `extraResources` (usual snippets) |
| Windows installer users expect | Squirrel unless you add a builder maker | NSIS / portable |
| Linux single file | Maker or builder wrapper | AppImage first-class |
| Auto-update from GitHub Releases | Roll your own / Squirrel feeds | `electron-updater` |
| Signing + publish in CI | Possible, more wiring | One `--publish` pipeline |

For a bundled Python server you already have a second build system (PyInstaller / python-build-standalone) and you care about AppImage + NSIS + DMG. That is builder’s home turf. Forge would add a bundler plugin you may not need and a Windows updater you will probably replace.

#### A reasonable split

- **New, JS-only app, happy with Squirrel + ZIP/DMG:** Forge.
- **Anything with extra binaries, store-grade installers, or GitHub auto-update:** electron-builder.
- **Already on Forge and only missing NSIS/AppImage:** you can add `electron-forge-maker-nsis` / `electron-forge-maker-appimage` without abandoning Forge — just know signing/publish/updater still want full builder.

“Older” here is slightly misleading: builder is older *and* still more complete at the last mile. Forge won the onboarding war. Builder still wins the shipping war, which is why it keeps getting recommended for apps like yours.

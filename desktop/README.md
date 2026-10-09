# RoBo POS Desktop for Windows

This Electron app opens the configured Robo POS server in a desktop window. On first launch, enter the server URL; the app saves it on this computer and uses it on later launches. Sales receipts that call `window.print()` are sent silently to the Windows default printer.

## Requirements

- Windows 10 or later
- Node.js 22.12 or later with npm
- Internet connection for the hosted POS
- Xprinter installed in Windows; set it as the default printer for silent receipt printing

## Install and run locally

Open PowerShell in this `desktop` folder, then run:

```powershell
npm install
npm start
```

The app opens maximized with the menu bar hidden. It uses the existing Railway-hosted application, so logins and POS data remain on the server.

## Background radio

The compact RoBo Radio control appears on the signed-in POS pages. It lists jazz, lounge, and instrumental stations from the Radio Browser directory, remembers the selected station and sound settings, and attempts to resume playback when the app opens. Keep an internet connection available. Browsers may block autoplay until Play is pressed once.

Radio station streams have their own usage terms. Confirm that a station and any required local public-performance license allow playback in a restaurant before using it for business.

## Windows app icon

The installer and app window use the RoBo robot icon in `assets\robo.ico`. Its editable vector artwork is in `assets\robo.svg`. To use a different Windows icon, replace `assets\robo.ico` with a multi-resolution `.ico` file, then rebuild the installer:

```powershell
npm run dist:win
```

The build uses the `.ico` file for the application window, installer, and shortcuts.

## Build the installer

In PowerShell, from this folder:

```powershell
npm install
npm run dist:win
```

The NSIS installer is created in:

```text
desktop\release\RoBo POS Setup 1.0.0.exe
```

The installer allows the user to choose an installation folder and creates Start Menu and desktop shortcuts.

## Printing

The app intercepts the POS receipt page's `window.print()` call and invokes Electron's `webContents.print({ silent: true, printBackground: true })`. Silent printing uses the Windows default printer; select the Xprinter and its 80 mm roll in Windows printer settings before use.

const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const fs = require('node:fs');
const path = require('node:path');

const APP_URL = 'https://pos-gigaversia-production.up.railway.app/';
const APP_ORIGIN = new URL(APP_URL).origin;
const PRELOAD_PATH = path.join(__dirname, 'preload.js');
const ICON_PATH = path.join(__dirname, 'assets', 'robo.ico');

let mainWindow;

function isTrustedAppUrl(value) {
  try {
    return new URL(value).origin === APP_ORIGIN;
  } catch {
    return false;
  }
}

function secureWebPreferences() {
  return {
    preload: PRELOAD_PATH,
    contextIsolation: true,
    nodeIntegration: false,
    sandbox: true
  };
}

function protectNavigation(window) {
  window.webContents.on('will-navigate', (event, destination) => {
    if (destination !== 'about:blank' && !isTrustedAppUrl(destination)) {
      event.preventDefault();
    }
  });

  window.webContents.setWindowOpenHandler(({ url }) => {
    if (url === 'about:blank') {
      return {
        action: 'allow',
        overrideBrowserWindowOptions: {
          title: 'RoBo — Qəbz',
          width: 420,
          height: 760,
          minWidth: 360,
          minHeight: 480,
          show: false,
          autoHideMenuBar: true,
          ...(process.platform === 'win32' && fs.existsSync(ICON_PATH) ? { icon: ICON_PATH } : {}),
          webPreferences: secureWebPreferences()
        }
      };
    }

    if (/^https?:\/\//i.test(url)) {
      shell.openExternal(url).catch(error => {
        console.error('Xarici keçid açıla bilmədi:', error);
      });
    }
    return { action: 'deny' };
  });

  window.webContents.on('did-create-window', childWindow => {
    childWindow.setMenuBarVisibility(false);
    childWindow.once('ready-to-show', () => childWindow.show());
    protectNavigation(childWindow);
  });

  window.webContents.on('before-input-event', (event, input) => {
    if (
      input.type === 'keyDown' &&
      input.key.toLowerCase() === 'p' &&
      (input.control || input.meta)
    ) {
      event.preventDefault();
      requestSilentPrint(window.webContents);
    }
  });
}

function requestSilentPrint(webContents) {
  if (webContents.isDestroyed()) return;

  webContents.print(
    {
      silent: true,
      printBackground: true
    },
    (success, failureReason) => {
      if (success) {
        const printWindow = BrowserWindow.fromWebContents(webContents);
        if (printWindow && printWindow !== mainWindow) {
          setTimeout(() => {
            if (!printWindow.isDestroyed()) printWindow.close();
          }, 250);
        }
        return;
      }

      const reason = failureReason || 'Naməlum printer xətası';
      console.error(`Səssiz çap uğursuz oldu: ${reason}`);
      dialog.showErrorBox(
        'Çap xətası',
        `Qəbz printerə göndərilə bilmədi.\n\n${reason}\n\nWindows-da Xprinter-i standart printer seçib yenidən yoxlayın.`
      );
    }
  );
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 960,
    minHeight: 640,
    show: false,
    autoHideMenuBar: true,
    ...(process.platform === 'win32' && fs.existsSync(ICON_PATH) ? { icon: ICON_PATH } : {}),
    webPreferences: secureWebPreferences()
  });

  mainWindow.setMenuBarVisibility(false);
  protectNavigation(mainWindow);
  mainWindow.once('ready-to-show', () => {
    mainWindow.maximize();
    mainWindow.show();
  });
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  mainWindow.loadURL(APP_URL).catch(error => {
    console.error('Robo POS yüklənmədi:', error);
    dialog.showErrorBox(
      'Robo POS açılmadı',
      'Railway saytına qoşulmaq mümkün olmadı. İnternet bağlantısını yoxlayıb proqramı yenidən başladın.'
    );
  });
}

app.whenReady().then(() => {
  ipcMain.handle('robo:print', event => {
    const printWindow = BrowserWindow.fromWebContents(event.sender);
    if (!printWindow || printWindow.isDestroyed()) {
      throw new Error('Çap pəncərəsi artıq mövcud deyil.');
    }
    requestSilentPrint(event.sender);
  });

  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

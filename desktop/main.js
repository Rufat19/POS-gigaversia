const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const fs = require('node:fs');
const path = require('node:path');

const PRELOAD_PATH = path.join(__dirname, 'preload.js');
const SETUP_PRELOAD_PATH = path.join(__dirname, 'setup-preload.js');
const SETUP_PAGE_PATH = path.join(__dirname, 'setup.html');
const ICON_PATH = path.join(__dirname, 'assets', 'robo.ico');

let mainWindow;
let setupWindow;
let settingsStore;
let appUrl;
let appOrigin;

app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');
app.commandLine.appendSwitch('disable-http-cache');

function isTrustedAppUrl(value) {
  try {
    return new URL(value).origin === appOrigin;
  } catch {
    return false;
  }
}

function normalizeServerUrl(value) {
  if (typeof value !== 'string' || !value.trim()) {
    throw new Error('Server ünvanını daxil edin.');
  }

  let parsedUrl;
  try {
    parsedUrl = new URL(value.trim());
  } catch {
    throw new Error('Düzgün server ünvanı daxil edin (məsələn, https://example.com).');
  }

  if (!['http:', 'https:'].includes(parsedUrl.protocol) || parsedUrl.username || parsedUrl.password) {
    throw new Error('Server ünvanı http:// və ya https:// ilə başlamalıdır.');
  }

  return parsedUrl.toString();
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

  mainWindow.loadURL(appUrl).catch(error => {
    console.error('Robo POS yüklənmədi:', error);
    dialog.showErrorBox(
      'Robo POS açılmadı',
      'Serverə qoşulmaq mümkün olmadı. İnternet bağlantısını və saxlanmış server ünvanını yoxlayın.'
    );
  });
}

function createSetupWindow() {
  setupWindow = new BrowserWindow({
    width: 520,
    height: 360,
    resizable: false,
    show: false,
    autoHideMenuBar: true,
    ...(process.platform === 'win32' && fs.existsSync(ICON_PATH) ? { icon: ICON_PATH } : {}),
    webPreferences: {
      preload: SETUP_PRELOAD_PATH,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });
  setupWindow.setMenuBarVisibility(false);
  setupWindow.once('ready-to-show', () => setupWindow.show());
  setupWindow.on('closed', () => {
    setupWindow = null;
  });
  setupWindow.loadFile(SETUP_PAGE_PATH).catch(error => {
    console.error('Server ünvanı pəncərəsi açıla bilmədi:', error);
    dialog.showErrorBox('Quraşdırma xətası', 'Server ünvanı pəncərəsini açmaq mümkün olmadı.');
  });
}

async function startApp() {
  const { default: Store } = await import('electron-store');
  settingsStore = new Store({ name: 'settings' });

  ipcMain.handle('robo:print', event => {
    const printWindow = BrowserWindow.fromWebContents(event.sender);
    if (!printWindow || printWindow.isDestroyed()) {
      throw new Error('Çap pəncərəsi artıq mövcud deyil.');
    }
    requestSilentPrint(event.sender);
  });

  ipcMain.handle('robo:save-server-url', (_event, value) => {
    const normalizedUrl = normalizeServerUrl(value);
    settingsStore.set('serverUrl', normalizedUrl);
    appUrl = normalizedUrl;
    appOrigin = new URL(appUrl).origin;
    if (setupWindow && !setupWindow.isDestroyed()) setupWindow.close();
    createWindow();
    return true;
  });

  const savedUrl = settingsStore.get('serverUrl');
  if (typeof savedUrl === 'string') {
    try {
      appUrl = normalizeServerUrl(savedUrl);
      appOrigin = new URL(appUrl).origin;
    } catch (error) {
      console.error('Saxlanmış server ünvanı yanlışdır:', error);
    }
  }

  if (appUrl) {
    createWindow();
  } else {
    createSetupWindow();
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length !== 0) return;
    if (appUrl) {
      createWindow();
    } else {
      createSetupWindow();
    }
  });
}

app.whenReady().then(startApp).catch(error => {
  console.error('Robo POS işə salına bilmədi:', error);
  dialog.showErrorBox('Robo POS açılmadı', 'Proqramı işə salmaq mümkün olmadı.');
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

const fs = require('node:fs');
const path = require('node:path');

const iconPath = path.join(__dirname, 'assets', 'robo.ico');
const win = {
  target: ['nsis']
};

if (fs.existsSync(iconPath)) {
  win.icon = 'assets/robo.ico';
}

module.exports = {
  appId: 'az.robo.pos',
  productName: 'RoBo POS',
  directories: {
    output: 'release',
    buildResources: 'assets'
  },
  files: ['main.js', 'preload.js', 'setup-preload.js', 'setup.html', 'package.json'],
  win,
  nsis: {
    oneClick: false,
    allowToChangeInstallationDirectory: true,
    createDesktopShortcut: true,
    createStartMenuShortcut: true,
    shortcutName: 'RoBo POS'
  }
};

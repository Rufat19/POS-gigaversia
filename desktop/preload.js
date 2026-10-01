const { contextBridge, ipcRenderer, webFrame } = require('electron');

contextBridge.exposeInMainWorld('roboDesktop', {
  print: () => ipcRenderer.invoke('robo:print')
});

window.addEventListener(
  'DOMContentLoaded',
  () => {
    webFrame
      .executeJavaScript(`
        (() => {
          if (!window.roboDesktop) return;
          window.print = () => window.roboDesktop.print();
        })();
      `)
      .catch(error => {
        console.error('Səssiz çap körpüsü qurulmadı:', error);
      });
  },
  { once: true }
);

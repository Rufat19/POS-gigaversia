const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('roboSetup', {
  saveServerUrl: value => ipcRenderer.invoke('robo:save-server-url', value)
});

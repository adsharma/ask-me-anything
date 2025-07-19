// preload.js
const {contextBridge, ipcRenderer} = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  getPythonPort: () => ipcRenderer.invoke("get-python-port"),
  // Pass options object to showOpenDialog
  showOpenDialog: (options) => ipcRenderer.invoke("show-open-dialog", options),
  openSettingsDialog: () => ipcRenderer.invoke("open-settings-dialog"),
  // Expose the new file reading function
  readFileContent: (filePath) => ipcRenderer.invoke("read-file-content", filePath),
  // Settings functions
  getCurrentSettings: () => ipcRenderer.invoke("get-current-settings"),
  getAvailableModels: () => ipcRenderer.invoke("get-available-models"),
  saveApiKey: (apiKey, model) => ipcRenderer.invoke("save-api-key", apiKey, model),
  onApiKeyUpdate: (callback) =>
    ipcRenderer.on("api-key-update-status", (event, ...args) =>
      callback(...args)
    ),
});

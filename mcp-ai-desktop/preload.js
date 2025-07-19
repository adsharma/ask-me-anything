// preload.js
const {contextBridge, ipcRenderer} = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  getPythonPort: () => ipcRenderer.invoke("get-python-port"),
  // Pass options object to showOpenDialog
  showOpenDialog: (options) => ipcRenderer.invoke("show-open-dialog", options),
  openSettingsDialog: () => ipcRenderer.invoke("open-settings-dialog"),
  // Expose the new file reading function
  readFileContent: (filePath) => ipcRenderer.invoke("read-file-content", filePath),
  // Backend functions
  getBackendTypes: () => ipcRenderer.invoke("get-backend-types"),
  getModelHelpers: () => ipcRenderer.invoke("get-model-helpers"),
  getCurrentBackend: () => ipcRenderer.invoke("get-current-backend"),
  setBackend: (backendType) => ipcRenderer.invoke("set-backend", backendType),
  // Settings functions
  getCurrentSettings: () => ipcRenderer.invoke("get-current-settings"),
  getAvailableModels: () => ipcRenderer.invoke("get-available-models"),
  saveApiKey: (apiKey, model, backend) => ipcRenderer.invoke("save-api-key", apiKey, model, backend),
  onApiKeyUpdate: (callback) =>
    ipcRenderer.on("api-key-update-status", (event, ...args) =>
      callback(...args)
    ),
});

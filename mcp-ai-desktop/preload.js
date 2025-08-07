// preload.js
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('darkMode', {
  toggle: (enable) => ipcRenderer.send('toggle-dark-mode', enable),
  onChange: (callback) => ipcRenderer.on('set-dark-mode', (event, enabled) => callback(enabled))
});

contextBridge.exposeInMainWorld("electronAPI", {
  getPythonPort: () => ipcRenderer.invoke("get-python-port"),
  // Pass options object to showOpenDialog
  showOpenDialog: (options) => ipcRenderer.invoke("show-open-dialog", options),
  openSettingsDialog: () => ipcRenderer.invoke("open-settings-dialog"),
  closeWindow: () => ipcRenderer.send("close-window-request"),
  // Expose the new file reading function
  readFileContent: (filePath) => ipcRenderer.invoke("read-file-content", filePath),
  // Image handling
  readImageAsBase64: (filePath) => ipcRenderer.invoke("read-image-as-base64", filePath),
  // Backend functions
  getBackendTypes: () => ipcRenderer.invoke("get-backend-types"),
  getModelHelpers: () => ipcRenderer.invoke("get-model-helpers"),
  getCurrentBackend: () => ipcRenderer.invoke("get-current-backend"),
  setBackend: (backendType) => ipcRenderer.invoke("set-backend", backendType),
  // Model functions
  getModel: () => ipcRenderer.invoke("get-model"),
  setModel: (modelName) => ipcRenderer.invoke("set-model", modelName),
  listModels: () => ipcRenderer.invoke("list-models"),
  // Settings functions
  getCurrentSettings: () => ipcRenderer.invoke("get-current-settings"),
  getAvailableModels: () => ipcRenderer.invoke("get-available-models"),
  saveApiKey: (apiKey, model, backend) => ipcRenderer.invoke("save-api-key", apiKey, model, backend),
  onApiKeyUpdate: (callback) =>
    ipcRenderer.on("api-key-update-status", (event, ...args) =>
      callback(...args)
    ),
  onModelUpdate: (callback) =>
    ipcRenderer.on("model-update-status", (event, ...args) =>
      callback(...args)
    ),
  // Debug pane functions
  onPythonBackendOutput: (callback) =>
    ipcRenderer.on("python-backend-output", (event, ...args) =>
      callback(...args)
    ),
});

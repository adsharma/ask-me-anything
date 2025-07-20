// settings_preload.js
const {contextBridge, ipcRenderer} = require("electron");

contextBridge.exposeInMainWorld("settingsAPI", {
  saveKey: (key) => ipcRenderer.send("save-api-key", key),
  closeDialog: () => ipcRenderer.send("close-settings-dialog"),
  // Model switching functions
  listModels: () => ipcRenderer.invoke("list-models"),
  getModel: () => ipcRenderer.invoke("get-model"),
  setModel: (modelName) => ipcRenderer.invoke("set-model", modelName),
  // Backend functions
  getBackendTypes: () => ipcRenderer.invoke("get-backend-types"),
  getModelHelpers: () => ipcRenderer.invoke("get-model-helpers"),
  getCurrentBackend: () => ipcRenderer.invoke("get-current-backend"),
  setBackend: (backendType) => ipcRenderer.invoke("set-backend", backendType),
  // Integrated settings save function
  saveSettings: (apiKey, model, backend) => ipcRenderer.invoke("save-api-key", apiKey, model, backend),
});

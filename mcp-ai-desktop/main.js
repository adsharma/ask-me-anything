// main.js
const { nativeTheme } = require('electron');
const {app, BrowserWindow, ipcMain, dialog} = require("electron");
const path = require("path");
const fs = require("fs").promises; // Import fs promises
const { spawn } = require('child_process');

let mainWindow;
let settingsWindow = null;
let pythonProcess = null;
const pythonPort = 5001;
let isQuitting = false; // Flag to prevent cleanup loop
let backendReady = false; // Track backend readiness
let backendStartupStage = 'starting'; // Track startup stage

// Backend configuration using LiteLLM providers
const BACKEND_TYPES = {
  GEMINI: 'gemini',
  OLLAMA: 'ollama',
  OPENAI: 'openai',
  MLX: 'mlx', // For MLX via OpenAI-compatible local server
  ANTHROPIC: 'anthropic',
  COHERE: 'cohere'
};

// Model name helpers for LiteLLM format
const MODEL_HELPERS = {
  parseModelName: (fullModelName) => {
    const parts = fullModelName.split('/');
    if (parts.length >= 2) {
      return {
        provider: parts[0],
        model: parts.slice(1).join('/')
      };
    }
    return { provider: 'unknown', model: fullModelName };
  },
  formatModelName: (provider, model) => {
    return `${provider}/${model}`;
  },
  getProviderFromModel: (fullModelName) => {
    return fullModelName.split('/')[0];
  }
};

let currentBackend = BACKEND_TYPES.OLLAMA; // Default to Ollama for local models

// Backend status checking function
async function checkBackendStatus() {
  try {
    const response = await fetch(`http://127.0.0.1:${pythonPort}/validate-backend`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (response.ok) {
      const data = await response.json();
      backendReady = data.status === 'success';
      return { ready: backendReady, stage: 'ready' };
    } else {
      return { ready: false, stage: 'starting' };
    }
  } catch (error) {
    return { ready: false, stage: 'starting' };
  }
}

// Monitor backend startup progress
async function monitorBackendStartup() {
  const maxAttempts = 30; // 30 seconds max wait time
  let attempts = 0;

  const checkInterval = setInterval(async () => {
    attempts++;

    if (attempts > maxAttempts) {
      clearInterval(checkInterval);
      backendStartupStage = 'error';
      if (mainWindow) {
        mainWindow.webContents.send('backend-status-update', {
          stage: 'error',
          message: 'Backend startup timed out'
        });
      }
      return;
    }

    // Check if Python process is running and responsive
    try {
      // First check if Flask server is responding
      const response = await fetch(`http://127.0.0.1:${pythonPort}/validate-backend`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      if (response.ok) {
        clearInterval(checkInterval);
        backendReady = true;
        backendStartupStage = 'ready';
        if (mainWindow) {
          mainWindow.webContents.send('backend-status-update', {
            stage: 'ready',
            message: 'Backend is ready'
          });
        }
      } else {
        // Backend responding but not ready yet
        backendStartupStage = 'initializing';
        if (mainWindow) {
          mainWindow.webContents.send('backend-status-update', {
            stage: 'initializing',
            message: 'Initializing AI backend...'
          });
        }
      }
    } catch (error) {
      // Still starting up
      if (attempts < 5) {
        backendStartupStage = 'starting';
        if (mainWindow) {
          mainWindow.webContents.send('backend-status-update', {
            stage: 'starting',
            message: 'Starting Python backend...'
          });
        }
      } else if (attempts < 15) {
        backendStartupStage = 'connecting';
        if (mainWindow) {
          mainWindow.webContents.send('backend-status-update', {
            stage: 'connecting',
            message: 'Connecting to backend service...'
          });
        }
      } else {
        backendStartupStage = 'initializing';
        if (mainWindow) {
          mainWindow.webContents.send('backend-status-update', {
            stage: 'initializing',
            message: 'Initializing AI models...'
          });
        }
      }
    }
  }, 1000); // Check every second
}

function createSettingsWindow() {
  if (settingsWindow) {
    settingsWindow.focus();
    return;
  }
  settingsWindow = new BrowserWindow({
    width: 400,
    height: 200,
    title: "Settings",
    parent: mainWindow,
    modal: true,
    show: false,
    resizable: false,
    minimizable: false,
    maximizable: false,
    webPreferences: {
      preload: path.join(__dirname, "settings_preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
    backgroundColor: "#f4f1e7",
  });

  settingsWindow.loadFile(path.join(__dirname, "settings.html"));

  settingsWindow.once("ready-to-show", () => {
    settingsWindow.show();
  });

  settingsWindow.on("closed", () => {
    settingsWindow = null;
  });
}

function createWindow() {
  console.log("[createWindow] Attempting to create main window...");
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
    titleBarStyle: "hidden",
    trafficLightPosition: {x: 15, y: 15},
    minWidth: 800,
    minHeight: 600,
    title: "Ask Me Anything",
    backgroundColor: "#fdfcf7",
    icon: path.join(
      __dirname,
      "assets",
      app.isPackaged ? "icon.png" : "icon.png"
    ), // Optional: set icon for window itself
  });
  console.log("[createWindow] BrowserWindow created.");

  // Set dark mode class on load
  mainWindow.webContents.on('did-finish-load', () => {
    if (nativeTheme.shouldUseDarkColors) {
      mainWindow.webContents.send('set-dark-mode', true);
    } else {
      mainWindow.webContents.send('set-dark-mode', false);
    }
  });

  const indexPath = path.join(__dirname, "index.html");
  console.log(`[createWindow] Attempting to load file: ${indexPath}`);
  mainWindow
    .loadFile(indexPath)
    .then(() => {
      console.log("[createWindow] index.html loaded successfully.");
    })
    .catch((err) => {
      console.error("[createWindow] Error loading index.html:", err);
      dialog.showErrorBox(
        "Loading Error",
        `Failed to load index.html: ${err.message}`
      );
    });

  mainWindow.on("closed", () => {
    console.log("[createWindow] Main window closed.");
    mainWindow = null;
    if (settingsWindow) {
      settingsWindow.close();
    }
    // Ensure app quits when main window is closed
    if (process.platform !== "darwin") {
      app.quit();
    }
  });

  mainWindow.on("ready-to-show", () => {
    console.log("[createWindow] Main window ready-to-show.");
    mainWindow.show();
    console.log("[createWindow] mainWindow.show() called after ready-to-show.");
  });

  mainWindow.webContents.on(
    "did-fail-load",
    (event, errorCode, errorDescription, validatedURL) => {
      console.error(
        `[createWindow] Failed to load URL: ${validatedURL}, Error Code: ${errorCode}, Description: ${errorDescription}`
      );
      dialog.showErrorBox(
        "Load Failed",
        `Failed to load content: ${errorDescription}`
      );
    }
  );
}

app.whenReady().then(() => {
  console.log("[app.whenReady] App ready. Starting Python backend and creating window...");

  // Determine Python backend path based on whether app is packaged
  let pythonBackendPath;
  let pythonBackendDir;

  if (app.isPackaged) {
    // In production, use the packaged Python source with uv run
    const resourcesPath = process.resourcesPath;
    pythonBackendPath = path.join(resourcesPath, 'python_backend', 'src', 'backend', 'mcp_flask_backend.py');
    pythonBackendDir = path.join(resourcesPath, 'python_backend');
  } else {
    // In development, use uv run with the Python script
    pythonBackendPath = path.join(__dirname, '..', 'python_backend', 'src', 'backend', 'mcp_flask_backend.py');
    pythonBackendDir = path.join(__dirname, '..', 'python_backend');
  }

  const spawnOptions = {
    cwd: pythonBackendDir,
    detached: false,
    shell: process.platform === 'win32',
    stdio: ['ignore', 'pipe', 'pipe']
  };

  console.log(`[app.whenReady] Using Python backend with uv run: ${pythonBackendPath}`);
  pythonProcess = spawn('uv', ['run', pythonBackendPath, '--port', pythonPort.toString()], spawnOptions);  // Start monitoring backend startup
  monitorBackendStartup();

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[Python Backend] ${data}`);
    if (mainWindow) {
      mainWindow.webContents.send('python-backend-output', { type: 'stdout', data: data.toString() });
    }
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`[Python Backend Error] ${data}`);
    if (mainWindow) {
      mainWindow.webContents.send('python-backend-output', { type: 'stderr', data: data.toString() });
    }
  });

  pythonProcess.on('close', (code) => {
    console.log(`[Python Backend] Process exited with code ${code}`);
    if (mainWindow) {
      mainWindow.webContents.send('python-backend-output', { type: 'exit', data: `Process exited with code ${code}` });
    }
    // Mark process as null when it actually exits
    pythonProcess = null;
  });

  pythonProcess.on('exit', (code, signal) => {
    console.log(`[Python Backend] Process exit event - code: ${code}, signal: ${signal}`);
  });

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  console.log("[app.window-all-closed] All windows closed.");

  // Ensure Python process cleanup happens here too
  if (pythonProcess && !pythonProcess.killed) {
    console.log("[app.window-all-closed] Cleaning up Python process...");
    if (process.platform === 'win32') {
      try {
        const { spawnSync } = require('child_process');
        const cleanupResult = spawnSync('taskkill', ['/pid', pythonProcess.pid, '/t', '/f'], {
          windowsHide: true,
          timeout: 3000
        });
        console.log(`[app.window-all-closed] Windows cleanup completed with code: ${cleanupResult.status}`);
      } catch (error) {
        console.error("[app.window-all-closed] Error in Windows cleanup:", error);
        pythonProcess.kill('SIGTERM');
      }
    } else {
      pythonProcess.kill('SIGTERM');
    }
  }

  if (process.platform !== "darwin") {
    app.quit();
  }
});

// Add before-quit handler for better cleanup
app.on("before-quit", async (event) => {
  console.log("[app.before-quit] App is about to quit, cleaning up...");

  // If already quitting, don't prevent the quit but still try to kill the process
  if (isQuitting) {
    console.log("[app.before-quit] Already in cleanup process, but ensuring Python process is killed...");

    // Still try to kill the Python process if it's running
    if (pythonProcess && !pythonProcess.killed) {
      console.log("[app.before-quit] Python process still running, force killing...");
      if (process.platform === 'win32') {
        try {
          const { spawnSync } = require('child_process');
          const killResult = spawnSync('taskkill', ['/pid', pythonProcess.pid, '/t', '/f'], {
            windowsHide: true,
            timeout: 2000
          });
          console.log(`[app.before-quit] Emergency taskkill result: ${killResult.status}`);
        } catch (error) {
          console.error("[app.before-quit] Emergency taskkill failed:", error);
        }
      }
      try {
        pythonProcess.kill('SIGKILL');
      } catch (e) {
        console.log("[app.before-quit] Emergency SIGKILL failed:", e.message);
      }
    }
    return; // Allow the quit to proceed
  }

  // Prevent immediate quit to allow cleanup
  event.preventDefault();
  isQuitting = true; // Set flag to prevent re-entry

  // Perform cleanup
  try {
    if (pythonPort) {
      console.log("[app.before-quit] Requesting Python backend to disconnect all MCP servers...");

      // Create a timeout promise to prevent hanging
      const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('Request timeout')), 3000); // 3 second timeout
      });

      const fetchPromise = fetch(`http://127.0.0.1:${pythonPort}/disconnect-all-servers`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      const response = await Promise.race([fetchPromise, timeoutPromise]);

      if (response.ok) {
        const result = await response.json().catch(() => ({ message: "No response body" }));
        console.log("[app.before-quit] All MCP servers disconnected successfully:", result);
        // Brief pause to allow response to complete
        await new Promise(resolve => setTimeout(resolve, 50));
      } else {
        const errorData = await response.json().catch(() => ({ message: "No error details" }));
        console.warn(`[app.before-quit] Failed to disconnect MCP servers - Status: ${response.status}, Error:`, errorData);
      }
    }
  } catch (error) {
    console.error("[app.before-quit] Error disconnecting MCP servers:", error);
    // Continue with process cleanup immediately
  }

  // Kill Python process if it's still running
  if (pythonProcess) {
    console.log("[app.before-quit] Terminating Python process...");
    console.log(`[app.before-quit] Python process PID: ${pythonProcess.pid}, killed status: ${pythonProcess.killed}`);

    // On Windows, we need to kill the entire process tree
    if (process.platform === 'win32') {
      try {
        // Use taskkill to terminate the process tree on Windows - wait for completion
        const { spawnSync } = require('child_process');
        console.log("[app.before-quit] Using taskkill to terminate process tree...");
        const killResult = spawnSync('taskkill', ['/pid', pythonProcess.pid, '/t', '/f'], {
          windowsHide: true,
          timeout: 3000, // Reduced timeout
          encoding: 'utf8'
        });

        console.log(`[app.before-quit] Taskkill completed with exit code: ${killResult.status}`);
        if (killResult.error) {
          console.error("[app.before-quit] Taskkill error:", killResult.error);
        }
        if (killResult.stderr && killResult.stderr.trim()) {
          console.error("[app.before-quit] Taskkill stderr:", killResult.stderr.trim());
        }
        if (killResult.stdout && killResult.stdout.trim()) {
          console.log("[app.before-quit] Taskkill stdout:", killResult.stdout.trim());
        }

        // If taskkill failed, try alternative approaches
        if (killResult.status !== 0) {
          console.log("[app.before-quit] Taskkill failed, trying alternative kill methods...");

          // Try killing individual processes by name
          const killPythonResult = spawnSync('taskkill', ['/f', '/im', 'python.exe'], {
            windowsHide: true,
            timeout: 2000,
            encoding: 'utf8'
          });
          console.log(`[app.before-quit] Kill python.exe result: ${killPythonResult.status}`);

          const killUvResult = spawnSync('taskkill', ['/f', '/im', 'uv.exe'], {
            windowsHide: true,
            timeout: 2000,
            encoding: 'utf8'
          });
          console.log(`[app.before-quit] Kill uv.exe result: ${killUvResult.status}`);
        }

        // Also send SIGTERM to the main process as backup
        try {
          pythonProcess.kill('SIGTERM');
          console.log("[app.before-quit] Sent SIGTERM to Python process");
        } catch (e) {
          console.log("[app.before-quit] SIGTERM failed (process may already be dead):", e.message);
        }
      } catch (error) {
        console.error("[app.before-quit] Error killing Windows process tree:", error);
        // Fallback to basic kill
        try {
          pythonProcess.kill('SIGTERM');
        } catch (e) {
          console.error("[app.before-quit] Fallback SIGTERM also failed:", e.message);
        }
      }
    } else {
      // On Unix-like systems, use SIGTERM
      pythonProcess.kill('SIGTERM');
    }

    // Brief wait to let the kill take effect
    console.log("[app.before-quit] Waiting briefly for process termination...");
    await new Promise(resolve => setTimeout(resolve, 100)); // Reduced wait time

    // Check if process is still running and force kill if needed
    if (pythonProcess && !pythonProcess.killed) {
      console.log("[app.before-quit] Process still running, force killing...");
      console.log(`[app.before-quit] Process PID: ${pythonProcess.pid}`);
      if (process.platform === 'win32') {
        try {
          const { spawnSync } = require('child_process');
          console.log("[app.before-quit] Using taskkill for force kill...");
          const forceKillResult = spawnSync('taskkill', ['/pid', pythonProcess.pid, '/t', '/f'], {
            windowsHide: true,
            timeout: 2000,
            encoding: 'utf8'
          });
          console.log(`[app.before-quit] Force kill completed with exit code: ${forceKillResult.status}`);

          // Also try killing by name as final resort
          if (forceKillResult.status !== 0) {
            console.log("[app.before-quit] Final resort: killing all python/uv processes...");
            spawnSync('taskkill', ['/f', '/im', 'python.exe'], { windowsHide: true, timeout: 1000 });
            spawnSync('taskkill', ['/f', '/im', 'uv.exe'], { windowsHide: true, timeout: 1000 });
          }
        } catch (error) {
          console.error("[app.before-quit] Error force killing Windows process:", error);
        }
      }

      // Final attempt with SIGKILL
      try {
        pythonProcess.kill('SIGKILL');
        console.log("[app.before-quit] Sent SIGKILL to Python process");
      } catch (e) {
        console.log("[app.before-quit] SIGKILL failed:", e.message);
      }
    } else {
      console.log("[app.before-quit] Python process terminated successfully");
    }
  }

  // Now actually quit - this will trigger quit event but not before-quit again
  setTimeout(() => {
    app.quit();
  }, 50);
});

app.on("quit", () => {
  console.log("[app.quit] App quitting (final cleanup).");

  // Final safety check - kill Python process if somehow still running
  if (pythonProcess && !pythonProcess.killed) {
    console.log("[app.quit] Force killing any remaining Python process...");
    if (process.platform === 'win32') {
      try {
        const { spawnSync } = require('child_process');
        const finalKillResult = spawnSync('taskkill', ['/pid', pythonProcess.pid, '/t', '/f'], {
          windowsHide: true,
          timeout: 3000
        });
        console.log(`[app.quit] Final Windows process kill completed with code: ${finalKillResult.status}`);
      } catch (error) {
        console.error("[app.quit] Error in final Windows process kill:", error);
      }
    } else {
      pythonProcess.kill('SIGKILL');
    }
  }
});

ipcMain.handle("get-python-port", async () => {
  return pythonPort;
});

ipcMain.handle("check-backend-status", async () => {
  return await checkBackendStatus();
});

// Listen for dark mode toggle from renderer
ipcMain.on('toggle-dark-mode', (event, enable) => {
  nativeTheme.themeSource = enable ? 'dark' : 'light';
  if (mainWindow) {
    mainWindow.webContents.send('set-dark-mode', enable);
  }
});

ipcMain.handle("get-backend-types", async () => {
  return BACKEND_TYPES;
});

ipcMain.handle("get-model-helpers", async () => {
  return MODEL_HELPERS;
});

ipcMain.handle("get-current-backend", async () => {
  return currentBackend;
});

ipcMain.handle("set-backend", async (event, backendType) => {
  console.log(`[set-backend] Setting backend to: ${backendType}`);
  if (Object.values(BACKEND_TYPES).includes(backendType)) {
    currentBackend = backendType;
    console.log(`[set-backend] Backend set to: ${currentBackend}`);

    // Inform the Python backend about the backend change
    try {
      if (pythonPort) {
        const response = await fetch(`http://127.0.0.1:${pythonPort}/set-backend`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ backend: backendType }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
        }

        console.log(`[set-backend] Python backend informed about backend change to: ${backendType}`);

        // Notify renderer about backend change to update model display
        if (mainWindow) {
          mainWindow.webContents.send('model-update-status', {
            success: true,
            message: `Backend changed to ${backendType}`,
            backend: backendType
          });
        }
      }
    } catch (error) {
      console.error(`[set-backend] Error informing Python backend about backend change:`, error);
      // Don't fail the entire operation if we can't inform the Python backend
      // The local backend is still set correctly
    }

    return { success: true, backend: currentBackend };
  } else {
    throw new Error(`Invalid backend type: ${backendType}`);
  }
});

ipcMain.handle("show-open-dialog", async (event, options) => {
  // Default options if none provided (for backward compatibility or other uses)
  const defaultOptions = {
    properties: ["openFile"],
    filters: [{ name: 'Python Scripts', extensions: ['py'] }]
  };
  const dialogOptions = options || defaultOptions;

  // Ensure mainWindow is used if available
  const window = mainWindow || BrowserWindow.getFocusedWindow();
  if (!window) {
      console.error("show-open-dialog: No window available to show dialog.");
      return []; // Return empty array or handle error as appropriate
  }

  const result = await dialog.showOpenDialog(window, dialogOptions);
  return result.filePaths;
});

ipcMain.handle("open-settings-dialog", () => {
  createSettingsWindow();
});

ipcMain.handle("close-window", () => {
  if (mainWindow) {
    mainWindow.close();
  }
});

// Add event listener for the close button in the renderer
ipcMain.on("close-window-request", () => {
  if (mainWindow) {
    mainWindow.close();
  }
  // Ensure app quits when main window is closed on non-macOS platforms
  if (process.platform !== "darwin") {
    app.quit();
  }
});

ipcMain.on("close-settings-dialog", (event) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win) {
    win.close();
  }
});

// Handler to read file content
ipcMain.handle("read-file-content", async (event, filePath) => {
  if (!filePath || typeof filePath !== 'string') {
    throw new Error("Invalid file path provided.");
  }
  try {
    // Basic security check: Ensure the path is within expected directories if needed
    // For simplicity now, we just read the path given. Add validation if required.
    console.log(`[read-file-content] Reading file: ${filePath}`);
    const content = await fs.readFile(filePath, "utf-8");
    return content;
  } catch (error) {
    console.error(`[read-file-content] Error reading file ${filePath}:`, error);
    throw new Error(`Failed to read file: ${error.message}`);
  }
});

ipcMain.handle("read-image-as-base64", async (event, filePath) => {
  if (!filePath || typeof filePath !== 'string') {
    throw new Error("Invalid file path provided.");
  }
  try {
    console.log(`[read-image-as-base64] Reading image: ${filePath}`);
    const imageBuffer = await fs.readFile(filePath);
    const base64Data = imageBuffer.toString('base64');
    return base64Data;
  } catch (error) {
    console.error(`[read-image-as-base64] Error reading image ${filePath}:`, error);
    throw new Error(`Failed to read image: ${error.message}`);
  }
});

// --- Model Switching IPC Handlers ---

ipcMain.handle("list-models", async () => {
  console.log("[ipcMain] Handling list-models request");
  try {
    const response = await fetch(`http://127.0.0.1:${pythonPort}/list-models`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.message || `HTTP error! status: ${response.status}`);
    }
    console.log("[ipcMain] list-models response:", data);
    return data.models; // Assuming backend returns { status: 'success', models: [...] }
  } catch (error) {
    console.error("[ipcMain] Error listing models:", error);
    throw error; // Re-throw to be caught in renderer
  }
});

ipcMain.handle("get-model", async () => {
  console.log("[ipcMain] Handling get-model request");
  try {
    const response = await fetch(`http://127.0.0.1:${pythonPort}/get-model`);
    const data = await response.json();
     if (!response.ok) {
      throw new Error(data.message || `HTTP error! status: ${response.status}`);
    }
    console.log("[ipcMain] get-model response:", data);
    return data.model; // Assuming backend returns { status: 'success', model: '...' }
  } catch (error) {
    console.error("[ipcMain] Error getting current model:", error);
    throw error;
  }
});

ipcMain.handle("set-model", async (event, modelName) => {
  console.log(`[ipcMain] Handling set-model request for: ${modelName}`);
  try {
    const response = await fetch(`http://127.0.0.1:${pythonPort}/set-model`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: modelName }),
    });
    const data = await response.json();
     if (!response.ok) {
      throw new Error(data.message || `HTTP error! status: ${response.status}`);
    }
    console.log("[ipcMain] set-model response:", data);
    // Optionally notify main window or handle success/error feedback
    if (mainWindow) {
        mainWindow.webContents.send("model-update-status", { success: true, message: data.message, model: modelName });
    }
    return { success: true, message: data.message }; // Return success status to settings window
  } catch (error) {
    console.error(`[ipcMain] Error setting model to ${modelName}:`, error);
     if (mainWindow) {
        mainWindow.webContents.send("model-update-status", { success: false, message: error.message, model: modelName });
    }
    throw error; // Re-throw for settings window
  }
});

// --- End Model Switching IPC Handlers ---

// Integrated settings handlers
ipcMain.handle("get-current-settings", async () => {
  try {
    if (!pythonPort) {
      return { apiKey: "", model: "", backend: currentBackend };
    }

    // For now, we don't store the API key locally for security reasons
    // But we can get the current model
    const modelResponse = await fetch(`http://127.0.0.1:${pythonPort}/get-model`);
    const modelData = await modelResponse.json();

    return {
      apiKey: "", // Don't return actual API key for security
      model: modelData.model || "",
      backend: currentBackend
    };
  } catch (error) {
    console.error("Error getting current settings:", error);
    return { apiKey: "", model: "", backend: currentBackend };
  }
});

ipcMain.handle("get-available-models", async () => {
  try {
    if (!pythonPort) {
      return [];
    }

    const response = await fetch(`http://127.0.0.1:${pythonPort}/list-models`);
    const data = await response.json();
    return data.models || [];
  } catch (error) {
    console.error("Error getting available models:", error);
    return [];
  }
});

ipcMain.handle("save-api-key", async (event, apiKey, model, backend) => {
  console.log("[save-api-key] Received settings from integrated settings.");
  try {
    if (!pythonPort) {
      throw new Error("Backend not available");
    }

    // Set backend if provided
    if (backend && Object.values(BACKEND_TYPES).includes(backend)) {
      currentBackend = backend;
      console.log(`[save-api-key] Backend updated to: ${currentBackend}`);

      // Inform the Python backend about the backend change
      try {
        const backendResponse = await fetch(`http://127.0.0.1:${pythonPort}/set-backend`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ backend: backend }),
        });

        if (!backendResponse.ok) {
          const errorData = await backendResponse.json().catch(() => ({}));
          throw new Error(errorData.message || `HTTP error! status: ${backendResponse.status}`);
        }

        console.log(`[save-api-key] Python backend informed about backend change to: ${backend}`);
      } catch (error) {
        console.error(`[save-api-key] Error informing Python backend about backend change:`, error);
        // Continue with the rest of the save process even if backend setting fails
      }
    }

    // Set API key
    const apiResponse = await fetch(`http://127.0.0.1:${pythonPort}/set-api-key`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({apiKey: apiKey}),
    });

    const apiData = await apiResponse.json();
    if (!apiResponse.ok) {
      throw new Error(apiData.message || `HTTP error! status: ${apiResponse.status}`);
    }

    // Set model if provided
    if (model) {
      const modelResponse = await fetch(`http://127.0.0.1:${pythonPort}/set-model`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({model: model}),
      });

      const modelData = await modelResponse.json();
      if (!modelResponse.ok) {
        throw new Error(modelData.message || `HTTP error! status: ${modelResponse.status}`);
      }

      // Notify renderer about model change
      if (mainWindow) {
        mainWindow.webContents.send('model-update-status', {
          success: true,
          message: `Model changed to ${model}`,
          model: model
        });
      }
    }

    console.log("[save-api-key] Settings saved successfully");
    return {success: true, message: "Settings saved successfully"};
  } catch (error) {
    console.error("[save-api-key] Error saving settings:", error);
    return {success: false, message: error.message};
  }
});

// Handle process exit events for thorough cleanup
process.on('exit', () => {
  console.log("[process.exit] Node.js process exiting, final cleanup...");
  if (pythonProcess && !pythonProcess.killed) {
    console.log("[process.exit] Force terminating Python process...");
    try {
      pythonProcess.kill('SIGKILL');
    } catch (error) {
      console.error("[process.exit] Error in final process kill:", error);
    }
  }
});

process.on('SIGINT', () => {
  console.log("[process.SIGINT] Received SIGINT, cleaning up...");
  if (pythonProcess && !pythonProcess.killed) {
    pythonProcess.kill('SIGTERM');
  }
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.log("[process.SIGTERM] Received SIGTERM, cleaning up...");
  if (pythonProcess && !pythonProcess.killed) {
    pythonProcess.kill('SIGTERM');
  }
  process.exit(0);
});

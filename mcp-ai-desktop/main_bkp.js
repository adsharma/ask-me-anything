// main.js
const {app, BrowserWindow, ipcMain, dialog} = require("electron");
const path = require("path");
const {spawn} = require("child_process");
const fs = require("fs");

let mainWindow;
let pythonProcess = null;
let pythonPort = 5001;

function getPythonExecutablePath() {
  // ... (keep the existing function from the previous step)
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "mcp_backend", "mcp_backend");
  } else {
    const baseVenvPaths = [
      path.join(__dirname, "..", "python_backend", ".venv"),
      path.join(__dirname, "..", "python_backend", "venv"),
    ];
    const platformPath =
      process.platform === "win32"
        ? ["Scripts", "python.exe"]
        : ["bin", "python"];

    for (const baseVenvPath of baseVenvPaths) {
      const potentialPath = path.join(baseVenvPath, ...platformPath);
      if (fs.existsSync(potentialPath)) {
        console.log(
          `[getPythonExecutablePath] Found Python executable at: ${potentialPath}`
        );
        return potentialPath;
      }
    }
    const expectedPath = path.join(
      __dirname,
      "..",
      "python_backend",
      ".venv",
      ...platformPath
    );
    console.error(
      `[getPythonExecutablePath] Python executable not found in sibling 'python_backend'. Tried .venv and venv. Expected: ${expectedPath}`
    );
    return expectedPath;
  }
}

function getPythonScriptPath() {
  // ... (keep the existing function from the previous step)
  if (app.isPackaged) {
    return null;
  } else {
    const scriptPath = path.join(
      __dirname,
      "..",
      "python_backend",
      "mcp_flask_backend.py"
    );
    console.log(`[getPythonScriptPath] Generated script path: ${scriptPath}`);
    return scriptPath;
  }
}

function startPythonBackend() {
  return new Promise((resolve, reject) => {
    // ... (keep the existing startPythonBackend logic with logging)
    const pythonExecutable = getPythonExecutablePath();
    const pythonScript = getPythonScriptPath();
    const args = pythonScript
      ? [pythonScript, "--port", pythonPort]
      : ["--port", pythonPort];

    console.log(
      `[startPythonBackend] Attempting to start Python backend with:`
    );
    console.log(`[startPythonBackend] Executable: ${pythonExecutable}`);
    if (pythonScript) {
      console.log(`[startPythonBackend] Script: ${pythonScript}`);
      console.log(
        `[startPythonBackend] Checking if script exists at: ${pythonScript}`
      );
      const scriptExists = fs.existsSync(pythonScript);
      console.log(`[startPythonBackend] Script exists? ${scriptExists}`);
      if (!scriptExists) {
        console.error(
          `[startPythonBackend] Python script check failed at: ${pythonScript}`
        );
        return reject(new Error(`Python script not found: ${pythonScript}`));
      }
    }

    if (!fs.existsSync(pythonExecutable)) {
      console.error(
        `[startPythonBackend] Python executable check failed at: ${pythonExecutable}`
      );
      return reject(
        new Error(`Python executable not found: ${pythonExecutable}`)
      );
    }

    const cwd = app.isPackaged
      ? process.resourcesPath
      : path.join(__dirname, "..", "python_backend");
    console.log(`[startPythonBackend] Setting Python backend cwd to: ${cwd}`);

    pythonProcess = spawn(pythonExecutable, args, {cwd: cwd});

    pythonProcess.stdout.on("data", (data) => {
      const output = data.toString();
      console.log(`Python Backend: ${output}`);
      if (output.includes(`Running on http://127.0.0.1:${pythonPort}`)) {
        console.log(
          "[startPythonBackend] Python backend started successfully. Resolving promise."
        );
        resolve();
      }
    });

    pythonProcess.stderr.on("data", (data) => {
      console.error(`Python Backend Error: ${data}`);
    });

    pythonProcess.on("close", (code) => {
      console.log(`Python backend exited with code ${code}`);
      pythonProcess = null;
    });

    pythonProcess.on("error", (err) => {
      console.error(
        "[startPythonBackend] Failed to start Python backend:",
        err
      );
      reject(err);
    });

    const startTimeout = setTimeout(() => {
      console.error(
        "[startPythonBackend] Backend start timed out after 15 seconds."
      );
      reject(
        new Error(
          "[startPythonBackend] Python backend failed to start within 15 seconds."
        )
      );
    }, 15000);

    pythonProcess.stdout.once("data", () => {
      clearTimeout(startTimeout);
    });
  });
}

function createWindow() {
  console.log("--- [createWindow] START ---");
  try {
    mainWindow = new BrowserWindow({
      width: 800,
      height: 600,
      x: 100, // Force position
      y: 100, // Force position
    });
    console.log(
      "[createWindow] BrowserWindow created (minimal) with forced position."
    );

    mainWindow
      .loadURL("about:blank")
      .then(() => {
        console.log("[createWindow] about:blank loaded.");
        mainWindow.show();
        console.log(
          "[createWindow] mainWindow.show() called after about:blank."
        );
        // if (!app.isPackaged) {
        //     mainWindow.webContents.openDevTools();
        //     console.log('[createWindow] DevTools temporarily disabled for visibility test.');
        // }
      })
      .catch((err) => {
        console.error("[createWindow] Error loading about:blank:", err);
      });

    mainWindow.on("closed", () => {
      console.log("[createWindow] Main window closed.");
      mainWindow = null;
    });

    mainWindow.on("ready-to-show", () => {
      console.log("[createWindow] Main window ready-to-show.");
      mainWindow.show();
    });

    mainWindow.webContents.on(
      "did-fail-load",
      (event, errorCode, errorDescription, validatedURL) => {
        console.error(
          `[createWindow] Failed to load URL: ${validatedURL}, Error Code: ${errorCode}, Description: ${errorDescription}`
        );
      }
    );
  } catch (error) {
    console.error("[createWindow] Error during window creation:", error);
  }
  console.log("--- [createWindow] END ---");
}

app.whenReady().then(async () => {
  console.log("[app.whenReady] Starting...");
  try {
    console.log("[app.whenReady] Awaiting startPythonBackend...");
    await startPythonBackend();
    console.log(
      "[app.whenReady] startPythonBackend resolved. Calling createWindow..."
    );
    createWindow();
    console.log("[app.whenReady] createWindow called.");
  } catch (error) {
    console.error("[app.whenReady] Error during app initialization:", error);
    dialog.showErrorBox(
      "Initialization Error",
      `Failed to start the backend: ${error.message}\nPlease check logs and ensure Python setup is correct.`
    );
    app.quit();
  }

  app.on("activate", () => {
    console.log("[app.activate] Activate event triggered.");
    if (BrowserWindow.getAllWindows().length === 0) {
      console.log("[app.activate] No windows open, calling createWindow.");
      createWindow();
    } else {
      console.log("[app.activate] Windows already open, focusing existing.");
      // Optionally focus existing window if needed
      if (mainWindow) {
        mainWindow.focus();
      }
    }
  });
});

app.on("window-all-closed", () => {
  console.log("[app.window-all-closed] All windows closed.");
  if (process.platform !== "darwin") {
    console.log("[app.window-all-closed] Quitting app (not macOS).");
    app.quit();
  }
});

app.on("before-quit", () => {
  console.log("[app.before-quit] Before quit triggered.");
  if (pythonProcess) {
    console.log("[app.before-quit] Terminating Python backend...");
    pythonProcess.kill();
    pythonProcess = null;
  }
});

ipcMain.handle("get-python-port", async () => {
  return pythonPort;
});

ipcMain.handle("show-open-dialog", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ["openFile"],
    filters: [{name: "Python Scripts", extensions: ["py"]}],
  });
  return result.filePaths;
});

console.log("main.js loaded.");

<div align="center">
  <img src="https://github.com/kkrishnan90/gemini-desktop/blob/main/mcp-gemini-desktop/assets/app_icon.png" width="128" height="128" alt="MCP AI Chat Logo">

  <h1>Ask Me Anything</h1>

  <p>
    Ask me anything app is a cross-platform desktop application that creates a seamless chat interface for AI models with extensible capabilities through a Model Context Protocol (MCP) framework.
  </p>
</div>

## ✨ Features

- **🤖 Multiple LLM Integration:** Seamless chat interface with Ollama, MLX, Google/OpenAI/Anthropic (configurable via Settings).
- **🔧 Extensible Tools (MCP):** Connect external tools and data sources via the Model Context Protocol.
  - Supports Python-based MCP servers (added via file path).
  - Supports command-based MCP servers (e.g., Node.js) defined in a JSON configuration file.
- **🖥️ Cross-Platform:** Runs on macOS and Windows (Electron build).
- **📊 Tool Status UI:** Provides visual feedback when AI is calling an MCP tool and whether it succeeded or failed.
- **📝 Markdown & LaTeX Rendering:** Displays AI responses with formatting.

## Screenshots

<p align="center">
  <img src="https://github.com/kkrishnan90/gemini-desktop/blob/main/mcp-gemini-desktop/demo_images/C9zdjSLfhAfEswt.png" width="80%" alt="Weather Tool Example">
  <br><em>Example of the weather tool in action</em>
</p>

<p align="center">
  <img src="https://github.com/kkrishnan90/gemini-desktop/blob/main/mcp-gemini-desktop/demo_images/BEvT6bS7bFJVVKK.png" width="80%" alt="Chat Interface">
  <br><em>Main chat interface with LLM</em>
</p>

<p align="center">
  <img src="https://github.com/kkrishnan90/gemini-desktop/blob/main/mcp-gemini-desktop/demo_images/KdLPsRCxjbJB9ph.png" width="80%" alt="Calculator Tool Example">
  <br><em>Using the calculator tool with Gemini</em>
</p>

## Overview

This repository contains both a Python backend and an Electron-based desktop application for interacting with LLMs.

## Project Structure

- **mcp-ai-desktop/**: Frontend Electron application
- **python_backend/**: Python backend server

## Running the Python Backend

### Prerequisites

- Python 3.13+ (as specified in pyproject.toml)
- uv (Modern Python package installer and resolver)

### Setup

1. Navigate to the Python backend directory:

   ```bash
   cd python_backend
   ```

2. Install uv if you don't have it already:

   ```bash
   pip install uv
   ```

3. Install the required dependencies using uv:

   ```bash
   uv pip install .
   ```

4. Set your Google API key as an environment variable:

   ```bash
   # For Linux/macOS
   export GOOGLE_API_KEY=your_api_key_here

   # For Windows
   set GOOGLE_API_KEY=your_api_key_here
   ```

5. Start the Python backend server:

   ```bash
   python main.py
   ```

   The server should start running on `http://localhost:5000`

## Running the Frontend Electron App

### Prerequisites

- Node.js (v16+)
- npm (Node package manager)

### Setup

1. Navigate to the Electron app directory:

   ```bash
   cd mcp-ai-desktop
   ```

2. Install the required dependencies:

   ```bash
   npm install
   ```

3. Start the Electron app in development mode:
   ```bash
   npm start
   ```

### Building the App

To build the Electron app for your platform:

```bash
cd mcp-ai-desktop
npm run build
```

This will create platform-specific binaries in the `dist` folder.

## Using Pre-built Binaries

If you prefer to use pre-built binaries directly:

1. Navigate to the `mcp-ai-desktop/dist` directory
2. For macOS: Install the `.dmg` file
3. For Windows: Run the `.exe` installer

### Available Binaries

- macOS (Apple Silicon): `MCP AI Chat-0.1.0-arm64.dmg`
- Windows: Check the `dist` folder for `.exe` files

## Example Servers

The repository includes example server implementations in `mcp-ai-desktop/mcp_example_servers/`:

- `mcp_server_calc.py`: Calculator server example
- `mcp_server_weather.py`: Weather information server example

## Troubleshooting

- Ensure the Python backend is running before starting the Electron app
- Check that your Google API key is correctly set
- Verify that the required ports are not blocked by a firewall

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Please raise PR for any contributions. Any PR raised will be reviewed and merged with the main branch.


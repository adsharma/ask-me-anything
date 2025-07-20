# MCP AI Chat - Multi-Backend Support

This application now supports multiple AI backends through LiteLLM integration:

## Supported Providers

### Google Gemini
- **Models**: `gemini/gemini-2.5-flash-preview-04-17`, `gemini/gemini-1.5-pro`, `gemini/gemini-1.5-flash`
- **API Key Required**: Yes
- **Setup**: Get your API key from [Google AI Studio](https://makersuite.google.com/app/apikey)

### Ollama (Local)
- **Models**: `ollama/qwen3:14b`, `ollama/llama3.2`, `ollama/codellama`, etc.
- **API Key Required**: No (local models)
- **Setup**: Install [Ollama](https://ollama.ai/) and pull your desired models

### OpenAI
- **Models**: `openai/gpt-4o`, `openai/gpt-4o-mini`, `openai/gpt-3.5-turbo`
- **API Key Required**: Yes
- **Setup**: Get your API key from [OpenAI](https://platform.openai.com/api-keys)

### MLX (Local)
- **Models**: `mlx/mlx-community/model_name` (via OpenAI-compatible local server)
- **API Key Required**: No (local models)
- **Setup**: Set up MLX with OpenAI-compatible server locally

### Anthropic Claude
- **Models**: `anthropic/claude-3-5-sonnet-20241022`, `anthropic/claude-3-5-haiku-20241022`
- **API Key Required**: Yes
- **Setup**: Get your API key from [Anthropic Console](https://console.anthropic.com/)

### Cohere
- **Models**: `cohere/command-r-plus`, `cohere/command-r`
- **API Key Required**: Yes
- **Setup**: Get your API key from [Cohere Dashboard](https://dashboard.cohere.ai/)

## Model Naming Convention

All models follow the LiteLLM naming convention: `provider/model_name`

Examples:
- `gemini/gemini-2.5-flash-preview-04-17`
- `ollama/qwen3:14b`
- `openai/gpt-4o`
- `mlx/mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`
- `anthropic/claude-3-5-sonnet-20241022`
- `cohere/command-r-plus`

## Configuration

1. **Frontend**: Select your provider and model in the Settings panel
2. **Backend**: Set up your API keys in the `.env` file (see `.env.example`)
3. **Local Models**: Ensure Ollama or MLX servers are running locally

## Backend Implementation

The Python backend uses LiteLLM to provide a unified interface across all providers. See `backend_example.py` for a complete implementation example.

### Key Features:
- Automatic provider detection from model names
- Unified API regardless of backend
- Environment-based API key management
- Error handling and fallback support

## Development

To extend support for additional providers:

1. Add the provider to `BACKEND_TYPES` in `main.js`
2. Update the UI options in settings files
3. Add provider-specific configuration in the backend
4. Update model lists and validation logic

## Local Development

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. Start the backend:
   ```bash
   python backend_example.py
   ```

4. Start the Electron app:
   ```bash
   npm start
   ```

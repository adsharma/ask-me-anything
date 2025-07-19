# Backend Configuration for MCP AI Chat
# This file shows how to configure the Python backend to support multiple AI providers

## Backend Types Supported:
- **Gemini**: Google's Gemini AI models (requires API key)
- **Ollama**: Local Ollama models (no API key required)
- **MLX**: Apple MLX models (no API key required)

## Python Backend Endpoints to Implement:

### 1. Set Backend Type
```
POST /set-backend
Body: {"backend": "gemini|ollama|mlx"}
```

### 2. List Models (backend-specific)
```
GET /list-models
Returns different models based on current backend:
- Gemini: gemini-1.5-pro, gemini-1.5-flash, etc.
- Ollama: llama3.1, mistral, codellama, etc.
- MLX: mlx-community models, etc.
```

### 3. Set Model (backend-specific)
```
POST /set-model
Body: {"model": "model-name"}
```

### 4. Get Current Model
```
GET /get-model
Returns: {"model": "current-model-name"}
```

### 5. Set API Key (if required)
```
POST /set-api-key
Body: {"apiKey": "api-key-value"}
Note: Only required for Gemini backend
```

### 6. Chat Endpoint (backend-agnostic)
```
POST /chat
Body: {"message": "user message"}
Returns: {"reply": "ai response"}
```

## Implementation Notes:

1. **Backend State Management**: The Python backend should maintain the current backend type and switch API clients accordingly.

2. **Model Validation**: Each backend should validate that the requested model is available for that specific backend.

3. **Error Handling**: Proper error messages for unsupported models or missing API keys.

4. **Configuration Storage**: Consider storing the current backend and model configuration persistently.

## Example Backend Class Structure:

```python
class AIBackendManager:
    def __init__(self):
        self.current_backend = "gemini"  # default
        self.gemini_client = None
        self.ollama_client = None
        self.mlx_client = None
        
    def set_backend(self, backend_type):
        if backend_type in ["gemini", "ollama", "mlx"]:
            self.current_backend = backend_type
            return True
        return False
        
    def list_models(self):
        if self.current_backend == "gemini":
            return self.get_gemini_models()
        elif self.current_backend == "ollama":
            return self.get_ollama_models()
        elif self.current_backend == "mlx":
            return self.get_mlx_models()
            
    def chat(self, message):
        if self.current_backend == "gemini":
            return self.gemini_chat(message)
        elif self.current_backend == "ollama":
            return self.ollama_chat(message)
        elif self.current_backend == "mlx":
            return self.mlx_chat(message)
```

## Frontend Integration:

The frontend has been updated to:
1. Allow backend selection in settings
2. Update UI labels based on selected backend
3. Handle API key requirements per backend
4. Reload available models when backend changes
5. Send backend information when saving settings

## Migration from Gemini-only:

If you have an existing Gemini-only backend, you'll need to:
1. Implement the new `/set-backend` endpoint
2. Modify existing endpoints to be backend-aware
3. Add support for Ollama and MLX clients
4. Update model listing logic to be backend-specific
5. Handle the optional API key requirement

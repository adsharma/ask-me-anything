# ai_backend_manager.py
import json
import logging
import os
from typing import Any, Dict, List

import litellm
import requests
from litellm import acompletion, completion

logger = logging.getLogger(__name__)

LOCAL_BACKENDS = ["ollama", "mlx"]


class AIBackendManager:
    """Manages multiple AI backends using LiteLLM for unified interface."""

    def __init__(self):
        self.current_backend = "ollama"  # default to Ollama for local models
        self.current_model = None
        self.api_key = None

        # Backend-specific settings
        self.backend_settings = {
            "gemini": {
                "default_model": "gemini-1.5-flash-latest",
                "requires_api_key": True,
                "models": [
                    "gemini-1.5-flash-latest",
                    "gemini-1.5-pro-latest",
                    "gemini-2.0-flash",
                    "gemini-exp-1206",
                ],
            },
            "ollama": {
                "default_model": None,
                "requires_api_key": False,
                "base_url": "http://localhost:11434",
                "models": [],  # Will be fetched dynamically
            },
            "mlx": {
                "default_model": None,
                "requires_api_key": False,
                "base_url": "http://localhost:8081",  # Default MLX OpenAI-compatible server
                "models": [],  # Will be fetched dynamically
            },
            "openai": {
                "default_model": "gpt-4o-mini",
                "requires_api_key": True,
                "models": [
                    "gpt-4o",
                    "gpt-4o-mini",
                    "gpt-4-turbo",
                    "gpt-3.5-turbo",
                ],
            },
        }

        # Configure LiteLLM
        litellm.set_verbose = False  # Set to True for debugging
        self._initialize_current_model()

    def _initialize_current_model(self):
        """Set the current model for the current backend."""
        logger.info(f"Initializing current model for {self.current_backend}")
        if self.current_backend in LOCAL_BACKENDS:
            try:
                available_models = self.list_models()
                if available_models:
                    self.current_model = available_models[0]
                    self.backend_settings[self.current_backend]["default_model"] = (
                        available_models[0]
                    )
                    logger.info(f"Set default model to {self.current_model}")
                else:
                    logger.warning(f"No models available for {self.current_backend}")
                    self.current_model = None

            except Exception as e:
                logger.error(f"Error fetching {self.current_backend} models: {e}")
        else:
            # Settings define default for non-local backends
            self.current_model = self.backend_settings[self.current_backend][
                "default_model"
            ]
            logger.info(f"Set default model to {self.current_model}")

    def set_backend(self, backend_type: str) -> bool:
        """Set the current backend type."""
        if backend_type not in self.backend_settings:
            logger.error(f"Unsupported backend type: {backend_type}")
            return False

        if backend_type != self.current_backend:
            logger.info(
                f"Switching backend from {self.current_backend} to {backend_type}"
            )
            self.current_backend = backend_type
            # Set default model for the new backend
            self.current_model = self.backend_settings[backend_type]["default_model"]
            logger.info(f"Set default model to {self.current_model}")

        return True

    def get_backend(self) -> str:
        """Get the current backend type."""
        return self.current_backend

    def set_model(self, model_name: str) -> bool:
        """Set the current model for the active backend."""
        # For synchronous validation, we'll use cached models or basic validation
        backend_config = self.backend_settings[self.current_backend]

        # For static model lists (Gemini, OpenAI), check immediately
        if backend_config["models"]:
            if model_name not in backend_config["models"]:
                logger.error(
                    f"Model {model_name} not available for backend {self.current_backend}"
                )
                return False
        # For dynamic backends (Ollama, MLX), we'll allow the model and validate later
        else:
            logger.info(
                f"Setting model {model_name} for {self.current_backend} (will validate dynamically)"
            )

        self.current_model = model_name
        logger.info(f"Set model to {model_name} for backend {self.current_backend}")
        return True

    async def set_model_async(self, model_name: str) -> bool:
        """Async version of set_model that can validate against dynamic model lists."""
        available_models = self.list_models()
        if model_name not in available_models:
            logger.error(
                f"Model {model_name} not available for backend {self.current_backend}"
            )
            return False

        self.current_model = model_name
        logger.info(f"Set model to {model_name} for backend {self.current_backend}")
        return True

    def get_model(self) -> str:
        """Get the current model name."""
        return self.current_model

    def set_api_key(self, api_key: str):
        """Set the API key for backends that require it."""
        self.api_key = api_key

        # Set environment variables for different providers
        if self.current_backend == "gemini":
            os.environ["GEMINI_API_KEY"] = api_key
        elif self.current_backend == "openai":
            os.environ["OPENAI_API_KEY"] = api_key

        logger.info(f"API key set for {self.current_backend} backend")

    def requires_api_key(self) -> bool:
        """Check if current backend requires an API key."""
        return self.backend_settings[self.current_backend]["requires_api_key"]

    def list_models(self) -> List[str]:
        """List available models for the current backend."""
        backend_config = self.backend_settings[self.current_backend]

        if self.current_backend in LOCAL_BACKENDS:
            # For local backends, try to fetch models dynamically
            try:
                models = self._fetch_local_models()
                if models:
                    backend_config["models"] = models
                    return models
            except Exception as e:
                logger.warning(f"Failed to fetch {self.current_backend} models: {e}")
                # Fall back to cached models if available
                if backend_config["models"]:
                    return backend_config["models"]

        return backend_config["models"]

    def _fetch_local_models(self) -> List[str]:
        """Fetch available models from local backends (Ollama/MLX)."""
        backend_config = self.backend_settings[self.current_backend]
        base_url = backend_config.get("base_url")

        if not base_url:
            return []

        try:
            if self.current_backend == "ollama":
                # Ollama API endpoint
                url = f"{base_url}/api/tags"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return [model["name"] for model in data.get("models", [])]
            elif self.current_backend == "mlx":
                # MLX OpenAI-compatible endpoint
                url = f"{base_url}/v1/models"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return [model["id"] for model in data.get("data", [])]
        except Exception as e:
            logger.error(f"Error fetching models from {self.current_backend}: {e}")

        return []

    def _prepare_litellm_model_name(self) -> str:
        """Prepare the model name for LiteLLM based on current backend."""
        if self.current_backend == "gemini":
            return f"gemini/{self.current_model}"
        elif self.current_backend == "ollama":
            return f"ollama/{self.current_model}"
        elif self.current_backend == "mlx":
            # MLX uses OpenAI-compatible format
            return f"openai/{self.current_model}"
        elif self.current_backend == "openai":
            return self.current_model
        else:
            return self.current_model

    def _prepare_litellm_kwargs(self) -> Dict[str, Any]:
        """Prepare additional arguments for LiteLLM based on current backend."""
        kwargs = {}

        if self.current_backend == "ollama":
            backend_config = self.backend_settings["ollama"]
            kwargs["api_base"] = backend_config["base_url"]
        elif self.current_backend == "mlx":
            backend_config = self.backend_settings["mlx"]
            kwargs["api_base"] = f"{backend_config['base_url']}/v1"
            kwargs["api_key"] = "dummy"  # MLX doesn't need real API key
        elif self.current_backend == "gemini":
            if self.api_key:
                kwargs["api_key"] = self.api_key
            elif os.getenv("GEMINI_API_KEY"):
                kwargs["api_key"] = os.getenv("GEMINI_API_KEY")
        elif self.current_backend == "openai":
            if self.api_key:
                kwargs["api_key"] = self.api_key
            elif os.getenv("OPENAI_API_KEY"):
                kwargs["api_key"] = os.getenv("OPENAI_API_KEY")

        return kwargs

    async def chat_async(
        self,
        message: str,
        system_prompt: str = None,
        tools: List[Dict] = None,
        image_data=None,
    ) -> str:
        """Send a chat message to the current backend and return the response."""
        try:
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            # Prepare user message content
            if image_data:
                # For models that support vision (OpenAI, Claude, etc.)
                user_content = [{"type": "text", "text": message}]

                # Add image content
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image_data['mimeType']};base64,{image_data['data']}"
                        },
                    }
                )

                messages.append({"role": "user", "content": user_content})
                logger.info(
                    f"Adding image to request: {image_data.get('name', 'unknown')}"
                )
            else:
                messages.append({"role": "user", "content": message})

            # Prepare LiteLLM parameters
            model_name = self._prepare_litellm_model_name()
            kwargs = self._prepare_litellm_kwargs()

            # Add tools if provided
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            logger.info(
                f"Sending chat request to {self.current_backend} with model {self.current_model}"
            )

            # Make async completion call
            response = await acompletion(model=model_name, messages=messages, **kwargs)

            # Extract response content
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                if content:
                    return content

                # Handle tool calls if present
                if (
                    hasattr(response.choices[0].message, "tool_calls")
                    and response.choices[0].message.tool_calls
                ):
                    tool_calls = response.choices[0].message.tool_calls
                    return json.dumps(
                        [
                            {
                                "id": tc.id,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in tool_calls
                        ],
                        indent=2,
                    )

            return "No response received from the model."

        except Exception as e:
            logger.error(f"Error in chat_async with {self.current_backend}: {e}")
            raise

    def chat_sync(
        self, message: str, system_prompt: str = None, tools: List[Dict] = None
    ) -> str:
        """Synchronous chat method."""
        try:
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": message})

            # Prepare LiteLLM parameters
            model_name = self._prepare_litellm_model_name()
            kwargs = self._prepare_litellm_kwargs()

            # Add tools if provided
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            logger.info(
                f"Sending sync chat request to {self.current_backend} with model {self.current_model}"
            )

            # Make completion call
            response = completion(model=model_name, messages=messages, **kwargs)

            # Extract response content
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                if content:
                    return content

                # Handle tool calls if present
                if (
                    hasattr(response.choices[0].message, "tool_calls")
                    and response.choices[0].message.tool_calls
                ):
                    tool_calls = response.choices[0].message.tool_calls
                    return json.dumps(
                        [
                            {
                                "id": tc.id,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in tool_calls
                        ],
                        indent=2,
                    )

            return "No response received from the model."

        except Exception as e:
            logger.error(f"Error in chat_sync with {self.current_backend}: {e}")
            raise

    def validate_configuration(self) -> Dict[str, Any]:
        """Validate the current backend configuration."""
        result = {
            "backend": self.current_backend,
            "model": self.current_model,
            "valid": True,
            "issues": [],
        }

        backend_config = self.backend_settings[self.current_backend]

        # Check if API key is required and present
        if backend_config["requires_api_key"]:
            has_key = False
            if self.current_backend == "gemini":
                has_key = bool(self.api_key or os.getenv("GEMINI_API_KEY"))
            elif self.current_backend == "openai":
                has_key = bool(self.api_key or os.getenv("OPENAI_API_KEY"))

            if not has_key:
                result["valid"] = False
                result["issues"].append(
                    f"API key required for {self.current_backend} backend"
                )

        # Check if local service is accessible for local backends
        if self.current_backend in LOCAL_BACKENDS:
            base_url = backend_config.get("base_url")
            if base_url:
                try:
                    health_url = (
                        f"{base_url}/api/tags"
                        if self.current_backend == "ollama"
                        else f"{base_url}/v1/models"
                    )
                    response = requests.get(health_url, timeout=3)
                    if response.status_code != 200:
                        result["valid"] = False
                        result["issues"].append(
                            f"{self.current_backend} service not accessible at {base_url}"
                        )
                except Exception as e:
                    result["valid"] = False
                    result["issues"].append(
                        f"{self.current_backend} service not accessible: {str(e)}"
                    )

        return result

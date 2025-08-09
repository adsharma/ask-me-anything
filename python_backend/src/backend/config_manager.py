# config_manager.py
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages user configuration and preferences."""
    
    def __init__(self, config_dir: Optional[str] = None):
        """Initialize the config manager.
        
        Args:
            config_dir: Directory to store config files. If None, uses default location.
        """
        if config_dir is None:
            # Store config in the python_backend directory by default
            config_dir = Path(__file__).parent.parent.parent
        
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "user_config.json"
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Default configuration
        self.default_config = {
            "backend": "ollama",
            "models": {
                "ollama": "qwen3:0.6b",
                "gemini": "gemini-1.5-flash-latest",
                "openai": "gpt-4o-mini",
                "mlx": "baidu/ERNIE-4.5-0.3B-PT",
                "anthropic": "claude-3-haiku-20240307",
                "cohere": "command-r"
            },
            "api_keys": {}  # Don't store API keys in config file for security
        }
        
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                # Merge with defaults to ensure all keys exist
                merged_config = self.default_config.copy()
                merged_config.update(config)
                # Ensure models dict has all backends
                if "models" not in merged_config:
                    merged_config["models"] = self.default_config["models"].copy()
                else:
                    for backend, model in self.default_config["models"].items():
                        if backend not in merged_config["models"]:
                            merged_config["models"][backend] = model
                logger.info(f"Loaded configuration from {self.config_file}")
                return merged_config
            else:
                logger.info("No existing config file found, using defaults")
                return self.default_config.copy()
        except Exception as e:
            logger.error(f"Error loading config from {self.config_file}: {e}")
            logger.info("Using default configuration")
            return self.default_config.copy()
    
    def _save_config(self) -> bool:
        """Save current configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self._config, f, indent=2)
            logger.info(f"Configuration saved to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving config to {self.config_file}: {e}")
            return False
    
    def get_backend(self) -> str:
        """Get the currently selected backend."""
        return self._config.get("backend", "ollama")
    
    def set_backend(self, backend: str) -> bool:
        """Set the current backend and save to config."""
        if backend != self._config.get("backend"):
            self._config["backend"] = backend
            saved = self._save_config()
            if saved:
                logger.info(f"Backend set to {backend}")
            return saved
        return True
    
    def get_model(self, backend: Optional[str] = None) -> str:
        """Get the model for a specific backend or current backend."""
        if backend is None:
            backend = self.get_backend()
        
        return self._config.get("models", {}).get(backend, 
                                                 self.default_config["models"].get(backend, ""))
    
    def set_model(self, backend: str, model: str) -> bool:
        """Set the model for a specific backend and save to config."""
        if "models" not in self._config:
            self._config["models"] = {}
        
        if self._config["models"].get(backend) != model:
            self._config["models"][backend] = model
            saved = self._save_config()
            if saved:
                logger.info(f"Model for {backend} set to {model}")
            return saved
        return True
    
    def get_current_model(self) -> str:
        """Get the model for the currently selected backend."""
        return self.get_model(self.get_backend())
    
    def set_current_model(self, model: str) -> bool:
        """Set the model for the currently selected backend."""
        return self.set_model(self.get_backend(), model)
    
    def get_all_config(self) -> Dict[str, Any]:
        """Get the entire configuration."""
        return self._config.copy()
    
    def reset_to_defaults(self) -> bool:
        """Reset configuration to defaults and save."""
        self._config = self.default_config.copy()
        saved = self._save_config()
        if saved:
            logger.info("Configuration reset to defaults")
        return saved
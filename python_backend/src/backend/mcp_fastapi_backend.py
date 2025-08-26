# python_backend/mcp_fastapi_backend.py
import argparse
import asyncio
import json
import logging
import sys
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp_chat_app import MCPChatApp

sys.path.insert(0, str(Path(__file__).parent.absolute()))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

fastapi_app = FastAPI(title="MCP Multi-Backend API", version="1.0.0")

# Add CORS middleware to allow requests from the frontend
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

chat_app = None
loop = None
loop_ready = threading.Event()


def start_async_loop():
    global loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop_ready.set()
    logger.info("Asyncio loop started and ready.")
    loop.run_forever()


async def initialize_chat_app():
    global chat_app
    if chat_app is None:
        chat_app = MCPChatApp()
        try:
            # Try to initialize with default backend (Ollama)
            if chat_app.requires_api_key():
                # Ollama doesn't require an API key, so this won't execute
                pass
            logger.info("MCPChatApp initialized successfully with Ollama backend.")
        except Exception as e:
            logger.error(f"Failed to initialize MCPChatApp: {e}", exc_info=True)
            # Don't set chat_app to None - keep it for later initialization
            logger.warning("Chat app created but not fully initialized")
    return chat_app


async def load_default_servers():
    """Load servers from mcp_servers.json configuration file"""
    app = await initialize_chat_app()
    if not app:
        logger.error("Cannot load default servers: Chat app not initialized")
        return

    # Look for mcp_servers.json in the python_backend directory
    config_path = Path(__file__).parent.parent.parent / "mcp_servers.json"

    if not config_path.exists():
        logger.info(f"No default server configuration found at {config_path}")
        return

    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        if not config or "mcpServers" not in config:
            logger.warning("Invalid configuration format in mcp_servers.json")
            return

        servers = config["mcpServers"]
        loaded_count = 0

        for server_name, server_config in servers.items():
            # Skip disabled servers
            if server_config.get("disabled", False):
                logger.info(f"Skipping disabled server: {server_name}")
                continue

            if not server_config.get("command") or not server_config.get("args"):
                logger.warning(
                    f"Invalid server config for {server_name}: missing command or args"
                )
                continue

            try:
                # Get environment variables if specified
                env_vars = server_config.get("env", {})
                if env_vars:
                    logger.info(
                        f"Passing environment variables to server {server_name}: {list(env_vars.keys())}"
                    )

                added_tools = await app.connect_to_mcp_server(
                    name=server_name,
                    command=server_config["command"],
                    args=server_config["args"],
                    env=env_vars,
                )
                logger.info(
                    f"Successfully loaded default server '{server_name}' with {len(added_tools)} tools"
                )
                loaded_count += 1

            except Exception as e:
                logger.error(f"Failed to load default server '{server_name}': {e}")

        if loaded_count > 0:
            logger.info(f"Successfully loaded {loaded_count} default MCP servers")
        else:
            logger.info("No default servers were loaded")

    except Exception as e:
        logger.error(
            f"Error loading default servers from {config_path}: {e}", exc_info=True
        )


async def add_server_async(path=None, name=None, command=None, args=None, env=None):
    app = await initialize_chat_app()
    if not app:
        return {"status": "error", "message": "Chat app not initialized"}, 500

    identifier = path if path else name
    if not identifier:
        return {
            "status": "error",
            "message": "Missing server identifier (path or name)",
        }, 400

    try:
        added_tools = await app.connect_to_mcp_server(
            path=path, name=name, command=command, args=args, env=env
        )
        server_display_name = Path(path).name if path else name
        return {
            "status": "success",
            "message": f"Server '{server_display_name}' added.",
            "tools": added_tools,
        }
    except FileNotFoundError as e:
        return {"status": "error", "message": str(e)}, 404
    except (
        ValueError
    ) as e:  # Catches issues from connect_to_mcp_server like missing params
        return {"status": "error", "message": str(e)}, 400
    except Exception as e:
        logger.error(f"Error adding server {identifier}: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to add server: {e}"}, 500


async def disconnect_server_async(identifier):
    app = await initialize_chat_app()
    if not app:
        return {"status": "error", "message": "Chat app not initialized"}, 500
    try:
        disconnected = await app.disconnect_mcp_server(identifier)
        server_display_name = (
            Path(identifier).name
            if "/" in identifier or "\\" in identifier
            else identifier
        )
        if disconnected:
            return {
                "status": "success",
                "message": f"Server '{server_display_name}' disconnected.",
            }
        else:
            return {
                "status": "error",
                "message": f"Server '{server_display_name}' not found or already disconnected.",
            }
    except Exception as e:
        logger.error(f"Error disconnecting server {identifier}: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to disconnect server: {e}"}, 500


async def disconnect_all_servers_async():
    """Disconnect all connected MCP servers using comprehensive cleanup"""
    logger.info("Starting disconnect_all_servers_async")

    app = await initialize_chat_app()
    if not app:
        logger.error("Chat app not initialized in disconnect_all_servers_async")
        return {"status": "error", "message": "Chat app not initialized"}, 500

    try:
        # Get list of all connected servers before cleanup
        servers = list(app.server_resources.keys())
        logger.info(f"Found {len(servers)} servers to cleanup: {servers}")

        if not servers:
            logger.info("No servers to disconnect")
            return {"status": "success", "message": "No servers to disconnect"}

        logger.info(f"Cleaning up {len(servers)} MCP servers: {servers}")

        # Use the comprehensive cleanup method
        logger.info("Calling app.cleanup_all_servers()")
        cleanup_success = await app.cleanup_all_servers()
        logger.info(f"cleanup_all_servers() returned: {cleanup_success}")

        if cleanup_success:
            logger.info(f"Successfully cleaned up {len(servers)} servers")
            return {
                "status": "success",
                "message": f"Successfully cleaned up {len(servers)} servers",
                "servers_cleaned": [
                    Path(s).name if "/" in s or "\\" in s else s for s in servers
                ],
            }
        else:
            logger.warning(
                "cleanup_all_servers() returned False - some errors occurred"
            )
            return {
                "status": "error",
                "message": "Cleanup completed with some errors - check logs",
            }

    except Exception as e:
        logger.error(f"Error in disconnect_all_servers_async: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to disconnect all servers: {e}",
        }


async def get_servers_async():
    app = await initialize_chat_app()
    if not app:
        return {"status": "error", "message": "Chat app not initialized"}, 500
    servers = []
    # Now iterating through identifiers (path or name)
    for identifier, resources in app.server_resources.items():
        server_display_name = (
            Path(identifier).name
            if "/" in identifier or "\\" in identifier
            else identifier
        )
        servers.append(
            {
                "identifier": identifier,  # Send the unique ID
                "display_name": server_display_name,  # Send a user-friendly name
                "tools": sorted(resources.get("tools", [])),
                "status": resources.get("status", "unknown"),
            }
        )
    return {"status": "success", "servers": servers}


async def process_chat_async(message):
    app = await initialize_chat_app()
    if not app:
        return {"reply": "Error: Backend chat app not initialized."}, 500
    try:
        reply = await app.process_query(message, maintain_context=True)
        return {"reply": reply}
    except Exception as e:
        logger.error(f"Error processing chat: {e}", exc_info=True)
        return {"reply": f"An error occurred: {e}"}, 500


async def set_api_key_async(api_key):
    app = await initialize_chat_app()
    if not app:
        return {"status": "error", "message": "Chat app not initialized"}, 500
    try:
        await app.set_api_key_and_reinitialize(api_key)
        backend = app.get_backend()
        return {
            "status": "success",
            "message": f"API Key set for {backend} backend.",
        }
    except Exception as e:
        logger.error(f"Error setting API key: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to set API key: {e}"}, 500


# --- Model Switching Async Functions ---
async def set_model_async(model_name):
    app = await initialize_chat_app()
    if not app:
        return {"status": "error", "message": "Chat app not initialized"}, 500
    try:
        success = await app.set_model_async(model_name)
        if success:
            backend = app.get_backend()
            return {
                "status": "success",
                "message": f"Model set to {model_name} for {backend} backend.",
            }
        else:
            available_models = await app.list_available_models()
            return {
                "status": "error",
                "message": f"Invalid model: {model_name}. Available: {', '.join(available_models)}",
            }
    except Exception as e:
        logger.error(f"Error setting model to {model_name}: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to set model: {e}"}, 500


async def get_model_async():
    app = await initialize_chat_app()
    if not app:
        return {"status": "error", "message": "Chat app not initialized"}, 500
    try:
        current_model = app.get_model()
        return {"status": "success", "model": current_model}
    except Exception as e:
        logger.error(f"Error getting current model: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to get model: {e}"}, 500


async def list_models_async():
    app = await initialize_chat_app()
    if not app:
        # Return empty list even if app not fully initialized
        temp_app = MCPChatApp()
        try:
            available_models = await temp_app.list_available_models()
            return {"status": "success", "models": available_models}
        except Exception as e:
            logger.error(f"Error listing models with temp app: {e}")
            return {"status": "error", "message": f"Failed to list models: {e}"}, 500
    try:
        available_models = await app.list_available_models()
        return {"status": "success", "models": available_models}
    except Exception as e:
        logger.error(f"Error listing available models: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to list models: {e}"}, 500


# --- End Model Switching Async Functions ---


# --- Backend Management Async Functions ---
async def set_backend_async(backend_type):
    app = await initialize_chat_app()
    if not app:
        return {"status": "error", "message": "Chat app not initialized"}, 500
    try:
        success = app.set_backend(backend_type)
        if success:
            return {
                "status": "success",
                "message": f"Backend set to {backend_type}",
            }
        else:
            return {
                "status": "error",
                "message": f"Invalid backend type: {backend_type}",
            }
    except Exception as e:
        logger.error(f"Error setting backend to {backend_type}: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to set backend: {e}"}, 500


async def get_backend_async():
    app = await initialize_chat_app()
    if not app:
        return {"status": "error", "message": "Chat app not initialized"}, 500
    try:
        backend = app.get_backend()
        return {"status": "success", "backend": backend}
    except Exception as e:
        logger.error(f"Error getting backend: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to get backend: {e}"}, 500


async def validate_backend_async():
    app = await initialize_chat_app()
    if not app:
        return {"status": "error", "message": "Chat app not initialized"}, 500
    try:
        validation = app.validate_configuration()
        return {"status": "success", "validation": validation}
    except Exception as e:
        logger.error(f"Error validating backend: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to validate backend: {e}"}, 500


async def clear_history_async():
    app = await initialize_chat_app()
    if not app:
        return {"status": "error", "message": "Chat app not initialized"}, 500
    try:
        app.clear_conversation_history()
        return {"status": "success", "message": "Conversation history cleared"}
    except Exception as e:
        logger.error(f"Error clearing conversation history: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to clear conversation history: {e}",
        }


# --- End Backend Management Async Functions ---

# --- FastAPI Routes ---


@fastapi_app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    message = data.get("message")
    if not message:
        raise HTTPException(status_code=400, detail="No message provided.")
    if not loop or not loop.is_running():
        raise HTTPException(status_code=500, detail="Backend loop not running.")

    future = asyncio.run_coroutine_threadsafe(process_chat_async(message), loop)
    try:
        result = future.result(timeout=60)
        return result
    except asyncio.TimeoutError:
        logger.error("Chat processing timed out.")
        raise HTTPException(status_code=504, detail="Error: Response timed out.")
    except Exception as e:
        logger.error(f"Error getting result from chat future: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error processing your request: {e}"
        )


@fastapi_app.post("/servers")
async def add_server(request: Request):
    data = await request.json()
    path = data.get("path")
    name = data.get("name")
    command = data.get("command")
    args = data.get("args")  # Expecting a list
    env = data.get("env", {})  # Expecting a dict

    if not loop or not loop.is_running():
        raise HTTPException(status_code=500, detail="Backend loop not running.")

    if path:
        # Adding via Python script path
        future = asyncio.run_coroutine_threadsafe(
            add_server_async(path=path, env=env), loop
        )
        identifier_log = path
    elif name and command and isinstance(args, list):
        # Adding via command/args (e.g., from JSON)
        future = asyncio.run_coroutine_threadsafe(
            add_server_async(name=name, command=command, args=args, env=env), loop
        )
        identifier_log = name
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid parameters. Provide either 'path' or 'name', 'command', and 'args'.",
        )

    try:
        result, status_code = future.result(timeout=30)
        return JSONResponse(content=result, status_code=status_code)
    except asyncio.TimeoutError:
        logger.error(f"Adding server {identifier_log} timed out.")
        raise HTTPException(status_code=504, detail="Error: Adding server timed out.")
    except Exception as e:
        logger.error(
            f"Error getting result from add_server future for {identifier_log}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Error adding server: {e}")


@fastapi_app.delete("/servers")
async def delete_server(request: Request):
    data = await request.json()
    identifier = data.get("identifier")  # Expect 'identifier' instead of 'path'
    if not identifier:
        raise HTTPException(
            status_code=400,
            detail="No server identifier provided for deletion.",
        )
    if not loop or not loop.is_running():
        raise HTTPException(status_code=500, detail="Backend loop not running.")

    future = asyncio.run_coroutine_threadsafe(
        disconnect_server_async(identifier), loop
    )  # Pass identifier
    try:
        result, status_code = future.result(timeout=30)
        return JSONResponse(content=result, status_code=status_code)
    except asyncio.TimeoutError:
        logger.error(f"Disconnecting server {identifier} timed out.")
        raise HTTPException(
            status_code=504, detail="Error: Disconnecting server timed out."
        )
    except Exception as e:
        logger.error(
            f"Error getting result from delete_server future for {identifier}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Error disconnecting server: {e}")


@fastapi_app.get("/servers")
async def get_servers():
    if not loop or not loop.is_running():
        raise HTTPException(status_code=500, detail="Backend loop not running.")

    future = asyncio.run_coroutine_threadsafe(get_servers_async(), loop)
    try:
        result, status_code = future.result(timeout=10)
        return JSONResponse(content=result, status_code=status_code)
    except asyncio.TimeoutError:
        logger.error("Getting servers timed out.")
        raise HTTPException(
            status_code=504, detail="Error: Getting server list timed out."
        )
    except Exception as e:
        logger.error(
            f"Error getting result from get_servers future: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Error getting servers: {e}")


@fastapi_app.post("/disconnect-all-servers")
async def disconnect_all_servers():
    """Disconnect all MCP servers for clean shutdown"""
    logger.info("Received request to disconnect all servers")

    if not loop or not loop.is_running():
        logger.error("Backend loop not running when disconnect-all-servers called")
        raise HTTPException(status_code=500, detail="Backend loop not running.")

    logger.info("Submitting disconnect_all_servers_async to event loop")
    future = asyncio.run_coroutine_threadsafe(disconnect_all_servers_async(), loop)
    try:
        result, status_code = future.result(
            timeout=30
        )  # Longer timeout for multiple disconnections
        logger.info(
            f"disconnect_all_servers_async completed with status {status_code}: {result}"
        )
        return JSONResponse(content=result, status_code=status_code)
    except asyncio.TimeoutError:
        logger.error("Disconnecting all servers timed out.")
        raise HTTPException(
            status_code=504, detail="Error: Disconnecting all servers timed out."
        )
    except Exception as e:
        logger.error(f"Error disconnecting all servers: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error disconnecting all servers: {e}"
        )


@fastapi_app.post("/set-api-key")
async def set_api_key(request: Request):
    data = await request.json()
    api_key = data.get("apiKey")
    if not api_key:
        raise HTTPException(status_code=400, detail="No API key provided.")
    if not loop or not loop.is_running():
        raise HTTPException(status_code=500, detail="Backend loop not running.")

    future = asyncio.run_coroutine_threadsafe(set_api_key_async(api_key), loop)
    try:
        result, status_code = future.result(timeout=20)  # Timeout for re-initialization
        return JSONResponse(content=result, status_code=status_code)
    except asyncio.TimeoutError:
        logger.error("Setting API key timed out.")
        raise HTTPException(status_code=504, detail="Error: Setting API key timed out.")
    except Exception as e:
        logger.error(
            f"Error getting result from set_api_key future: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Error setting API key: {e}")


# --- Model Switching Endpoints ---
@fastapi_app.post("/set-model")
async def set_model(request: Request):
    data = await request.json()
    model_name = data.get("model")
    if not model_name:
        raise HTTPException(status_code=400, detail="No model name provided.")
    if not loop or not loop.is_running():
        raise HTTPException(status_code=500, detail="Backend loop not running.")

    future = asyncio.run_coroutine_threadsafe(set_model_async(model_name), loop)
    try:
        result, status_code = future.result(timeout=10)
        return JSONResponse(content=result, status_code=status_code)
    except asyncio.TimeoutError:
        logger.error(f"Setting model to {model_name} timed out.")
        raise HTTPException(status_code=504, detail="Error: Setting model timed out.")
    except Exception as e:
        logger.error(f"Error getting result from set_model future: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error setting model: {e}")


@fastapi_app.get("/get-model")
async def get_model():
    if not loop or not loop.is_running():
        raise HTTPException(status_code=500, detail="Backend loop not running.")

    future = asyncio.run_coroutine_threadsafe(get_model_async(), loop)
    try:
        result, status_code = future.result(timeout=5)
        return JSONResponse(content=result, status_code=status_code)
    except asyncio.TimeoutError:
        logger.error("Getting current model timed out.")
        raise HTTPException(
            status_code=504, detail="Error: Getting current model timed out."
        )
    except Exception as e:
        logger.error(f"Error getting result from get_model future: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting current model: {e}")


@fastapi_app.get("/list-models")
async def list_models():
    # Allow listing even if loop isn't fully ready, as list may be available
    pass

    # Run directly if loop isn't ready, otherwise use threadsafe call
    if loop and loop.is_running():
        future = asyncio.run_coroutine_threadsafe(list_models_async(), loop)
        try:
            result, status_code = future.result(timeout=5)
            return JSONResponse(content=result, status_code=status_code)
        except asyncio.TimeoutError:
            logger.error("Listing models timed out.")
            raise HTTPException(
                status_code=504, detail="Error: Listing models timed out."
            )
        except Exception as e:
            logger.error(
                f"Error getting result from list_models future: {e}", exc_info=True
            )
            raise HTTPException(status_code=500, detail=f"Error listing models: {e}")
    else:
        # Fallback for when loop isn't running (e.g., during startup errors)
        try:
            temp_app = MCPChatApp()
            models = asyncio.run(temp_app.list_available_models())
            return {"status": "success", "models": models}
        except Exception as e:
            logger.error(f"Error listing models directly (no loop): {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error listing models: {e}")


# --- End Model Switching Endpoints ---


# --- Backend Management Endpoints ---
@fastapi_app.post("/set-backend")
async def set_backend(request: Request):
    data = await request.json()
    backend_type = data.get("backend")
    if not backend_type:
        raise HTTPException(status_code=400, detail="No backend type provided.")
    if not loop or not loop.is_running():
        raise HTTPException(status_code=500, detail="Backend loop not running.")

    future = asyncio.run_coroutine_threadsafe(set_backend_async(backend_type), loop)
    try:
        result, status_code = future.result(timeout=10)
        return JSONResponse(content=result, status_code=status_code)
    except asyncio.TimeoutError:
        logger.error(f"Setting backend to {backend_type} timed out.")
        raise HTTPException(status_code=504, detail="Error: Setting backend timed out.")
    except Exception as e:
        logger.error(
            f"Error getting result from set_backend future: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Error setting backend: {e}")


@fastapi_app.get("/get-backend")
async def get_backend():
    if not loop or not loop.is_running():
        raise HTTPException(status_code=500, detail="Backend loop not running.")

    future = asyncio.run_coroutine_threadsafe(get_backend_async(), loop)
    try:
        result, status_code = future.result(timeout=5)
        return JSONResponse(content=result, status_code=status_code)
    except asyncio.TimeoutError:
        logger.error("Getting backend timed out.")
        raise HTTPException(status_code=504, detail="Error: Getting backend timed out.")
    except Exception as e:
        logger.error(
            f"Error getting result from get_backend future: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Error getting backend: {e}")


@fastapi_app.get("/validate-backend")
async def validate_backend():
    if not loop or not loop.is_running():
        raise HTTPException(status_code=500, detail="Backend loop not running.")

    future = asyncio.run_coroutine_threadsafe(validate_backend_async(), loop)
    try:
        result, status_code = future.result(timeout=10)
        return JSONResponse(content=result, status_code=status_code)
    except asyncio.TimeoutError:
        logger.error("Validating backend timed out.")
        raise HTTPException(
            status_code=504, detail="Error: Validating backend timed out."
        )
    except Exception as e:
        logger.error(
            f"Error getting result from validate_backend future: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Error validating backend: {e}")


@fastapi_app.post("/clear-history")
async def clear_history():
    if not loop or not loop.is_running():
        raise HTTPException(status_code=500, detail="Backend loop not running.")

    future = asyncio.run_coroutine_threadsafe(clear_history_async(), loop)
    try:
        result, status_code = future.result(timeout=5)
        return JSONResponse(content=result, status_code=status_code)
    except asyncio.TimeoutError:
        logger.error("Clearing conversation history timed out.")
        raise HTTPException(
            status_code=504, detail="Error: Clearing conversation history timed out."
        )
    except Exception as e:
        logger.error(
            f"Error getting result from clear_history future: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Error clearing conversation history: {e}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MCP Multi-Backend FastAPI Server")
    parser.add_argument(
        "--port", type=int, default=5001, help="Port to run the backend on"
    )
    parser.add_argument("--backend", type=str, help="Initial backend to use")
    parser.add_argument("--model", type=str, help="Initial model to use")
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Host to run the backend on"
    )
    args = parser.parse_args()

    thread = threading.Thread(target=start_async_loop, daemon=True)
    thread.start()

    if not loop_ready.wait(timeout=10):
        logger.error("Asyncio loop did not start within timeout.")
        sys.exit(1)

    try:
        init_future = asyncio.run_coroutine_threadsafe(initialize_chat_app(), loop)
        try:
            init_future.result(timeout=20)
            if chat_app is None:
                logger.error("Chat app initialization returned None.")
                sys.exit(1)
            logger.info(
                "Chat app initialized successfully via asyncio loop with Ollama backend."
            )

            # Set initial backend and model if provided
            if args.backend:
                chat_app.set_backend(args.backend)
                logger.info(f"Set initial backend to: {args.backend}")

            if args.model:
                chat_app.set_model(args.model)
                logger.info(f"Set initial model to: {args.model}")

            # Load default servers from mcp_servers.json BEFORE starting FastAPI
            load_servers_future = asyncio.run_coroutine_threadsafe(
                load_default_servers(), loop
            )
            try:
                load_servers_future.result(timeout=30)
                logger.info("Default servers loading completed.")
            except Exception as e:
                logger.error(f"Error loading default servers: {e}", exc_info=True)
                # Don't exit - the app can still work without default servers

        except Exception as e:
            logger.error(f"Error during chat app initialization: {e}", exc_info=True)
            # Don't exit if init fails due to no key, allow setting it later
            logger.warning(
                "Initial backend initialization failed. Backend can be configured later via API."
            )
            # Ensure we have a chat_app instance even if init fails
            if chat_app is None:
                loop_for_init = asyncio.run_coroutine_threadsafe(
                    initialize_chat_app(), loop
                )
                try:
                    loop_for_init.result(timeout=5)
                except:
                    pass  # Ignore errors, we'll create manually
                if chat_app is None:
                    chat_app = MCPChatApp()
                    logger.info(
                        "Created MCPChatApp instance with Ollama backend despite initialization failure."
                    )

    except:
        logger.error("Asyncio loop not available after waiting.")
        sys.exit(1)

    logger.info(f"Starting FastAPI server on {args.host}:{args.port}")
    uvicorn.run(fastapi_app, host=args.host, port=args.port)

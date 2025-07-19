# python_backend/mcp_flask_backend.py
from mcp_chat_app import MCPChatApp
import sys
import os
import argparse
from flask import Flask, request, jsonify
import asyncio
import threading
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)
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
            await chat_app.initialize_gemini()
            logger.info("MCPChatApp initialized successfully.")
        except Exception as e:
            logger.error(
                f"Failed to initialize MCPChatApp: {e}", exc_info=True)
            chat_app = None
            raise
    return chat_app


async def add_server_async(path=None, name=None, command=None, args=None):
    app = await initialize_chat_app()
    if not app:
        return {"status": "error", "message": "Chat app not initialized"}, 500

    identifier = path if path else name
    if not identifier:
         return {"status": "error", "message": "Missing server identifier (path or name)"}, 400

    try:
        added_tools = await app.connect_to_mcp_server(path=path, name=name, command=command, args=args)
        server_display_name = os.path.basename(path) if path else name
        return {"status": "success", "message": f"Server '{server_display_name}' added.", "tools": added_tools}, 200
    except FileNotFoundError as e:
        return {"status": "error", "message": str(e)}, 404
    except ValueError as e: # Catches issues from connect_to_mcp_server like missing params
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
        server_display_name = os.path.basename(identifier) if '/' in identifier or '\\' in identifier else identifier
        if disconnected:
            return {"status": "success", "message": f"Server '{server_display_name}' disconnected."}, 200
        else:
            return {"status": "error", "message": f"Server '{server_display_name}' not found or already disconnected."}, 404
    except Exception as e:
        logger.error(f"Error disconnecting server {identifier}: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to disconnect server: {e}"}, 500


async def get_servers_async():
    app = await initialize_chat_app()
    if not app:
        return {"status": "error", "message": "Chat app not initialized"}, 500
    servers = []
    # Now iterating through identifiers (path or name)
    for identifier, resources in app.server_resources.items():
        server_display_name = os.path.basename(identifier) if '/' in identifier or '\\' in identifier else identifier
        servers.append({
            "identifier": identifier, # Send the unique ID
            "display_name": server_display_name, # Send a user-friendly name
            "tools": sorted(resources.get('tools', [])),
            "status": resources.get('status', 'unknown')
        })
    return {"status": "success", "servers": servers}, 200


async def process_chat_async(message):
    app = await initialize_chat_app()
    if not app:
        return {"reply": "Error: Backend chat app not initialized."}, 500
    try:
        reply = await app.process_query(message)
        return {"reply": reply}, 200
    except Exception as e:
        logger.error(f"Error processing chat: {e}", exc_info=True)
        return {"reply": f"An error occurred: {e}"}, 500


async def set_api_key_async(api_key):
    app = await initialize_chat_app()
    if not app:
        return {"status": "error", "message": "Chat app not initialized"}, 500
    try:
        await app.set_api_key_and_reinitialize(api_key)
        return {"status": "success", "message": "API Key set and Gemini client re-initialized."}, 200
    except Exception as e:
        logger.error(
            f"Error setting API key and re-initializing: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to set API key: {e}"}, 500

# --- Model Switching Async Functions ---
async def set_model_async(model_name):
    app = await initialize_chat_app()
    if not app:
        return {"status": "error", "message": "Chat app not initialized"}, 500
    try:
        app.set_gemini_model(model_name)
        return {"status": "success", "message": f"Gemini model set to {model_name}."}, 200
    except ValueError as e: # Catch unsupported model error
        return {"status": "error", "message": str(e)}, 400
    except Exception as e:
        logger.error(f"Error setting Gemini model to {model_name}: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to set model: {e}"}, 500

async def get_model_async():
    app = await initialize_chat_app()
    if not app:
        return {"status": "error", "message": "Chat app not initialized"}, 500
    try:
        current_model = app.get_gemini_model()
        return {"status": "success", "model": current_model}, 200
    except Exception as e:
        logger.error(f"Error getting current Gemini model: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to get model: {e}"}, 500

async def list_models_async():
    app = await initialize_chat_app()
    if not app:
        # Return empty list even if app not fully initialized, as the list is static for now
        # If fetching dynamically, would return error here.
        temp_app = MCPChatApp() # Get default list
        return {"status": "success", "models": temp_app.get_available_models()}, 200
        # return {"status": "error", "message": "Chat app not initialized"}, 500
    try:
        available_models = app.get_available_models()
        return {"status": "success", "models": available_models}, 200
    except Exception as e:
        logger.error(f"Error listing available Gemini models: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to list models: {e}"}, 500
# --- End Model Switching Async Functions ---

@flask_app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message')
    if not message:
        return jsonify({"reply": "No message provided."}), 400
    if not loop or not loop.is_running():
        return jsonify({"reply": "Backend loop not running."}), 500

    future = asyncio.run_coroutine_threadsafe(
        process_chat_async(message), loop)
    try:
        result, status_code = future.result(timeout=60)
        return jsonify(result), status_code
    except asyncio.TimeoutError:
        logger.error("Chat processing timed out.")
        return jsonify({"reply": "Error: Response timed out."}), 504
    except Exception as e:
        logger.error(
            f"Error getting result from chat future: {e}", exc_info=True)
        return jsonify({"reply": f"Error processing your request: {e}"}), 500


@flask_app.route('/servers', methods=['POST'])
def add_server():
    data = request.get_json()
    path = data.get('path')
    name = data.get('name')
    command = data.get('command')
    args = data.get('args') # Expecting a list

    if not loop or not loop.is_running():
        return jsonify({"status": "error", "message": "Backend loop not running."}), 500

    if path:
        # Adding via Python script path
        future = asyncio.run_coroutine_threadsafe(add_server_async(path=path), loop)
        identifier_log = path
    elif name and command and isinstance(args, list):
        # Adding via command/args (e.g., from JSON)
        future = asyncio.run_coroutine_threadsafe(add_server_async(name=name, command=command, args=args), loop)
        identifier_log = name
    else:
        return jsonify({"status": "error", "message": "Invalid parameters. Provide either 'path' or 'name', 'command', and 'args'."}), 400

    try:
        result, status_code = future.result(timeout=30)
        return jsonify(result), status_code
    except asyncio.TimeoutError:
        logger.error(f"Adding server {identifier_log} timed out.")
        return jsonify({"status": "error", "message": "Error: Adding server timed out."}), 504
    except Exception as e:
        logger.error(
            f"Error getting result from add_server future for {identifier_log}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Error adding server: {e}"}), 500


@flask_app.route('/servers', methods=['DELETE'])
def delete_server():
    data = request.get_json()
    identifier = data.get('identifier') # Expect 'identifier' instead of 'path'
    if not identifier:
        return jsonify({"status": "error", "message": "No server identifier provided for deletion."}), 400
    if not loop or not loop.is_running():
        return jsonify({"status": "error", "message": "Backend loop not running."}), 500

    future = asyncio.run_coroutine_threadsafe(
        disconnect_server_async(identifier), loop) # Pass identifier
    try:
        result, status_code = future.result(timeout=30)
        return jsonify(result), status_code
    except asyncio.TimeoutError:
        logger.error(f"Disconnecting server {identifier} timed out.")
        return jsonify({"status": "error", "message": "Error: Disconnecting server timed out."}), 504
    except Exception as e:
        logger.error(
            f"Error getting result from delete_server future for {identifier}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Error disconnecting server: {e}"}), 500


@flask_app.route('/servers', methods=['GET'])
def get_servers():
    if not loop or not loop.is_running():
        return jsonify({"status": "error", "message": "Backend loop not running."}), 500

    future = asyncio.run_coroutine_threadsafe(get_servers_async(), loop)
    try:
        result, status_code = future.result(timeout=10)
        return jsonify(result), status_code
    except asyncio.TimeoutError:
        logger.error("Getting servers timed out.")
        return jsonify({"status": "error", "message": "Error: Getting server list timed out."}), 504
    except Exception as e:
        logger.error(
            f"Error getting result from get_servers future: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Error getting servers: {e}"}), 500


@flask_app.route('/set-api-key', methods=['POST'])
def set_api_key():
    data = request.get_json()
    api_key = data.get('apiKey')
    if not api_key:
        return jsonify({"status": "error", "message": "No API key provided."}), 400
    if not loop or not loop.is_running():
        return jsonify({"status": "error", "message": "Backend loop not running."}), 500

    future = asyncio.run_coroutine_threadsafe(set_api_key_async(api_key), loop)
    try:
        result, status_code = future.result(
            timeout=20)  # Timeout for re-initialization
        return jsonify(result), status_code
    except asyncio.TimeoutError:
        logger.error("Setting API key timed out.")
        return jsonify({"status": "error", "message": "Error: Setting API key timed out."}), 504
    except Exception as e:
        logger.error(
            f"Error getting result from set_api_key future: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Error setting API key: {e}"}), 500

# --- Model Switching Endpoints ---
@flask_app.route('/set-model', methods=['POST'])
def set_model():
    data = request.get_json()
    model_name = data.get('model')
    if not model_name:
        return jsonify({"status": "error", "message": "No model name provided."}), 400
    if not loop or not loop.is_running():
        return jsonify({"status": "error", "message": "Backend loop not running."}), 500

    future = asyncio.run_coroutine_threadsafe(set_model_async(model_name), loop)
    try:
        result, status_code = future.result(timeout=10)
        return jsonify(result), status_code
    except asyncio.TimeoutError:
        logger.error(f"Setting model to {model_name} timed out.")
        return jsonify({"status": "error", "message": "Error: Setting model timed out."}), 504
    except Exception as e:
        logger.error(f"Error getting result from set_model future: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Error setting model: {e}"}), 500

@flask_app.route('/get-model', methods=['GET'])
def get_model():
    if not loop or not loop.is_running():
        return jsonify({"status": "error", "message": "Backend loop not running."}), 500

    future = asyncio.run_coroutine_threadsafe(get_model_async(), loop)
    try:
        result, status_code = future.result(timeout=5)
        return jsonify(result), status_code
    except asyncio.TimeoutError:
        logger.error("Getting current model timed out.")
        return jsonify({"status": "error", "message": "Error: Getting current model timed out."}), 504
    except Exception as e:
        logger.error(f"Error getting result from get_model future: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Error getting current model: {e}"}), 500

@flask_app.route('/list-models', methods=['GET'])
def list_models():
    if not loop or not loop.is_running():
        # Allow listing even if loop isn't fully ready, as list is static
        pass
        # return jsonify({"status": "error", "message": "Backend loop not running."}), 500

    # Run directly if loop isn't ready, otherwise use threadsafe call
    if loop and loop.is_running():
        future = asyncio.run_coroutine_threadsafe(list_models_async(), loop)
        try:
            result, status_code = future.result(timeout=5)
            return jsonify(result), status_code
        except asyncio.TimeoutError:
            logger.error("Listing models timed out.")
            return jsonify({"status": "error", "message": "Error: Listing models timed out."}), 504
        except Exception as e:
            logger.error(f"Error getting result from list_models future: {e}", exc_info=True)
            return jsonify({"status": "error", "message": f"Error listing models: {e}"}), 500
    else:
        # Fallback for when loop isn't running (e.g., during startup errors)
        try:
            temp_app = MCPChatApp()
            models = temp_app.get_available_models()
            return jsonify({"status": "success", "models": models}), 200
        except Exception as e:
            logger.error(f"Error listing models directly (no loop): {e}", exc_info=True)
            return jsonify({"status": "error", "message": f"Error listing models: {e}"}), 500
# --- End Model Switching Endpoints ---

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='MCP Gemini Flask Backend')
    parser.add_argument('--port', type=int, default=5001,
                        help='Port to run the backend on')
    args = parser.parse_args()

    thread = threading.Thread(target=start_async_loop, daemon=True)
    thread.start()

    if not loop_ready.wait(timeout=10):
        logger.error("Asyncio loop did not start within timeout.")
        sys.exit(1)

    if loop:
        init_future = asyncio.run_coroutine_threadsafe(
            initialize_chat_app(), loop)
        try:
            init_future.result(timeout=20)
            if chat_app is None:
                logger.error("Chat app initialization returned None.")
                sys.exit(1)
            logger.info("Chat app initialized successfully via asyncio loop.")
        except Exception as e:
            logger.error(
                f"Error during chat app initialization: {e}", exc_info=True)
            # Don't exit if init fails due to no key, allow setting it later
            logger.warning(
                "Initial Gemini initialization failed, likely no API key. Waiting for key to be set.")
            # chat_app will still be None if it failed badly
            if chat_app is None:
                chat_app = MCPChatApp()  # Create instance even if init fails
                logger.info(
                    "Created MCPChatApp instance despite initial Gemini failure.")

    else:
        logger.error("Asyncio loop not available after waiting.")
        sys.exit(1)

    logger.info(f"Starting Flask server on 127.0.0.1:{args.port}")
    flask_app.run(host='127.0.0.1', port=args.port)

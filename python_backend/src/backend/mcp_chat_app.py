# python_backend/mcp_chat_app.py
import asyncio
import sys
import os
import json
from dotenv import load_dotenv
from contextlib import AsyncExitStack
from typing import List, Dict, Any, Optional, Tuple, Set
import logging

from google import genai
from google.genai import types as genai_types
from google.genai import errors as genai_errors
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from ai_backend_manager import AIBackendManager

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()


class MCPChatApp:
    def __init__(self, backend_type: str = "ollama", model_name: str = None):
        # Initialize the AI backend manager
        self.ai_backend = AIBackendManager()
        if backend_type:
            self.ai_backend.set_backend(backend_type)
        if model_name:
            self.ai_backend.set_model(model_name)

        # Legacy Gemini-specific properties (for backward compatibility)
        self.gemini_sync_client: Optional[genai.Client] = None
        self.gemini_client: Optional[genai.client.AsyncClient] = None

        # MCP-related properties
        self.mcp_tools: List[Any] = []
        self.tool_to_session: Dict[str, ClientSession] = {}
        self.chat_history: List[genai_types.Content] = []
        self.server_resources: Dict[str, Dict[str, Any]] = {}
        self.cached_gemini_declarations: Optional[List[genai_types.FunctionDeclaration]] = None
        self.gemini_tools_dirty: bool = True
        self.status_check_task: Optional[asyncio.Task] = None
        self.api_key: Optional[str] = None

    # Backend Management Methods
    def set_backend(self, backend_type: str) -> bool:
        """Set the AI backend type."""
        return self.ai_backend.set_backend(backend_type)

    def get_backend(self) -> str:
        """Get the current AI backend type."""
        return self.ai_backend.get_backend()

    def set_model(self, model_name: str) -> bool:
        """Set the model for the current backend."""
        return self.ai_backend.set_model(model_name)

    async def set_model_async(self, model_name: str) -> bool:
        """Async version that validates against dynamic model lists."""
        return await self.ai_backend.set_model_async(model_name)

    def get_model(self) -> str:
        """Get the current model name."""
        return self.ai_backend.get_model()

    async def list_available_models(self) -> List[str]:
        """List available models for the current backend."""
        return await self.ai_backend.list_models()

    def requires_api_key(self) -> bool:
        """Check if current backend requires an API key."""
        return self.ai_backend.requires_api_key()

    async def set_api_key_and_reinitialize(self, new_key: str):
        """Set API key for the current backend."""
        logger.info(f"Received new API key for {self.ai_backend.get_backend()} backend.")
        self.api_key = new_key
        self.ai_backend.set_api_key(new_key)

        # For backward compatibility, also initialize Gemini if it's the current backend
        if self.ai_backend.get_backend() == "gemini":
            try:
                await self.initialize_gemini()
                logger.info("Gemini client re-initialized successfully with new API key.")
            except Exception as e:
                logger.error(f"Failed to re-initialize Gemini with new API key: {e}")
                self.api_key = None
                raise

    def validate_configuration(self) -> Dict[str, Any]:
        """Validate the current backend configuration."""
        return self.ai_backend.validate_configuration()

    async def initialize_gemini(self):
        """Legacy method for Gemini initialization."""
        if self.ai_backend.get_backend() != "gemini":
            logger.warning("initialize_gemini called but current backend is not Gemini")
            return

        api_key_to_use = self.api_key or os.getenv("GEMINI_API_KEY")
        if not api_key_to_use:
            logger.error("GEMINI_API_KEY not found in environment variables or instance.")
            raise ValueError("GEMINI_API_KEY is required.")

        try:
            self.ai_backend.set_api_key(api_key_to_use)
            self.gemini_sync_client = genai.Client(api_key=api_key_to_use)
            self.gemini_client = self.gemini_sync_client.aio
            logger.info("Gemini async client initialized successfully.")

            if not self.status_check_task or self.status_check_task.done():
                self.status_check_task = asyncio.create_task(self._periodic_status_checker())
                logger.info("Started periodic server status checker.")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            self.gemini_client = None
            self.gemini_sync_client = None
            raise

    async def _check_server_status(self, identifier: str, session: ClientSession):
        # Use identifier (path or name) for logging and access
        server_display_name = os.path.basename(identifier) if '/' in identifier or '\\' in identifier else identifier
        try:
            await session.list_tools() # Ping the server
            if self.server_resources.get(identifier, {}).get('status') == 'error':
                logger.info(
                    f"Server '{server_display_name}' recovered, setting status to 'connected'.")
                self.server_resources[identifier]['status'] = 'connected'
        except Exception as e:
            if self.server_resources.get(identifier, {}).get('status') == 'connected':
                logger.warning(
                    f"Server '{server_display_name}' became unresponsive: {e}. Setting status to 'error'.")
                self.server_resources[identifier]['status'] = 'error'

    async def _periodic_status_checker(self, interval_seconds: int = 10):
        while True:
            await asyncio.sleep(interval_seconds)
            logger.debug("Running periodic server status check...")
            tasks = []
            # Use identifier instead of path
            active_servers = list(self.server_resources.items())
            for identifier, resources in active_servers:
                if 'session' in resources:
                    tasks.append(self._check_server_status(
                        identifier, resources['session']))
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        try:
                            # Get the identifier corresponding to the failed task
                            failed_identifier = active_servers[i][0]
                            logger.error(
                                f"Error during periodic status check gather for {failed_identifier}: {result}", exc_info=result)
                        except IndexError:
                            logger.error(
                                f"Error during periodic status check gather (index {i}, result: {result}) - identifier mapping failed", exc_info=result)
            logger.debug("Periodic server status check finished.")

    async def connect_to_mcp_server(self, path: Optional[str] = None, name: Optional[str] = None, command: Optional[str] = None, args: Optional[List[str]] = None) -> List[str]:
        identifier = path if path else name
        if not identifier:
            raise ValueError("Either 'path' or 'name' must be provided.")

        if identifier in self.server_resources:
            server_display_name = os.path.basename(path) if path else name
            logger.warning(
                f"Server '{server_display_name}' ({identifier}) is already connected. Skipping.")
            raise ValueError(
                f"Server '{server_display_name}' is already connected.")

        command_list: List[str] = []
        if path:
            if not os.path.exists(path):
                logger.error(f"MCP server script not found: {path}")
                raise FileNotFoundError(f"Server script not found: {path}")
            # Assume python if path is given for now, could add more checks
            command_to_use = sys.executable
            command_list = [command_to_use, path]
            logger.info(f"Preparing to connect via path: {path} using '{command_to_use}'")
        elif name and command and args is not None:
            command_list = [command] + args
            logger.info(f"Preparing to connect via command: name='{name}', command='{command}', args={args}")
        else:
            raise ValueError("Invalid parameters. Provide either 'path' or ('name', 'command', 'args').")

        server_params = StdioServerParameters(
            command=command_list[0],
            args=command_list[1:],
            env=None # Consider allowing env vars later if needed
        )

        server_stack = AsyncExitStack()
        try:
            logger.info(f"Connecting to MCP server: {identifier}")
            stdio_transport = await server_stack.enter_async_context(stdio_client(server_params))
            stdio, write = stdio_transport
            session = await server_stack.enter_async_context(ClientSession(stdio, write))
            await session.initialize()
            logger.info(f"Connected to MCP server: {identifier}")

            # Add to resources immediately after successful connection
            self.server_resources[identifier] = {
                'session': session,
                'stack': server_stack,
                'tools': [], # Will be populated below
                'status': 'connected',
                'command_list': command_list # Store how it was launched
            }

            response = await session.list_tools()
            server_tools = response.tools
            logger.info(
                f"Server {identifier} provides tools: {[tool.name for tool in server_tools]}")

            added_tools_names = []
            for tool in server_tools:
                if tool.name in self.tool_to_session:
                    logger.warning(
                        f"Tool name conflict: '{tool.name}' already exists. Skipping tool from {identifier}.")
                else:
                    self.mcp_tools.append(tool)
                    self.tool_to_session[tool.name] = session
                    added_tools_names.append(tool.name)
                    self.gemini_tools_dirty = True

            # Update the tools list for the server
            self.server_resources[identifier]['tools'] = added_tools_names
            logger.info(f"Stored resources for server: {identifier}")
            return added_tools_names

        except Exception as e:
            logger.error(
                f"Failed to connect to or initialize MCP server {identifier}: {e}", exc_info=True)
            # Ensure resources are cleaned up if connection fails
            if identifier in self.server_resources:
                 # If it got added before the exception
                 res = self.server_resources.pop(identifier)
                 await res['stack'].aclose() # Close stack if it exists
            else:
                 # If exception happened before adding to resources, just close stack
                 await server_stack.aclose()
            raise

    async def disconnect_mcp_server(self, identifier: str) -> bool:
        if identifier not in self.server_resources:
            logger.warning(
                f"Attempted to disconnect non-existent server: {identifier}")
            return False

        logger.info(f"Disconnecting MCP server: {identifier}")
        resources = self.server_resources.pop(identifier)
        stack = resources['stack']
        tools_to_remove = resources['tools']

        try:
            await stack.aclose() # This should terminate the process via stdio closing
            logger.info(
                f"Successfully closed resources for server: {identifier}")
        except Exception as e:
            logger.error(
                f"Error closing resources for server {identifier}: {e}", exc_info=True)
        # No need to discard from connected_server_paths anymore

        self.mcp_tools = [
            tool for tool in self.mcp_tools if tool.name not in tools_to_remove]
        for tool_name in tools_to_remove:
            self.tool_to_session.pop(tool_name, None)

        if tools_to_remove:
            self.gemini_tools_dirty = True
            logger.info(
                f"Removed tools from disconnected server {identifier}: {tools_to_remove}")

        logger.info(f"Successfully disconnected server: {identifier}")
        return True

    def get_gemini_tool_declarations(self) -> List[genai_types.FunctionDeclaration]:
        if not self.gemini_tools_dirty and self.cached_gemini_declarations is not None:
            return self.cached_gemini_declarations

        logger.info("Generating Gemini tool declarations.")
        declarations = []
        type_mapping = {
            'string': 'STRING',
            'number': 'NUMBER',
            'integer': 'INTEGER',
            'boolean': 'BOOLEAN',
            'array': 'ARRAY',
            'object': 'OBJECT',
        }

        for mcp_tool in self.mcp_tools:
            try:
                if hasattr(mcp_tool.inputSchema, 'model_dump'):
                    mcp_schema_dict = mcp_tool.inputSchema.model_dump(
                        exclude_none=True)
                elif isinstance(mcp_tool.inputSchema, dict):
                    mcp_schema_dict = mcp_tool.inputSchema
                else:
                    logger.warning(
                        f"MCP tool '{mcp_tool.name}' has unexpected inputSchema type: {type(mcp_tool.inputSchema)}. Skipping.")
                    continue

                if mcp_schema_dict.get('type', '').lower() != 'object':
                    logger.warning(
                        f"MCP tool '{mcp_tool.name}' has non-OBJECT inputSchema ('{mcp_schema_dict.get('type')}'). Skipping for Gemini.")
                    continue

                gemini_properties = {}
                required_props = mcp_schema_dict.get('required', [])
                valid_properties_found = False

                for prop_name, prop_schema_dict in mcp_schema_dict.get('properties', {}).items():
                    if not isinstance(prop_schema_dict, dict):
                        logger.warning(
                            f"Property '{prop_name}' in tool '{mcp_tool.name}' has non-dict schema. Skipping property.")
                        continue

                    mcp_type = prop_schema_dict.get('type', '').lower()
                    gemini_type_str = type_mapping.get(mcp_type)

                    # *** FIX START ***
                    # If MCP type is 'object' but has no defined sub-properties, treat as STRING for Gemini
                    if mcp_type == 'object' and not prop_schema_dict.get('properties'):
                        logger.warning(f"Property '{prop_name}' in tool '{mcp_tool.name}' is MCP type 'object' with no sub-properties. Mapping to Gemini STRING type.")
                        gemini_type_str = 'STRING' # Override to STRING
                    # *** FIX END ***

                    if gemini_type_str:
                        # For OBJECT types mapped to STRING, adjust description
                        description = prop_schema_dict.get('description', '')
                        if gemini_type_str == 'STRING' and mcp_type == 'object':
                            description += " (Provide as JSON string)"

                        gemini_properties[prop_name] = genai_types.Schema(
                            type=gemini_type_str,
                            description=description.strip() or None # Ensure None if empty
                        )
                        valid_properties_found = True
                    else:
                        logger.warning(
                            f"Property '{prop_name}' in tool '{mcp_tool.name}' has unmappable MCP type '{mcp_type}'. Skipping property.")

                if valid_properties_found or not mcp_schema_dict.get('properties'):
                    gemini_params_schema = genai_types.Schema(
                        type='OBJECT',
                        properties=gemini_properties if gemini_properties else None,
                        required=required_props if required_props and gemini_properties else None
                    )

                    declaration = genai_types.FunctionDeclaration(
                        name=mcp_tool.name,
                        description=mcp_tool.description,
                        parameters=gemini_params_schema,
                    )
                    declarations.append(declaration)
                else:
                    logger.warning(
                        f"Skipping tool '{mcp_tool.name}' for Gemini: No valid properties could be mapped from its OBJECT schema.")

            except Exception as e:
                logger.error(
                    f"Failed to convert MCP tool '{mcp_tool.name}' to Gemini declaration: {e}. Skipping this tool.", exc_info=True)
                continue

        self.cached_gemini_declarations = declarations
        self.gemini_tools_dirty = False
        logger.info(f"Cached {len(declarations)} Gemini tool declarations.")
        return declarations

    async def execute_mcp_tool(self, tool_name: str, args: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        """Executes an MCP tool and returns a tuple: (status_string, result_content_or_none)."""
        if tool_name not in self.tool_to_session:
            logger.error(
                f"Attempted to call unknown or disconnected MCP tool: {tool_name}")
            error_msg = f"Error: Tool '{tool_name}' not found or its server is disconnected."
            return error_msg, None # Return error status and None content

        session = self.tool_to_session[tool_name]
        server_identifier = None
        for identifier, resources in self.server_resources.items():
            if resources['session'] == session:
                server_identifier = identifier
                break

        if not server_identifier:
            logger.error(
                f"Could not find server identifier for tool '{tool_name}' with session {session}. This shouldn't happen.")
            error_msg = f"Error: Internal error finding server for tool '{tool_name}'."
            return error_msg, None # Return error status and None content

        try:
            logger.info(f"Executing MCP tool '{tool_name}' with args: {args}")
            response = await session.call_tool(tool_name, args)
            logger.info(f"MCP tool '{tool_name}' executed successfully.")
            # Check if server recovered after successful call
            if self.server_resources[server_identifier]['status'] == 'error':
                 server_display_name = os.path.basename(server_identifier) if '/' in server_identifier or '\\' in server_identifier else server_identifier
                 logger.info(
                    f"Server '{server_display_name}' recovered, setting status to 'connected'.")
                 self.server_resources[server_identifier]['status'] = 'connected'
            # Assuming response.content is the string result or similar primitive
            result_content = str(response.content) if response.content is not None else ""
            # Return "Success" status and the actual content
            return "Success", result_content
        except Exception as e:
            logger.error(
                f"Error executing MCP tool '{tool_name}' on server '{server_identifier}': {e}", exc_info=True)
            if server_identifier: # Check if identifier exists before setting status
                self.server_resources[server_identifier]['status'] = 'error'
            # Return error status string and None content
            error_msg = f"Error executing tool '{tool_name}': {e}"
            return error_msg, None

    async def process_query(self, query, maintain_context: bool = True) -> str:
        """Process a query using the current AI backend."""
        # Handle both string queries and object queries with images
        if isinstance(query, str):
            query_text = query
            image_data = None
        elif isinstance(query, dict):
            query_text = query.get('text', '')
            image_data = query.get('image')
        else:
            return "Error: Invalid query format"

        logger.info(f"Processing query with {self.ai_backend.get_backend()} backend: '{query_text[:100]}...'")
        if image_data:
            logger.info(f"Query includes image: {image_data.get('name', 'unknown')}")

        # Check if backend is configured
        config_validation = self.ai_backend.validate_configuration()
        if not config_validation["valid"]:
            error_msg = f"Backend not properly configured: {', '.join(config_validation['issues'])}"
            logger.error(error_msg)
            return f"Error: {error_msg}"

        try:
            # For Gemini backend, use the existing implementation with MCP tools
            if self.ai_backend.get_backend() == "gemini":
                return await self._process_query_gemini(query_text, image_data)
            else:
                # For other backends, use LiteLLM
                return await self._process_query_litellm(query_text, image_data, maintain_context)

        except Exception as e:
            logger.error(f"Error processing query with {self.ai_backend.get_backend()}: {e}", exc_info=True)
            return f"An error occurred while processing your request: {e}"

    async def _process_query_litellm(self, query: str, image_data=None, maintain_context: bool = True) -> str:
        """Process query using LiteLLM for non-Gemini backends."""
        try:
            # Convert MCP tools to OpenAI function format if available
            tools = None
            if self.mcp_tools:
                tools = self._convert_mcp_tools_to_openai_format()

            # Create system prompt for MCP context
            system_prompt = None
            if self.mcp_tools:
                tool_descriptions = [f"- {tool.name}: {tool.description or 'No description'}" for tool in self.mcp_tools]
                system_prompt = f"You have access to the following tools:\n" + "\n".join(tool_descriptions)

            # Add conversation history to the message if maintaining context
            full_message = query
            if maintain_context and hasattr(self, '_conversation_history'):
                # Format conversation history for LiteLLM
                history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in self._conversation_history])
                if history_text:
                    full_message = f"Previous conversation:\n{history_text}\n\nCurrent question: {query}"

            # Send request to backend with image support
            response = await self.ai_backend.chat_async(
                message=full_message,
                system_prompt=system_prompt,
                tools=tools,
                image_data=image_data
            )

            # Handle tool calls if present
            if tools and response.startswith('[') and 'function' in response:
                try:
                    tool_calls = json.loads(response)
                    result = await self._handle_tool_calls_litellm(tool_calls, query)
                    # Add to conversation history
                    if maintain_context:
                        if not hasattr(self, '_conversation_history'):
                            self._conversation_history = []
                        self._conversation_history.append({"role": "user", "content": query})
                        self._conversation_history.append({"role": "assistant", "content": result})
                    return result
                except (json.JSONDecodeError, KeyError):
                    # Not a tool call, return as regular response
                    pass

            # Add to conversation history
            if maintain_context:
                if not hasattr(self, '_conversation_history'):
                    self._conversation_history = []
                self._conversation_history.append({"role": "user", "content": query})
                self._conversation_history.append({"role": "assistant", "content": response})

            return response

        except Exception as e:
            logger.error(f"Error in LiteLLM processing: {e}", exc_info=True)
            return f"Error processing request: {e}"

    def _convert_mcp_tools_to_openai_format(self) -> List[Dict[str, Any]]:
        """Convert MCP tools to OpenAI function format."""
        openai_tools = []
        for tool in self.mcp_tools:
            # Extract schema properly from MCP tool object
            input_schema = {}
            if hasattr(tool.inputSchema, 'model_dump'):
                input_schema = tool.inputSchema.model_dump(exclude_none=True)
            elif isinstance(tool.inputSchema, dict):
                input_schema = tool.inputSchema

            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": input_schema
                }
            }
            openai_tools.append(openai_tool)
        return openai_tools

    async def _handle_tool_calls_litellm(self, tool_calls: List[Dict], original_query: str) -> str:
        """Handle tool calls for non-Gemini backends."""
        tool_results = []

        for tool_call in tool_calls:
            function_info = tool_call.get("function", {})
            tool_name = function_info.get("name")
            tool_args_str = function_info.get("arguments", "{}")

            try:
                tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
                logger.info(f"Executing tool: {tool_name} with args: {tool_args}")

                tool_status, tool_content = await self.execute_mcp_tool(tool_name, tool_args)

                if tool_status == "Success":
                    tool_results.append(f"Tool '{tool_name}' executed successfully. Result: {tool_content}")
                else:
                    tool_results.append(f"Tool '{tool_name}' failed: {tool_status}")

            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}")
                tool_results.append(f"Tool '{tool_name}' failed with error: {e}")

        # Create follow-up message with tool results
        if tool_results:
            follow_up_message = f"Original query: {original_query}\n\nTool execution results:\n" + "\n".join(tool_results) + "\n\nPlease provide a summary response based on these results."
            return await self.ai_backend.chat_async(follow_up_message)

        return "Tool calls were requested but no results were generated."

    async def _process_query_gemini(self, query: str, image_data=None) -> str:
        """Legacy Gemini processing method with full MCP integration."""
        logger.info(f"Processing query with Gemini: '{query}'")
        if image_data:
            logger.info(f"Query includes image: {image_data.get('name', 'unknown')}")

        if not self.gemini_client:
            logger.error("process_query called but Gemini client not initialized.")
            return "Error: Gemini client not initialized. Please set your API key via settings."

        # Prepare message parts
        parts = [genai_types.Part(text=query)]

        # Add image if provided
        if image_data:
            try:
                import base64
                image_bytes = base64.b64decode(image_data['data'])
                parts.append(genai_types.Part(
                    inline_data=genai_types.Blob(
                        mime_type=image_data['mimeType'],
                        data=image_bytes
                    )
                ))
                logger.info("Successfully added image to Gemini request")
            except Exception as e:
                logger.error(f"Error processing image for Gemini: {e}")
                return f"Error processing image: {e}"

        # Append user message with text and optional image
        logger.debug("Appending user message to history.")
        self.chat_history.append(genai_types.Content(role="user", parts=parts))

        gemini_function_declarations = self.get_gemini_tool_declarations()
        gemini_tools = [genai_types.Tool(
            function_declarations=gemini_function_declarations)] if gemini_function_declarations else None
        config = genai_types.GenerateContentConfig(
            tools=gemini_tools) if gemini_tools else None

        try:
            # Ensure the currently set model name is used
            current_model = self.ai_backend.get_model()
            logger.debug(f"Generating content with model: {current_model}")
            logger.info(f"Sending request to Gemini model: {current_model}")
            logger.debug(f"Request contents: {self.chat_history}")
            logger.debug(f"Request config: {config}")
            response = await self.gemini_client.models.generate_content(
                model=current_model,
                contents=self.chat_history,
                config=config,
            )

            logger.debug(f"Received Gemini response: {response}")
            if not response.candidates or not response.candidates[0].content:
                logger.warning("Gemini response missing candidates or content.")
                feedback = response.prompt_feedback if hasattr(
                    response, 'prompt_feedback') else None
                if feedback and feedback.block_reason:
                    logger.warning(
                        f"Gemini response blocked: {feedback.block_reason}")
                    if self.chat_history and self.chat_history[-1].role == "user":
                        self.chat_history.pop()
                    return f"Response blocked due to: {feedback.block_reason}. {getattr(feedback, 'block_reason_message', '')}"
                if self.chat_history and self.chat_history[-1].role == "user":
                    self.chat_history.pop()
                return "Error: No response content from Gemini."

            model_content = response.candidates[0].content

            if not model_content.parts:
                logger.warning("Received model content with empty parts.")
                if self.chat_history and self.chat_history[-1].role == "user":
                    self.chat_history.pop()
                return "Received an empty response from the AI."

            self.chat_history.append(model_content)

            function_calls_to_execute = [
                part.function_call for part in model_content.parts if hasattr(part, 'function_call') and part.function_call
            ]

            if function_calls_to_execute:
                logger.info(f"Gemini requested {len(function_calls_to_execute)} tool call(s).")
                tool_response_parts = []
                tool_status_messages = [] # Store status messages for prepending

                for function_call in function_calls_to_execute:
                    tool_name = function_call.name
                    tool_args = dict(function_call.args)
                    logger.info(f"Preparing tool call: {tool_name} with args: {tool_args}")
                    # Add start message
                    tool_status_messages.append(f"TOOL_CALL_START: {tool_name} args={tool_args}")

                    # Execute tool and get both status and content
                    tool_status_str, tool_content = await self.execute_mcp_tool(tool_name, tool_args)
                    logger.info(f"Tool '{tool_name}' execution finished with status: {tool_status_str}")

                    # Add end message using only the status string
                    tool_status_messages.append(f"TOOL_CALL_END: {tool_name} status={tool_status_str}")

                    # Prepare the result for Gemini. Use the actual content on success,
                    # or the error status string on failure.
                    gemini_tool_result_content = tool_content if tool_status_str == "Success" else tool_status_str

                    tool_response_parts.append(genai_types.Part.from_function_response(
                        name=tool_name,
                        response={"result": gemini_tool_result_content}, # Send actual content or error string
                    ))

                if tool_response_parts:
                    logger.debug("Appending tool responses to history.")
                    self.chat_history.append(genai_types.Content(
                        role="tool", parts=tool_response_parts))

                    # Ensure the currently set model name is used after tool call
                    current_model = self.ai_backend.get_model()
                    logger.info(f"Sending tool results back to Gemini model: {current_model}")
                    logger.debug(f"Request contents (with tool results): {self.chat_history}")
                    response = await self.gemini_client.models.generate_content(
                        model=current_model,
                        contents=self.chat_history,
                        config=config,
                    )

                    logger.debug(f"Received Gemini response after tool call: {response}")
                    if not response.candidates or not response.candidates[0].content:
                        logger.warning("Gemini response missing candidates or content after tool call.")
                        feedback = response.prompt_feedback if hasattr(
                            response, 'prompt_feedback') else None
                        if feedback and feedback.block_reason:
                            logger.warning(
                                f"Gemini response blocked after tool call: {feedback.block_reason}")
                            if len(self.chat_history) >= 2 and self.chat_history[-1].role == "tool" and self.chat_history[-2].role == "model":
                                self.chat_history.pop()
                                self.chat_history.pop()
                            return f"Response blocked after tool call: {feedback.block_reason}. {getattr(feedback, 'block_reason_message', '')}"
                        if len(self.chat_history) >= 2 and self.chat_history[-1].role == "tool" and self.chat_history[-2].role == "model":
                            self.chat_history.pop()
                            self.chat_history.pop()
                        return "Error: No response content from Gemini after tool execution."

                    final_model_content = response.candidates[0].content

                    if not final_model_content.parts:
                        logger.warning(
                            "Received final model content with empty parts after tool call.")
                        if len(self.chat_history) >= 2 and self.chat_history[-1].role == "tool" and self.chat_history[-2].role == "model":
                            self.chat_history.pop()
                            self.chat_history.pop()
                        return "Received empty response after tool call (no parts)."

                    self.chat_history.append(final_model_content)
                    if final_model_content.parts and hasattr(final_model_content.parts[0], 'text') and final_model_content.parts[0].text is not None:
                        final_reply_text = final_model_content.parts[0].text
                        logger.info("Received final text response from Gemini after tool call.")
                    else:
                        logger.warning("Final Gemini response after tool call has no text part.")
                        final_reply_text = "Received empty response after tool call (no text part)."

                    # Prepend status messages to the final reply
                    status_prefix = "\n".join(tool_status_messages) + "\n\n" if tool_status_messages else ""
                    return status_prefix + final_reply_text
                else:
                    logger.error(
                        "function_calls_to_execute was present, but tool_response_parts became empty.")
                    return "Error: Tool calls were requested but no responses could be generated."

            elif model_content.parts and hasattr(model_content.parts[0], 'text') and model_content.parts[0].text is not None:
                logger.info("Received standard text response from Gemini (no tool call).")
                return model_content.parts[0].text
            else:
                logger.warning("Received Gemini response with no text part and no tool call.")
                return "Received response with no text."

        except genai_errors.APIError as e:
            logger.error(f"Gemini API error: {e}")
            if self.chat_history and self.chat_history[-1].role == "user":
                self.chat_history.pop()
            return f"Gemini API Error: {e.message}"
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            if self.chat_history and self.chat_history[-1].role == "user":
                self.chat_history.pop()
            return f"An unexpected error occurred: {e}"

    async def cleanup(self):
        logger.info("Cleaning up MCPChatApp resources...")
        if self.status_check_task and not self.status_check_task.done():
            self.status_check_task.cancel()
            try:
                await self.status_check_task
            except asyncio.CancelledError:
                logger.info("Periodic status checker task cancelled.")
            except Exception as e:
                logger.error(
                    f"Error during status checker task cleanup: {e}", exc_info=True)
            self.status_check_task = None
        server_identifiers = list(self.server_resources.keys())
        for identifier in server_identifiers:
            await self.disconnect_mcp_server(identifier)
        logger.info("MCPChatApp cleanup complete.")

    def clear_conversation_history(self):
        """Clear the conversation history."""
        self.chat_history = []  # For Gemini
        if hasattr(self, '_conversation_history'):
            self._conversation_history = []  # For other backends
        logger.info("Conversation history cleared.")

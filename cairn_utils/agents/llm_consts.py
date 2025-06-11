"""
Defines wrappers around Anthropic API to add tool calling and other features.

Currently only supports Anthropic models.
"""

import aiohttp
import os
import datetime
import pathlib
from typing import List, Optional, Dict, Any, Union
import json
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """
    Pydantic model for a single tool call.

    Represents the structure returned by get_tool_calls() method.
    """
    id: str = Field(..., description="Unique identifier for the tool call")
    name: str = Field(..., description="Name of the tool to call")
    input: Dict[str, Any] = Field(..., description="Input parameters for the tool. Fed directly to the tool in toolbox.py or agent_classes.py")
    type: Optional[str] = Field(None, description="Type of the tool call (e.g., 'function')")
    server_executed: Optional[bool] = Field(None, description="Whether the tool was executed server-side")


class ToolResult(BaseModel):
    """
    Pydantic model for a single tool result.

    Represents the structure of individual values in the dict returned by get_tool_results() method.
    """
    content: Union[str, List[Any]] = Field(..., description="The result content")
    type: str = Field(..., description="Type identifier for the result")
    id: Optional[str] = Field(None, description="ID of the tool call this result corresponds to")


class LLMResponseData(BaseModel):
    """
    Pydantic model for the complete LLM response data.

    Combines the outputs of get_tool_calls(), get_tool_results(), and get_text_content() methods.
    """
    tool_calls: List[ToolCall] = Field(default_factory=list, description="List of tool calls from the response")
    tool_results: Dict[str, ToolResult] = Field(default_factory=dict, description="Dictionary mapping tool call IDs to their results")
    text_content: str = Field(default="", description="The raw text content from the response (i.e. the thought, message, or response), excluding tool calls")


class LLMResponse:
    """
    Base class for LLM response handling with standardized interface for LangGraph.

    Just defines standard getter methods for the ToolCalls, ToolResults, and TextContent.
    """

    def __init__(self, content: Union[str, List[Dict[str, Any]]], status_code: int = 200, raw_logging: bool = False):
        """
        Initialize an LLM response. The getter methods are used by LangGraphUtils to parse the response.

        Args:
            content: Raw content from the LLM response
            status_code: HTTP status code of the response
            raw_logging: Whether to log parsed response to a file
        """
        self.content = content
        self.text_content = ""
        self.status_code = status_code
        self.tool_calls: List[ToolCall] = []
        self.tool_results: Dict[str, ToolResult] = {} # maps the id of the tool call to the result.
        self.raw_logging = raw_logging

        # Process content to extract tool calls and results
        self._process_content()

        # Log parsed response if enabled
        if self.raw_logging:
            self._log_parsed_response()

    def _process_content(self):
        """
        Base implementation of content processing. Should be overridden by subclasses.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def _log_parsed_response(self):
        """
        Logs the parsed response to a JSON file if raw_logging is enabled.
        """
        if not self.raw_logging:
            return

        # Create logs directory if it doesn't exist
        log_dir = pathlib.Path("logs/llm_logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamp for the filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        log_file = log_dir / f"{timestamp}_parsed_response.json"

        # Get response data as a dictionary
        response_data = self.get_response_data().dict()

        # Write response data to file
        with open(log_file, "w") as f:
            json.dump(response_data, f, indent=2, default=str)

    def get_tool_calls(self) -> List[ToolCall]:
        """Return list of ToolCall Pydantic models."""
        return self.tool_calls

    def get_tool_results(self) -> Dict[str, ToolResult]:
        """Return dictionary mapping tool call IDs to ToolResult Pydantic models."""
        return self.tool_results

    def get_text_content(self) -> str:
        """Return the text content as a string."""
        return self.text_content

    def get_response_data(self) -> LLMResponseData:
        """Return the complete response data as an LLMResponseData Pydantic model."""
        return LLMResponseData(
            tool_calls=self.get_tool_calls(),
            tool_results=self.get_tool_results(),
            text_content=self.get_text_content()
        )



class AnthropicResponse(LLMResponse):
    """
    Anthropic-specific response wrapper that inherits from LLMResponse.

    Handles the definition of _process_content() in order to extract tool calls, tool results, and text content.
    """

    def __init__(self, content: Union[str, List[Dict[str, Any]]], status_code: int = 200, raw_logging: bool = False):
        """
        Initialize an Anthropic response wrapper.

        Args:
            content: Raw content from the Anthropic API response
            status_code: HTTP status code of the response
            raw_logging: Whether to log the parsed response to a file
        """
        super().__init__(content, status_code, raw_logging)

    def _process_content(self):
        """
        Process content blocks to extract tool calls, results, and text content for Anthropic format.

        Anthropic returns content as a list of blocks with different types:
        - "text": Contains the model's text response
        - "server_tool_use": Contains a tool call executed server-side
        - "web_search_tool_result": Contains results from a web search
        """

        # Handle string-only content directly
        if isinstance(self.content, str):
            self.text_content = self.content
            return

        # Process list of content blocks
        if isinstance(self.content, list):
            text_parts = []
            for block in self.content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        # Extract text content
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "server_tool_use":
                        # Create ToolCall Pydantic model
                        tool_call = ToolCall(
                            id=block.get("id", ""),
                            name=block.get("name", ""),
                            input=block.get("input", {}),
                            type="server_tool_use",
                            server_executed=True
                        )
                        self.tool_calls.append(tool_call)
                    elif block.get("type") == "web_search_tool_result":
                        tool_use_id = block.get("tool_use_id")
                        if tool_use_id:
                            # Create ToolResult Pydantic model
                            tool_result = ToolResult(
                                content=block.get("content", []),
                                type="web_search_tool_result",
                                id=tool_use_id
                            )
                            self.tool_results[tool_use_id] = tool_result

            # Set the concatenated text content
            self.text_content = "".join(text_parts)





class ChatLLM:
    """
    Generic base class with some utility methods for LLM API calls.

    NOTE: see example_aiinvoke_input.json for an example of the input format to ainvoke.

    The format follows Anthropic's Messages API convention with:
    1. System message with plain text content
    2. User messages with either plain text or tool_result content blocks
    3. Assistant messages with text content and optional tool_use blocks
    """


    def __init__(self, model: str, api_key: Optional[str] = None, raw_logging: bool = False):
        """Initialize a chat with an LLM with a model str and an API key."""
        self.model = model
        if not self.model or not isinstance(self.model, str):
            raise ValueError("Invalid model name. Must be a non-empty string.")
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable or api_key parameter must be set")
        self.raw_logging = raw_logging # if this is true, will save local json files under /logs/llm_logs/ that detail the raw API calls.


    def _filter_messages(self, messages: List[Dict[str, Any]]) -> str:
        """
        Extract the system prompt from the rest of the messages.

        Returns: system_prompt, rest_of_messages
        """
        system_prompt = None
        rest_of_messages = []
        for message in messages:
            if message.get("role") == "system":
                system_prompt = message.get("content", "")
            else:
                rest_of_messages.append(message)
        return system_prompt, rest_of_messages

    def _log_api_payload(self, payload: Dict[str, Any]):
        """
        Logs the API payload to a JSON file if raw_logging is enabled.

        Args:
            payload: The API request payload to log
        """
        if not self.raw_logging:
            return

        # Create logs directory if it doesn't exist
        log_dir = pathlib.Path("logs/llm_logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamp for the filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        log_file = log_dir / f"{timestamp}_api_payload.json"

        # Write payload to file
        with open(log_file, "w") as f:
            json.dump(payload, f, indent=2, default=str)


    async def _make_api_request(self, url: str, payload: Dict[str, Any], headers: Dict[str, str]):
        """
        Generic method to make API requests with proper error handling.

        Args:
            url: API endpoint URL
            payload: Request payload
            headers: Request headers

        Returns:
            Response data and status code as a tuple (response_data, status_code)
        """
        # Log the API payload if raw_logging is enabled
        if self.raw_logging:
            self._log_api_payload(payload)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as response:
                    status_code = response.status
                    if response.status != 200:
                        error_text = await response.text()
                        error = Exception(f"API call failed with status {response.status}: {error_text}")
                        error.status_code = status_code  # Attach status code to exception
                        raise error

                    response_data = await response.json()
                    return response_data, status_code
        except aiohttp.ClientError as e:
            # Handle network-related errors
            status_code = getattr(e, 'status', 0)
            if not status_code and hasattr(e, 'message'):
                # Try to extract status code from error message
                import re
                status_match = re.search(r'(\d{3})', str(e.message))
                if status_match:
                    status_code = int(status_match.group(1))

            error = Exception(f"Network error: {str(e)}")
            error.status_code = status_code
            raise error



class OpenAIResponse(LLMResponse):
    """
    OpenAI-specific response wrapper that inherits from LLMResponse.

    Handles the specific format of OpenAI's API responses, including:
    - Processing message content with potential tool_calls
    - Extracting tool calls from the response
    - Converting OpenAI's tool call format to the standardized format

    Properties:
        response_data (Dict[str, Any]): The full OpenAI API response data
    """

    def __init__(self, response_data: Dict[str, Any], status_code: int = 200, raw_logging: bool = False):
        """
        Initialize an OpenAI response wrapper.

        Args:
            response_data: The full OpenAI API response data
            status_code: HTTP status code of the response
            raw_logging: Whether to log the parsed response to a file
        """
        self.response_data = response_data
        # Extract content from the OpenAI response structure
        content = ""
        if "choices" in response_data and len(response_data["choices"]) > 0:
            message = response_data["choices"][0].get("message", {})
            content = message.get("content", "")

        # Initialize the base class with the extracted content
        super().__init__(content, status_code, raw_logging)

    def _process_content(self):
        """
        Process OpenAI response format to extract tool calls and results.

        OpenAI's format differs from Anthropic:
        - Tool calls are in the 'tool_calls' field of the message
        - Each tool call has an 'id', 'function' object with 'name' and 'arguments'
        """
        if "choices" in self.response_data and len(self.response_data["choices"]) > 0:
            message = self.response_data["choices"][0].get("message", {})

            # Extract tool calls from the message
            openai_tool_calls = message.get("tool_calls", [])
            for tool_call in openai_tool_calls:
                if isinstance(tool_call, dict) and "function" in tool_call:
                    # Convert OpenAI's tool call format to our standardized format
                    function_data = tool_call.get("function", {})

                    # Parse arguments from string to dict
                    tool_input = {}
                    try:
                        arguments = function_data.get("arguments", "{}")
                        tool_input = json.loads(arguments)
                    except json.JSONDecodeError:
                        # If JSON parsing fails, use the raw string
                        tool_input = {"raw_arguments": arguments}

                    # Create ToolCall Pydantic model
                    pydantic_tool_call = ToolCall(
                        id=tool_call.get("id", ""),
                        name=function_data.get("name", ""),
                        input=tool_input,
                        type="function",
                        server_executed=False
                    )
                    self.tool_calls.append(pydantic_tool_call)

        # OpenAI doesn't have server-side tool results in the same way as Anthropic
        # This would need to be updated if that changes

    def get_text_content(self) -> str:
        """
        Extract text content from OpenAI response.

        Returns:
            str: The content field from the message in the first choice
        """
        if "choices" in self.response_data and len(self.response_data["choices"]) > 0:
            message = self.response_data["choices"][0].get("message", {})
            return message.get("content", "")
        return ""


class ChatAnthropic(ChatLLM):
    """Direct Anthropic API client with tool calling support."""

    def __init__(self, model: str, api_key: Optional[str] = None, raw_logging: bool = False):
        """
        Initialize an Anthropic API client.

        Args:
            model: The Anthropic model to use
            api_key: Optional API key. If not provided, will try to get it from environment
            raw_logging: Whether to log API calls and responses to files
        """
        # Get API key from environment if not provided
        if not api_key:
            api_key = os.environ.get("ANTHROPIC_API_KEY")

        # Initialize the base class with the model and API key
        super().__init__(model, api_key, raw_logging)

    async def ainvoke(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        server_tools: Optional[Dict[str, Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs,
    ) -> AnthropicResponse:
        """
        Invoke the model with messages and optional tool calling support.

        Args:
            messages: The messages to send to the model (can include system messages)
            tools: List of client-side tools in Anthropic format
            server_tools: Dictionary of server-side tools handled by Anthropic
            tool_choice: Tool choice configuration ("auto", "any", or specific tool)
            **kwargs: Additional kwargs to pass to the model

        Returns:
            AnthropicResponse with the model's response and status code
        """

        system_prompt, filtered_messages = self._filter_messages(messages)

        # Build API payload
        payload = {
            "model": self.model,
            "messages": filtered_messages,
            "system": system_prompt,
            "max_tokens": kwargs.get("max_tokens", 4096),
            **{k: v for k, v in kwargs.items() if k in ["temperature", "top_p", "top_k"]}
        }

        # Combine client-side and server-side tools
        api_tools = []

        if tools:
            api_tools.extend(tools)

        if server_tools:
            # Add server-side tools to the API payload
            for tool_config in server_tools.values():
                # Extract only the fields needed for the API
                api_tool = {
                    "type": tool_config["type"],
                    "name": tool_config["name"]
                }
                if "max_uses" in tool_config:
                    api_tool["max_uses"] = tool_config["max_uses"]
                api_tools.append(api_tool)

        if api_tools:
            payload["tools"] = api_tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

        # Make API call
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        # Make the API request and wrap the response
        response_data, status_code = await self._make_api_request(
            "https://api.anthropic.com/v1/messages",
            payload,
            headers
        )
        return AnthropicResponse(response_data.get("content", []), status_code=status_code, raw_logging=self.raw_logging)


class ChatOpenAI(ChatLLM):
    """OpenAI API client with tool calling support."""

    async def ainvoke(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        server_tools: Optional[Dict[str, Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs,
    ) -> OpenAIResponse:
        """
        Invoke the OpenAI model with messages and optional tool calling support.

        Args:
            messages: The messages to send to the model (can include system messages)
            tools: List of client-side tools in OpenAI format
            server_tools: Dictionary of server-side tools (not directly supported by OpenAI)
            tool_choice: Tool choice configuration ("auto", "any", or specific tool)
            **kwargs: Additional kwargs to pass to the model

        Returns:
            OpenAIResponse with the model's response and status code
        """
        # This is a placeholder implementation
        # When implementing, you should:
        # 1. Convert system messages to OpenAI format (they handle system messages differently)
        # 2. Convert tools to OpenAI's function calling format
        # 3. Make the API request to OpenAI
        # 4. Wrap the response in an OpenAIResponse object

        raise NotImplementedError("OpenAI support is not yet implemented")

        # Example implementation outline (needs to be completed):
        """
        # Extract system message if present
        system_content = None
        filtered_messages = []
        for message in messages:
            if message.get("role") == "system":
                system_content = message.get("content", "")
            else:
                filtered_messages.append(message)

        # If system message exists, add it in OpenAI's format
        if system_content:
            filtered_messages.insert(0, {"role": "system", "content": system_content})

        # Convert tools to OpenAI format if provided
        openai_tools = []
        if tools:
            for tool in tools:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.get("name"),
                        "description": tool.get("description"),
                        "parameters": tool.get("input_schema", {})
                    }
                })

        # Build API payload
        payload = {
            "model": self.model,
            "messages": filtered_messages,
            **{k: v for k, v in kwargs.items() if k in ["temperature", "max_tokens"]}
        }

        if openai_tools:
            payload["tools"] = openai_tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

        # Make API call
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # Make the API request
        response_data, status_code = await self._make_api_request(
            "https://api.openai.com/v1/chat/completions",
            payload,
            headers
        )

        # Return the response wrapped in an OpenAIResponse
        return OpenAIResponse(response_data, status_code=status_code, raw_logging=self.raw_logging)
        """

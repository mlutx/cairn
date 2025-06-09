"""
Defines wrappers around Anthropic API to add tool calling and other features.

Currently only supports Anthropic models.
"""

import aiohttp
import os
from typing import List, Optional, Dict, Any, Union


class AnthropicResponse:
    """Simple response wrapper to match expected interface."""

    def __init__(self, content: Union[str, List[Dict[str, Any]]], status_code: int = 200):
        self.content = content
        self.tool_calls = []
        self.tool_results = {}
        self.status_code = status_code
        self._process_content()

    def _process_content(self):
        """Process content blocks to extract tool calls and results."""
        if isinstance(self.content, list):
            for block in self.content:
                if isinstance(block, dict):
                    if block.get("type") == "server_tool_use":
                        self.tool_calls.append(block)
                    elif block.get("type") == "web_search_tool_result":
                        tool_use_id = block.get("tool_use_id")
                        if tool_use_id:
                            self.tool_results[tool_use_id] = block

    def get_web_search_results(self):
        """Extract web search results from the response."""
        results = []
        for tool_call in self.tool_calls:
            if tool_call.get("name") == "web_search":
                tool_use_id = tool_call.get("id")
                if tool_use_id in self.tool_results:
                    search_result = self.tool_results[tool_use_id]
                    # Extract the search results and format them
                    search_content = search_result.get("content", [])
                    for item in search_content:
                        if item.get("type") == "web_search_result":
                            results.append({
                                "title": item.get("title", ""),
                                "url": item.get("url", ""),
                                "encrypted_content": item.get("encrypted_content", ""),
                                "page_age": item.get("page_age", "")
                            })
        return results


class ChatAnthropic:
    """Direct Anthropic API client with tool calling support."""

    def __init__(self, model: str, api_key: Optional[str] = None):
        """Initialize ChatAnthropic with model and API key."""
        self.model = model or os.getenv("ANTHROPIC_MODEL_NAME", "claude-3-sonnet-20240229")
        if not self.model or not isinstance(self.model, str):
            raise ValueError("Invalid model name. Must be a non-empty string.")
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable or api_key parameter must be set")

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
        # Extract system message and build payload
        system_prompt = None
        filtered_messages = []

        for message in messages:
            if message.get("role") == "system":
                system_prompt = message.get("content", "")
            else:
                filtered_messages.append(message)

        if not system_prompt:
            raise ValueError("No system prompt found in messages. Need a message with role 'system'")

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

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
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
                    return AnthropicResponse(response_data.get("content", []), status_code=status_code)
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

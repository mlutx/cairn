"""
Utility functions and common components for LangGraph-based agents.

This module contains shared functionality used by multiple LangGraph agent implementations
such as ExplorerAgent and ProjectManagerAgent.
"""

import json
import time
import asyncio
import re
import os
import traceback
from typing import Dict, List, Any, Optional, Type
from pydantic import BaseModel
from langgraph.graph import StateGraph, END

from agent_consts import AgentState
from thought_logger import AgentLogger
from llm_consts import LLMResponse, ToolCall


def create_user_message(content: str) -> Dict[str, Any]:
    """Create a user message in the proper format."""
    return {"role": "user", "content": content}


def create_assistant_message(
    content: str, tool_calls: Optional[List[ToolCall]] = None
) -> Dict[str, Any]:
    """Create an assistant message in the proper format with optional tool calls."""
    # For Anthropic's format, tool calls are embedded in the content blocks
    content_blocks = []

    # Add text content if provided (strip whitespace to prevent API errors)
    if content and content.strip():
        content_blocks.append({"type": "text", "text": content.strip()})

    # Add tool use blocks if provided
    if tool_calls:
        for tool_call in tool_calls:
            content_blocks.append(
                {
                    "type": "tool_use",
                    "id": tool_call.id,
                    "name": tool_call.name,
                    "input": tool_call.input,
                }
            )

    return {"role": "assistant", "content": content_blocks}


def create_tool_result_message(
    tool_use_id: str, content: str, is_error: bool = False
) -> Dict[str, Any]:
    """Create a tool result message in the proper format."""
    return {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": content,
                "is_error": is_error,
            }
        ],
    }


def _fetch_dynamic_content(toolbox: Any, method_name: str, content_type: str) -> str:
    """
    Helper function to dynamically fetch content from toolbox.

    Args:
        toolbox: The toolbox instance
        method_name: Name of the method to call on the toolbox
        content_type: Type of content being fetched (for debug messages)

    Returns:
        str: The fetched content or empty string if failed
    """
    if not toolbox or not hasattr(toolbox, method_name):
        return ""

    try:
        content = getattr(toolbox, method_name)()
        # print(
        #     f"\n[DEBUG] Dynamically fetched {content_type}: {content[:100]}..."
        #     if content
        #     else f"\n[DEBUG] No {content_type} available"
        # )
        return content
    except Exception as e:
        # print(f"\n[DEBUG] Failed to fetch {content_type}: {e}")
        return ""


def reformat_messages(state: AgentState, system_prompt: str, logger: AgentLogger = None) -> List[Dict[str, Any]]:
    """
    Reformat the messages to include the new system prompt.
    """
    if not state.messages:
        full_messages = [
            {"role": "system", "content": system_prompt},
            create_user_message(state.user_input),
        ]
        # Log the system message immediately
        if logger:
            logger.log_message(full_messages[0])
            logger.log_message(full_messages[1])

    else:
        full_messages = state.messages.copy()
        # Find and update the system message (should be the first message)
        if full_messages and full_messages[0].get("role") == "system":
            full_messages[0] = {"role": "system", "content": system_prompt}
            # print(
            #     f"\n[DEBUG] Updated existing system message with fresh cairn_settings and cairn_memory"
            # )
        else:
            # If no system message exists, add one at the beginning
            full_messages.insert(0, {"role": "system", "content": system_prompt})
            # print(
            #     f"\n[DEBUG] Added new system message with cairn_settings and cairn_memory"
            # )

    return full_messages.copy()


def truncate_conversation_history(full_messages: List[Dict[str, Any]], max_call_stack: int) -> List[Dict[str, Any]]:
    """
    Truncate conversation history to limit context length, while preserving interaction cycles correctly.

    Args:
        full_messages: Complete list of messages including system prompt
        max_call_stack: Maximum number of recent assistant/user interaction cycles to keep

    Returns:
        List of messages truncated for LLM consumption
    """
    # system and user input are always kept
    if len(full_messages) <= 2:
        return full_messages.copy()

    system_message = full_messages[0]
    user_input_message = full_messages[1]
    conversation_messages = full_messages[2:]  # All messages except system and user input

    # check whether we have an incomplete interaction cycle (shouldn't happen, but just in case)
    if len(conversation_messages) % 2 != 0:
        print(f"\n[DEBUG] Warning: Incomplete interaction cycle detected ({len(conversation_messages)} messages). Continuing with truncation anyway.")
        # Handle incomplete cycle by adjusting the calculation to work with odd numbers
        incomplete_cycle = True
    else:
        incomplete_cycle = False

    # check whether we have enough messages to truncate
    complete_cycles = len(conversation_messages) // 2
    to_truncate = complete_cycles > max_call_stack

    if not to_truncate:
        return full_messages.copy()

    # Calculate how many messages to keep, accounting for incomplete cycles
    if incomplete_cycle:
        # Keep max_call_stack complete cycles plus the incomplete message
        messages_to_keep = (max_call_stack * 2) + 1
    else:
        # Keep max_call_stack complete cycles
        messages_to_keep = max_call_stack * 2

    # Ensure we don't try to keep more messages than we have
    messages_to_keep = min(messages_to_keep, len(conversation_messages))

    non_truncated_messages = conversation_messages[-messages_to_keep:]
    truncated_messages = conversation_messages[:-messages_to_keep]
    truncation_notice = create_user_message(
            f"[System Notice: Truncated {len(truncated_messages)} older messages to preserve context length. "
            f"Kept {len(non_truncated_messages) // 2} recent interaction cycles. Use analysis of recent interactions to gain context about prior work.]"
        )

    return [system_message, user_input_message, truncation_notice] + non_truncated_messages # return the full messages, but with the truncation notice and the non-truncated messages


async def query_llm_get_new_state(
    messages_for_llm: List[Dict[str, Any]],
    serializable_tools: List[Dict[str, Any]],
    llm_client: Any,
    logger: AgentLogger,
    full_messages: List[Dict[str, Any]],
    toolbox: Any = None,
    state: AgentState = None,
    print_raw_llm_response: bool = False,
    max_attempts: int = 20,
    max_backoff: int = 300
) -> tuple[LLMResponse, AgentState]:
    """
    Query the LLM with retry logic and exponential backoff for transient errors.

    Args:
        messages_for_llm: List of messages to send to the LLM
        serializable_tools: List of tools the LLM can use
        llm_client: LLM client instance
        logger: Logger instance
        full_messages: Full conversation history
        toolbox: Toolbox instance
        state: Current agent state
        print_raw_llm_response: Whether to print the raw LLM response
        max_attempts: Maximum number of retry attempts for transient errors
        max_backoff: Maximum backoff time in seconds

    Returns:
        Tuple of (response, new_state)
    """
    # Get server tools if available
    server_tools = None
    if toolbox and hasattr(toolbox, 'get_server_tools'):
        server_tools = toolbox.get_server_tools()

    for attempt in range(max_attempts):
        try:
            if attempt > 0:
                backoff_seconds = min(2 ** (attempt - 1), max_backoff)
                print(f"\n[DEBUG] API retry {attempt + 1}/{max_attempts} - Backing off {backoff_seconds}s")
                await asyncio.sleep(backoff_seconds)

            # Call the LLM with tools - use messages_for_llm (truncated) not full_messages
            response = await llm_client.ainvoke(
                messages_for_llm,
                tools=serializable_tools,
                server_tools=server_tools,
                tool_choice={"type": "auto"}
            )

            # Check response status code
            status_code = getattr(response, 'status_code', 200)

            if print_raw_llm_response:
                print(f"\n[DEBUG] RAW LLM RESPONSE: \n     {response}")

            # Get text content and tool calls using the LLMResponse interface
            assistant_content = response.get_text_content()
            tool_calls = response.get_tool_calls()  # List[ToolCall] pydantic models
            print(f'\n[DEBUG] Tool calls: {tool_calls}')
            server_tool_results = response.get_tool_results()  # Dict[str, ToolResult] pydantic models

            # Log the content blocks for debugging
            content_blocks_debug = []
            for tool_call in tool_calls:
                content_blocks_debug.append({
                    "type": tool_call.type,
                    "id": tool_call.id,
                    "name": tool_call.name
                })

            print(f"\n[DEBUG] Found {len(tool_calls)} tool calls and {len(server_tool_results)} server tool results")
            print(f"[DEBUG] Server tool results keys: {list(server_tool_results.keys())}")
            print(f"[DEBUG] Tool call IDs: {[tc.id for tc in tool_calls]}")

            # Extract clean thought and process repo memory
            analysis_content = extract_tag_info(assistant_content, "analysis")
            repo_memory_content = extract_tag_info(assistant_content, "repo_memory")
            clean_thought = analysis_content if analysis_content else assistant_content
            clean_thought = clean_thought.strip() if clean_thought else ""

            # Update repo memory if agent generated new memory
            if toolbox and hasattr(toolbox, "_update_repo_memory") and repo_memory_content:
                await toolbox._update_repo_memory(repo_memory_content)

            # Create assistant message with proper content blocks
            assistant_message = create_assistant_message(
                assistant_content, tool_calls
            )

            # Log the assistant message immediately
            if logger:
                logger.log_message(assistant_message)

            # Create new state with FULL conversation history preserved
            new_state = AgentState(
                user_input=state.user_input,
                messages=full_messages + [assistant_message],  # Keep full history in state
                tool_calls=[ToolCall(**tc.model_dump()) for tc in tool_calls],  # Convert to dict and back to ensure proper instantiation
                most_recent_thought=clean_thought,
                tool_outputs=state.tool_outputs,  # Keep existing tool outputs
                server_tool_results=server_tool_results,  # Now directly using ToolResult pydantic models
            )

            return response, new_state

        except Exception as e:
            error_str = str(e)
            print(f"\n[DEBUG] API ERROR attempt {attempt + 1}/{max_attempts}: {error_str}")
            print(f'Full traceback: {traceback.format_exc()}')

            # Extract status code if available
            status_code = getattr(e, 'status_code', None)

            # Check for rate limit error (429)
            if status_code == 429:
                with open("debug.log", "a") as f:
                    f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - RATE LIMITED (Status: {status_code}): {error_str}\n")
                print(f"\n[DEBUG] Rate limit detected (Status: {status_code}). Logged to debug.log. Will retry with longer backoff.")

            # Check if we've exhausted all retries
            if attempt == max_attempts - 1:  # Last attempt
                print("\n[DEBUG] EXHAUSTED ALL API RETRIES, RAISING FATAL ERROR")
                raise Exception(
                    f"Failed to get LLM response after {max_attempts} attempts. "
                    f"Last error: {error_str}. Check API key, rate limits, and billing."
                )

            # Check if retryable based on status code
            retryable_status_codes = [429, 503, 502, 500, 529]
            is_retryable_code = status_code in retryable_status_codes if status_code else False

            # If no status code found, fall back to string matching
            if not status_code:
                retryable_indicators = ["overloaded", "529", "503", "rate limit", "429", "overloaded_error"]
                is_retryable_message = any(indicator in error_str.lower() for indicator in retryable_indicators)
                is_retryable = is_retryable_message
            else:
                is_retryable = is_retryable_code

            if is_retryable:
                print(f"\n[DEBUG] Retryable error (Status: {status_code}), will retry (attempt {attempt + 2}/{max_attempts})")
            else:
                print("\n[DEBUG] Non-retryable error, will try once more then fail")
                # For non-retryable errors, try once more then raise
                if attempt > 0:  # If this wasn't the first attempt
                    raise


async def agent_node(
    state: AgentState,
    tools: List[Any],
    prompt: Any,
    llm_client: Any,
    logger: AgentLogger,
    toolbox: Any = None,
    max_call_stack: int = 3,
) -> Dict[str, Any]:
    """
    Agent node that processes state using proper message-based conversation.
    Uses Anthropic's recommended approach with user/assistant messages and tool results.
    """
    # Regenerate system prompt with fresh cairn_settings and cairn_memory
    cairn_settings = _fetch_dynamic_content(toolbox, "_format_cairn_settings_for_injection", "cairn_settings")
    cairn_memory = _fetch_dynamic_content(toolbox, "_format_repo_memory_for_injection", "cairn_memory")
    system_prompt = prompt.format(cairn_settings=cairn_settings, repo_memory=cairn_memory)

    # Prepare messages with truncation
    full_messages = reformat_messages(state, system_prompt, logger)
    messages_for_llm = truncate_conversation_history(full_messages, max_call_stack)

    # print(f"\n[DEBUG] Using {len(messages_for_llm)} messages for LLM (truncated from {len(full_messages)})")

    # Call LLM with integrated retry logic
    serializable_tools = serialize_tools(tools)
    response, new_state = await query_llm_get_new_state(
        messages_for_llm, serializable_tools, llm_client,
        logger, full_messages, toolbox, state
    )

    return new_state


async def tool_execution_node(
    state: AgentState,
    tools_dict: Dict[str, Any],
    logger: AgentLogger,
) -> AgentState:
    """
    Tool execution node that runs all tools and updates state with a single user message containing all tool results.
    """
    if not state.tool_calls:
        print("\n[DEBUG] No tool calls to execute in tool_execution_node")
        return state

    # Execute all tools and collect results
    tool_results = []
    tool_output_entries = []

    for tool_call in state.tool_calls:
        tool_id, tool_name, tool_input = tool_call.id, tool_call.name, tool_call.input
        print(f"\n[DEBUG] Executing tool: {tool_name} (ID: {tool_id})")

        # Execute the tool and get the result
        tool_output, is_error = await _execute_single_tool(tool_call, tools_dict, state)

        # Create tool result content block
        output_str = json.dumps(tool_output, indent=2) if isinstance(tool_output, dict) else str(tool_output)
        tool_result_content = {
            "type": "tool_result",
            "tool_use_id": tool_id,
            "content": output_str
        }
        if is_error:
            tool_result_content["is_error"] = True

        tool_results.append(tool_result_content)

        # Create tool output entry for tracking
        tool_output_entry = {
            "tool_name": tool_name,
            "tool_id": tool_id,
            "tool_input": tool_input,
            "tool_output": tool_output,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_error": is_error,
        }
        tool_output_entries.append(tool_output_entry)

    # Create a single user message with all tool results
    combined_tool_result_msg = {
        "role": "user",
        "content": tool_results
    }

    # Log the combined tool result message
    if logger:
        logger.log_message(combined_tool_result_msg)

    # Return updated state with no remaining tool calls
    return AgentState(
        user_input=state.user_input,
        messages=state.messages + [combined_tool_result_msg],
        tool_calls=[],  # Clear all tool calls since we executed them all
        most_recent_thought=state.most_recent_thought,
        tool_outputs=state.tool_outputs + tool_output_entries,
        server_tool_results=state.server_tool_results,
    )


async def _execute_single_tool(tool_call: ToolCall, tools_dict: Dict[str, Any], state: AgentState) -> tuple[Any, bool]:
    """
    Execute a single tool call and return the output and error status.

    Args:
        tool_call: ToolCall pydantic model containing the tool call information
        tools_dict: Dictionary mapping tool names to tool definitions
        state: Current agent state

    Returns:
        tuple[Any, bool]: (tool_output, is_error) where tool_output is the result and is_error indicates if an error occurred
    """
    if tool_call.server_executed:
        return await _handle_server_tool(tool_call, state)
    return await _handle_client_tool(tool_call, tools_dict)


async def _handle_server_tool(tool_call: ToolCall, state: AgentState) -> tuple[Any, bool]:
    """Handle execution of server-side tools like web_search."""
    tool_id, tool_name = tool_call.id, tool_call.name
    server_tool_results = state.server_tool_results

    if tool_id not in server_tool_results:
        error_msg = f"Server-executed tool {tool_name} (ID: {tool_id}) results not found. Available IDs: {list(server_tool_results.keys())}"
        return error_msg, True

    search_result = server_tool_results[tool_id]
    tool_output = {
        "result": search_result.content,
        "status": "success",
        "server_executed": True,
        "instructions": f"Tool {tool_name} executed by the server."
    }

    return tool_output, False


async def _handle_client_tool(tool_call: ToolCall, tools_dict: Dict[str, Any]) -> tuple[Any, bool]:
    """Handle execution of client-side tools."""
    tool_name = tool_call.name
    tool_definition = tools_dict.get(tool_name)

    if not tool_definition:
        return f"Tool {tool_name} not found", True

    try:
        tool_function = tool_definition.get("function")
        tool_output = await tool_function(tool_call.input)

        if tool_output is None:
            return {"result": "No output returned from tool"}, False

        return tool_output, False

    except Exception as e:
        return f"Error executing tool {tool_name}: {str(e)}", True


def _check_for_task_completion(messages: List[Dict]) -> bool:
    """Check if any recent tool results indicate task completion (end_task=True)."""

    if not messages:
        return False

    # Look at the last few messages for tool results with end_task=True, as set by the generate_output tool
    for message in reversed(messages[-5:]):
        if message.get("role") == "user" and isinstance(message.get("content"), list):
            for content_block in message["content"]:
                if content_block.get("type") == "tool_result":
                    try:
                        result_data = json.loads(content_block.get("content", ""))
                        if isinstance(result_data, dict) and result_data.get("end_task", False):
                            return True
                    except (json.JSONDecodeError, TypeError):
                        continue
    return False


def should_continue(state: AgentState) -> str:
    """
    Router that decides whether to continue to the agent or terminate based on:
    1. Whether there are still more tools to execute in the current sequence
    2. Whether the generate_output tool was used with end_task=True
    """
    # Check if there are more tools to execute
    if state.tool_calls:
        return "tool_executor"

    # Check for task completion signals
    if _check_for_task_completion(state.messages):
        return END

    return "agent"




def create_agent_graph(
    tools: List[Any],
    prompt: Any,  # Changed from PromptTemplate to Any since we're not using LangChain
    llm_client: Any,
    logger: AgentLogger,
    toolbox: Any = None,  # Add toolbox parameter for dynamic cairn_settings
    state_type: Type[BaseModel] = AgentState,
    max_call_stack: int = 3,
) -> StateGraph:
    """
    Create a LangGraph workflow for an agent with common patterns.

    Args:
        tools: List of tools available to the agent (in Anthropic format)
        prompt: Prompt template to use for agent prompting
        llm_client: LLM client to use for agent calls
        logger: Logger to log agent thoughts and actions
        toolbox: Toolbox instance for accessing dynamic settings like cairn_settings
        state_type: The state type to use for the graph (defaults to AgentState)
        max_call_stack: Maximum number of recent assistant/user message pairs to keep in history (defaults to 4)
          -> lower numbers == less context, but cheaper and faster LLM calls.
          -> does not include the original user input or system prompt. Adds a message explaining truncation if truncation is needed.

    Returns:
        StateGraph: The compiled agent graph
    """
    # Create a dictionary of tool names to full tool definitions for easy lookup
    tools_dict = {tool["name"]: tool for tool in tools}

    async def agent_node_wrapper(state: AgentState) -> Dict[str, Any]:
        """Wrapper for the extracted agent_node function."""
        return await agent_node(
            state=state,
            tools=tools,
            prompt=prompt,
            llm_client=llm_client,
            logger=logger,
            toolbox=toolbox,
            max_call_stack=max_call_stack,
        )

    async def tool_execution_node_wrapper(state: AgentState) -> AgentState:
        """Wrapper for the extracted tool_execution_node function."""
        return await tool_execution_node(
            state=state,
            tools_dict=tools_dict,
            logger=logger,
        )

    # Create the graph
    workflow = StateGraph(state_type)

    # Add the nodes
    workflow.add_node("agent", agent_node_wrapper)
    workflow.add_node("tool_executor", tool_execution_node_wrapper)

    # Add the edges (loop between agent and tool_executor, with a conditional edge)
    workflow.add_edge("agent", "tool_executor")
    workflow.add_conditional_edges(
        "tool_executor",
        should_continue,
        {
            "agent": "agent",
            "tool_executor": "tool_executor",
            END: END,
        },
    )
    workflow.set_entry_point("agent")

    # Compile the graph
    return workflow.compile()



def create_run_config(
    run_id: str, recursion_limit: int = 50
) -> Dict[str, Any]:
    """
    Create a standard configuration for LangGraph runs.
    """
    return {
        "configurable": {
            "thread_id": run_id,
        },
        "recursion_limit": recursion_limit,
    }


def print_run_start(description: str, live_logging: bool = False):
    """Print the start of an agent run if logging is enabled."""
    if live_logging:
        print(f"\n{'='*80}")
        print(f"STARTING AGENT RUN: {description}")
        print(f"{'='*80}\n")


def print_run_end(live_logging: bool = False):
    """Print the end of an agent run if logging is enabled."""
    if live_logging:
        print(f"\n{'='*80}")
        print(f"AGENT RUN COMPLETED")
        print(f"{'='*80}\n")



def format_other_agents_info(
    other_agents: list = None, live_logging: bool = False
) -> str:
    """
    Format information about other agents working on the same task into a string for prompt templates.

    Args:
        other_agents: List of agent dictionaries with information about other agents working on the same task.
        -> has keys of run_id, description, and repo (each keyed to a string).


    Returns:
        str: Formatted string with information about other agents, or a message indicating no other agents
    """
    if not other_agents or len(other_agents) == 0:
        return "No other agents are currently working on related tasks."

    if live_logging:
        print(f"\n[DEBUG] Formatting info for {len(other_agents)} other agents")

    formatted_info = "Other agents currently working on related tasks:\n\n"

    for i, agent in enumerate(other_agents, 1):
        run_id = agent.get("run_id", "Unknown")
        description = agent.get("description", "No description available")
        repo = agent.get("repo", "Unknown repository")

        formatted_info += f"{i}. Agent {run_id}\n"
        formatted_info += f"   Repository: {repo}\n"
        formatted_info += f"   Subtask: {description}\n\n"

    formatted_info += "Consider coordinating with these agents to avoid duplicate work and leverage their insights."

    return formatted_info


def extract_tag_info(text: str, tag: str) -> Optional[str]:
    """
    Extract content from specified XML-style tags in text.

    Args:
        text: The text to search in
        tag: The tag name to extract (without angle brackets, e.g. "analysis", "repo_memory")

    Returns:
        The content inside the specified tags, or None if no tags found
    """
    if not text:
        return None

    # Use regex to find the specified tags (case insensitive, multiline)
    pattern = rf"<{tag}>\s*(.*?)\s*</{tag}>"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)

    if match:
        tag_content = match.group(1).strip()
        return tag_content

    return None


def serialize_tools(tools: List[Any]) -> List[Dict[str, Any]]:
    """
    Create a serializable version of tools for LLM API calls.

    Args:
        tools: List of tool objects with name, description, and input_schema

    Returns:
        List of serialized tool dictionaries suitable for API calls (rem fcn obj.)
    """
    copy = [x.copy() for x in tools]
    for x in copy:
        x.pop("function")
    return copy

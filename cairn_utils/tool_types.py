"""
Specifies pydantic models for certain tool inputs and outputs.

May or may not be used by the toolboxes. Used as a reference for the types of inputs and outputs used for the tools, and can be used to generate tool descriptions.
(i.e. to specify input types to the LLM in a very explicit manner, or to feed the output of an LLM to ensure a specific format)
"""

import asyncio
from langchain_core.tools import tool
import time
import json
from typing import Annotated, Optional, Dict, Any, List
from pydantic import BaseModel, Field
import traceback
import sys
import re
from typing import List, Optional, get_origin, get_args
import ast


def parse_model_json_response_robust(response, debug=False):
    """
    Parse JSON-like output from an LLM into a Python dictionary or list, using print statements for debug.

    This function attempts to handle various formatting issues in LLM outputs, including:
    - Inputs already as Python dict or list objects (returned as-is).
    - JSON strings or Python-style literal strings (possibly enclosed in markdown code fences).
    - Mixed JSON/Python formats (e.g., JSON with Python booleans like True/False or None).
    - Escaped or double-encoded JSON strings (JSON text wrapped in quotes and escaped).
    - Malformed JSON issues: unquoted keys, single quotes for strings, trailing commas, etc.
    - Partial or truncated JSON data at the end of the string.
    - Truncated string values at the end of input.

    The function tries multiple strategies in order, and only raises if all attempts fail.

    Args:
        response: The LLM response (dict, list, str, or bytes).
        debug (bool): If True, prints debug information to stdout.

    Returns:
        A Python dict or list parsed from the response.

    Raises:
        ValueError: If unable to parse after all attempts.
    """
    # 1. Already parsed
    if isinstance(response, (dict, list)):
        if debug:
            print("Input is already a dict or list, returning as-is.")
        return response

    # 2. Convert bytes to string or cast to str
    if isinstance(response, bytes):
        try:
            cleaned = response.decode("utf-8", errors="ignore").strip()
            if debug:
                print("Decoded bytes input to string.")
        except Exception as e:
            raise ValueError(f"Failed to decode bytes: {e}")
    else:
        cleaned = str(response).strip()
        if debug:
            print(
                f"Converted input to string: {cleaned[:100]}{'...' if len(cleaned)>100 else ''}"
            )

    # 3. Remove markdown code fences and inline backticks
    if cleaned.startswith("```"):
        if debug:
            print("Removing markdown code fences.")
        lines = cleaned.splitlines()
        # drop opening fence
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        # drop closing fence
        for i, line in enumerate(lines):
            if line.startswith("```"):
                lines = lines[:i]
                break
        cleaned = "\n".join(lines)
    if cleaned.startswith("`") and cleaned.endswith("`"):
        if debug:
            print("Removing inline backticks.")
        cleaned = cleaned.strip("`")

    # 4. Handle double-encoded JSON strings
    if len(cleaned) >= 2 and (cleaned[0] == cleaned[-1] in ['"', "'"]):
        if debug:
            print("Checking for double-encoded JSON string.")
        inner_str = None
        # try JSON decode
        if cleaned.startswith('"'):
            try:
                decoded = json.loads(cleaned)
                if isinstance(decoded, str):
                    inner_str = decoded
                    if debug:
                        print("Decoded JSON string to inner text.")
            except Exception:
                pass
        # fallback to ast.literal_eval
        if inner_str is None:
            try:
                decoded = ast.literal_eval(cleaned)
                if isinstance(decoded, str):
                    inner_str = decoded
                    if debug:
                        print("Literal-eval decoded to inner text.")
            except Exception:
                pass
        if inner_str and inner_str.lstrip().startswith(("{", "[")):
            cleaned = inner_str.strip()
            if debug:
                print("Using extracted inner JSON content.")

    # 5. Extract JSON/blob by brace/bracket matching
    start_idx = None
    start_char = None
    for idx, ch in enumerate(cleaned):
        if ch in ["{", "["]:
            start_idx = idx
            start_char = ch
            break
    if start_idx is None:
        raise ValueError("No JSON object or array found in input.")
    closing_char = "}" if start_char == "{" else "]"
    depth = 0
    closing_idx = None
    for i in range(start_idx, len(cleaned)):
        if cleaned[i] == start_char:
            depth += 1
        elif cleaned[i] == closing_char:
            depth -= 1
            if depth == 0:
                closing_idx = i
                break
    if closing_idx is not None:
        json_content = cleaned[start_idx : closing_idx + 1]
        if debug:
            print(f"Extracted JSON snippet from {start_idx} to {closing_idx}.")
    else:
        json_content = cleaned[start_idx:]
        if debug:
            print("Partial JSON detected; using until end of string.")

    # remove outer quotes if still wrapped
    if json_content and json_content[0] == json_content[-1] in ['"', "'"]:
        if debug:
            print("Stripping outer quotes of JSON content.")
        inner = json_content[1:-1]
        inner = inner.replace('\\"', '"').replace("\\'", "'").replace("\\\\", "\\")
        json_content = inner

    # 6. Try strict JSON
    try:
        result = json.loads(json_content)
        if debug:
            print("Successfully parsed with json.loads.")
        return result
    except Exception as e:
        if debug:
            print(f"json.loads failed: {e}")

    # 7. Fallback to ast.literal_eval after replacing JSON literals
    temp = re.sub(
        r"\b(true|false|null)\b",
        lambda m: {"true": "True", "false": "False", "null": "None"}[m.group(0)],
        json_content,
    )
    try:
        result = ast.literal_eval(temp)
        if debug:
            print(
                "Successfully parsed with ast.literal_eval after literal replacement."
            )
        return result
    except Exception as e:
        if debug:
            print(f"ast.literal_eval failed: {e}")

    # 8. Fix unquoted keys and trailing commas
    fixed = temp
    # quote unquoted keys
    key_pattern = re.compile(r"(?<=[{,])\s*([A-Za-z_]\w*)(?=\s*:)")
    prev = None
    while True:
        keys = key_pattern.findall(fixed)
        if not keys or fixed == prev:
            break
        prev = fixed
        fixed = key_pattern.sub(lambda m: f'"{m.group(1)}"', fixed)
        if debug:
            print(f"Quoted keys: {keys}")
    # remove trailing commas
    if re.search(r",\s*([}\]])", fixed):
        fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
        if debug:
            print("Removed trailing commas.")
    try:
        result = ast.literal_eval(fixed)
        if debug:
            print("Parsed after fixing keys/commas.")
        return result
    except Exception as e:
        if debug:
            print(f"Final ast parsing failed: {e}")

    # 9. Handle truncated string values
    # First, check and fix any unfinished string values at the end of the input
    string_pattern = re.compile(r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')')
    last_pos = 0
    all_strings = []
    for m in string_pattern.finditer(fixed):
        all_strings.append((m.start(), m.end()))
        last_pos = m.end()

    # Check if we have an unclosed quote
    quote_positions = [i for i, c in enumerate(fixed) if c in ['"', "'"]]
    unclosed_quote = None
    for pos in quote_positions:
        # Skip quotes inside already matched strings
        if any(start <= pos < end for start, end in all_strings):
            continue
        # This is potentially an unclosed quote
        unclosed_quote = pos
        break

    if unclosed_quote is not None and unclosed_quote > last_pos:
        if debug:
            print(f"Found unclosed quote at position {unclosed_quote}, closing it.")
        # Close the unclosed quote and any unfinished structures
        quote_char = fixed[unclosed_quote]
        fixed = fixed[:unclosed_quote] + quote_char  # Close the string

    # 10. Salvage partial JSON by balancing braces/brackets
    salvage = fixed.strip()
    last_curly = salvage.rfind("}")
    last_square = salvage.rfind("]")
    last_idx = max(last_curly, last_square)
    if last_idx != -1:
        salvage = salvage[: last_idx + 1]
        if debug:
            print(f"Truncated to last closing bracket at {last_idx}.")
    # balance braces/brackets
    oc, cc = salvage.count("{"), salvage.count("}")
    if cc < oc:
        salvage += "}" * (oc - cc)
        if debug:
            print(f"Appended {oc-cc} missing '}}' to balance.")
    osq, csq = salvage.count("["), salvage.count("]")
    if csq < osq:
        salvage += "]" * (osq - csq)
        if debug:
            print(f"Appended {osq-csq} missing ']' to balance.")

    # Replace truncated string values that have template literals or other Python expressions
    # Look for suspicious string endings that might be truncated
    suspicious_endings = [r"\${[^}]*$", r"\$[a-zA-Z_][a-zA-Z0-9_]*$"]
    for pattern in suspicious_endings:
        salvage = re.sub(pattern, '"', salvage)

    try:
        result = ast.literal_eval(salvage)
        if debug:
            print("Successfully parsed salvage content.")
        return result
    except Exception as e:
        if debug:
            print(f"Salvage parsing failed: {e}")

    # 11. Handle Python-specific constructs that JSON doesn't support
    # Try to make the most complete valid object possible from what we have
    try:
        # Replace any remaining template literals with empty strings
        salvage = re.sub(r"\${[^}]*}", '""', salvage)
        # Replace any remaining $ variables with empty strings
        salvage = re.sub(r"\$[a-zA-Z_][a-zA-Z0-9_]*", '""', salvage)
        # Add quotes around any remaining unquoted values that look like identifiers
        salvage = re.sub(r":\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(,|})", r': "\1"\2', salvage)

        # Try one final parse with a more permissive approach
        result = ast.literal_eval(salvage)
        if debug:
            print("Parsed after handling Python-specific constructs.")
        return result
    except Exception as e:
        if debug:
            print(f"Final parsing attempt failed: {e}")

    raise ValueError("Unable to parse model JSON response")


# 1. Batch Tool Call - used in get_batch_tool_call_tool


class MultiToolCallParams(BaseModel):
    tool_calls: Annotated[
        List[Dict[str, Any]],
        Field(
            ...,
            description="List of tool calls to make",
            json_schema_extra={
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the tool to call",
                        },
                        "args": {
                            "type": "object",
                            "description": "Arguments to pass to the tool",
                        },
                    },
                    "required": ["name", "args"],
                }
            },
        ),
    ]

    model_config = {"json_schema_dialect": "2020-12"}


# 2. View Repository Structure - used in get_view_repository_structure_tool
class ViewRepositoryStructureParams(BaseModel):
    max_depth: str = Field(
        default="5", description="Maximum depth of directories to display"
    )


# Note: Web search is now handled as a server-side tool in DefaultToolBox.SERVER_TOOLS
# No client-side parameters needed since Anthropic handles it server-side


# 5. List Files - used in get_list_files_tool
class ListFilesParams(BaseModel):
    """Parameters for listing files in a repository directory."""

    path: str = Field(
        "",
        description="The directory path to list contents from, relative to the repository root",
    )


# 6. Read File - used in get_read_file_tool
class ReadFileParams(BaseModel):
    """Parameters for reading a file from the repository."""

    path: str = Field(
        ..., description="The file path inside the repository, relative to the root"
    )
    line_start: Optional[int] = Field(
        None, description="First line to read (1-indexed), optional"
    )
    line_end: Optional[int] = Field(
        None, description="Last line to read (1-indexed), optional"
    )
    read_near_content_like: Optional[str] = Field(
        None,
        description="Use fuzzy matching to find content similar to this string and return ~100 lines around the best match. This is often more useful than line numbers when you don't know the exact location but have an idea of what the code looks like.",
    )


# 7. Embedding Search - used in get_embedding_search_tool
class SearchParams(BaseModel):
    """Parameters for searching the codebase semantically."""

    query: str = Field(
        ...,
        description="Natural language search query describing functionality, concept, pattern, or feature",
    )


# 8. Edit Files - used in get_edit_file_tool
class EditFilesParams(BaseModel):
    file_path: str = Field(description="The path to the file to edit or create.")
    unified_diff: Optional[str] = Field(
        default=None,
        description="A unified diff string (representing changes) to apply to the file. REQUIRED: you must replace any open brackets { with the tag <bracket> and any close brackets } with the tag </bracket>. If you use normal brackets, the tool will not be able to apply the diff, and will throw an error. If you are not able to specify an input correctly, you should make sure that you are properly abstracting out brackets.",
    )
    new_content: Optional[str] = Field(
        default=None,
        description="Complete content for the file. Used when creating new files or completely replacing file content.",
    )
    create_file: bool = Field(
        default=False,
        description="if you want to create a new file with blank content, set this to true",
    )
    delete_file: bool = Field(
        default=False,
        description="Whether to delete the file specified by `file_path`.",
    )


# 9. Delegate Task - used in get_delegate_task_tool
class TaskDescription(BaseModel):
    """Parameters for delegating a task to the Software Engineer agent."""

    task: str = Field(
        ..., description="A clear, detailed description of the task to be implemented"
    )


# 10. Switch Repo - used in get_switch_repo_tool
class SwitchRepoParams(BaseModel):
    """Parameters for switching the current repository."""

    repo_name: str = Field(..., description="The name of the repository to switch to")


# 11. Spy On Agent - used in get_spy_on_agent_tool
class SpyOnAgentParams(BaseModel):
    """Parameters for spying on another agent's logs."""

    run_id: Optional[str] = Field(
        None, description="UUID of the agent/subtask to spy on"
    )
    page: int = Field(
        default=1, description="Page number for log pagination, starting from 1. Most recent logs are shown first (page 1)."
    )
    page_size: int = Field(default=3, description="Number of logs per page")


class SearchFilesByNameParams(BaseModel):
    """Parameters for searching files by name using fuzzy matching."""

    query: str = Field(
        ..., description="The filename or partial filename to search for"
    )
    threshold: int = Field(
        default=60,
        description="Fuzzy matching threshold (0-100), higher values require closer matches",
    )
    max_results: int = Field(
        default=5, description="Maximum number of results to return"
    )


class CodeSearchParams(BaseModel):
    """Parameters for searching code content in the repository."""

    query: str = Field(
        ...,
        description="The code snippet, function name, variable name, or text to search for in the repository",
    )
    path: Optional[str] = Field(
        None,
        description="Optional subdirectory path to limit search (e.g. 'src/utils'). If not specified, searches entire repository.",
    )
    page: int = Field(
        default=1, description="Page number for pagination, starting from 1"
    )
    page_size: int = Field(
        default=10, description="Number of matched files to return per page"
    )


# Define Pydantic models for tool outputs
# Explorer Tool Box - get_generate_output_tool
class ExplorerResponse(BaseModel):
    """Response from the Problem Explorer Agent."""

    summary_of_the_problem: str = Field(description="Summary of the problem")
    response_to_the_question: str = Field(
        description="Response to the question (if input was a question), else this should be empt string",
        default=None,
    )
    most_relevant_code_file_paths: List[str] = Field(
        description="Most relevant code file paths"
    )
    list_of_subtasks: List[str] = Field(
        description="List of subtasks. Each subtask is a detailed description of what to do."
    )
    list_of_subtask_titles: List[str] = Field(
        description="List of subtask titles. Each title is a short description of what to do."
    )
    list_of_subtask_repos: List[str] = Field(
        description="List of the repository that each subtask should be done in"
    )
    assessment_of_difficulty: str = Field(
        description="Assessment of whether the problem can be solved easily (high, medium, or low difficulty), if input was a question, this should be 'unknown'"
    )
    assessment_of_subtask_difficulty: List[str] = Field(
        description="Assessment of the difficulty of each subtask, if input was a problem description, this should be an empty list"
    )
    assessment_of_subtask_assignment: List[str] = Field(
        description="Assessment of the assignment of each subtask to 'agent' or 'human' (if input was a problem description), else this should be an empty list"
    )
    recommended_approach: str = Field(
        description="Any additional thoughts on the best approach to solve the problem go here."
    )


# Code Editor Tool Box - get_generate_output_tool
class SWEResponse(BaseModel):
    """Response from the Software Engineer Agent."""

    summary_of_changes: str = Field(description="Summary of the changes made")
    files_modified: List[str] = Field(description="List of files that were modified")
    verification_status: str = Field(
        description="Whether the changes were successfully verified"
    )
    error_messages: Optional[List[str]] = Field(
        description="List of error messages encountered, if any", default=None
    )
    additional_notes: Optional[str] = Field(
        description="Any additional notes about the implementation", default=None
    )
    branch_url: Optional[str] = Field(
        description="URL link to the GitHub branch containing the changes", default=None
    )


# Manager Tool Box - get_generate_output_tool
class PMResponse(BaseModel):
    """Response from the Project Manager Agent."""

    recommendations: Optional[List[str]] = Field(
        description="Recommendations for further improvements or next steps",
        default=None,
    )
    issues_encountered: Optional[List[str]] = Field(
        description="Issues encountered during implementation", default=None
    )
    pull_request_message: str = Field(description="A message for the pull request")


class PMResponseWithPR(BaseModel):
    """Response from the Project Manager Agent with PR URL."""

    recommendations: Optional[List[str]] = Field(
        description="Recommendations for further improvements or next steps",
        default=None,
    )
    issues_encountered: Optional[List[str]] = Field(
        description="Issues encountered during implementation. Include full stack trace if applicable.",
        default=None,
    )
    pull_request_message: str = Field(
        description="A message for the pull request. USE MARKDOWN FORMATTING. Be detailed and specific about what changes were made, how to test them, and what the benefits are. Include emojis when appropriate."
    )
    pr_url: Optional[str] = Field(
        description="URL to the created pull request", default=None
    )


# Edit Suggestions - used in get_edit_suggestions_tool
class EditSuggestionsParams(BaseModel):
    """Parameters for applying edit suggestions to a file using LLM."""

    file_path: str = Field(
        description="The path to the file to edit, relative to the repository root."
    )
    edit: str = Field(
        description="Changes to make to the file, in the format of the actual code with comments explaining new blocks, and comments abstracting out unchanged code."
    )

class EditFilesParams(BaseModel):
    file_path: str = Field(description="The path to the file to edit or create.")
    unified_diff: Optional[str] = Field(
        default=None,
        description="A unified diff string of changes to apply to the file. ",
    )
    create_file: bool = Field(
        default=False,
        description="if you want to create a new file with blank content, set this to true",
    )
    delete_file: bool = Field(
        default=False,
        description="Whether to delete the file specified by `file_path`.",
    )

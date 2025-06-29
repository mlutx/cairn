"""
This defines a generic toolbox with all the tools agents may have access to..

You can inherit from this class and then write a get_all_tools() method that returns a list of all the tools you want to use.
Only the tools that you return from get_all_tools() will be available to the agent.

Take a look at existing examples in agent_classes.py for how to inherit from this class and override the methods you want to change.
"""

import json
import os
import time
import traceback
from typing import Any, Dict, Optional

from agents.llm_consts import ChatAnthropic
from fuzzywuzzy import fuzz
from github_utils import (
    batch_update_files,
    generate_jwt,
    get_all_file_paths,
    get_default_branch_sha,
    get_directory_structure,
    get_installation_token,
    list_files_in_repo,
    read_file_from_repo,
    search_files_by_name,
    search_repo_code,
    create_branch_from_default,
)
from task_storage import TaskStorage

# from supabase_utils import (
#     get_formatted_agent_logs,
#     get_other_agents_from_subtask_id,
#     get_supabase_client,
# )
from tool_related_prompts import (
    EDIT_FILE_SYSTEM_PROMPT,
    EDIT_FILE_USER_MESSAGE,
    REPO_MEMORY_PROMPT_HAS_MEM,
    REPO_MEMORY_PROMPT_NO_MEM,
)
from tool_types import (
    CodeSearchParams,
    EditFilesParams,
    EditSuggestionsParams,
    ListFilesParams,
    MultiToolCallParams,
    ReadFileParams,
    SearchFilesByNameParams,
    SearchParams,
    SpyOnAgentParams,
    SwitchRepoParams,
    TaskDescription,
    ViewRepositoryStructureParams,
    parse_model_json_response_robust,
    EditFilesParams,
    CodeSearchParams,
    EditSuggestionsParams,
)
from tool_related_prompts import (
    EDIT_FILE_SYSTEM_PROMPT,
    EDIT_FILE_USER_MESSAGE,
    REPO_MEMORY_PROMPT_NO_MEM,
    REPO_MEMORY_PROMPT_HAS_MEM,
)
from supported_models import SUPPORTED_MODELS, find_supported_model_given_model_name

class DefaultToolBox:
    """
    A default collection of tools that can be used by agents.
    """

    def __init__(
        self,
        owner: str,
        repos: list[str],
        installation_id: int,
        branch: str = None,
        model_name: str = "claude-3-7-sonnet-latest",
        subtask_id=None,
        other_agents=None,
        running_locally: bool = False,
    ):
        self.owner = owner
        self.repos = repos
        self.has_1_repo = len(repos) == 1
        self.repo = repos[0]  # currently selected repo
        self.installation_id = installation_id

        self.task_storage = TaskStorage()

        self.branch = branch
        self.tools = []

        # Generate fresh tokens
        self.jwt_token = None
        self.installation_token = None
        self.model_name = model_name

        self.agent = None
        self.last_value: Optional[Dict[str, Any]] = None

        self.subtask_id = subtask_id
        self.other_agents = (
            other_agents  # other agents working on different subtasks of the same task
        )

        self.running_locally = running_locally
        self.settings = None
        self._load_cairn_settings()
        self.repo_memory = {}
        self._load_cairn_repo_memory()
        self.branch_created = False

    def _get_cairn_dir(self) -> str:
        """
        Get the path to the .cairn directory, which should be one level up from where toolbox.py is located.
        """
        # Get the directory where toolbox.py is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go one directory up to get to the parent directory
        parent_dir = os.path.dirname(current_dir)
        # Return the path to .cairn in the parent directory
        return os.path.join(parent_dir, ".cairn")

    async def authenticate(self):
        """
        Authenticate with GitHub and ensure the specified branch exists.
        If the branch doesn't exist, creates it based on the default branch.
        """
        # Get the installation token
        self.jwt_token = generate_jwt()
        self.installation_token = await get_installation_token(
            self.jwt_token, self.installation_id
        )

        # Check if a branch is specified and ensure it exists
        if self.branch and not self.branch_created:
            try:
                # Try to list files in the branch to see if it exists
                await list_files_in_repo(
                    self.installation_token,
                    self.owner,
                    self.repo,
                    "",
                    branch=self.branch,
                )
                print(f"Branch '{self.branch}' already exists.")
            except Exception as e:
                if "404" in str(e):  # Branch doesn't exist
                    try:
                        await create_branch_from_default(
                            self.installation_token, self.owner, self.repo, self.branch
                        )
                        self.branch_created = True
                    except Exception as E:
                        print(f'Error creating branch with name: {self.branch} with error code: {E}')
                    print(f"Branch '{self.branch}' created successfully.")
                else:
                    # If it's another error, just log it and continue
                    print(f"Warning: Error checking branch: {str(e)}")

        # Some toolboxes require a branch to be specified
        if hasattr(self, 'requires_branch') and self.requires_branch and not self.branch:
            raise ValueError(f"No branch specified for {self.__class__.__name__}")

    def get_batch_tool_call_tool(self, tool_name_2_function: dict):
        async def batch_tool(params: dict) -> dict:
            try:
                input_model = MultiToolCallParams(**params)
                results = []

                for tool_call in input_model.tool_calls:
                    tool_name = tool_call["name"]
                    args = tool_call["args"]
                    args_parsed = parse_model_json_response_robust(args, debug=False)
                    tool_function = tool_name_2_function[tool_name][0]

                    # Check if the tool function has an ainvoke method, otherwise call it directly
                    if hasattr(tool_function, "ainvoke"):
                        result = await tool_function.ainvoke(args_parsed)
                    else:
                        result = await tool_function(args_parsed)

                    results.append(
                        {"tool_name": tool_name, "tool_args": args, "result": result}
                    )

                return results
            except Exception as e:
                return {
                    "success": False,
                    "error_messages": [str(e)],
                    "traceback": traceback.format_exc(),
                }

        description = """
            Invoke multiple other tool calls simultaneously.

            If you have multiple tools that you want to call, you should use this tool to call them all at once (more efficient).
            """

        function_name = "batch_tool"
        function_schema = MultiToolCallParams.model_json_schema()
        function_schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        function_schema["$id"] = "MultiToolCallParams"

        return batch_tool, function_name, function_schema, description

    def get_view_repository_structure_tool(self):
        async def view_repository_structure(params: dict) -> str:
            params = ViewRepositoryStructureParams(**params)
            max_depth = int(params.max_depth) if params.max_depth else 5
            file_paths = await get_all_file_paths(
                self.installation_token,
                self.owner,
                self.repo,
                max_depth=max_depth,
                branch=self.branch,
            )
            return get_directory_structure(file_paths)

        description = "View the directory structure of the repository."
        function_name = "view_repository_structure"
        function_schema = ViewRepositoryStructureParams.model_json_schema()

        return view_repository_structure, function_name, function_schema, description

    # Configuration for server-side tools (handled by Anthropic)
    SERVER_TOOLS = {
        "web_search": {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5,
            "description": "Search the internet for information and extract relevant content in a single step. Provides comprehensive search results with automatic citations and extracted content from relevant websites.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query in natural language"
                    }
                },
                "required": ["query"]
            }
        }
    }

    def get_server_tools(self):
        """
        Get configuration for server-side tools that are handled by Anthropic.

        Returns:
            dict: Dictionary of server tool configurations
        """
        return self.SERVER_TOOLS.copy()

    def get_list_files_tool(self):
        async def list_files(params: dict) -> list[dict]:
            params = ListFilesParams(**params)

            if self.installation_token is None:
                raise ValueError("Authentication required before using the tool.")

            # Extract the path from the parameters
            dir_path = params.path

            # Remove any quotes from the path that might have been included
            if dir_path:
                dir_path = dir_path.strip().strip("\"'")

            try:
                res = await list_files_in_repo(
                    self.installation_token,
                    self.owner,
                    self.repo,
                    dir_path,
                    sparse=True,
                    branch=self.branch,
                )
                return res
            except Exception as e:
                # Return empty list with error info to avoid breaking the agent
                return [{"name": f"Error: {str(e)}", "path": dir_path, "type": "error"}]

        description = """
            List all files and directories in the GitHub repository at a specified path.

            Args:
                path: The directory path to list contents from, relative to the
                      repository root. Defaults to "" (root directory).

            Returns:
                list[dict]: A list of dictionaries, each representing a file or directory with the following keys:
                    - 'name': The name of the file or directory
                    - 'path': The full path of the file or directory relative to the repo root
                    - 'type': Either 'file' or 'dir' indicating the entry type

            Examples:
                >>> list_files({"path": ""})
                [
                    {'name': 'src', 'path': 'src', 'type': 'dir'}
                ]
            """
        function_name = "list_files"
        function_schema = ListFilesParams.model_json_schema()

        return list_files, function_name, function_schema, description

    def get_read_file_tool(self):
        async def read_file(params: dict) -> str:
            if self.installation_token is None:
                raise ValueError("Authentication required before using the tool.")

            params = ReadFileParams(**params)

            # Extract parameters from the Pydantic model
            path = params.path
            line_start = int(params.line_start) if params.line_start else None
            line_end = int(params.line_end) if params.line_end else None
            read_near_content_like = params.read_near_content_like

            # Remove any quotes from the path that might have been included
            if path:
                path = path.strip().strip("\"'")

            try:
                # If fuzzy matching is requested, read the entire file first
                if read_near_content_like:
                    full_contents = await read_file_from_repo(
                        self.installation_token,
                        self.owner,
                        self.repo,
                        path,
                        branch=self.branch,
                    )

                    # Split into lines for fuzzy matching
                    lines = full_contents.split("\n")

                    # Find the best matching line using fuzzy matching
                    best_score = 0
                    best_line_idx = 0
                    search_text = read_near_content_like.strip()

                    for i, line in enumerate(lines):
                        # Try different fuzzy matching approaches
                        score1 = fuzz.partial_ratio(search_text, line)
                        score2 = fuzz.token_sort_ratio(search_text, line)
                        score3 = fuzz.token_set_ratio(search_text, line)

                        # Use the maximum score across different matching methods
                        score = max(score1, score2, score3)

                        if score > best_score:
                            best_score = score
                            best_line_idx = i

                    # Return ±100 lines around the best match (or less if near file boundaries)
                    context_lines = 100
                    start_idx = max(0, best_line_idx - context_lines)
                    end_idx = min(len(lines), best_line_idx + context_lines + 1)

                    # Create the context window
                    context_lines_list = lines[start_idx:end_idx]

                    # Add line numbers to the output
                    numbered_lines = []
                    for i, line in enumerate(context_lines_list):
                        line_num = start_idx + i + 1  # Convert to 1-indexed
                        numbered_lines.append(f"{line}")

                    result = "\n".join(numbered_lines)

                    # Add metadata about the fuzzy match
                    metadata = "=== FUZZY MATCH RESULT ===\n"
                    metadata += f"Search query: '{search_text}'\n"
                    metadata += f"Best match found at line {best_line_idx + 1} with score {best_score}/100\n"
                    metadata += f"Best matching line: {lines[best_line_idx].strip()}\n"
                    metadata += f"Showing lines {start_idx + 1}-{end_idx} (±{context_lines} lines around match)\n"
                    metadata += "========================\n\n"

                    return metadata + result

                else:
                    # Original behavior for line-based reading
                    contents = await read_file_from_repo(
                        self.installation_token,
                        self.owner,
                        self.repo,
                        path,
                        branch=self.branch,
                        line_start=line_start,
                        line_end=line_end,
                    )
                    return contents

            except Exception as e:
                # Provide a more informative error message
                return f"Error reading file '{path}': {str(e)}"

        description = """
            Read and return the contents of a specific file from the GitHub repository.

            This tool allows direct access to the content of any file in the repository.
            Use it to examine source code, configuration files, documentation, or any other
            textual content in the codebase.

            PREFERRED APPROACH: Use 'read_near_content_like' with a snippet of code or text you're looking for.
            This uses fuzzy matching to find the most relevant section and returns ~100 lines around it.
            This is much more useful than guessing line numbers when you have an idea of what the code looks like.

            Args:
                file_request: Parameters specifying the file to read and search options.
                    - path: The file path inside the repository, relative to the root.
                            For example: 'src/utils.py', 'config/settings.json', 'README.md'.
                    - read_near_content_like: [RECOMMENDED] A code snippet or text to search for using fuzzy matching.
                            The tool will find the best match and return ~100 lines around it.
                            Example: "def process_data" or "class UserModel" or "import pandas"
                    - line_start: First line to read (1-indexed, optional) - use only if you know exact line numbers
                    - line_end: Last line to read (1-indexed, optional) - use only if you know exact line numbers

            Returns:
                str: The requested contents of the file. If fuzzy matching is used, includes metadata
                     about the match quality and line numbers. If line range is specified, only those lines.

            Examples:
                >>> read_file({"path": "src/main.py", "read_near_content_like": "def main"})
                Returns the main function and ~100 lines around it with match metadata

                >>> read_file({"path": "README.md"})
                "# My Project\nThis is the project documentation..."

                >>> read_file({"path": "src/main.py", "line_start": 5, "line_end": 10})
                "5: def main():\n6:     print('Hello world')\n7: \n8: if __name__ == '__main__':\n9:     main()"
            """
        function_name = "read_file"
        function_schema = ReadFileParams.model_json_schema()

        return read_file, function_name, function_schema, description


    def get_search_files_by_name_tool(self):
        async def search_files_by_name_tool(params: dict) -> list[dict]:
            if self.installation_token is None:
                raise ValueError("Authentication required before using the tool.")

            params = SearchFilesByNameParams(**params)

            try:
                results = await search_files_by_name(
                    self.installation_token,
                    self.owner,
                    self.repo,
                    params.query,
                    threshold=params.threshold,
                    max_results=params.max_results,
                    branch=self.branch,
                )
                return results
            except Exception as e:
                return [{"error": f"Error searching files: {str(e)}"}]

        description = """
            Search for files in the repository by filename using fuzzy matching.

            This tool is useful when you know part of a filename but don't know the exact path.
            It uses fuzzy string matching to find files with similar names and returns them
            sorted by relevance score.

            Args:
                query: The filename or partial filename to search for
                threshold: Fuzzy matching threshold (0-100), higher values require closer matches (default: 60)
                max_results: Maximum number of results to return (default: 20)

            Returns:
                list[dict]: A list of matching files with the following structure:
                    - path: Full path to the file in the repository
                    - filename: Just the filename (last part of the path)
                    - score: Fuzzy matching score (0-100, higher is better match)

            Examples:
                >>> search_files_by_name({"query": "utils"})
                [
                    {"path": "src/utils.py", "filename": "utils.py", "score": 85},
                    {"path": "tests/test_utils.py", "filename": "test_utils.py", "score": 75}
                ]

                >>> search_files_by_name({"query": "config", "threshold": 80, "max_results": 5})
                [
                    {"path": "config/settings.py", "filename": "settings.py", "score": 82}
                ]
            """
        function_name = "search_files_by_name"
        function_schema = SearchFilesByNameParams.model_json_schema()

        return search_files_by_name_tool, function_name, function_schema, description

    def get_substring_search_tool(self):
        async def substring_search_tool(params: dict) -> list[dict]:
            if self.installation_token is None:
                raise ValueError("Authentication required before using the tool.")

            params = CodeSearchParams(**params)

            try:
                results = await search_repo_code(
                    self.installation_token,
                    self.owner,
                    self.repo,
                    params.query,
                    path=params.path,
                    page=params.page,
                    page_size=params.page_size,
                )
                return results
            except Exception as e:
                return [{"error": f"Error searching code: {str(e)}"}]

        description = """
            Search for exact substring matches in code content across the repository.

            ⚠️  IMPORTANT: This tool only finds EXACT substring matches in code. For more effective repository exploration, consider these alternatives:
            • Use "embedding_search" for finding semantically relevant files based on natural language queries
            • Use "view_repository_structure" to understand the overall codebase organization
            • Use "search_files_by_name" to find files by filename patterns

            This substring search is best for:
            • Finding where a specific function, variable, or class name is used
            • Locating exact code snippets or error messages
            • Tracking down specific string literals or constants

            Args:
                query: The exact substring, function name, variable name, or text to search for
                path: Optional subdirectory path to limit search (e.g. 'src/utils')
                page: Page number for pagination, starting from 1 (default: 1)
                page_size: Number of matched files to return per page (default: 10)

            Returns:
                Dictionary containing:
                - results: List of files containing the exact search term with file paths and text matches
                - pagination: Information about current page, total pages, etc.

            If you receive too many results, you can paginate or make your query more specific.
            If you receive no matches and you were expecting to find some, the codebase may not be indexed yet.
            """
        function_name = "substring_search"
        function_schema = CodeSearchParams.model_json_schema()

        return substring_search_tool, function_name, function_schema, description

    def get_edit_file_tool(self):
        async def edit_files(params: dict) -> dict:
            # print(f"PRINTING RAW INPUT: {params}")
            if "unified_diff" not in params:
                create_new = (
                    False if "create_file" not in params else params["create_file"]
                )

                if not create_new:
                    return """Error: unified_diff field (str, required) is required if not trying to create a new blank file (in which case you should set create_file to true). \n The unified diff should be a string that represents the changes to apply to the file. \n Here is formatting information: \n unified_diff [REQUIRED]: A unified diff string describing the changes to apply to the file \n Each diff should follow the standard unified diff format with: \n - Hunk headers (@@ -<start_old>,<len_old> +<start_new>,<len_new> @@) \n - Lines prefixed with a space (context), - (deletion), or + (addition) \n"""
                else:
                    # Create a new empty file using new_content instead of unified_diff
                    params["new_content"] = ""

            if "file_path" not in params:
                return "Error: file_path (str, required) is a required field. Make sure you properly specified the file path of the file you want to apply the unified_diff to."

            input_parsed = EditFilesParams(**params)

            # Ensure we have an installation token
            if self.installation_token is None:
                await self.authenticate()

            # Use the current branch if it's set, otherwise use the default branch
            target_branch = self.branch
            if not target_branch:
                # Get the default branch if we don't have a specific branch set
                default_branch, _ = await get_default_branch_sha(
                    self.installation_token, self.owner, self.repo
                )
                target_branch = default_branch

            try:
                # Create the path_to_changes dict
                path_to_changes = {}

                if input_parsed.delete_file:
                    path_to_changes[input_parsed.file_path] = {"delete_file": True}
                elif input_parsed.unified_diff:
                    path_to_changes[input_parsed.file_path] = {
                        "unified_diffs": [input_parsed.unified_diff]
                    }
                elif hasattr(input_parsed, 'new_content') or "new_content" in params:
                    # Handle creating new files with content (including empty content)
                    new_content = getattr(input_parsed, 'new_content', params.get("new_content", ""))
                    path_to_changes[input_parsed.file_path] = {"new_content": new_content}

                # Apply all the file edits in the current branch
                results = await batch_update_files(
                    self.installation_token,
                    self.owner,
                    self.repo,
                    target_branch,
                    path_to_changes,
                )

                # Get the number of files modified and their content
                modified_files_count = results["modified_files_count"]
                modified_files_content = results["modified_files_content"]
                diff_results = results.get("diff_results", {})

                # Extract information about any failed diff applications
                failed_diffs = {}
                for file_path, diff_result in diff_results.items():
                    if diff_result.get("status") is False or diff_result.get(
                        "failed_hunks"
                    ):
                        failed_diffs[file_path] = {
                            "operation": diff_result.get("operation", "unknown"),
                            "failed_hunks": diff_result.get("failed_hunks", []),
                            "error": diff_result.get("error", ""),
                        }

                # Create a response with both the count and the content
                response = {
                    "message": f"Successfully modified {modified_files_count} file(s) in branch '{target_branch}'.",
                    "modified_files_count": modified_files_count,
                    "modified_files_content": modified_files_content,
                }

                # Include diff application results if any diffs failed
                if failed_diffs:
                    response["failed_diffs"] = failed_diffs
                    response[
                        "message"
                    ] += " Some diffs had issues and were applied using fallback methods. See 'failed_diffs' for details."

                return json.dumps(response)
            except Exception as e:
                return f"Error editing files: {str(e)}"

        description = """
            Edit, create, or delete files in the GitHub repository by specifying an explicit unified diff.

            This tool allows you to make changes to the codebase by specifying a target file and a modification to apply. You can:
            - Create new files by specifying a path that doesn't exist yet
            - Modify existing files by applying a unified diff (you can apply multiple diffs to the same file at once)
            - Delete files by setting delete_file to true

            You may use this tool in conjunction with the batch call tool to apply multiple diffs at the same time.

            Args:
                file_path (str) [REQUIRED]: The path to the file to edit or create, relative to the repository root
                unified_diff (str) [REQUIRED]: A unified diff string describing the changes to apply to the file
                              Each diff should follow the standard unified diff format with:
                              - Hunk headers (@@ -<start_old>,<len_old> +<start_new>,<len_new> @@)
                              - Lines prefixed with a space (context), - (deletion), or + (addition)
                delete_file (bool) [OPTIONAL]: Set to true if you want to delete the entire file instead of editing it
                create_file (bool) [OPTIONAL]: Set to true if you want to create a new blank file (you can also do this by setting unified_diff and file_path to a new file path).

            This tool is best used for simple changes that don't require a lot of content.
            """
        function_name = "edit_files"
        function_schema = EditFilesParams.model_json_schema()

        return edit_files, function_name, function_schema, description

    def get_edit_file_descriptively_tool(self):
        async def edit_file_descriptively(params: dict) -> dict:
            if self.installation_token is None:
                raise ValueError("Authentication required before using the tool.")

            params = EditSuggestionsParams(**params)
            file_path = params.file_path.strip().strip("\"'")
            edit_suggestions = params.edit

            try:
                # Read the current file content
                file_exists = True
                try:
                    original_content = await read_file_from_repo(
                        self.installation_token,
                        self.owner,
                        self.repo,
                        file_path,
                        branch=self.branch,
                    )
                except Exception:
                    # If file doesn't exist, start with blank content (creating new file)
                    original_content = ""
                    file_exists = False
                    # print(f"File '{file_path}' doesn't exist, creating new file with blank content")

                # If no edit suggestions provided
                if edit_suggestions is None:
                    # If file exists, return helpful error message
                    if file_exists:
                        return {
                            "success": False,
                            "error": f"The file '{file_path}' already exists. You must provide the 'edit' parameter with your changes. Use the read_file tool first to see the current content.",
                            "file_exists": True,
                            "hint": "Use the read_file tool to see the current content before making changes."
                        }
                    else:
                        # Create a new blank file
                        # Use the current branch if it's set, otherwise use the default branch
                        target_branch = self.branch
                        if not target_branch:
                            default_branch, _ = await get_default_branch_sha(
                                self.installation_token, self.owner, self.repo
                            )
                            target_branch = default_branch

                        # Apply the changes using batch_update_files
                        path_to_changes = {file_path: {"new_content": ""}}

                        results = await batch_update_files(
                            self.installation_token,
                            self.owner,
                            self.repo,
                            target_branch,
                            path_to_changes,
                        )

                        return {
                            "success": True,
                            "message": f"Successfully created new blank file at {file_path}",
                            "modified_files_count": results["modified_files_count"],
                            "modified_files_content": results["modified_files_content"],
                        }

                # find associated LLM client given model name...
                provider, model_info = find_supported_model_given_model_name(self.model_name)
                chat_class = model_info['chat_class']

                llm_client = chat_class(model=self.model_name)

                # Format the user message with the original content and edit suggestions
                user_message = EDIT_FILE_USER_MESSAGE.format(
                    original_content=original_content, edit_suggestions=edit_suggestions
                )

                # Create messages with system message included in the array
                messages = [
                    {"role": "system", "content": EDIT_FILE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ]

                # Make the LLM call
                response = await llm_client.ainvoke(messages, use_predictive_output=True, predictive_content=edit_suggestions)

                # Extract the response content
                if isinstance(response.content, str):
                    response_text = response.content
                else:
                    response_text = str(response.content)

                # Extract the new file content from the <new_file> tags
                import re

                match = re.search(
                    r"<new_file>(.*?)</new_file>", response_text, re.DOTALL
                )
                if not match:
                    return {
                        "success": False,
                        "error": "LLM response did not contain <new_file> tags",
                        "llm_response": response_text,
                    }

                new_content = match.group(1).strip()

                # Fix backslash-escaped quotes that shouldn't be escaped
                # Replace common escape patterns in frontend code: \' → ' and \" → "
                # TODO: investigate if this is a good idea and why this happens in the first place
                new_content = new_content.replace("\\'", "'").replace('\\"', '"')

                # Use the current branch if it's set, otherwise use the default branch
                target_branch = self.branch
                if not target_branch:
                    default_branch, _ = await get_default_branch_sha(
                        self.installation_token, self.owner, self.repo
                    )
                    target_branch = default_branch

                # Apply the changes using batch_update_files
                path_to_changes = {file_path: {"new_content": new_content}}

                results = await batch_update_files(
                    self.installation_token,
                    self.owner,
                    self.repo,
                    target_branch,
                    path_to_changes,
                )

                return {
                    "success": True,
                    "message": f"Successfully applied edit suggestions to {file_path}",
                    "modified_files_count": results["modified_files_count"],
                    "modified_files_content": results["modified_files_content"],
                    "edit_suggestions_applied": edit_suggestions,
                }

            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error applying edit suggestions to '{file_path}': {str(e)}",
                    "traceback": traceback.format_exc(),
                }

        description = """
            Apply edits to a file using natural language suggestions or create a new file.

            - Your edits can be formatted to include code snippets showing exactly what the new code should look like while abstracting out unchanged code
            - Be VERY detailed and specific about what you want to change
            - If you fail to apply the edits, instead of using code blocks, use more natural-language based edit descriptions.
            - Use "// ... existing code ..." (or equivalent comment syntax based on the language) to represent unchanged code
            - Only include the specific code sections that need to be modified or added, and other bits of code as context for where to apply the change
            - You can include multiple code chunks in your suggestions, but make sure to include the context for where to apply the change
            - If the file doesn't exist and you only provide the file_path parameter (no edit), a blank file will be created
            - If you want to create a file with content, provide both 'file_path' and 'edit' parameters

            Args:
                file_path: The path to the file to edit or create, relative to the repository root
                edit: Changes to make to the file in natural language + code blocks.

            Returns:
                dict: Success status, message, and details about the changes made

            This tool is best used for large complex rewrites or creating new files.
            """
        function_name = "edit_file_descriptively"
        function_schema = EditSuggestionsParams.model_json_schema()

        return edit_file_descriptively, function_name, function_schema, description

    def get_delegate_task_tool(self):
        async def delegate_task(params: dict) -> dict:
            params = TaskDescription(**params)
            if not hasattr(self, "swe"):
                raise ValueError("Software Engineer agent not initialized")

            try:
                # Parse the input JSON and extract task description
                task_description = params.task

                # Create a new task ID for the delegated SWE agent
                # Format the task ID to make it visible through spy_on_agent
                parent_id = self.parent_run_id if hasattr(self, 'parent_run_id') and self.parent_run_id else None
                task_id = self.swe.run_id

                # Create payload for the delegated SWE task
                swe_payload = {
                    "run_id": task_id,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "repo": self.repo,
                    "owner": self.owner,
                    "description": task_description,
                    "agent_output": {},
                    "agent_status": "Running",
                    "agent_type": "SWE",
                    "related_run_ids": [],
                    "parent_run_id": parent_id,  # Track parent
                    "raw_logs_dump": {},
                    "branch": self.branch
                }

                # Create the task entry in active_tasks table
                persistent_payload = self.task_storage.create_active_task_persistent(task_id, swe_payload)

                # Update the parent PM task to add this child task
                if parent_id:
                    parent_task = self.task_storage.get_active_task_persistent(parent_id)
                    if parent_task:
                        if "child_run_ids" not in parent_task:
                            parent_task["child_run_ids"] = []
                        if task_id not in parent_task["child_run_ids"]:
                            parent_task["child_run_ids"].append(task_id)
                        parent_task["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

                # Make sure the SWE agent initializes a logger with the same task_id
                # Specifically force the run_id to match the task_id exactly to ensure logs are connected
                response = await self.swe.implement_task(task_description, run_id=task_id)

                # After the SWE task is complete, update the log records to ensure they can be found
                # Create a direct link between the parent task and the SWE logs
                task_storage = TaskStorage()
                swe_logs = task_storage.load_log(task_id, "agent_logger")
                if swe_logs and parent_id:
                    # Ensure the logs are linked to the parent for visibility through spy_on_agent
                    parent_task = task_storage.get_active_task_persistent(parent_id)
                    if parent_task and "related_log_ids" not in parent_task:
                        parent_task["related_log_ids"] = []
                    if parent_task and task_id not in parent_task["related_log_ids"]:
                        parent_task["related_log_ids"].append(task_id)

                # # Update the task status to completed
                persistent_payload["agent_status"] = "Completed"
                persistent_payload["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

                # get the last tool call...
                last_tool_call = response["tool_outputs"][-1]["tool_output"]
                last_tool_call["end_task"] = (
                    False  # avoid ending task when was delegating...
                )

                # Update the agent output in the persistent payload
                persistent_payload["agent_output"] = last_tool_call

                return last_tool_call
            except Exception as e:
                # If we created a task entry, mark it as failed
                if 'persistent_payload' in locals():
                    persistent_payload["agent_status"] = "Failed"
                    persistent_payload["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

                return {
                    "summary_of_changes": f"Error delegating task: {params}",
                    "files_modified": [],
                    "verification_status": False,
                    "error_messages": [str(e)],
                    "additional_notes": "An error occurred when delegating to the Software Engineer agent",
                }

        description = """
            Delegate a specific task to the Software Engineer agent for implementation.

            Input: a string describing the task in detail, relevant file paths, etc.

            Returns:
                dict: The implementation results from the Software Engineer agent, including:
                    - summary_of_changes: Summary of the changes made
                    - files_modified: List of files that were modified
                    - verification_status: Whether the changes were successfully verified
                    - error_messages: List of error messages encountered, if any
                    - additional_notes: Any additional notes about the implementation
            """
        function_name = "delegate_task"
        function_schema = TaskDescription.model_json_schema()

        return delegate_task, function_name, function_schema, description

    def get_switch_repo_tool(self):
        async def switch_repo(params: dict) -> dict:
            params = SwitchRepoParams(**params)
            if self.has_1_repo:
                return {
                    "success": True,
                    "current_repo": self.repo,
                    "error_messages": ["there is only one repository available"],
                    "available_repos": self.repos,
                }

            repo_name = params.repo_name

            if repo_name not in self.repos:
                return {
                    "success": False,
                    "current_repo": self.repo,
                    "error_messages": ["repository not available"],
                    "available_repos": self.repos,
                }

            self.repo = repo_name

            return {
                "success": True,
                "current_repo": self.repo,
                "error_messages": [],
                "available_repos": self.repos,
            }

        description = """
            Switch the current repository to a different one.

            You can call this whenever you want the subsequent actions to be performed on a different repository.

            Args:
                input: A stringified json of the form:
                {
                    "repo_name": "name of the repo to switch to"
                }

            A response will be returned with the following fields:
                - success: Whether the repo switch was successful
                - current_repo: The name of the current repository
                - error_messages: List of error messages encountered, if any
                - available_repos: List of available repositories to switch to
            """
        function_name = "switch_repo"
        function_schema = SwitchRepoParams.model_json_schema()

        return switch_repo, function_name, function_schema, description

    def get_spy_on_agent_tool(self):
        async def spy_on_agent(params: dict) -> dict:
            params = SpyOnAgentParams(**params)
            return await self._spy_on_agent_locally(params)


        description = """
            This tool allows you to see the logs of an agent who may be working on a different subtask for the same overall task.

            This is useful if you want to see what the agent is doing. For example, if you are a making a frontend change that relies on a backend change,
            you might want to see what the agent implementing the backend change is doing.

            If other agents were not specified upon starting a run, calling this will show you new agents that have been created if no input is specified.
            I.e. just call with a dict with no arguments, i.e. {{}}.

            Your response may depend on the status of the other agent. If the other agent has not started yet, then you won't receive any logs, and should make the decisions yourself
            with the assumption that the other agent will view *your* logs and match its format accordingly.

            Input format:
            {
                "agent_id": "UUID of the agent/subtask to spy on",
                "page": 1,  # (Optional) Page number for log pagination, starting from 1
                "page_size": 10  # (Optional) Number of logs per page, default 10
            }

            The response will include pagination information:
            - total_logs: Total number of logs available
            - current_page: Current page number
            - total_pages: Total number of pages available
            - has_next: True if there are more pages after this one
            - has_prev: True if there are previous pages
            """
        function_name = "spy_on_agent"
        function_schema = SpyOnAgentParams.model_json_schema()

        return spy_on_agent, function_name, function_schema, description

    async def _spy_on_agent_locally(self, params: SpyOnAgentParams) -> dict:
        """Spy on a specific agent by reading its logs from the database"""
        run_id = params.run_id

        # Initialize the task storage with the default database path
        task_storage = TaskStorage()

        # If no run_id provided, list all available agents
        if not run_id:
            # Get all active tasks
            all_tasks = task_storage.get_all_active_tasks()

            # Filter for SWE tasks or related tasks
            available_agents = []
            for task_id, task_data in all_tasks.items():
                # Only include tasks that would be relevant
                if task_data.get("agent_type") == "SWE" or "_swe" in task_id:
                    available_agents.append({
                        "run_id": task_id,
                        "description": task_data.get("description", "No description available"),
                        "status": task_data.get("agent_status", "Unknown"),
                        "created_at": task_data.get("created_at", "Unknown")
                    })

            return {
                "success": True,
                "message": "No specific agent ID provided. Here are the available agents:",
                "available_agents": available_agents,
                "available_other_agents": self.other_agents,
            }

        try:
            # Get all logs for the specified run_id
            logs = task_storage.get_all_logs_for_run(run_id)

            # If no logs found directly, check if there are related logs through child or related log IDs
            if not logs:
                # Check if this is a parent task with child_run_ids or related_log_ids
                parent_task = task_storage.get_active_task_persistent(run_id)
                if parent_task:
                    # Check for child run IDs first
                    child_run_ids = parent_task.get("child_run_ids", [])
                    related_log_ids = parent_task.get("related_log_ids", [])

                    # Combine both types of related IDs
                    all_related_ids = child_run_ids + related_log_ids

                    # Get logs from all related IDs
                    for related_id in all_related_ids:
                        related_logs = task_storage.get_all_logs_for_run(related_id)
                        if related_logs:
                            # Add these logs to our collection
                            logs.extend(related_logs)

            if not logs:
                return {
                    "success": False,
                    "error_messages": ["Agent not found. It is possible that the agent has not started yet. You should proceed without it or check in later."],
                    "available_other_agents": self.other_agents,
                }

            # Combine all progress logs from all agent types
            all_progress_logs = []
            for log_entry in logs:
                log_data = log_entry["log_data"]
                progress_logs = log_data.get("progress", [])
                all_progress_logs.extend(progress_logs)

            # Sort logs by created_at if available, otherwise assume they're already in order
            # This is a simplification since we're combining logs from different agent types

            # Apply pagination
            page = params.page or 1
            page_size = params.page_size or 10

            total_logs = len(all_progress_logs)
            total_pages = max(1, (total_logs + page_size - 1) // page_size)

            # Calculate start and end indices from the end (most recent first)
            # Page 1 shows the most recent logs, page 2 shows older logs, etc.
            start_idx = max(0, total_logs - (page * page_size))
            end_idx = total_logs - ((page - 1) * page_size)

            paginated_logs = all_progress_logs[start_idx:end_idx]

            # Format logs for display
            formatted_logs = []
            for log_entry in paginated_logs:
                role = log_entry.get("role", "unknown")
                if role == "unknown" or role == "system":
                    continue
                formatted_logs.append({
                    "role": role,
                    "content": log_entry.get("content", ""),
                })

            return {
                "success": True,
                "logs_by_agent_id": {run_id: formatted_logs},
                "available_other_agents": self.other_agents,
                "pagination": {
                    "total_logs": total_logs,
                    "current_page": page,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1,
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error_messages": [f"Error reading logs from database: {str(e)}"],
                "available_other_agents": self.other_agents,
            }


    def _format_cairn_settings_for_injection(self) -> str:
        """
        Formats the cairn settings for injection into the system prompt.
        """
        if not self.settings:
            return ""  # No settings available, inject blank string

        general_settings = self.settings.get("general_rules", [])
        repo_settings = self.settings.get("repo_specific_rules", {}).get(self.repo, [])

        # formats prompt based on what settings are available or not...
        if general_settings and repo_settings:
            return f"""
            These are some additional rules provided by the user of this system which must be followed: {general_settings}
            Finally, these are some additional rules provided by the user of this system which must be followed for this specific repository ({self.repo}): {repo_settings}
            """
        elif general_settings:
            return f"""
            These are some additional rules provided by the user of this system which must be followed: {general_settings}
            """
        elif repo_settings:
            return f"""
            These are some additional rules provided by the user of this system which must be followed for this specific repository ({self.repo}): {repo_settings}
            """
        else:
            return ""  # no settings available, inject blank string.

    def _load_cairn_settings(self):
        """
        Attempts to load cairn settings from .cairn/
        Sets to the self.settings attribute.
        """

        if not self.running_locally:
            # When not running locally, set settings to None (no custom settings available)
            self.settings = None
            return

        # Use the correct .cairn directory path
        cairn_dir = self._get_cairn_dir()
        settings_file = os.path.join(cairn_dir, "settings.json")

        print(f"settings file: {settings_file}")

        # checks if .cairn/ exists, and if not, creates it
        if not os.path.exists(cairn_dir):
            print("creating .cairn/ directory...")
            os.makedirs(cairn_dir)

        # checks if .cairn/settings.json exists, and if not, creates it
        if not os.path.exists(settings_file):
            print(f"creating {settings_file}...")
            with open(settings_file, "w") as f:
                json.dump(
                    {
                        "general_rules": [],
                        "repo_specific_rules": {self.repo: []},
                    },
                    f,
                    indent=4,
                )

        # loads the settings
        try:
            with open(settings_file, "r") as f:
                settings = json.load(f)

            # Check if current repo exists in repo_specific_rules, add if missing
            if "repo_specific_rules" not in settings:
                settings["repo_specific_rules"] = {}

            if self.repo not in settings["repo_specific_rules"]:
                # print(f'adding new repo "{self.repo}" to cairn settings...')
                settings["repo_specific_rules"][self.repo] = []

                # Write the updated settings back to file
                with open(settings_file, "w") as f:
                    json.dump(settings, f, indent=4)

            self.settings = settings
        except Exception as e:
            print(f"Warning: Failed to load cairn settings: {e}")
            self.settings = None
        return

    async def _update_repo_memory(self, repo_memory: str):
        """
        Updates the repo memory for the current repo.
        """
        if not self.running_locally:
            return

        # update the repo memory stored in self.repo_memory
        self.repo_memory[self.repo] = repo_memory

        # write the updated repo memory to the file
        memory_file = os.path.join(self._get_cairn_dir(), "memory", f"{self.repo}.json")
        with open(memory_file, "w") as f:
            json.dump({"memory": repo_memory}, f, indent=4)

        print(f"[DEBUG] updated repo memory for {self.repo} to: {repo_memory}")

    def _format_repo_memory_for_injection(self) -> str:
        """
        Formats the repo memory for injection into the system prompt.
        """
        if not self.repo_memory:
            return REPO_MEMORY_PROMPT_NO_MEM.format()

        current_repo_memory = self.repo_memory.get(self.repo, "")
        if not current_repo_memory:
            return REPO_MEMORY_PROMPT_NO_MEM.format()

        # If memory content is empty or just whitespace, treat as no memory
        if not current_repo_memory.strip():
            return REPO_MEMORY_PROMPT_NO_MEM.format()

        # Format the memory prompt with the existing memory
        return REPO_MEMORY_PROMPT_HAS_MEM.format(
            current_repo_name=self.repo, current_repo_memory=current_repo_memory
        )

    def _load_cairn_repo_memory(self):
        """
        Loads the cairn repo memory from .cairn/memory/<repo_name>.json
        Sets to the self.repo_memory attribute.
        """

        if not self.running_locally:
            self.repo_memory = None
            return

        # check if directory exists, and if not, creates it
        cairn_dir = self._get_cairn_dir()
        memory_dir = os.path.join(cairn_dir, "memory")
        if not os.path.exists(memory_dir):
            os.makedirs(memory_dir)

        # check if file exists, and if not, creates it
        for repo in self.repos:
            memory_file = os.path.join(memory_dir, f"{repo}.json")
            if not os.path.exists(memory_file):
                with open(memory_file, "w") as f:
                    # write a blank json file with a key of 'memory'
                    json.dump({"memory": ""}, f, indent=4)

        # load the memory for all repos in self.repos
        for repo in self.repos:
            memory_file = os.path.join(memory_dir, f"{repo}.json")
            with open(memory_file, "r") as f:
                self.repo_memory[repo] = json.load(f).get("memory", "")

        return

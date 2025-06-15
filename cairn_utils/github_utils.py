import asyncio
import base64
import difflib
import json
import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import Dict, Optional

import httpx
import jwt
import requests
from dateutil import parser
from diff_match_patch import diff_match_patch
from dotenv import load_dotenv
from fuzzywuzzy import fuzz

"""
NOTE: Understanding Github Auth Flow!
--> This is just a quick note to understand ro

"""

# Get the directory where this file is located
CURRENT_DIR = Path(__file__).resolve().parent
# Path to the parent directory (fastapi_app)
APP_DIR = CURRENT_DIR.parent

# Load environment variables from .env file
load_dotenv(APP_DIR / ".env")

# Get GitHub app credentials from environment variables
APP_ID = os.getenv("GITHUB_APP_ID")
PEM_FILE_PATH = os.getenv("GITHUB_PEM_FILE_NAME")
PRIVATE_KEY_PATH = APP_DIR / PEM_FILE_PATH

print(f"PEM FILE PATH: {PEM_FILE_PATH}")
print(f"PRIVATE KEY PATH: {PRIVATE_KEY_PATH}")


async def list_installations(jwt_token: str):
    """
    List all GitHub App installations using the provided JWT token.

    Example:
        installations = await list_installations("eyJhbGciOiJSUzI1NiJ9...")
    """
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
    }
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://api.github.com/app/installations", headers=headers
        )
        res.raise_for_status()
        return res.json()


def generate_jwt():
    """
    Generate a JWT token for GitHub App authentication using the private key.

    Example:
        jwt_token = generate_jwt()
    """
    with open(PRIVATE_KEY_PATH, "r") as f:
        private_key = f.read()

    payload = {
        "iat": int(time.time()) - 60,
        "exp": int(time.time()) + (10 * 60),
        "iss": APP_ID,
    }

    return jwt.encode(payload, private_key, algorithm="RS256")


async def get_installation_token(jwt_token: str, installation_id: int):
    """
    Get an installation access token for a specific GitHub App installation.

    Example:
        token = await get_installation_token("eyJhbGciOiJSUzI1NiJ9...", 12345678)
    """
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
    }
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers=headers,
        )
        res.raise_for_status()
        return res.json()["token"]


async def read_file_from_repo(
    token: str,
    owner: str,
    repo: str,
    path: str,
    branch: str = None,
    add_line_numbers: bool = True,
    line_start: int = None,
    line_end: int = None,
):
    """
    Read and return the contents of a file from a GitHub repository.

    Args:
        token: GitHub access token
        owner: Repository owner
        repo: Repository name
        path: Path to the file within the repository
        branch: The branch to get the file from (default: None which uses the default branch)
        add_line_numbers: Whether to prefix each line with its line number (1-indexed)
        line_start: First line to read (1-indexed, default: None to start from beginning)
        line_end: Last line to read (1-indexed, default: None to read until the end)

    Example:
        file_content = await read_file_from_repo("ghs_abc123...", "octocat", "hello-world", "README.md", branch="main")
        numbered_content = await read_file_from_repo("ghs_abc123...", "octocat", "hello-world", "README.md", add_line_numbers=True)
        partial_content = await read_file_from_repo("ghs_abc123...", "octocat", "hello-world", "README.md", line_start=10, line_end=20)
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3.raw",
    }

    # Sanitize path: remove whitespace, newlines and other control characters
    if path is not None:
        path = path.strip()
        # Remove any non-printable ASCII characters, quotes, and backslashes
        path = "".join(
            char for char in path if char.isprintable() and char not in ('"', "'", "\\")
        )
    else:
        path = ""

    # URL encode the path properly
    encoded_path = urllib.parse.quote(path, safe="")

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_path}"

    # Add branch parameter if specified
    if branch:
        # Sanitize branch name
        branch = branch.strip()
        branch = "".join(
            char
            for char in branch
            if char.isprintable() and char not in ('"', "'", "\\")
        )
        # URL encode the branch properly
        encoded_branch = urllib.parse.quote(branch, safe="")
        url += f"?ref={encoded_branch}"

    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers)
        res.raise_for_status()
        content = res.text

        # Split content into lines
        lines = content.split("\n")
        total_lines = len(lines)

        # Process line range if specified
        if line_start is not None or line_end is not None:
            # Default values if not specified
            start = max(1, line_start or 1) - 1  # Convert to 0-indexed
            end = min(
                total_lines, line_end or total_lines
            )  # Use total lines if not specified

            # Add context information if partial read
            if start > 0 or end < total_lines:
                result_lines = []

                # Add header if not starting from first line
                if start > 0:
                    result_lines.append(
                        f"[...] {start} lines omitted at the beginning [...]"
                    )

                # Add the selected lines
                result_lines.extend(lines[start:end])

                # Add footer if not ending at last line
                if end < total_lines:
                    result_lines.append(
                        f"[...] {total_lines - end} lines omitted at the end [...]"
                    )

                lines = result_lines

        # Add line numbers if requested
        if add_line_numbers:
            # If we're showing a range and not the whole file, show actual line numbers
            if line_start is not None or line_end is not None:
                start = max(1, line_start or 1)
                numbered_lines = []
                for i, line in enumerate(lines):
                    # Skip header/footer placeholder lines
                    if "[...] lines omitted" in line:
                        numbered_lines.append(line)
                    else:
                        # Width based on the highest line number we'll display
                        width = len(str(end))
                        numbered_lines.append(f"{start + i:{width}d}: {line}")
                lines = numbered_lines
            else:
                # Normal line numbering for full file
                width = len(str(len(lines)))
                lines = [f"{i + 1:{width}d}: {line}" for i, line in enumerate(lines)]

        content = "\n".join(lines)
        return content


async def list_repos_for_installation(token: str):
    """
    List all repositories accessible to the GitHub App installation.

    Example:
        repos = await list_repos_for_installation("ghs_abc123...")
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://api.github.com/installation/repositories", headers=headers
        )
        res.raise_for_status()
        return res.json()["repositories"]


async def list_files_in_repo(
    token: str,
    owner: str,
    repo: str,
    path: str = "",
    sparse: bool = True,
    branch: str = None,
):
    """
    List files in a given GitHub repo path (default: root).

    Sparse mode:
        only returns the file name, path, type.

    Args:
        token: GitHub access token
        owner: Repository owner
        repo: Repository name
        path: Path within the repository (default: root directory)
        sparse: Whether to return only essential file info (default: True)
        branch: The branch to get files from (default: None which uses the default branch)

    Example:
        files = await list_files_in_repo("ghs_abc123...", "octocat", "hello-world", "src", branch="main")
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }

    # Sanitize path: remove whitespace, newlines and other control characters
    if path is not None:
        path = path.strip()
        # Remove any non-printable ASCII characters, quotes, and backslashes
        path = "".join(
            char for char in path if char.isprintable() and char not in ('"', "'", "\\")
        )
    else:
        path = ""

    # URL encode the path properly
    encoded_path = urllib.parse.quote(path, safe="")

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_path}"

    # Add branch parameter if specified
    if branch:
        # Sanitize branch name
        branch = branch.strip()
        branch = "".join(
            char
            for char in branch
            if char.isprintable() and char not in ('"', "'", "\\")
        )
        # URL encode the branch properly
        encoded_branch = urllib.parse.quote(branch, safe="")
        url += f"?ref={encoded_branch}"

    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers)
        res.raise_for_status()

        if sparse:
            return [
                {"name": item["name"], "path": item["path"], "type": item["type"]}
                for item in res.json()
            ]
        else:
            return res.json()


async def get_default_branch_sha(token, owner, repo):
    """
    Get the default branch name and its latest commit SHA for a repository.

    Example:
        branch, sha = await get_default_branch_sha("ghs_abc123...", "octocat", "hello-world")
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    async with httpx.AsyncClient() as client:
        repo_info = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}", headers=headers
        )
        repo_info.raise_for_status()
        default_branch = repo_info.json()["default_branch"]

        branch_info = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/branches/{default_branch}",
            headers=headers,
        )
        branch_info.raise_for_status()
        sha = branch_info.json()["commit"]["sha"]
        return default_branch, sha


async def create_branch(token, owner, repo, new_branch_name, base_sha):
    """
    Create a new branch in a GitHub repository based on a specific commit SHA.

    Example:
        result = await create_branch("ghs_abc123...", "octocat", "hello-world", "feature-branch", "a1b2c3d4...")
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    data = {"ref": f"refs/heads/{new_branch_name}", "sha": base_sha}
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"https://api.github.com/repos/{owner}/{repo}/git/refs",
            headers=headers,
            json=data,
        )
        res.raise_for_status()
        return res.json()


async def update_file(token, owner, repo, branch, path, new_content, file_sha):
    """
    Update a file in a GitHub repository with new content.

    Example:
        result = await update_file(
            "ghs_abc123...",
            "octocat",
            "hello-world",
            "main",
            "README.md",
            "# Updated content",
            "a1b2c3d4..."
        )
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }

    # Sanitize path
    if path is not None:
        path = path.strip()
        # Remove any non-printable ASCII characters, quotes, and backslashes
        path = "".join(
            char for char in path if char.isprintable() and char not in ('"', "'", "\\")
        )
    else:
        path = ""

    # URL encode the path properly
    encoded_path = urllib.parse.quote(path, safe="")

    content_encoded = base64.b64encode(new_content.encode()).decode()

    data = {
        "message": "Update file via GitHub App",
        "content": content_encoded,
        "sha": file_sha,
        "branch": branch,
    }

    async with httpx.AsyncClient() as client:
        res = await client.put(
            f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_path}",
            headers=headers,
            json=data,
        )
        res.raise_for_status()
        return res.json()


async def create_pull_request(token, owner, repo, head, base, title, body):
    """
    Create a pull request in a GitHub repository.

    Example:
        pr = await create_pull_request(
            "ghs_abc123...",
            "octocat",
            "hello-world",
            "feature-branch",
            "main",
            "Add new feature",
            "This PR adds the new feature we discussed."
        )
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }

    data = {"title": title, "body": body, "head": head, "base": base}

    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            headers=headers,
            json=data,
        )
        res.raise_for_status()
        return res.json()


async def get_file_metadata(token: str, owner: str, repo: str, path: str, branch: str):
    """
    Get file SHA and base64 content for a specific branch.

    Returns:
        dict with keys: 'sha', 'content' (base64 encoded)
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }

    # Sanitize path and branch
    if path is not None:
        path = path.strip()
        # Remove any non-printable ASCII characters, quotes, and backslashes
        path = "".join(
            char for char in path if char.isprintable() and char not in ('"', "'", "\\")
        )
    else:
        path = ""

    # URL encode the path and branch properly
    encoded_path = urllib.parse.quote(path, safe="")
    encoded_branch = urllib.parse.quote(branch, safe="")

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_path}?ref={encoded_branch}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers)
        res.raise_for_status()
        return res.json()


async def run_flow(change):
    jwt_token = generate_jwt()
    installation_id = 65848345
    token = await get_installation_token(jwt_token, installation_id)

    # Get first repo from installation
    repos = await list_repos_for_installation(token)
    repo = repos[0]
    owner = repo["owner"]["login"]
    repo_name = "test"
    file_path = "README.md"

    # Get default branch and SHA
    default_branch, base_sha = await get_default_branch_sha(token, owner, repo_name)

    # Create a new branch
    new_branch = "automated-change-branch23-" + change
    await create_branch(token, owner, repo_name, new_branch, base_sha)

    # Get file metadata (content + SHA)
    file_meta = await get_file_metadata(token, owner, repo_name, file_path, new_branch)
    current_sha = file_meta["sha"]
    decoded_content = base64.b64decode(file_meta["content"]).decode()

    # Edit content
    updated_content = (
        decoded_content
        + "\n\nThis line was added by the GitHub App! Nae nae on that beat real quickkkk."
        + change
    )

    # Commit file update
    await update_file(
        token, owner, repo_name, new_branch, file_path, updated_content, current_sha
    )

    # Open pull request
    pr = await create_pull_request(
        token,
        owner,
        repo_name,
        head=new_branch,
        base=default_branch,
        title="Programmatic Edit: Add note",
        body="Added a line via GitHub App automation.",
    )

    print(f"✅ Pull Request created: {pr['html_url']}")


async def get_all_file_paths(
    token: str,
    owner: str,
    repo: str,
    path: str = "",
    max_depth: int = None,
    branch: str = None,
    _current_depth: int = 0,
):
    """
    Recursively get all file paths in a GitHub repository.

    Args:
        token: GitHub access token
        owner: Repository owner
        repo: Repository name
        path: Current path to explore (default: root)
        max_depth: Maximum directory depth to explore (default: None for unlimited)
        branch: The branch to get files from (default: None which uses the default branch)
        _current_depth: Internal parameter to track current recursion depth

    Returns:
        List of file paths in the repository

    Example:
        files = await get_all_file_paths("ghs_abc123...", "octocat", "hello-world", max_depth=2, branch="main")
    """
    all_files = []
    items = await list_files_in_repo(token, owner, repo, path, branch=branch)

    for item in items:
        if item["type"] == "file":
            all_files.append(item["path"])
        elif item["type"] == "dir":
            # Check if we've reached max depth before recursing
            if max_depth is None or _current_depth < max_depth:
                # Recursively get files in subdirectory with incremented depth
                subdir_files = await get_all_file_paths(
                    token,
                    owner,
                    repo,
                    item["path"],
                    max_depth=max_depth,
                    branch=branch,
                    _current_depth=_current_depth + 1,
                )
                all_files.extend(subdir_files)

    return all_files


def get_directory_structure(paths: list[str], include_full_paths: bool = True) -> str:
    """
    Given a list of file paths, return a string that represents the directory structure of the files.

    For example, if the paths are: ['src/utils.py', 'src/main.py', 'src/config.py', 'test.txt']
    The output will be:
    src/
    ├── utils.py
    └── main.py
    └── config.py
    test.txt

    If include_full_paths is True, the full path will be shown in parentheses after each file name.
    """
    if not paths:
        return ""

    # Build tree structure
    tree = {}
    path_mapping = {}  # Store the mapping between file names and their full paths

    for path in paths:
        parts = path.split("/")
        current = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:  # Last part (file)
                if "_files" not in current:
                    current["_files"] = []
                current["_files"].append(part)
                # Store the full path for this file
                path_key = "/".join(parts[:i]) + "/" + part if i > 0 else part
                path_mapping[path_key] = path
            else:  # Directory
                if part not in current:
                    current[part] = {}
                current = current[part]

    # Generate string representation
    result = []

    def print_tree(node, prefix="", is_root=True, path_prefix=""):
        # Print directories
        dirs = sorted([k for k in node.keys() if k != "_files"])
        files = sorted(node.get("_files", []))

        for i, dir_name in enumerate(dirs):
            is_last_dir = i == len(dirs) - 1 and not files
            result.append(f"{prefix}{'└── ' if is_last_dir else '├── '}{dir_name}/")
            new_prefix = f"{prefix}{'    ' if is_last_dir else '│   '}"
            new_path_prefix = (
                f"{path_prefix}{dir_name}/" if path_prefix else f"{dir_name}/"
            )
            print_tree(node[dir_name], new_prefix, False, new_path_prefix)

        # Print files
        for i, file_name in enumerate(files):
            is_last = i == len(files) - 1
            file_path = f"{path_prefix}{file_name}" if path_prefix else file_name

            # Add full path in parentheses if requested
            if include_full_paths and file_path in path_mapping:
                result.append(
                    f"{prefix}{'└── ' if is_last else '├── '}{file_name} (path: {path_mapping[file_path]})"
                )
            else:
                result.append(f"{prefix}{'└── ' if is_last else '├── '}{file_name}")

    # Handle root level files first
    root_files = []
    root_dirs = {}

    for k, v in tree.items():
        if k == "_files":
            root_files = sorted(v)
        else:
            root_dirs[k] = v

    # Print the structure for root directories
    for i, dir_name in enumerate(sorted(root_dirs.keys())):
        is_last_dir = i == len(root_dirs) - 1 and not root_files
        result.append(f"{'└── ' if is_last_dir else '├── '}{dir_name}/")
        new_prefix = f"{'    ' if is_last_dir else '│   '}"
        print_tree(root_dirs[dir_name], new_prefix, False, f"{dir_name}/")

    # Print root level files
    for i, file_name in enumerate(root_files):
        is_last = i == len(root_files) - 1
        # Add full path in parentheses if requested
        if include_full_paths and file_name in path_mapping:
            result.append(
                f"{'└── ' if is_last else '├── '}{file_name} (path: {path_mapping[file_name]})"
            )
        else:
            result.append(f"{'└── ' if is_last else '├── '}{file_name}")

    return "\n".join(result)


async def get_gitignore_patterns(token: str, owner: str, repo: str):
    """
    Extract patterns from the root .gitignore file in a repository.
    Only checks for a .gitignore file in the root directory.

    Args:
        token: GitHub access token
        owner: Repository owner
        repo: Repository name

    Returns:
        List of strings containing gitignore patterns (comments removed),
        or an empty list if no root .gitignore exists

    Example:
        patterns = await get_gitignore_patterns("ghs_abc123...", "octocat", "hello-world")
    """
    all_patterns = []

    # Try to get the root .gitignore file
    try:
        root_content = await read_file_from_repo(token, owner, repo, ".gitignore")

        # Process root .gitignore content line by line
        for line in root_content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            all_patterns.append(line)

    except httpx.HTTPStatusError as e:
        # Root .gitignore not found, return empty list
        if e.response.status_code == 404:
            return []
        else:
            raise  # Re-raise if it's not a 404 error

    return all_patterns


async def apply_file_edits(current_content: str, edits: list) -> str:
    """
    Apply a list of edit operations to file content.

    Args:
        current_content: The current content of the file as a string
        edits: A list of edit operations, each containing:
            - type: "replacement", "insertion", or "deletion"
            - start_line/line_number: The line where the edit begins (1-indexed)
            - end_line: The line where the edit ends for replacements and deletions (1-indexed)
            - content: The new content for replacements and insertions

    Returns:
        The modified content as a string
    """
    lines = current_content.splitlines()

    # Sort edits in reverse order of line number so we can apply them without
    # affecting the line numbers of other edits
    sorted_edits = sorted(
        edits, key=lambda e: e.get("start_line", e.get("line_number", 0)), reverse=True
    )

    for edit in sorted_edits:
        edit_type = edit.get("type")

        if edit_type == "replacement":
            start_line = edit.get("start_line", 1) - 1  # Convert to 0-indexed
            end_line = edit.get("end_line", start_line + 1) - 1  # Convert to 0-indexed
            new_content = edit.get("content", "").splitlines()

            # Ensure start and end are within bounds
            start_line = max(0, min(start_line, len(lines)))
            end_line = max(start_line, min(end_line, len(lines) - 1))

            # Replace the lines
            lines[start_line : end_line + 1] = new_content

        elif edit_type == "insertion":
            line_number = edit.get("line_number", 1) - 1  # Convert to 0-indexed
            new_content = edit.get("content", "").splitlines()

            # Ensure line number is within bounds or at the end
            line_number = max(0, min(line_number, len(lines)))

            # Insert the new content
            lines[line_number:line_number] = new_content

        elif edit_type == "deletion":
            start_line = edit.get("start_line", 1) - 1  # Convert to 0-indexed
            end_line = edit.get("end_line", start_line + 1) - 1  # Convert to 0-indexed

            # Ensure start and end are within bounds
            start_line = max(0, min(start_line, len(lines)))
            end_line = max(start_line, min(end_line, len(lines) - 1))

            # Delete the lines
            del lines[start_line : end_line + 1]

    # Rejoin the lines with the original line ending
    return "\n".join(lines)


async def check_file_exists(
    token: str, owner: str, repo: str, path: str, branch: str
) -> bool:
    """
    Check if a file exists in the repository.

    Args:
        token: GitHub access token
        owner: Repository owner
        repo: Repository name
        path: Path to the file
        branch: Branch to check

    Returns:
        True if the file exists, False otherwise
    """
    try:
        await get_file_metadata(token, owner, repo, path, branch)
        return True
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return False
        raise


async def create_file(
    token: str, owner: str, repo: str, branch: str, path: str, content: str
) -> dict:
    """
    Create a new file in the repository.

    Args:
        token: GitHub access token
        owner: Repository owner
        repo: Repository name
        branch: Branch to create the file in
        path: Path to the new file
        content: Content of the new file

    Returns:
        Response from the GitHub API
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }

    # Sanitize path
    if path is not None:
        path = path.strip()
        path = "".join(
            char for char in path if char.isprintable() and char not in ('"', "'", "\\")
        )
    else:
        path = ""

    # URL encode the path
    encoded_path = urllib.parse.quote(path, safe="")

    # Encode content as base64
    content_encoded = base64.b64encode(content.encode()).decode()

    data = {
        "message": "Create file via GitHub App",
        "content": content_encoded,
        "branch": branch,
    }

    async with httpx.AsyncClient() as client:
        res = await client.put(
            f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_path}",
            headers=headers,
            json=data,
        )
        res.raise_for_status()
        return res.json()


async def batch_update_files(
    token: str, owner: str, repo: str, branch: str, path_to_changes: dict
) -> dict:
    """
    Update multiple files in a GitHub repository with various types of edits in a single operation.

    This is the core function for applying file modifications, supporting unified diffs, full content
    replacement, structured edits, file creation, and file deletion. It handles both existing and
    new files intelligently.

    Args:
        token (str): GitHub installation token with write access to the repository
        owner (str): Repository owner/organization name (e.g., "octocat")
        repo (str): Repository name (e.g., "hello-world")
        branch (str): Target branch name where changes will be applied (e.g., "main", "feature-branch")
        path_to_changes (dict): Dictionary mapping file paths to their change specifications.
            Each key is a file path (relative to repo root), and each value is a dict specifying
            the type of change to apply. Supported change types:

            1. **Full Content Replacement/Creation:**
            ```python
            {
                "path/to/file.py": {
                    "new_content": "Complete file content as a string"
                }
            }
            ```
            - Creates file if it doesn't exist, or replaces entire content if it does
            - Use for new files or complete rewrites
            - Automatically decodes escape sequences (\\n → newline, \\t → tab, etc.)
            - This allows LLMs to specify newlines and special characters using escape sequences

            2. **Unified Diffs (Recommended for most edits):**
            ```python
            {
                "path/to/file.py": {
                    "unified_diffs": [
                        "@@ -5,3 +5,4 @@\n def example():\n     x = 1\n-    y = 2\n+    y = 3\n+    z = 4\n     return x + y",
                        "@@ -20,1 +21,1 @@\n-    return None\n+    return True"
                    ]
                }
            }
            ```
            - Applies standard unified diff format (same as `git diff`)
            - Can apply multiple diffs to the same file in sequence
            - Supports fuzzy matching for robustness
            - Creates file if it doesn't exist (for new file diffs)
            - Can delete entire file if diff results in empty content

            3. **Structured Edits (Line-based operations):**
            ```python
            {
                "path/to/existing_file.py": {
                    "edits": [
                        {
                            "type": "replacement",
                            "start_line": 5,
                            "end_line": 7,
                            "content": "def updated_function():\\n    return True"
                        },
                        {
                            "type": "insertion",
                            "line_number": 15,
                            "content": "    print('New line inserted')"
                        },
                        {
                            "type": "deletion",
                            "start_line": 10,
                            "end_line": 12
                        }
                    ]
                }
            }
            ```
            - Only works on existing files
            - Line numbers are 1-indexed
            - Edits are applied in the order specified

            4. **File Deletion:**
            ```python
            {
                "path/to/file_to_delete.py": {
                    "delete_file": True
                }
            }
            ```
            - Deletes the specified file
            - Succeeds silently if file doesn't exist

    Returns:
        dict: Comprehensive results dictionary containing:
        ```python
        {
            "results": [list],              # Raw GitHub API responses for each file operation
            "modified_files_count": int,    # Number of files actually modified
            "modified_files_content": {     # Final content of each file after changes
                "path/to/file1.py": "content...",
                "path/to/deleted_file.py": None,  # None indicates file was deleted
                ...
            },
            "diff_results": {               # Detailed information about each operation
                "path/to/file1.py": {
                    "status": True,                    # True if operation succeeded
                    "operation": "update",             # "create", "update", "delete", etc.
                    "failed_hunks": [],               # List of diff hunks that failed (unified_diffs only)
                    "is_new_file": False,             # Whether this was a new file creation
                    "is_deleted_file": False,         # Whether file was deleted
                    "error": "error message"          # Present if status is False
                },
                ...
            }
        }
        ```

    Raises:
        ValueError: If trying to apply structured edits to a non-existent file
        httpx.HTTPStatusError: If GitHub API calls fail (authentication, permissions, etc.)

    Examples:
        ```python
        # Create a new file with escape sequences (\\n becomes actual newlines)
        changes = {
            "src/new_module.py": {
                "new_content": "def hello():\\n    return 'Hello, World!'\\n\\nif __name__ == '__main__':\\n    print(hello())"
            }
        }

        # Apply a unified diff to existing file (escape sequences NOT processed in diffs)
        changes = {
            "src/existing.py": {
                "unified_diffs": [
                    "@@ -1,3 +1,4 @@\\nimport os\\n+import sys\\nfrom pathlib import Path"
                ]
            }
        }

        # Delete a file
        changes = {
            "obsolete/old_file.py": {
                "delete_file": True
            }
        }

        # Mix multiple operations
        changes = {
            "src/new.py": {"new_content": "# New file\\nprint('Hello')"},
            "src/update.py": {"unified_diffs": ["@@ -1,1 +1,2 @@\\n+# Updated\\noriginal_line"]},
            "src/delete.py": {"delete_file": True}
        }

        result = await batch_update_files(token, "owner", "repo", "main", changes)
        print(f"Modified {result['modified_files_count']} files")
        ```

    Notes:
        - Operations are applied in the order they appear in the dictionary
        - For unified diffs, the function uses fuzzy matching to handle minor differences
        - File paths should be relative to the repository root
        - All operations are committed to the specified branch
        - The function handles both existing and non-existing files intelligently
        - For safety, always check the `diff_results` for any failed operations
        - Escape sequences (\\n, \\t, etc.) are automatically decoded in 'new_content' but NOT in 'unified_diffs'
    """
    results = []
    modified_files_content = {}
    diff_results = {}

    for file_path, changes in path_to_changes.items():
        # Check if file exists and get original content if it does
        file_exists = await check_file_exists(token, owner, repo, file_path, branch)
        original_content = ""

        if file_exists:
            file_meta = await get_file_metadata(token, owner, repo, file_path, branch)
            original_content = base64.b64decode(file_meta["content"]).decode()

        # Handle file deletion
        if changes.get("delete_file", False):
            if file_exists:
                file_sha = file_meta["sha"]

                # Delete file by creating a commit that removes the file
                headers = {
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github+json",
                }

                data = {
                    "message": f"Delete {file_path}",
                    "sha": file_sha,
                    "branch": branch,
                }

                encoded_path = urllib.parse.quote(file_path, safe="")

                async with httpx.AsyncClient() as client:
                    res = await client.delete(
                        f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_path}",
                        headers=headers,
                        content=json.dumps(data),
                    )
                    res.raise_for_status()
                    result = res.json()
                    results.append(result)
                    modified_files_content[file_path] = (
                        None  # Indicate file was deleted
                    )
                    diff_results[file_path] = {"status": True, "operation": "delete"}
            else:
                # Cannot delete a non-existent file, but we'll consider it a success
                modified_files_content[file_path] = None
                diff_results[file_path] = {
                    "status": True,
                    "operation": "delete_nonexistent",
                }

        elif "new_content" in changes:
            # Simple full file replacement or creation
            new_content = changes["new_content"]

            # Decode escape sequences (like \n, \t) in the new content
            # This allows LLMs to specify newlines and other characters using escape sequences
            new_content = decode_escape_sequences(new_content)

            if file_exists:
                # Update existing file
                file_sha = file_meta["sha"]
                result = await update_file(
                    token, owner, repo, branch, file_path, new_content, file_sha
                )
                diff_results[file_path] = {"status": True, "operation": "update"}
            else:
                # Create new file
                result = await create_file(
                    token, owner, repo, branch, file_path, new_content
                )
                diff_results[file_path] = {"status": True, "operation": "create"}

            results.append(result)
            # Store the limited content
            limited_content = limit_file_content_around_changes(
                original_content, new_content
            )
            modified_files_content[file_path] = limited_content

        elif "unified_diffs" in changes:
            # Apply unified diffs to file
            unified_diffs = changes["unified_diffs"]

            # For new files, empty files, and existing files
            diff_application_result = await apply_unified_diffs(
                original_content, unified_diffs
            )

            # Get the final content after applying diffs
            new_content = diff_application_result["content"]

            # Store diff application results for reporting
            diff_results[file_path] = {
                "status": diff_application_result["status"],
                "failed_hunks": diff_application_result["failed_hunks"],
                "is_new_file": diff_application_result["is_new_file"],
                "is_deleted_file": diff_application_result["is_deleted_file"],
            }

            # Handle based on the diff result
            if diff_application_result["is_deleted_file"]:
                # Delete file
                if file_exists:
                    file_sha = file_meta["sha"]
                    headers = {
                        "Authorization": f"token {token}",
                        "Accept": "application/vnd.github+json",
                    }
                    data = {
                        "message": f"Delete {file_path}",
                        "sha": file_sha,
                        "branch": branch,
                    }
                    encoded_path = urllib.parse.quote(file_path, safe="")
                    async with httpx.AsyncClient() as client:
                        res = await client.delete(
                            f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_path}",
                            headers=headers,
                            content=json.dumps(data),
                        )
                        res.raise_for_status()
                        result = res.json()
                        results.append(result)
                        modified_files_content[file_path] = None
                        diff_results[file_path]["operation"] = "delete"
            elif not new_content.strip():
                # Content is empty but not marked for deletion - do nothing
                diff_results[file_path]["operation"] = "no_change"
                continue
            elif file_exists and not diff_application_result["is_new_file"]:
                # Update existing file
                file_sha = file_meta["sha"]
                result = await update_file(
                    token, owner, repo, branch, file_path, new_content, file_sha
                )
                results.append(result)
                # Store the limited content
                limited_content = limit_file_content_around_changes(
                    original_content, new_content
                )
                modified_files_content[file_path] = limited_content
                diff_results[file_path]["operation"] = "update"
            else:
                # Create new file
                result = await create_file(
                    token, owner, repo, branch, file_path, new_content
                )
                results.append(result)
                # Store the limited content (original_content is empty for new files)
                limited_content = limit_file_content_around_changes("", new_content)
                modified_files_content[file_path] = limited_content
                diff_results[file_path]["operation"] = "create"

        elif "edits" in changes and file_exists:
            # Apply edits to existing file
            file_sha = file_meta["sha"]
            current_content = original_content  # We already have it

            # Apply all edits to get the new content
            new_content = await apply_file_edits(current_content, changes["edits"])

            # Update the file with the edited content
            result = await update_file(
                token, owner, repo, branch, file_path, new_content, file_sha
            )
            results.append(result)
            # Store the limited content
            limited_content = limit_file_content_around_changes(
                original_content, new_content
            )
            modified_files_content[file_path] = limited_content
            diff_results[file_path] = {"status": True, "operation": "update_with_edits"}

        elif "edits" in changes and not file_exists:
            # Cannot apply edits to a non-existent file
            error_message = f"Cannot apply edits to non-existent file: {file_path}"
            diff_results[file_path] = {
                "status": False,
                "error": error_message,
                "operation": "failed",
            }
            raise ValueError(error_message)

    return {
        "results": results,
        "modified_files_count": len(results),
        "modified_files_content": modified_files_content,
        "diff_results": diff_results,
    }


async def create_branch_from_default(
    token: str, owner: str, repo: str, new_branch_name: str
):
    """
    Create a new branch based on the default branch (usually main/master) without needing to specify the base SHA.

    Args:
        token: GitHub access token
        owner: Repository owner
        repo: Repository name
        new_branch_name: Name for the new branch to create

    Returns:
        The response from the GitHub API for the branch creation

    Example:
        result = await create_branch_from_default("ghs_abc123...", "octocat", "hello-world", "feature-branch")
    """
    # Get the default branch and its latest commit SHA
    default_branch, base_sha = await get_default_branch_sha(token, owner, repo)

    # Create the new branch using the obtained SHA
    return await create_branch(token, owner, repo, new_branch_name, base_sha)


async def fetch_changes_from_name(
    token: str, owner: str, repo: str, date_string: str
) -> dict:
    """
    Fetch changes from a repository since a given date and summarize them at the file level.

    Args:
        token: GitHub installation token
        owner: Repository owner/organization name
        repo: Repository name
        date_string: ISO-formatted date string from which to fetch changes (e.g. "2025-04-30 20:40:55.283623+00")

    Returns:
        Dictionary mapping file paths to their change status:
        {
            "path/to/file1.py": {
                "deleted": False,
                "new": False,
                "modified": True
            },
            "path/to/file2.py": {
                "deleted": True,
                "new": False,
                "modified": False
            },
            ...
        }

    Example:
        changes = await fetch_changes_from_name(
            "ghs_abc123...",
            "octocat",
            "hello-world",
            "2025-04-30 20:40:55.283623+00"
        )
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }

    # Parse the date string to datetime object
    try:
        since_date = parser.parse(date_string)
        # Convert to ISO 8601 format as required by GitHub API
        since_iso = since_date.isoformat()
    except Exception as e:
        raise ValueError(
            f"Invalid date format: {e}. Please provide a valid ISO-formatted date string."
        )

    # Get the default branch
    default_branch, _ = await get_default_branch_sha(token, owner, repo)

    # Fetch commits since the specified date
    async with httpx.AsyncClient() as client:
        # Build URL with query parameters
        url = f"https://api.github.com/repos/{owner}/{repo}/commits"
        params = {"since": since_iso, "sha": default_branch}

        res = await client.get(url, headers=headers, params=params)
        res.raise_for_status()
        commits = res.json()

        # If no commits found since the date
        if not commits:
            return {}

        # Track changes for each file
        file_changes = {}

        # Process each commit to extract file changes
        for commit in commits:
            commit_sha = commit["sha"]

            # Get detailed commit info including files changed
            commit_detail_url = (
                f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}"
            )
            commit_res = await client.get(commit_detail_url, headers=headers)
            commit_res.raise_for_status()
            commit_detail = commit_res.json()

            # Process each file in the commit
            for file_info in commit_detail.get("files", []):
                file_path = file_info["filename"]
                status = file_info["status"]  # added, modified, removed, renamed

                # Initialize file entry if not exists
                if file_path not in file_changes:
                    file_changes[file_path] = {
                        "deleted": False,
                        "new": False,
                        "modified": False,
                    }

                # Update file status based on changes
                if status == "added":
                    file_changes[file_path]["new"] = True
                elif status == "removed":
                    file_changes[file_path]["deleted"] = True
                elif status == "modified":
                    file_changes[file_path]["modified"] = True
                elif status == "renamed":
                    # For renamed files, mark the old path as deleted and new path as new
                    old_file_path = file_info.get("previous_filename")
                    if old_file_path:
                        if old_file_path not in file_changes:
                            file_changes[old_file_path] = {
                                "deleted": True,
                                "new": False,
                                "modified": False,
                            }
                        else:
                            file_changes[old_file_path]["deleted"] = True

                        file_changes[file_path]["new"] = True

    return file_changes


def line_range_to_slice(start, length, total_lines):
    """
    Convert 1-based line range (start, length) to 0-based slice indices (i, j).

    Args:
        start: 1-based starting line number
        length: Number of lines in the range
        total_lines: Total number of lines in the file

    Returns:
        Tuple of (start_idx, end_idx) as 0-indexed positions
    """
    i = max(0, start - 1)  # Convert to 0-indexed
    j = min(total_lines, i + length)  # Ensure we don't go past the end
    return i, j


async def apply_unified_diffs(current_content: str, unified_diffs: list[str]) -> dict:
    """
    Apply a list of unified diff strings to file content using fuzzy matching.

    This function parses unified diff format (the standard format used by git diff)
    and applies the changes to the current content, with fuzzy matching to handle
    slight differences in the source code.

    Args:
        current_content: The current content of the file as a string
        unified_diffs: A list of unified diff strings in the format:
            @@ -<start_old>,<len_old> +<start_new>,<len_new> @@
            context line
            -deleted line
            +added line
            context line

    Returns:
        Dictionary containing:
        - content: The modified content as a string
        - status: Success status of the operation
        - failed_hunks: List of hunks that failed to apply cleanly
    """
    # Initialize diff-match-patch
    dmp = diff_match_patch()

    # Split content into lines for line number calculations
    content_lines = current_content.splitlines()
    modified_content = current_content

    # Track which hunks failed to apply cleanly
    failed_hunks = []
    is_new_file = False
    is_deleted_file = False

    for diff_idx, diff_str in enumerate(unified_diffs):
        # Skip empty diffs
        if not diff_str.strip():
            continue

        # Parse the hunk header
        header_match = re.search(
            r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", diff_str
        )
        if not header_match:
            failed_hunks.append(
                {
                    "hunk_index": diff_idx,
                    "reason": "Failed to parse hunk header",
                    "hunk": diff_str[:100] + "..." if len(diff_str) > 100 else diff_str,
                }
            )
            continue

        start_old = int(header_match.group(1))
        len_old = int(header_match.group(2) or 1)
        start_new = int(header_match.group(3))
        len_new = int(header_match.group(4) or 1)

        # Check for new file or deleted file
        if start_old == 0 and len_old == 0:
            is_new_file = True
        elif start_new == 0 and len_new == 0:
            is_deleted_file = True

        # Extract lines after the header
        diff_lines = diff_str.splitlines()
        hunk_start = 0
        for i, line in enumerate(diff_lines):
            if line.startswith("@@"):
                hunk_start = i + 1
                break

        # Create old and new versions based on the diff
        old_snippet = []
        new_snippet = []

        for line in diff_lines[hunk_start:]:
            if line.startswith(" "):  # Context line
                old_snippet.append(line[1:])
                new_snippet.append(line[1:])
            elif line.startswith("-"):  # Deletion
                old_snippet.append(line[1:])
            elif line.startswith("+"):  # Addition
                new_snippet.append(line[1:])

        old_text = "\n".join(old_snippet)
        new_text = "\n".join(new_snippet)

        # Process new and deleted files specially, but don't return early
        if is_new_file:
            # We'll process all diffs and return at the end
            modified_content = new_text
            continue

        if is_deleted_file:
            # Mark for deletion but process all diffs
            modified_content = ""
            continue

        # For normal patches, use diff-match-patch for fuzzy matching
        # Create a patch from old_text→new_text
        patches = dmp.patch_make(old_text, new_text)

        # Apply the patch to modified_content
        new_content, results = dmp.patch_apply(patches, modified_content)

        # Check if all patches were applied successfully
        if not all(results):
            # If fuzzy patching failed, try to apply it based on line numbers
            lines = modified_content.splitlines()

            # Calculate approximate line position using our helper
            start_idx, end_idx = line_range_to_slice(start_old, len_old, len(lines))

            # Extract the context window around the target area
            context_size = 10  # Add more context lines for better matching
            context_start = max(0, start_idx - context_size)
            context_end = min(len(lines), end_idx + context_size)

            context_window = "\n".join(lines[context_start:context_end])

            # Try to fuzzy match in this smaller window - reuse existing patches
            patched_window, window_results = dmp.patch_apply(patches, context_window)

            if all(window_results):
                # Successfully patched the window, now splice it back
                new_lines = (
                    lines[:context_start]
                    + patched_window.splitlines()
                    + lines[context_end:]
                )
                new_content = "\n".join(new_lines)
            else:
                # If still failing, fall back to direct line replacement but record the failure
                failed_hunks.append(
                    {
                        "hunk_index": diff_idx,
                        "reason": "Fuzzy matching failed, using direct line replacement",
                        "hunk": (
                            diff_str[:100] + "..." if len(diff_str) > 100 else diff_str
                        ),
                    }
                )

                if old_snippet:  # Only if we have old content to replace
                    # For safety, limit the replacement to the specified range
                    lines[start_idx:end_idx] = new_snippet
                    new_content = "\n".join(lines)
                else:
                    # If no old content, just insert at the specified position
                    lines[start_idx:start_idx] = new_snippet
                    new_content = "\n".join(lines)

        # Update modified_content for the next iteration
        modified_content = new_content

    # Return the final content and status information
    return {
        "content": modified_content,
        "status": len(failed_hunks) == 0,
        "failed_hunks": failed_hunks,
        "is_new_file": is_new_file,
        "is_deleted_file": is_deleted_file,
    }


async def search_files_by_name(
    token: str,
    owner: str,
    repo: str,
    query: str,
    threshold: int = 60,
    max_results: int = 20,
    branch: str = None,
) -> list[dict]:
    """
    Search for files in a GitHub repository using fuzzy matching on file names.

    Args:
        token: GitHub access token
        owner: Repository owner
        repo: Repository name
        query: The filename or partial filename to search for
        threshold: Fuzzy matching threshold (0-100), higher values require closer matches
        max_results: Maximum number of results to return
        branch: The branch to search in (default: None which uses the default branch)

    Returns:
        List of dictionaries containing matched files with their paths and scores

    Example:
        results = await search_files_by_name("ghs_abc123...", "octocat", "hello-world", "utils", threshold=70, max_results=10)
        # Returns: [{"path": "src/utils.py", "filename": "utils.py", "score": 85}, ...]
    """
    # Get all file paths in the repository
    all_file_paths = await get_all_file_paths(token, owner, repo, branch=branch)

    # Extract just the filename from each path and calculate fuzzy match scores
    matches = []

    for file_path in all_file_paths:
        # Get just the filename (last part of the path)
        filename = file_path.split("/")[-1]

        # Calculate fuzzy match scores using different algorithms
        ratio_score = fuzz.ratio(query.lower(), filename.lower())
        partial_ratio_score = fuzz.partial_ratio(query.lower(), filename.lower())
        token_sort_score = fuzz.token_sort_ratio(query.lower(), filename.lower())
        token_set_score = fuzz.token_set_ratio(query.lower(), filename.lower())

        # Use the highest score from all algorithms
        best_score = max(
            ratio_score, partial_ratio_score, token_sort_score, token_set_score
        )

        # Only include matches above the threshold
        if best_score >= threshold:
            matches.append(
                {"path": file_path, "filename": filename, "score": best_score}
            )

    # Sort by score (highest first) and limit results
    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches[:max_results]


async def search_repo_code(
    installation_token: str,
    owner: str,
    repo: str,
    snippet: str,
    path: Optional[str] = None,
    per_page: int = 100,
    context_lines: int = 5,
    page: int = 1,
    page_size: int = 10,
) -> Dict:
    """
    Search a GitHub repository's code for a given snippet and return matching lines with context.

    Args:
        installation_token: GitHub App installation access token.
        owner: Repository owner (user or org).
        repo: Repository name.
        snippet: Search term or code snippet.
        path: Subdirectory path to limit search (e.g. "src/utils"). Defaults to None.
        per_page: Results per page (max 100). Defaults to 100.
        context_lines: Number of lines before and after each match to include. Defaults to 5.
        page: Page number for pagination, starting from 1. Defaults to 1.
        page_size: Number of matched files to return per page. Defaults to 10.

    Returns:
        A dictionary containing:
        - results: list of result items, each containing:
          - name: filename
          - path: full file path
          - matches: list of matching snippets with line numbers and context as a string
        - pagination: pagination information including:
          - current_page: current page number
          - page_size: number of files per page
          - total_files: total number of files with matches
          - total_pages: total number of pages
          - has_next: whether there are more pages
          - has_prev: whether there are previous pages
    """
    base_url = "https://api.github.com/search/code"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {installation_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Construct the search query with required qualifiers
    qualifiers = ["in:file", f"repo:{owner}/{repo}"]
    if path:
        qualifiers.append(f"path:{path}")
    # Combine snippet with qualifiers
    q = " ".join([snippet] + qualifiers)

    file_results = []
    page = 1

    # First, get all matching files from GitHub's code search
    while True:
        params = {"q": q, "per_page": per_page, "page": page}
        resp = requests.get(base_url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("items", [])
        file_results.extend(items)

        # Stop if we've fetched all available items
        if len(items) < per_page:
            break
        page += 1

    # Now read each file and find the actual matching lines
    detailed_results = []

    for file_item in file_results:
        file_path = file_item["path"]
        file_name = file_item["name"]

        try:
            # Read the file content
            file_content = await read_file_from_repo(
                installation_token, owner, repo, file_path, add_line_numbers=False
            )

            # Find all lines that contain the snippet
            lines = file_content.split("\n")
            matches = []

            for line_num, line in enumerate(lines, 1):
                if snippet.lower() in line.lower():
                    # Calculate context window
                    start_line = max(
                        0, line_num - 1 - context_lines
                    )  # Convert to 0-indexed
                    end_line = min(
                        len(lines), line_num + context_lines
                    )  # line_num is already 1-indexed

                    # Extract context lines and build a single string
                    context_lines_list = []
                    for i in range(start_line, end_line):
                        line_number = i + 1
                        line_content = lines[i]
                        # Mark the matching line with >>>
                        marker = ">>> " if line_number == line_num else "    "
                        context_lines_list.append(f"{marker}{line_content}")

                    context_string = "\n".join(context_lines_list)

                    matches.append(
                        {
                            "line_number": line_num,
                            "matched_line": line,
                            "context": context_string,
                        }
                    )

            # Only include files that have actual matches
            if matches:
                detailed_results.append(
                    {
                        "name": file_name,
                        "path": file_path,
                        "total_matches": len(matches),
                        "matches": matches,
                    }
                )

        except Exception as e:
            # If we can't read the file, include it with an error note
            detailed_results.append(
                {
                    "name": file_name,
                    "path": file_path,
                    "total_matches": 0,
                    "matches": [],
                    "error": f"Could not read file: {str(e)}",
                }
            )

    # Paginate results
    total_files = len(detailed_results)
    total_pages = (total_files + page_size - 1) // page_size
    has_next = page < total_pages
    has_prev = page > 1

    # Slice results based on current page
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_results = detailed_results[start_idx:end_idx]

    return {
        "results": paginated_results,
        "pagination": {
            "current_page": page,
            "page_size": page_size,
            "total_files": total_files,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_prev": has_prev,
        },
    }


def limit_file_content_around_changes(
    original_content: str,
    new_content: str,
    context_lines: int = 5,
    max_total_lines: int = 50,
) -> str:
    """
    Limit the returned file content to show only the changed portions with context.

    Args:
        original_content: The original file content before changes
        new_content: The new file content after changes
        context_lines: Number of context lines to show above/below changes
        max_total_lines: Maximum total lines to show (if exceeded, will truncate further)

    Returns:
        Limited content string with indicators for omitted sections
    """
    if not original_content and not new_content:
        return ""

    # If original content is empty (new file), return limited new content
    if not original_content:
        new_lines = new_content.splitlines()
        if len(new_lines) <= max_total_lines:
            return new_content
        else:
            visible_lines = new_lines[:max_total_lines]
            omitted_count = len(new_lines) - max_total_lines
            return (
                "\n".join(visible_lines)
                + f"\n\n... {omitted_count} more lines below omitted ..."
            )

    # If new content is empty (deleted file), show deletion message
    if not new_content:
        return "File was deleted"

    original_lines = original_content.splitlines()
    new_lines = new_content.splitlines()

    # If the file is small enough, return the full content
    if len(new_lines) <= max_total_lines:
        return new_content

    # Find changed line ranges by comparing original and new content

    diff = list(
        difflib.unified_diff(
            original_lines,
            new_lines,
            lineterm="",
            n=0,  # No context in diff itself
        )
    )

    changed_line_ranges = []
    current_new_line = 1

    for line in diff:
        if line.startswith("@@"):
            # Parse the hunk header to get line numbers
            match = re.search(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if match:
                new_start = int(match.group(3))
                new_count = int(match.group(4)) if match.group(4) else 1
                if new_count > 0:
                    changed_line_ranges.append((new_start, new_start + new_count - 1))

    # If no changes detected or ranges are too complex, show beginning of file
    if not changed_line_ranges:
        visible_lines = new_lines[:max_total_lines]
        omitted_count = (
            len(new_lines) - max_total_lines if len(new_lines) > max_total_lines else 0
        )
        result = "\n".join(visible_lines)
        if omitted_count > 0:
            result += f"\n\n... {omitted_count} more lines below omitted ..."
        return result

    # Merge overlapping ranges and add context
    merged_ranges = []
    for start, end in sorted(changed_line_ranges):
        # Add context lines
        start_with_context = max(1, start - context_lines)
        end_with_context = min(len(new_lines), end + context_lines)

        # Merge with previous range if they overlap
        if merged_ranges and start_with_context <= merged_ranges[-1][1] + 1:
            merged_ranges[-1] = (
                merged_ranges[-1][0],
                max(merged_ranges[-1][1], end_with_context),
            )
        else:
            merged_ranges.append((start_with_context, end_with_context))

    # Build the limited content
    result_lines = []
    last_end = 0

    for start, end in merged_ranges:
        # Add omission indicator if there's a gap
        if start > last_end + 1:
            if last_end == 0:
                # Lines omitted from the beginning
                omitted_count = start - 1
                result_lines.append(f"... {omitted_count} lines above omitted ...")
            else:
                # Lines omitted in the middle
                omitted_count = start - last_end - 1
                result_lines.append(f"... {omitted_count} lines omitted ...")

        # Add the lines from this range
        range_lines = new_lines[start - 1 : end]  # Convert to 0-based indexing
        result_lines.extend(range_lines)
        last_end = end

    # Add final omission indicator if needed
    if last_end < len(new_lines):
        omitted_count = len(new_lines) - last_end
        result_lines.append(f"... {omitted_count} lines below omitted ...")

    # Check if we're still over the max total lines limit
    if len(result_lines) > max_total_lines:
        # Keep the first part and add an omission indicator
        visible_lines = result_lines[: max_total_lines - 1]
        total_omitted = len(result_lines) - max_total_lines + 1
        visible_lines.append(
            f"... {total_omitted} more lines omitted (content too long) ..."
        )
        result_lines = visible_lines

    return "\n".join(result_lines)


def decode_escape_sequences(content: str) -> str:
    """
    Decode newline escape sequences in a string.

    This function handles only \\n escape sequences that might be present in LLM-generated
    content, converting them to actual newline characters. This is specifically
    designed for processing 'new_content' fields where the LLM might include
    literal \\n sequences that should be interpreted as newlines.

    Args:
        content: String that may contain \\n escape sequences

    Returns:
        String with \\n escape sequences converted to actual newlines

    Example:
        decode_escape_sequences("Hello\\nWorld\\nTest") -> "Hello\nWorld\nTest"
    """
    if not isinstance(content, str):
        return content

    # Only handle \n escape sequences explicitly
    return content.replace("\\n", "\n")


if __name__ == "__main__":
    generate_jwt()

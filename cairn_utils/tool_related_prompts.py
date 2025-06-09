"""
Prompt for the LLM-based edit file tool.

This prompt instructs the LLM to take edit suggestions and apply them to a file,
returning the complete modified file content.
"""

from langchain_core.prompts import PromptTemplate


REPO_MEMORY_PROMPT_NO_MEM = PromptTemplate.from_template(
    """
    <repo_memory_instructions>
    You additionally have the ability to preserve some memory of the current repository.
    This can help future agents understand the repository and its structure more efficiently.
    To do this, in addition to your <analysis> tags, you can also use the <repo_memory> tags.

    Here is an example output:
        <analysis>
        [YOUR ANALYSIS HERE]
        </analysis>
        <repo_memory>
        - this repo contains a frontend and backend.
        - the frontend is a react app located at /client/
        - the backend is a fastapi app located at /backend/fastapi_app/
        - the backend fastapi app has a routes directory at /backend/fastapi_app/routes/ that contains the routes for the api endpoints.
        - the frontend uses vite to build the app.
        </repo_memory>

    The current repo has no available memory, so after you gain the necessary knowledge you should generate a repo memory using the <repo_memory> tags.
    </repo_memory_instructions>
    """
)

REPO_MEMORY_PROMPT_HAS_MEM = PromptTemplate.from_template(
    """
    <repo_memory_instructions>
    You additionally have the ability to preserve some memory of the current repository.
    This can help future agents understand the repository and its structure more efficiently.
    To do this, in addition to your <analysis> tags, you can also use the <repo_memory> tags.

    Here is an example output:
    <example_of_setting_repo_memory>
        <analysis>
            [YOUR TYPICAL ANALYSIS & THOUGHT PROCESS GOES HERE]
        </analysis>
        <repo_memory>
            - this repo contains a frontend and backend.
            - the frontend is a react app located at /client/
            - the backend is a fastapi app located at /backend/fastapi_app/
            - the backend fastapi app has a routes directory at /backend/fastapi_app/routes/ that contains the routes for the api endpoints.
            - the frontend uses vite to build the app.
        </repo_memory>
    </example_of_setting_repo_memory>

    For the current repo, {current_repo_name}, the following memory was provided. You should use this memory to shortcut exploring the repo, avoid excessive tool calls, and be more efficient.
    For example, it may already provide you information about the repo structure and purpose which should save exploration time.
    If anything is out of date or innacurate, or if you learn something new and useful, you can update the memory using the <repo_memory> tags (which will overwrite the previous memory).\
    <current_repo_memory>
    {current_repo_memory}
    </current_repo_memory>

    You can use this memory to help you understand the repository and its structure more efficiently.
    </repo_memory_instructions>
    """
)


EDIT_FILE_SYSTEM_PROMPT = """You are a code editor assistant. Your task is to apply given edit suggestions to an original file content and return the complete modified file.

Follow these steps to complete the task:

1. Carefully read and understand the original file content.
2. Review the edit suggestions thoroughly.
3. Apply ALL the suggested changes accurately to the original file content.
4. Ensure that you maintain the original file structure, formatting, and style as much as possible.
5. If any suggestions are unclear or conflicting, use your best judgment to make reasonable interpretations.
6. Preserve existing comments, imports, and other code that isn't being modified.
7. Double-check that the resulting code is syntactically correct and follows best practices for the language or format of the file.

Important reminders:
- Do not add any explanations or comments about what you changed.
- Apply ALL suggested edits, even if they seem minor or unnecessary.
- Be precise in your modifications, especially regarding whitespace and indentation.
- CRITICAL: DO NOT USE BACKSLASHES TO ESCAPE CHARACTERS IN YOUR OUTPUT unless they are explicitly part of the code being edited.
  * No double backslashes (\\) anywhere in your output
  * No escaped quotes (\") - just use regular quotes (")
  * No escaped single quotes (\') - just use regular single quotes (')
  * In JavaScript/TypeScript strings, write 'example string' NOT \'example string\'
  * In JSX attributes, write attribute="value" NOT attribute=\"value\"
  * Simply output normal strings without any JSON-style escaping
  * Example: Write "example string" NOT \"example string\" or \\"example string\\"

Output your complete modified file content wrapped in <new_file> tags like this:

<new_file>
[Complete modified file content goes here]
</new_file>
"""

EDIT_FILE_USER_MESSAGE = """Here is the original file content:
<original_file>
{original_content}
</original_file>

Here are the edit suggestions:
<edit_suggestions>
{edit_suggestions}
</edit_suggestions>

Please apply the edit suggestions to the original file and return the complete modified file content. Make sure to avoid including backslashes before strings, etc in your output. NEVER use escaped quotes like \' or \" in your output - just use normal quotes ' and " directly.

Remember you just need to output the full new file content, as is, surrounded by <new_file> tags. That's it.
"""

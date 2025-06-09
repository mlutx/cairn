# Contributing to Cairn

Thank you for your interest in contributing to Cairn! This document provides guidelines and information for contributors.

## 🌟 Ways to Contribute

- **🐛 Bug Reports**: Help us identify and fix issues
- **💡 Feature Requests**: Suggest new features or improvements
- **📖 Documentation**: Improve our docs, examples, and guides
- **🔧 Code Contributions**: Implement features, fix bugs, or improve performance
- **🧪 Testing**: Write tests or help with quality assurance
- **🎨 UI/UX**: Improve the web interface and user experience

## 🚀 Getting Started

### Development Environment Setup

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/cairn.git
   cd cairn
   ```

3. **Set up Python environment** (Python 3.10+ required):
   ```bash
   # Using venv
   python -m venv cairn-env
   source cairn-env/bin/activate  # On Windows: cairn-env\Scripts\activate

   # OR Using conda
   conda create -n cairn python=3.10
   conda activate cairn
   ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # Development dependencies
   ```

5. **Set up pre-commit hooks**:
   ```bash
   pre-commit install
   ```

6. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

### Verifying Your Setup

1. **Run tests**:
   ```bash
   pytest
   ```

2. **Start the application**:
   ```bash
   # Terminal interface
   python interactive_worker_manager.py

   # Web interface
   cd fastapi_app
   uvicorn app:app --reload
   ```

## 📋 Contribution Process

### For Bug Reports

1. **Check existing issues** to avoid duplicates
2. **Use the bug report template** when creating a new issue
3. **Provide detailed information**:
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, etc.)
   - Relevant logs or error messages

### For Feature Requests

1. **Check existing feature requests** and discussions
2. **Use the feature request template**
3. **Provide context**:
   - Use case and motivation
   - Proposed solution or approach
   - Any alternatives considered

### For Code Contributions

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Make your changes**:
   - Write clean, readable code
   - Follow our coding standards (see below)
   - Add tests for new functionality
   - Update documentation as needed

3. **Test your changes**:
   ```bash
   # Run all tests
   pytest

   # Run with coverage
   pytest --cov=cairn_utils --cov=agent_worker --cov=fastapi_app

   # Run specific test types
   pytest tests/unit/
   pytest tests/integration/
   ```

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: add new agent capability"
   # Use conventional commit format (see below)
   ```

5. **Push and create a Pull Request**:
   ```bash
   git push origin feature/your-feature-name
   ```

## 📝 Coding Standards

### Python Style Guide

- Follow **PEP 8** style guidelines
- Use **type hints** for function signatures
- Write **docstrings** for classes and functions
- Maximum line length: **88 characters** (Black formatter)

### Code Quality Tools

We use several tools to maintain code quality:

- **Black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **pytest**: Testing

Run all checks before submitting:
```bash
# Format code
black .
isort .

# Check linting
flake8

# Type checking
mypy cairn_utils/ agent_worker/ fastapi_app/

# Run tests
pytest
```

### Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```bash
feat(agents): add custom tool support for SWE agent
fix(api): resolve task status update race condition
docs(readme): update installation instructions
test(utils): add tests for github_utils module
```

## 🧪 Testing Guidelines

### Test Structure

```
tests/
├── unit/                    # Unit tests
│   ├── test_agents.py
│   ├── test_task_storage.py
│   └── test_github_utils.py
├── integration/             # Integration tests
│   ├── test_api_endpoints.py
│   └── test_worker_manager.py
└── e2e/                     # End-to-end tests
    └── test_full_workflow.py
```

### Writing Tests

- **Unit tests**: Test individual functions/classes in isolation
- **Integration tests**: Test component interactions
- **E2E tests**: Test complete user workflows

**Test naming convention:**
```python
def test_<functionality>_<condition>_<expected_result>():
    # Example: test_create_task_with_valid_payload_returns_task_id()
    pass
```

**Fixtures and utilities:**
```python
import pytest
from cairn_utils.task_storage import TaskStorage

@pytest.fixture
def task_storage():
    """Provide a clean TaskStorage instance for testing."""
    return TaskStorage(":memory:")  # Use in-memory database

def test_create_task_stores_in_database(task_storage):
    task_id = task_storage.create_task({"description": "test task"})
    assert task_id is not None
    assert task_storage.get_task(task_id) is not None
```

## 📁 Project Structure

Understanding the codebase organization:

```
cairn/
├── agent_worker/              # Worker process for task execution
│   ├── worker.py             # Main worker logic
│   ├── __main__.py           # CLI entry point
│   └── __init__.py
├── cairn_utils/              # Core library code
│   ├── agents/               # Agent implementations
│   ├── github_utils.py       # GitHub API integration
│   ├── toolbox.py           # Agent tools and capabilities
│   ├── task_storage.py      # Database operations
│   ├── agent_classes.py     # Base agent classes
│   └── tool_types.py        # Tool type definitions
├── fastapi_app/              # Web interface
│   └── app.py               # FastAPI application
├── static/                   # Frontend assets
├── docs/                     # Documentation
├── examples/                 # Usage examples
├── tests/                    # Test suite
├── .github/                  # GitHub workflows and templates
├── requirements.txt          # Production dependencies
├── requirements-dev.txt      # Development dependencies
├── pyproject.toml           # Project configuration
└── setup.py                 # Package setup
```

## 🔍 Code Review Process

### Pull Request Guidelines

1. **Clear title and description**: Explain what and why
2. **Link related issues**: Use "Fixes #123" or "Relates to #456"
3. **Keep changes focused**: One feature/fix per PR
4. **Update documentation**: Include relevant doc updates
5. **Add tests**: Ensure new code is tested

### Review Checklist

**For Reviewers:**
- [ ] Code follows style guidelines
- [ ] Tests cover new functionality
- [ ] Documentation is updated
- [ ] No breaking changes (or properly documented)
- [ ] Performance impact considered
- [ ] Security implications reviewed

**For Contributors:**
- [ ] All tests pass
- [ ] Pre-commit hooks pass
- [ ] Documentation updated
- [ ] Changelog entry added (for significant changes)
- [ ] Backward compatibility maintained

## 🌐 Community Guidelines

### Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please review our [Code of Conduct](CODE_OF_CONDUCT.md).

### Communication

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and community discussions
- **Discord**: Real-time chat and community support *(placeholder)*
- **Email**: Security issues and sensitive matters

### Getting Help

- **Documentation**: Check our [docs](docs/) first
- **Search existing issues**: Your question might already be answered
- **Ask in discussions**: For general questions
- **Join our Discord**: For real-time help *(placeholder)*

## 🏷️ Release Process

### Versioning

We follow [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Workflow

1. **Feature freeze** on release branch
2. **Testing and bug fixes**
3. **Documentation updates**
4. **Release candidate** testing
5. **Final release** and tagging

## 📞 Questions?

If you have questions about contributing:

1. **Check the [FAQ](docs/faq.md)**
2. **Search [existing discussions](https://github.com/[YOUR_ORG]/cairn/discussions)**
3. **Create a new [discussion](https://github.com/[YOUR_ORG]/cairn/discussions/new)**
4. **Contact maintainers**: [maintainers@cairn.dev](mailto:maintainers@cairn.dev) *(placeholder)*

---

Thank you for contributing to Cairn! 🙏

"""Repository hygiene.

These tests enforce the refactor's structural decisions mechanically, so a later change
cannot quietly reintroduce a deterministic path, leave a dead module behind, or ship a
tool the model cannot understand.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

SOURCE_ROOT = Path("src/support_scout")
PYTHON_FILES = sorted(SOURCE_ROOT.rglob("*.py"))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------------------
# Removals stay removed
# --------------------------------------------------------------------------------------
REMOVED_MODULES = [
    "execution_mode.py",
    "shadow_orchestrator.py",
    "specialist_adapters.py",
    "agent_runner.py",
    "tool_registry.py",
    "tool_context.py",
    "trace_recorder.py",
    "orchestrator.py",
    "operational_diagnostics_service.py",
    "content_pipeline.py",
    "routing_service.py",
    "model_client.py",
    "chat.py",
    "live.py",
]


@pytest.mark.parametrize("filename", REMOVED_MODULES)
def test_removed_modules_are_absent(filename):
    assert not list(SOURCE_ROOT.rglob(filename)), f"{filename} should have been removed"


def test_no_execution_mode_remains():
    """FR-A22: agentic is the only path."""
    for path in PYTHON_FILES:
        content = read(path)
        for token in ("ExecutionMode", "SUPPORTSCOUT_EXECUTION_MODE", "shadow_orchestrator"):
            assert token not in content, f"{path} still references {token}"


def test_no_deterministic_mode_switch():
    for path in PYTHON_FILES:
        content = read(path).casefold()
        assert "execution_mode" not in content, f"{path} still has an execution mode switch"


def test_legacy_agents_package_is_gone():
    """The old non-agentic agents/ modules must not coexist with the new ones."""
    legacy_markers = ("class TriageAgent:\n    def __init__(self, model_client", "SearchPlan")
    for path in PYTHON_FILES:
        content = read(path)
        for marker in legacy_markers:
            assert marker not in content, f"{path} contains legacy agent code"


# --------------------------------------------------------------------------------------
# Source quality
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("path", PYTHON_FILES, ids=lambda p: str(p))
def test_source_is_ascii(path):
    """Non-ASCII characters have caused corrupted pastes before."""
    content = path.read_bytes()
    try:
        content.decode("ascii")
    except UnicodeDecodeError as exc:
        pytest.fail(f"{path} contains non-ASCII at byte {exc.start}")


@pytest.mark.parametrize("path", PYTHON_FILES, ids=lambda p: str(p))
def test_source_parses(path):
    ast.parse(read(path), filename=str(path))


@pytest.mark.parametrize("path", PYTHON_FILES, ids=lambda p: str(p))
def test_module_has_a_docstring(path):
    tree = ast.parse(read(path), filename=str(path))
    assert ast.get_docstring(tree), f"{path} has no module docstring"


def test_no_bare_except_clauses():
    for path in PYTHON_FILES:
        tree = ast.parse(read(path), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                pytest.fail(f"{path}:{node.lineno} uses a bare except")


def test_no_print_outside_the_cli():
    """Console output belongs to the CLI and the logger, not to library modules."""
    allowed = {"main.py", "logging_config.py", "hitl.py"}
    for path in PYTHON_FILES:
        if path.name in allowed:
            continue
        tree = ast.parse(read(path), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ):
                pytest.fail(f"{path}:{node.lineno} calls print outside the CLI")


# --------------------------------------------------------------------------------------
# Tool quality
# --------------------------------------------------------------------------------------
TOOL_MODULES = sorted((SOURCE_ROOT / "tools").glob("*_tools.py"))


def test_tool_modules_exist():
    assert len(TOOL_MODULES) == 6


@pytest.mark.parametrize("path", TOOL_MODULES, ids=lambda p: p.stem)
def test_every_tool_uses_the_decorator(path):
    """FR-A01/NFR-A03: tools are readable @tool functions, not Tool subclasses."""
    tree = ast.parse(read(path), filename=str(path))

    decorated = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any(isinstance(d, ast.Name) and d.id == "tool" for d in node.decorator_list)
    ]
    assert decorated, f"{path} defines no @tool functions"

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
            assert "Tool" not in bases, f"{path}:{node.lineno} subclasses Tool instead of using @tool"


@pytest.mark.parametrize("path", TOOL_MODULES, ids=lambda p: p.stem)
def test_every_tool_documents_every_argument(path):
    """smolagents derives the model-visible schema from the docstring Args section."""
    tree = ast.parse(read(path), filename=str(path))

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if not any(isinstance(d, ast.Name) and d.id == "tool" for d in node.decorator_list):
            continue

        docstring = ast.get_docstring(node)
        assert docstring, f"{path}:{node.lineno} @tool {node.name} has no docstring"

        for argument in node.args.args:
            assert f"{argument.arg}:" in docstring, (
                f"{path} @tool {node.name} does not document '{argument.arg}' in Args"
            )

        assert node.returns is not None, f"@tool {node.name} has no return annotation"
        for argument in node.args.args:
            assert argument.annotation is not None, (
                f"@tool {node.name} argument '{argument.arg}' has no type hint"
            )


# --------------------------------------------------------------------------------------
# Required project artifacts
# --------------------------------------------------------------------------------------
REQUIRED_FILES = [
    "README.md",
    "CLAUDE.md",
    "pyproject.toml",
    "requirements.txt",
    ".env.example",
    ".specify/memory/constitution.md",
    "specs/001-agentic-refactor/spec.md",
    "specs/001-agentic-refactor/plan.md",
    "specs/001-agentic-refactor/research.md",
    "specs/001-agentic-refactor/data-model.md",
    "specs/001-agentic-refactor/tasks.md",
    "specs/001-agentic-refactor/quickstart.md",
    "specs/001-agentic-refactor/contracts/tool-contracts.md",
    "specs/001-agentic-refactor/contracts/operations-api.md",
    "diagrams/architecture.mmd",
    "docs/mission.md",
    "docs/roadmap.md",
    "docs/tech_stack.md",
    "tests/TRACEABILITY_MATRIX.md",
    "src/support_scout/prompts/prompt-decision-log.md",
]


@pytest.mark.parametrize("relative_path", REQUIRED_FILES)
def test_required_artifact_exists(relative_path):
    """FY27 required artifacts: specs, diagram, tests, README, prompts, CLAUDE.md."""
    path = Path(relative_path)
    assert path.exists(), f"{relative_path} is missing"
    assert path.stat().st_size > 0, f"{relative_path} is empty"


def test_every_agent_has_prompt_documentation():
    prompts = SOURCE_ROOT / "prompts"
    for agent in (
        "orchestrator",
        "triage",
        "research",
        "support",
        "qa",
        "documentation",
    ):
        assert (prompts / f"{agent}-agent.md").exists(), f"{agent} prompt doc missing"


def test_env_example_declares_no_secret_values():
    """The template must never ship a real key."""
    for line in Path(".env.example").read_text(encoding="utf-8").splitlines():
        if line.startswith(("UDACITY_API_KEY", "TAVILY_API_KEY")):
            assert line.split("=", 1)[1].strip() == "", f"{line} appears to contain a value"

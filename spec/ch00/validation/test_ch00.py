"""
Chapter 0 Validation Tests
==========================

These tests validate the reader's Ch 0 setup: project structure, environment,
dependencies, and LLM connectivity.

Run from the reader's project root:
    python -m pytest test_ch00.py -v

Or:
    python test_ch00.py
"""

import subprocess
import os
import sys

# ============================================================================
# CONFIGURATION
# ============================================================================

# Path to the reader's project root. Adjust if needed.
PROJECT_ROOT = os.environ.get("TBH_PROJECT_ROOT", os.getcwd())
TODO_API_PATH = os.path.join(PROJECT_ROOT, "todo-api")
SMOKE_TEST_PATH = os.path.join(PROJECT_ROOT, "smoke_test.py")


# ============================================================================
# TESTS — PYTHON ENVIRONMENT
# ============================================================================

class TestPythonEnvironment:
    """The reader must have Python 3.10+ and a working environment."""

    def test_python_version(self):
        """Python 3.10+ is required."""
        assert sys.version_info >= (3, 10), (
            f"Python 3.10+ required, got {sys.version}"
        )

    def test_llm_sdk_installed(self):
        """Either anthropic or openai SDK must be installed."""
        anthropic_ok = False
        openai_ok = False
        try:
            import anthropic
            anthropic_ok = True
        except ImportError:
            pass
        try:
            import openai
            openai_ok = True
        except ImportError:
            pass
        assert anthropic_ok or openai_ok, (
            "Neither 'anthropic' nor 'openai' SDK is installed. "
            "Run: pip install anthropic  (or pip install openai)"
        )

    def test_api_key_set(self):
        """At least one LLM API key must be in environment."""
        has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
        has_openai = bool(os.environ.get("OPENAI_API_KEY"))
        assert has_anthropic or has_openai, (
            "No API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY "
            "in your environment."
        )

    def test_api_key_not_in_source(self):
        """API keys must not be hardcoded in smoke_test.py."""
        if not os.path.exists(SMOKE_TEST_PATH):
            return  # skip if smoke test doesn't exist yet
        with open(SMOKE_TEST_PATH, "r") as f:
            content = f.read()
        assert "sk-ant-" not in content, (
            "API key found in smoke_test.py! Use environment variables instead."
        )
        # Check for OpenAI-style keys (sk- followed by alphanumeric chars)
        import re
        key_pattern = re.findall(r'["\']sk-[A-Za-z0-9]{20,}["\']', content)
        assert len(key_pattern) == 0, (
            "Possible API key found in smoke_test.py! Use environment variables."
        )


# ============================================================================
# TESTS — PROJECT STRUCTURE
# ============================================================================

class TestProjectStructure:
    """The project directory must have the expected layout."""

    def test_todo_api_exists(self):
        """todo-api/ directory must exist."""
        assert os.path.isdir(TODO_API_PATH), (
            f"todo-api/ not found at {TODO_API_PATH}. "
            "Copy it from the book repo: cp -r spec/todo-api ./todo-api"
        )

    def test_todo_api_has_source_files(self):
        """todo-api/ must contain the expected source files."""
        expected_files = [
            "src/main.pseudo",
            "src/middleware/auth.pseudo",
            "src/routes/tasks.pseudo",
            "src/routes/auth.pseudo",
        ]
        for f in expected_files:
            full = os.path.join(TODO_API_PATH, f)
            assert os.path.exists(full), (
                f"Missing file: todo-api/{f}"
            )

    def test_todo_api_has_test_files(self):
        """todo-api/ must contain test files."""
        expected_tests = [
            "tests/tasks_test.pseudo",
            "tests/auth_test.pseudo",
        ]
        for f in expected_tests:
            full = os.path.join(TODO_API_PATH, f)
            assert os.path.exists(full), (
                f"Missing test file: todo-api/{f}"
            )

    def test_package_directory_exists(self):
        """tbh_code/ package directory must exist."""
        pkg_dir = os.path.join(PROJECT_ROOT, "tbh_code")
        assert os.path.isdir(pkg_dir), (
            "tbh_code/ directory not found. "
            "Run: mkdir -p tbh_code && touch tbh_code/__init__.py"
        )

    def test_package_init_exists(self):
        """tbh_code/__init__.py must exist."""
        init = os.path.join(PROJECT_ROOT, "tbh_code", "__init__.py")
        assert os.path.exists(init), (
            "tbh_code/__init__.py not found. Run: touch tbh_code/__init__.py"
        )

    def test_smoke_test_exists(self):
        """smoke_test.py must exist."""
        assert os.path.exists(SMOKE_TEST_PATH), (
            "smoke_test.py not found in project root."
        )


# ============================================================================
# TESTS — SMOKE TEST
# ============================================================================

class TestSmokeTest:
    """The smoke test must run and get a response from the LLM."""

    def test_smoke_test_runs(self):
        """smoke_test.py must execute without errors."""
        if not os.path.exists(SMOKE_TEST_PATH):
            assert False, "smoke_test.py not found — skipping"
        result = subprocess.run(
            [sys.executable, SMOKE_TEST_PATH],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"smoke_test.py failed (exit code {result.returncode}):\n"
            f"stderr: {result.stderr}"
        )

    def test_smoke_test_output(self):
        """smoke_test.py must output 'tbh-code ready'."""
        if not os.path.exists(SMOKE_TEST_PATH):
            assert False, "smoke_test.py not found — skipping"
        result = subprocess.run(
            [sys.executable, SMOKE_TEST_PATH],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"smoke_test.py failed: {result.stderr}"
        )
        output = result.stdout.strip().lower()
        assert "tbh-code ready" in output, (
            f"Expected 'tbh-code ready' in output, got: {result.stdout.strip()}"
        )


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    test_classes = [
        TestPythonEnvironment,
        TestProjectStructure,
        TestSmokeTest,
    ]
    passed = 0
    failed = 0
    errors = []

    for cls in test_classes:
        print(f"\n{cls.__name__}")
        print("-" * len(cls.__name__))
        instance = cls()
        for method_name in sorted(dir(instance)):
            if method_name.startswith("test_"):
                test_name = f"{cls.__name__}.{method_name}"
                try:
                    getattr(instance, method_name)()
                    print(f"  PASS  {method_name}")
                    passed += 1
                except AssertionError as e:
                    print(f"  FAIL  {method_name}: {e}")
                    failed += 1
                    errors.append((test_name, str(e)))
                except Exception as e:
                    print(f"  ERROR {method_name}: {e}")
                    failed += 1
                    errors.append((test_name, str(e)))

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    if errors:
        print(f"\nFailures:")
        for name, err in errors:
            print(f"  {name}: {err}")
    sys.exit(0 if failed == 0 else 1)

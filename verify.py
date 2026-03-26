#!/usr/bin/env python3
"""Verify installation and project structure for Emotional RAG Backend."""

import sys
from pathlib import Path
from typing import List, Tuple


def check_file_exists(path: str) -> bool:
    return Path(path).exists()


def check_directory_exists(path: str) -> bool:
    return Path(path).is_dir()


def verify_project_structure() -> Tuple[int, int]:
    """Verify required files/directories for current workspace layout."""
    checks: List[bool] = []

    core_files = [
        ("app/__init__.py", "App package"),
        ("app/main.py", "FastAPI app"),
        ("app/core/config.py", "Configuration"),
        ("app/core/memory.py", "Memory manager"),
        ("app/core/token_manager.py", "Token manager"),
        ("app/routes/chat.py", "Chat routes"),
        ("app/routes/health.py", "Health routes"),
        ("app/services/llm_provider.py", "LLM provider abstraction"),
        ("app/services/rag_engine.py", "RAG engine"),
        ("app/services/emotion_tracker.py", "Emotion tracker"),
        ("app/services/knowledge_ingester.py", "Knowledge ingester"),
    ]

    optional_service_files = [
        ("app/services/chromadb_store.py", "ChromaDB store"),
        ("app/services/reranker.py", "Reranker"),
        ("app/services/transformer_emotions.py", "Transformer emotions"),
        ("app/services/redis_memory.py", "Redis memory"),
        ("app/services/metrics.py", "Metrics collector"),
    ]

    config_files = [
        (".env.example", "Environment template"),
        ("requirements.txt", "Dependencies"),
        ("run.sh", "Run script"),
        ("setup.py", "Setup script"),
        ("README.md", "README"),
        ("QUICKSTART.md", "Quickstart"),
        ("ARCHITECTURE.md", "Architecture docs"),
        ("LICENSE", "License"),
    ]

    test_files = [
        ("tests/test_api.py", "API tests"),
        ("tests/test_memory.py", "Memory tests"),
        ("tests/test_emotion.py", "Emotion tests"),
    ]

    directories = [
        ("app", "App directory"),
        ("app/core", "Core directory"),
        ("app/routes", "Routes directory"),
        ("app/services", "Services directory"),
        ("tests", "Tests directory"),
        ("examples", "Examples directory"),
        ("data", "Data directory"),
        ("data/sessions", "Session DB directory"),
        ("knowledge_base", "Knowledge base directory"),
    ]

    print("=" * 70)
    print("Project Structure Verification".center(70))
    print("=" * 70)

    print("\nCore Files:")
    for file_path, description in core_files:
        exists = check_file_exists(file_path)
        checks.append(exists)
        marker = "OK" if exists else "MISSING"
        print(f"  [{marker:7}] {description:30s} {file_path}")

    print("\nOptional Service Files:")
    for file_path, description in optional_service_files:
        exists = check_file_exists(file_path)
        marker = "OK" if exists else "MISSING"
        print(f"  [{marker:7}] {description:30s} {file_path}")

    print("\nConfig and Docs:")
    for file_path, description in config_files:
        exists = check_file_exists(file_path)
        checks.append(exists)
        marker = "OK" if exists else "MISSING"
        print(f"  [{marker:7}] {description:30s} {file_path}")

    print("\nTests:")
    for file_path, description in test_files:
        exists = check_file_exists(file_path)
        checks.append(exists)
        marker = "OK" if exists else "MISSING"
        print(f"  [{marker:7}] {description:30s} {file_path}")

    print("\nDirectories:")
    for dir_path, description in directories:
        exists = check_directory_exists(dir_path)
        checks.append(exists)
        marker = "OK" if exists else "MISSING"
        print(f"  [{marker:7}] {description:30s} {dir_path}")

    passed = sum(checks)
    total = len(checks)

    print("\n" + "=" * 70)
    print(f"Results: {passed}/{total} required checks passed")
    print("=" * 70)

    return passed, total


def check_python_version() -> bool:
    version = sys.version_info
    required = (3, 10)

    print("\nPython Version:")
    print(f"  Current : {version.major}.{version.minor}.{version.micro}")
    print(f"  Required: {required[0]}.{required[1]}+")

    ok = version >= required
    print("  Status  : OK" if ok else "  Status  : TOO OLD")
    return ok


def check_virtual_env() -> bool:
    print("\nVirtual Environment:")
    ok = Path("venv").exists()
    print("  Status  : OK" if ok else "  Status  : MISSING")
    if not ok:
        print("  Action  : python3 -m venv venv")
    return ok


def _read_env() -> str:
    env_path = Path(".env")
    if not env_path.exists():
        return ""
    return env_path.read_text(encoding="utf-8", errors="replace")


def check_env_file() -> bool:
    """Check .env and provider-specific key based on LLM_PROVIDER."""
    print("\nEnvironment Configuration:")

    env_path = Path(".env")
    if not env_path.exists():
        print("  Status  : MISSING")
        print("  Action  : cp .env.example .env")
        return False

    content = _read_env()

    provider = "openrouter"
    for line in content.splitlines():
        if line.strip().startswith("LLM_PROVIDER="):
            provider = line.split("=", 1)[1].strip().lower()
            break

    key_var = {
        "openrouter": "OPENROUTER_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "mancer": "MANCER_API_KEY",
    }.get(provider, "OPENROUTER_API_KEY")

    key_present = False
    for line in content.splitlines():
        if line.strip().startswith(f"{key_var}="):
            value = line.split("=", 1)[1].strip()
            if value and "your_" not in value and "_here" not in value:
                key_present = True
            break

    print(f"  Provider: {provider}")
    print(f"  Key var : {key_var}")
    print("  Key set : YES" if key_present else "  Key set : NO")

    if not key_present:
        print("  Note    : Set a real API key in .env before running production calls.")

    return True


def count_lines_of_code() -> int:
    total = 0
    for py_file in Path(".").rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            total += len(py_file.read_text(encoding="utf-8", errors="replace").splitlines())
        except Exception:
            pass
    return total


def print_summary() -> None:
    loc = count_lines_of_code()
    py_files = len(list(Path(".").rglob("*.py")))
    md_files = len(list(Path(".").rglob("*.md")))

    print("\n" + "=" * 70)
    print("Project Summary".center(70))
    print("=" * 70)
    print(f"\nLines of Python code : {loc:,}")
    print(f"Python files         : {py_files}")
    print(f"Markdown files       : {md_files}")


def main() -> int:
    print("\nEmotional RAG Backend - Verification\n")

    checks: List[bool] = []

    checks.append(check_python_version())
    passed, total = verify_project_structure()
    checks.append(passed == total)
    checks.append(check_virtual_env())
    checks.append(check_env_file())

    print_summary()

    print("\n" + "=" * 70)
    if all(checks):
        print("VERIFIED: installation looks good".center(70))
        print("=" * 70)
        print("\nNext steps:")
        print("  1. source venv/bin/activate")
        print("  2. ./run.sh")
        print("  3. curl http://localhost:8001/health")
        print("  4. Set SillyTavern API URL to http://localhost:8001/v1")
        return 0

    print("ISSUES FOUND: review output above".center(70))
    print("=" * 70)
    return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Verify project installation and structure.
Run this after setup to ensure everything is in place.
"""

import sys
import os
from pathlib import Path
from typing import List, Tuple


def check_file_exists(path: str) -> bool:
    """Check if file exists."""
    return Path(path).exists()


def check_directory_exists(path: str) -> bool:
    """Check if directory exists."""
    return Path(path).is_dir()


def verify_project_structure() -> Tuple[int, int]:
    """
    Verify all required files and directories exist.
    Returns (passed, total) counts.
    """
    checks = []
    
    # Core application files
    core_files = [
        ("app/__init__.py", "App package"),
        ("app/main.py", "FastAPI application"),
        ("app/core/config.py", "Configuration"),
        ("app/core/memory.py", "Memory manager"),
        ("app/core/token_manager.py", "Token manager"),
        ("app/models/chat.py", "Chat models"),
        ("app/models/memory.py", "Memory models"),
        ("app/services/gemini_client.py", "Gemini client"),
        ("app/services/rag_engine.py", "RAG engine"),
        ("app/services/emotion_tracker.py", "Emotion tracker"),
        ("app/routes/chat.py", "Chat routes"),
        ("app/routes/health.py", "Health routes"),
    ]
    
    # Configuration files
    config_files = [
        (".env.example", "Environment template"),
        ("requirements.txt", "Dependencies"),
        ("run.sh", "Startup script"),
        ("setup.py", "Setup script"),
    ]
    
    # Documentation files
    doc_files = [
        ("README.md", "Main documentation"),
        ("QUICKSTART.md", "Quick start guide"),
        ("ARCHITECTURE.md", "Architecture docs"),
        ("PROJECT_SUMMARY.md", "Project summary"),
        ("LICENSE", "License file"),
    ]
    
    # Test files
    test_files = [
        ("tests/test_memory.py", "Memory tests"),
        ("tests/test_emotion.py", "Emotion tests"),
        ("tests/test_api.py", "API tests"),
    ]
    
    # Example files
    example_files = [
        ("examples/test_usage.py", "Usage examples"),
    ]
    
    # Data directories
    directories = [
        ("app", "App directory"),
        ("app/core", "Core directory"),
        ("app/models", "Models directory"),
        ("app/services", "Services directory"),
        ("app/routes", "Routes directory"),
        ("tests", "Tests directory"),
        ("examples", "Examples directory"),
        ("data", "Data directory"),
        ("data/sessions", "Sessions directory"),
        ("data/embeddings", "Embeddings directory"),
        ("logs", "Logs directory"),
    ]
    
    print("=" * 70)
    print("Project Structure Verification".center(70))
    print("=" * 70)
    
    # Check core files
    print("\n📦 Core Application Files:")
    for file_path, description in core_files:
        exists = check_file_exists(file_path)
        checks.append(exists)
        icon = "✅" if exists else "❌"
        print(f"  {icon} {description:30s} {file_path}")
    
    # Check config files
    print("\n⚙️  Configuration Files:")
    for file_path, description in config_files:
        exists = check_file_exists(file_path)
        checks.append(exists)
        icon = "✅" if exists else "❌"
        print(f"  {icon} {description:30s} {file_path}")
    
    # Check documentation
    print("\n📚 Documentation:")
    for file_path, description in doc_files:
        exists = check_file_exists(file_path)
        checks.append(exists)
        icon = "✅" if exists else "❌"
        print(f"  {icon} {description:30s} {file_path}")
    
    # Check tests
    print("\n🧪 Tests:")
    for file_path, description in test_files:
        exists = check_file_exists(file_path)
        checks.append(exists)
        icon = "✅" if exists else "❌"
        print(f"  {icon} {description:30s} {file_path}")
    
    # Check examples
    print("\n💡 Examples:")
    for file_path, description in example_files:
        exists = check_file_exists(file_path)
        checks.append(exists)
        icon = "✅" if exists else "❌"
        print(f"  {icon} {description:30s} {file_path}")
    
    # Check directories
    print("\n📁 Directories:")
    for dir_path, description in directories:
        exists = check_directory_exists(dir_path)
        checks.append(exists)
        icon = "✅" if exists else "❌"
        print(f"  {icon} {description:30s} {dir_path}")
    
    # Summary
    passed = sum(checks)
    total = len(checks)
    
    print("\n" + "=" * 70)
    print(f"Results: {passed}/{total} checks passed")
    print("=" * 70)
    
    return passed, total


def check_python_version() -> bool:
    """Check Python version >= 3.10."""
    version = sys.version_info
    required = (3, 10)
    
    print("\n🐍 Python Version Check:")
    print(f"   Current: {version.major}.{version.minor}.{version.micro}")
    print(f"   Required: {required[0]}.{required[1]}+")
    
    if version >= required:
        print("   ✅ Python version OK")
        return True
    else:
        print("   ❌ Python version too old")
        return False


def check_virtual_env() -> bool:
    """Check if virtual environment exists."""
    print("\n🔧 Virtual Environment Check:")
    
    venv_exists = Path("venv").exists()
    if venv_exists:
        print("   ✅ Virtual environment found")
        return True
    else:
        print("   ❌ Virtual environment not found")
        print("   Run: python3 -m venv venv")
        return False


def check_env_file() -> bool:
    """Check if .env file is configured."""
    print("\n⚙️  Environment Configuration:")
    
    env_exists = Path(".env").exists()
    if not env_exists:
        print("   ❌ .env file not found")
        print("   Run: cp .env.example .env")
        return False
    
    # Check if GEMINI_API_KEY is set
    with open(".env", "r") as f:
        content = f.read()
        if "your_api_key_here" in content:
            print("   ⚠️  .env exists but GEMINI_API_KEY not configured")
            print("   Please edit .env and add your API key")
            return False
        elif "GEMINI_API_KEY=" in content:
            print("   ✅ .env configured")
            return True
    
    return False


def count_lines_of_code() -> int:
    """Count total lines of Python code."""
    total = 0
    for py_file in Path(".").rglob("*.py"):
        if "__pycache__" not in str(py_file):
            with open(py_file) as f:
                total += len(f.readlines())
    return total


def print_summary():
    """Print project summary."""
    loc = count_lines_of_code()
    
    print("\n" + "=" * 70)
    print("Project Summary".center(70))
    print("=" * 70)
    print(f"\n📊 Statistics:")
    print(f"   Lines of Code: {loc:,}")
    print(f"   Python Files: {len(list(Path('.').rglob('*.py')))}")
    print(f"   Documentation: {len(list(Path('.').rglob('*.md')))}")
    
    print(f"\n🎯 Features:")
    print(f"   ✅ OpenAI-compatible API")
    print(f"   ✅ Multi-tiered memory system")
    print(f"   ✅ RAG with semantic search")
    print(f"   ✅ Emotion tracking")
    print(f"   ✅ Token management")
    print(f"   ✅ Gemini integration")
    print(f"   ✅ Automatic summarization")
    print(f"   ✅ SillyTavern compatible")


def main():
    """Run all verification checks."""
    print("\n🔍 Emotional RAG Backend - Installation Verification\n")
    
    all_checks = []
    
    # Check Python version
    all_checks.append(check_python_version())
    
    # Check project structure
    passed, total = verify_project_structure()
    all_checks.append(passed == total)
    
    # Check virtual environment
    all_checks.append(check_virtual_env())
    
    # Check environment configuration
    env_ok = check_env_file()
    all_checks.append(env_ok)
    
    # Print summary
    print_summary()
    
    # Final verdict
    print("\n" + "=" * 70)
    if all(all_checks):
        print("✅ Installation Verified - Ready to Run!".center(70))
        print("=" * 70)
        print("\nNext steps:")
        print("  1. Activate virtual environment: source venv/bin/activate")
        print("  2. Start the server: ./run.sh")
        print("  3. Test: curl http://localhost:8000/health")
        print("  4. Configure SillyTavern to http://localhost:8000/v1")
        return 0
    else:
        print("⚠️  Installation Incomplete - Please Fix Issues Above".center(70))
        print("=" * 70)
        
        if not env_ok:
            print("\n⚠️  IMPORTANT: Configure .env file with your Gemini API key!")
        
        return 1


if __name__ == "__main__":
    sys.exit(main())

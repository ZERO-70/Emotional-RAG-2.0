#!/usr/bin/env python3
"""
Setup script for Emotional RAG Backend.
Automates installation and configuration.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def print_header(text):
    """Print formatted header."""
    print("\n" + "=" * 60)
    print(text.center(60))
    print("=" * 60 + "\n")


def print_step(step_num, text):
    """Print step number and description."""
    print(f"\n[{step_num}/6] {text}")
    print("-" * 60)


def run_command(cmd, description=""):
    """Run shell command and handle errors."""
    if description:
        print(f"  → {description}")
    
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"  ❌ Error: {result.stderr}")
        return False
    
    return True


def main():
    """Main setup function."""
    print_header("Emotional RAG Backend Setup")
    
    # Check Python version
    if sys.version_info < (3, 10):
        print("❌ Error: Python 3.10 or higher required")
        print(f"   Current version: {sys.version}")
        sys.exit(1)
    
    print(f"✅ Python version: {sys.version.split()[0]}")
    
    # Step 1: Check virtual environment
    print_step(1, "Virtual Environment")
    
    venv_path = Path("venv")
    if not venv_path.exists():
        print("  Creating virtual environment...")
        if not run_command(f"{sys.executable} -m venv venv", "Creating venv"):
            print("  ❌ Failed to create virtual environment")
            sys.exit(1)
        print("  ✅ Virtual environment created")
    else:
        print("  ✅ Virtual environment already exists")
    
    # Determine venv activation
    if sys.platform == "win32":
        pip_cmd = "venv\\Scripts\\pip"
        python_cmd = "venv\\Scripts\\python"
    else:
        pip_cmd = "venv/bin/pip"
        python_cmd = "venv/bin/python"
    
    # Step 2: Install dependencies
    print_step(2, "Installing Dependencies")
    
    print("  This may take a few minutes (downloading models)...")
    if not run_command(
        f"{pip_cmd} install --upgrade pip",
        "Upgrading pip"
    ):
        print("  ⚠️  Pip upgrade failed, continuing anyway...")
    
    if not run_command(
        f"{pip_cmd} install -r requirements.txt",
        "Installing packages"
    ):
        print("  ❌ Failed to install dependencies")
        sys.exit(1)
    
    print("  ✅ All dependencies installed")
    
    # Step 3: Create directories
    print_step(3, "Creating Data Directories")
    
    directories = [
        "data/sessions",
        "data/embeddings",
        "logs"
    ]
    
    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"  ✅ {dir_path}")
    
    # Step 4: Configure environment
    print_step(4, "Environment Configuration")
    
    env_file = Path(".env")
    if not env_file.exists():
        shutil.copy(".env.example", ".env")
        print("  ✅ Created .env from template")
        print("\n  ⚠️  IMPORTANT: Edit .env and add your GEMINI_API_KEY")
        
        # Try to open .env in default editor
        if sys.platform == "darwin":  # macOS
            os.system("open .env")
        elif sys.platform == "win32":  # Windows
            os.system("notepad .env")
        else:  # Linux
            print("\n  Run: nano .env")
    else:
        print("  ✅ .env already exists")
    
    # Step 5: Download embedding model
    print_step(5, "Downloading Embedding Model")
    
    print("  Downloading sentence-transformers model (~80MB)...")
    download_script = """
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
print('Model downloaded successfully')
"""
    
    with open("temp_download.py", "w") as f:
        f.write(download_script)
    
    if run_command(f"{python_cmd} temp_download.py"):
        print("  ✅ Embedding model ready")
    else:
        print("  ⚠️  Model will download on first use")
    
    os.remove("temp_download.py")
    
    # Step 6: Verify installation
    print_step(6, "Verifying Installation")
    
    checks = []
    
    # Check .env
    env_ok = env_file.exists()
    checks.append(("Environment file", env_ok))
    
    # Check directories
    dirs_ok = all(Path(d).exists() for d in directories)
    checks.append(("Data directories", dirs_ok))
    
    # Check venv
    venv_ok = venv_path.exists()
    checks.append(("Virtual environment", venv_ok))
    
    print()
    for check_name, status in checks:
        icon = "✅" if status else "❌"
        print(f"  {icon} {check_name}")
    
    # Final instructions
    print_header("Setup Complete!")
    
    print("Next steps:")
    print()
    print("1. Edit .env and add your Gemini API key:")
    print("   GEMINI_API_KEY=your_key_here")
    print()
    print("2. Activate virtual environment:")
    if sys.platform == "win32":
        print("   venv\\Scripts\\activate")
    else:
        print("   source venv/bin/activate")
    print()
    print("3. Start the server:")
    print("   ./run.sh")
    print("   OR")
    print("   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    print()
    print("4. Configure SillyTavern:")
    print("   - API: Custom (OpenAI-compatible)")
    print("   - URL: http://localhost:8000/v1")
    print("   - Model: gemini-1.5-pro")
    print()
    print("📚 For detailed instructions, see QUICKSTART.md")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Setup failed: {e}")
        sys.exit(1)

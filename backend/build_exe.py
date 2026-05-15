"""
Build script to create LohanDigitals.exe
Run: python build_exe.py
"""
import subprocess
import sys
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"
STATIC_DIR = BASE_DIR / "static"


def build_frontend():
    """Build Next.js frontend into static files."""
    print("=" * 50)
    print("Step 1: Building frontend...")
    print("=" * 50)

    # Install dependencies if needed
    if not (FRONTEND_DIR / "node_modules").exists():
        subprocess.run(["npm", "install"], cwd=str(FRONTEND_DIR), check=True)

    # Build static export
    subprocess.run(["npm", "run", "build"], cwd=str(FRONTEND_DIR), check=True)

    # Copy built files to backend/static
    out_dir = FRONTEND_DIR / "out"
    if not out_dir.exists():
        print("ERROR: Frontend build failed - no 'out' directory")
        sys.exit(1)

    if STATIC_DIR.exists():
        shutil.rmtree(STATIC_DIR)
    shutil.copytree(out_dir, STATIC_DIR)
    print(f"Frontend built: {sum(1 for _ in STATIC_DIR.rglob('*') if _.is_file())} files")


def build_exe():
    """Package with PyInstaller."""
    print("=" * 50)
    print("Step 2: Building executable...")
    print("=" * 50)

    # Install PyInstaller if needed
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "LohanDigitals",
        "--onedir",
        "--console",  # Show console for logs
        "--add-data", f"static;static",
        "--add-data", f"app;app",
        "--add-data", f"app/templates;app/templates",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.h11_impl",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "psd_tools",
        "--hidden-import", "pytoshop",
        "--hidden-import", "cv2",
        "--hidden-import", "numpy",
        "--hidden-import", "PIL",
        "--collect-all", "psd_tools",
        "--collect-all", "pytoshop",
        "run_app.py",
    ]

    subprocess.run(cmd, cwd=str(BASE_DIR), check=True)
    print("=" * 50)
    print("BUILD COMPLETE!")
    print(f"Executable: {BASE_DIR / 'dist' / 'LohanDigitals' / 'LohanDigitals.exe'}")
    print("=" * 50)


if __name__ == "__main__":
    build_frontend()
    build_exe()

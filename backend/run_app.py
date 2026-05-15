"""
LohanDigitals - Desktop Application Entry Point
Double-click this to start the app. Opens in your browser automatically.
"""
import sys
import os
import time
import threading
import webbrowser
from pathlib import Path

# Set working directory to the script's location
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    BASE_DIR = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(sys.executable).parent
    os.chdir(Path(sys.executable).parent)
else:
    BASE_DIR = Path(__file__).parent
    os.chdir(BASE_DIR)

PORT = 8001
URL = f"http://localhost:{PORT}"


def open_browser():
    """Wait for server to start, then open browser."""
    time.sleep(3)
    webbrowser.open(URL)


def main():
    print("=" * 50)
    print("  LohanDigitals - Album Generator")
    print("=" * 50)
    print(f"  Starting server on {URL}")
    print("  Opening browser...")
    print("  Close this window to stop the app.")
    print("=" * 50)

    # Open browser in background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Import the app directly (works in both dev and bundled mode)
    from app.main import app
    import uvicorn
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()

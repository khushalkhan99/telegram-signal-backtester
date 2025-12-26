import streamlit as st
import sys
import os

# Set page config FIRST
st.set_page_config(
    page_title="Telegram Backtester",
    page_icon="🚀",
    layout="wide"
)

# Add a visible element immediately
st.title("🚀 Telegram Signal Backtester")
st.write("Initializing application...")

# Then your existing code continues...
"""
🚀 Telegram Signal Backtester - Launcher
Beautiful Streamlit interface for crypto signal backtesting
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    print("🚀 Starting Telegram Signal Backtester...")
    print("📊 Beautiful Streamlit interface will open in your browser")
    print("🌐 If it doesn't open automatically, go to: http://localhost:8501")
    print("=" * 60)
    
    # Get the directory of this script
    script_dir = Path(__file__).resolve().parent
    streamlit_app = script_dir / "src" / "streamlit_app.py"
    
    if not streamlit_app.exists():
        print("❌ Error: streamlit_app.py not found!")
        print(f"Expected location: {streamlit_app}")
        return
    
    try:
        # Run streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            str(streamlit_app),
            "--server.port", "8501",
            "--server.address", "localhost",
            "--browser.gatherUsageStats", "false"
        ])
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error running Streamlit: {e}")

if __name__ == "__main__":
    main()


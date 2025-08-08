import os
import sys
import subprocess
import webbrowser
import time
import threading

def check_requirements():
    """Check if required packages are installed"""
    required_packages = ['flask', 'flask_socketio', 'psutil']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("Missing required packages:", missing_packages)
        print("Please run: python install_requirements.py")
        return False
    
    return True

def open_browser():
    """Open browser after a short delay"""
    time.sleep(3)  # Wait for server to start
    webbrowser.open('http://localhost:5000')

def main():
    """Main function to run the system monitor"""
    print("System Monitor Dashboard")
    print("=" * 50)
    
    # Check if requirements are installed
    if not check_requirements():
        return
    
    # Start browser opening in background
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    # Run the Flask application
    try:
        print("Starting System Monitor Dashboard...")
        print("Dashboard will open automatically in your browser")
        print("If it doesn't open, go to: http://localhost:5000")
        print("Press Ctrl+C to stop the server")
        print("-" * 50)
        
        # Import and run the app
        from app import app, socketio
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
        
    except KeyboardInterrupt:
        print("\nShutting down System Monitor Dashboard...")
    except Exception as e:
        print(f"Error starting the application: {e}")
        print("Make sure all requirements are installed by running: python install_requirements.py")

if __name__ == "__main__":
    main()

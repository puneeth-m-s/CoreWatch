import subprocess
import sys
import os

def install_requirements():
    """Install required packages for the system monitor"""
    requirements = [
        'Flask==2.3.3',
        'Flask-SocketIO==5.3.6',
        'psutil==5.9.6',
        'python-socketio==5.9.0',
        'python-engineio==4.7.1'
    ]
    
    print("Installing required packages for System Monitor Dashboard...")
    
    for package in requirements:
        try:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"✓ {package} installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to install {package}: {e}")
            return False
    
    print("\n✓ All packages installed successfully!")
    print("\nTo run the system monitor:")
    print("python app.py")
    print("\nThen open your browser to: http://localhost:5000")
    
    return True

if __name__ == "__main__":
    install_requirements()

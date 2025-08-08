from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import psutil
import json
import time
import threading
from datetime import datetime
import platform
import subprocess
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'system_monitor_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables for storing historical data
cpu_history = []
memory_history = []
disk_history = []
network_history = []
gpu_history = []
temperature_history = []
battery_history = []

# Alert thresholds
ALERT_THRESHOLDS = {
    'cpu_threshold': 95,
    'gpu_threshold': 95,
    'battery_threshold': 10,
    'temperature_threshold': 40
}

active_alerts = []

def get_gpu_info():
    """Get GPU information using nvidia-smi if available"""
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu', '--format=csv,noheader,nounits'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            gpus = []
            for i, line in enumerate(lines):
                parts = line.split(', ')
                if len(parts) >= 4:
                    gpus.append({
                        'id': i,
                        'utilization': float(parts[0]),
                        'memory_used': float(parts[1]),
                        'memory_total': float(parts[2]),
                        'temperature': float(parts[3])
                    })
            return gpus
    except:
        pass
    return []

def get_system_info():
    """Get comprehensive system information"""
    # CPU Information
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()
    
    # Memory Information
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    # Disk Information
    disk_usage = psutil.disk_usage('/')
    disk_io = psutil.disk_io_counters()
    
    # Network Information
    network_io = psutil.net_io_counters()
    
    # Temperature Information
    temperatures = {}
    try:
        temps = psutil.sensors_temperatures()
        for name, entries in temps.items():
            temperatures[name] = [{'label': entry.label or f'{name}_{i}', 'current': entry.current} 
                                for i, entry in enumerate(entries)]
    except:
        temperatures = {}
    
    # Battery Information
    battery = None
    try:
        battery_info = psutil.sensors_battery()
        if battery_info:
            battery = {
                'percent': battery_info.percent,
                'power_plugged': battery_info.power_plugged,
                'secsleft': battery_info.secsleft if battery_info.secsleft != psutil.POWER_TIME_UNLIMITED else None
            }
    except:
        pass
    
    # GPU Information
    gpu_info = get_gpu_info()
    
    return {
        'timestamp': datetime.now().isoformat(),
        'cpu': {
            'percent': cpu_percent,
            'count': cpu_count,
            'frequency': cpu_freq._asdict() if cpu_freq else None,
            'per_cpu': psutil.cpu_percent(percpu=True)
        },
        'memory': {
            'total': memory.total,
            'available': memory.available,
            'percent': memory.percent,
            'used': memory.used,
            'free': memory.free
        },
        'swap': {
            'total': swap.total,
            'used': swap.used,
            'free': swap.free,
            'percent': swap.percent
        },
        'disk': {
            'total': disk_usage.total,
            'used': disk_usage.used,
            'free': disk_usage.free,
            'percent': (disk_usage.used / disk_usage.total) * 100,
            'io': disk_io._asdict() if disk_io else None
        },
        'network': {
            'io': network_io._asdict() if network_io else None
        },
        'temperatures': temperatures,
        'battery': battery,
        'gpu': gpu_info,
        'system': {
            'platform': platform.platform(),
            'processor': platform.processor(),
            'architecture': platform.architecture(),
            'boot_time': psutil.boot_time()
        }
    }

def check_alerts(system_info):
    """Check for alert conditions and manage active alerts"""
    global active_alerts
    current_alerts = []
    
    # CPU Alert
    if system_info['cpu']['percent'] > ALERT_THRESHOLDS['cpu_threshold']:
        current_alerts.append({
            'type': 'cpu',
            'message': f"High CPU Usage: {system_info['cpu']['percent']:.1f}%",
            'severity': 'critical',
            'timestamp': datetime.now().isoformat()
        })
    
    # GPU Alert
    for gpu in system_info['gpu']:
        if gpu['utilization'] > ALERT_THRESHOLDS['gpu_threshold']:
            current_alerts.append({
                'type': 'gpu',
                'message': f"High GPU Usage: GPU {gpu['id']} at {gpu['utilization']:.1f}%",
                'severity': 'critical',
                'timestamp': datetime.now().isoformat()
            })
    
    # Battery Alert
    if system_info['battery'] and system_info['battery']['percent'] < ALERT_THRESHOLDS['battery_threshold']:
        current_alerts.append({
            'type': 'battery',
            'message': f"Low Battery: {system_info['battery']['percent']:.1f}%",
            'severity': 'warning',
            'timestamp': datetime.now().isoformat()
        })
    
    # Temperature Alert
    for sensor_name, sensors in system_info['temperatures'].items():
        for sensor in sensors:
            if sensor['current'] > ALERT_THRESHOLDS['temperature_threshold']:
                current_alerts.append({
                    'type': 'temperature',
                    'message': f"High Temperature: {sensor['label']} at {sensor['current']:.1f}°C",
                    'severity': 'warning',
                    'timestamp': datetime.now().isoformat()
                })
    
    # Update active alerts
    active_alerts = current_alerts
    return current_alerts

def background_monitoring():
    """Background thread for continuous monitoring"""
    while True:
        try:
            system_info = get_system_info()
            alerts = check_alerts(system_info)
            
            # Store historical data (keep last 100 points)
            global cpu_history, memory_history, disk_history, network_history, gpu_history, temperature_history, battery_history
            
            cpu_history.append({'timestamp': system_info['timestamp'], 'value': system_info['cpu']['percent']})
            memory_history.append({'timestamp': system_info['timestamp'], 'value': system_info['memory']['percent']})
            disk_history.append({'timestamp': system_info['timestamp'], 'value': system_info['disk']['percent']})
            
            if system_info['network']['io']:
                network_history.append({
                    'timestamp': system_info['timestamp'], 
                    'bytes_sent': system_info['network']['io']['bytes_sent'],
                    'bytes_recv': system_info['network']['io']['bytes_recv']
                })
            
            if system_info['gpu']:
                gpu_history.append({
                    'timestamp': system_info['timestamp'],
                    'gpus': [{'id': gpu['id'], 'utilization': gpu['utilization']} for gpu in system_info['gpu']]
                })
            
            if system_info['battery']:
                battery_history.append({'timestamp': system_info['timestamp'], 'value': system_info['battery']['percent']})
            
            # Keep only last 100 data points
            for history in [cpu_history, memory_history, disk_history, network_history, gpu_history, battery_history]:
                if len(history) > 100:
                    history.pop(0)
            
            # Emit real-time data to connected clients
            socketio.emit('system_update', {
                'system_info': system_info,
                'alerts': alerts,
                'history': {
                    'cpu': cpu_history[-20:],  # Last 20 points for charts
                    'memory': memory_history[-20:],
                    'disk': disk_history[-20:],
                    'network': network_history[-20:],
                    'gpu': gpu_history[-20:],
                    'battery': battery_history[-20:]
                }
            })
            
            time.sleep(2)  # Update every 2 seconds
        except Exception as e:
            print(f"Error in background monitoring: {e}")
            time.sleep(5)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/cpu')
def cpu_page():
    return render_template('cpu.html')

@app.route('/gpu')
def gpu_page():
    return render_template('gpu.html')

@app.route('/memory')
def memory_page():
    return render_template('memory.html')

@app.route('/network')
def network_page():
    return render_template('network.html')

@app.route('/disk')
def disk_page():
    return render_template('disk.html')

@app.route('/system')
def system_page():
    return render_template('system.html')

@app.route('/alerts')
def alerts_page():
    return render_template('alerts.html')

@app.route('/api/system-info')
def api_system_info():
    return jsonify(get_system_info())

@app.route('/api/alerts')
def api_alerts():
    return jsonify(active_alerts)

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    # Send initial data
    system_info = get_system_info()
    emit('system_update', {
        'system_info': system_info,
        'alerts': active_alerts,
        'history': {
            'cpu': cpu_history[-20:],
            'memory': memory_history[-20:],
            'disk': disk_history[-20:],
            'network': network_history[-20:],
            'gpu': gpu_history[-20:],
            'battery': battery_history[-20:]
        }
    })

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    # Start background monitoring thread
    monitoring_thread = threading.Thread(target=background_monitoring, daemon=True)
    monitoring_thread.start()
    
    print("System Monitor Dashboard starting...")
    print("Access the dashboard at: http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)

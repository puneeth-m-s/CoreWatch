import psutil
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import time
import threading
from datetime import datetime
import platform
import subprocess
import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
import csv

app = Flask(__name__)
app.config['SECRET_KEY'] = 'system_monitor_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global histories
cpu_history = []
memory_history = []
disk_history = []
network_history = []
gpu_history = []
temperature_history = []
battery_history = []
cpu_predictions = []

# Thread-safe globals for slow hardware info
prediction_lock = threading.Lock()
hardware_info_lock = threading.Lock()
gpu_info_global = []
temperatures_global = {}

# Alert thresholds
ALERT_THRESHOLDS = {
    'cpu_threshold': 95,
    'gpu_threshold': 95,
    'battery_threshold': 10,
    'temperature_threshold': 40
}

active_alerts = []

# ---------------------------
# GPU INFORMATION
# ---------------------------
def update_gpu_info():
    """Background thread to update GPU info.
    
    Updates happen every 10 seconds, but the first update is immediate.
    """
    global gpu_info_global
    
    def _get_gpu_info():
        try:
            # Check if nvidia-smi exists and is runnable
            subprocess.run(['nvidia-smi'], capture_output=True, check=True, timeout=5)
            
            # Get GPU details
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                gpus = []
                for i, line in enumerate(result.stdout.strip().split('\n')):
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
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # This is not an error, just a system without NVIDIA GPU
            return None
        except Exception as e:
            print(f"Could not query GPU info: {e}")
            return None
        return None

    # Perform an immediate update on startup
    initial_gpu_info = _get_gpu_info()
    if initial_gpu_info is None:
        print("NVIDIA GPU not found or nvidia-smi not available. GPU monitoring disabled.")
        return  # Exit the thread if no GPU

    with hardware_info_lock:
        gpu_info_global = initial_gpu_info

    # Then, loop for periodic updates
    while True:
        time.sleep(10) # Update every 10 seconds
        gpu_info = _get_gpu_info()
        if gpu_info is not None:
            with hardware_info_lock:
                gpu_info_global = gpu_info

def update_temperature_info():
    """Background thread to update temperature info.
    
    Updates happen every 10 seconds, but the first update is immediate.
    """
    global temperatures_global
    
    if not hasattr(psutil, 'sensors_temperatures'):
        print("Temperature monitoring not supported on this system. Monitoring disabled.")
        return # Exit the thread

    def _get_temp_info():
        try:
            temps = psutil.sensors_temperatures()
            temperatures = {}
            for name, entries in temps.items():
                temperatures[name] = [
                    {'label': entry.label or f'{name}_{i}', 'current': entry.current}
                    for i, entry in enumerate(entries)
                ]
            return temperatures
        except Exception as e:
            print(f"Could not update temperature info: {e}")
            return {}

    # Perform an immediate update on startup
    with hardware_info_lock:
        temperatures_global = _get_temp_info()

    # Then, loop for periodic updates
    while True:
        time.sleep(10) # Update every 10 seconds
        with hardware_info_lock:
            temperatures_global = _get_temp_info()


# ---------------------------
# SYSTEM INFORMATION
# ---------------------------
def get_system_info():
    # Get high-level stats first
    cpu_percent = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()

    # Get detailed info that is more expensive
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()
    
    # Optimized process fetching
    processes = []
    try:
        num_cores = psutil.cpu_count(logical=True)
        # Get top 5 processes by CPU
        all_procs = list(psutil.process_iter(['pid', 'name', 'cpu_percent']))
        top_procs = sorted(all_procs, key=lambda p: p.info['cpu_percent'], reverse=True)[:5]
        
        for proc in top_procs:
            try:
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'] or "Unknown",
                    'cpu_percent': round(proc.info['cpu_percent'] / num_cores, 2)
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        print(f"Could not retrieve top processes: {e}")

    swap = psutil.swap_memory()
    disk_usage = psutil.disk_usage('/')
    disk_io = psutil.disk_io_counters()
    network_io = psutil.net_io_counters()

    with hardware_info_lock:
        gpu_info = gpu_info_global
        temperatures = temperatures_global

    battery = None
    if hasattr(psutil, 'sensors_battery'):
        try:
            b = psutil.sensors_battery()
            if b:
                battery = {
                    'percent': b.percent,
                    'power_plugged': b.power_plugged,
                    'secsleft': b.secsleft if b.secsleft != psutil.POWER_TIME_UNLIMITED else None
                }
        except Exception:
            # Battery not found or error reading it
            pass

    return {
        'timestamp': datetime.now().isoformat(),
        'cpu': {
            'percent': cpu_percent,
            'count': cpu_count,
            'frequency': cpu_freq._asdict() if cpu_freq else None,
            'per_cpu': psutil.cpu_percent(percpu=True),
            'top_processes': processes
        },
        'memory': {
            'total': memory.total,
            'available': memory.available,
            'percent': memory.percent,
            'used': memory.used,
            'free': memory.free
        },
        'swap': swap._asdict(),
        'disk': {
            'total': disk_usage.total,
            'used': disk_usage.used,
            'free': disk_usage.free,
            'percent': (disk_usage.used / disk_usage.total) * 100,
            'io': disk_io._asdict() if disk_io else None
        },
        'network': {'io': network_io._asdict() if network_io else None},
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

# ---------------------------
# API: PER-PROCESS CPU USAGE
# ---------------------------
@app.route('/cpu_processes')
def cpu_processes():
    num_cores = psutil.cpu_count(logical=True)
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            proc.info['cpu_percent'] = round(proc.info['cpu_percent'] / num_cores, 2)
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    processes.sort(key=lambda p: p['cpu_percent'], reverse=True)
    return jsonify(processes)

# ---------------------------
# API: CPU PREDICTION (ARIMA)
# ---------------------------
@app.route('/cpu_prediction_arima')
def cpu_prediction_arima():
    """Predict next 10 CPU usage points using ARIMA."""
    if len(cpu_history) < 20:
        return jsonify({"error": "Not enough data for prediction"}), 400

    # Use the last 50 data points for faster prediction
    data = [p['value'] for p in cpu_history[-50:]]
    
    try:
        # Fit ARIMA model
        model = ARIMA(data, order=(5,1,0))
        model_fit = model.fit()
        
        # Forecast next 10 points
        forecast = model_fit.forecast(steps=10)
        
        return jsonify({"predictions": forecast.tolist()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------
# ALERT SYSTEM
# ---------------------------
def check_alerts(system_info):
    global active_alerts
    current_alerts = []

    if system_info['cpu']['percent'] > ALERT_THRESHOLDS['cpu_threshold']:
        current_alerts.append({
            'type': 'cpu',
            'message': f"High CPU Usage: {system_info['cpu']['percent']:.1f}%",
            'severity': 'critical',
            'timestamp': datetime.now().isoformat()
        })

    for gpu in system_info['gpu']:
        if gpu['utilization'] > ALERT_THRESHOLDS['gpu_threshold']:
            current_alerts.append({
                'type': 'gpu',
                'message': f"High GPU Usage: GPU {gpu['id']} at {gpu['utilization']:.1f}%",
                'severity': 'critical',
                'timestamp': datetime.now().isoformat()
            })

    if system_info['battery'] and system_info['battery']['percent'] < ALERT_THRESHOLDS['battery_threshold']:
        current_alerts.append({
            'type': 'battery',
            'message': f"Low Battery: {system_info['battery']['percent']:.1f}%",
            'severity': 'warning',
            'timestamp': datetime.now().isoformat()
        })

    for sensor_name, sensors in system_info['temperatures'].items():
        for sensor in sensors:
            if sensor['current'] > ALERT_THRESHOLDS['temperature_threshold']:
                current_alerts.append({
                    'type': 'temperature',
                    'message': f"High Temperature: {sensor['label']} at {sensor['current']:.1f}°C",
                    'severity': 'warning',
                    'timestamp': datetime.now().isoformat()
                })

    active_alerts = current_alerts
    return current_alerts

# ---------------------------
# BACKGROUND MONITORING THREAD
# ---------------------------
def predict_cpu_usage():
    """Predicts CPU usage in the background."""
    global cpu_predictions
    while True:
        if len(cpu_history) >= 20:
            with prediction_lock:
                try:
                    # Using a smaller dataset for prediction to speed it up
                    data = [p['value'] for p in cpu_history[-30:]]
                    model = ARIMA(data, order=(5, 1, 0))
                    model_fit = model.fit()
                    forecast = model_fit.forecast(steps=5) # Predict fewer steps
                    cpu_predictions = forecast.tolist()
                except Exception as e:
                    print(f"Error during prediction: {e}")
        time.sleep(30) # Predict every 30 seconds, was 3

def background_monitoring():
    # Prime the non-blocking cpu_percent call
    psutil.cpu_percent(interval=None)
    time.sleep(1)

    prediction_thread = threading.Thread(target=predict_cpu_usage, daemon=True)
    prediction_thread.start()

    while True:
        try:
            system_info = get_system_info()
            alerts = check_alerts(system_info)

            global cpu_history, memory_history, disk_history, network_history, gpu_history, battery_history

            cpu_history.append({'timestamp': system_info['timestamp'], 'value': system_info['cpu']['percent']})
            # Removed CSV writing from the hot path to reduce I/O latency
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

            for history in [cpu_history, memory_history, disk_history, network_history, gpu_history, battery_history]:
                if len(history) > 60: # Keep more history for better graphs
                    history.pop(0)

            with prediction_lock:
                current_predictions = cpu_predictions

            socketio.emit('system_update', {
                'system_info': system_info,
                'alerts': alerts,
                'history': {
                    'cpu': cpu_history[-30:], # Send last 30 points
                    'memory': memory_history[-30:],
                    'disk': disk_history[-30:],
                    'network': network_history[-30:],
                    'gpu': gpu_history[-30:],
                    'battery': battery_history[-30:],
                    'cpu_predictions': current_predictions
                }
            })

            time.sleep(1) # Update every 1 second, was 3
        except Exception as e:
            print(f"Error in background monitoring: {e}")
            time.sleep(5)

# ---------------------------
# PAGE ROUTES
# ---------------------------
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

# ---------------------------
# SOCKET.IO EVENTS
# ---------------------------
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    # Initial data emission can be simplified or removed if not needed
    # as the background thread will send data every 2 seconds.
    emit('initial_data', {
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

# ---------------------------
# MAIN
# ---------------------------
if __name__ == '__main__':
    # Start hardware monitoring threads
    gpu_thread = threading.Thread(target=update_gpu_info, daemon=True)
    gpu_thread.start()
    temp_thread = threading.Thread(target=update_temperature_info, daemon=True)
    temp_thread.start()

    monitoring_thread = threading.Thread(target=background_monitoring, daemon=True)
    monitoring_thread.start()
    print("System Monitor Dashboard starting...")
    print("Access at: http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)

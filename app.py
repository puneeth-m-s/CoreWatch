import psutil
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import time
import threading
from datetime import datetime
import platform
import subprocess

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
def get_gpu_info():
    """Fetch GPU info via nvidia-smi if available."""
    try:
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
    except:
        pass
    return []

# ---------------------------
# SYSTEM INFORMATION
# ---------------------------
def get_system_info():
    """Get system stats with top CPU processes."""
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()

    # Top CPU processes (normalized to 0–100%)
    num_cores = psutil.cpu_count(logical=True)
    processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            cpu_usage = proc.cpu_percent(interval=None) / num_cores
            processes.append({
                'pid': proc.info['pid'],
                'name': proc.info['name'] or "Unknown",
                'cpu_percent': round(cpu_usage, 2)
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    processes = sorted(processes, key=lambda p: p['cpu_percent'], reverse=True)[:10]

    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()

    disk_usage = psutil.disk_usage('/')
    disk_io = psutil.disk_io_counters()

    network_io = psutil.net_io_counters()

    temperatures = {}
    try:
        temps = psutil.sensors_temperatures()
        for name, entries in temps.items():
            temperatures[name] = [
                {'label': entry.label or f'{name}_{i}', 'current': entry.current}
                for i, entry in enumerate(entries)
            ]
    except:
        pass

    battery = None
    try:
        b = psutil.sensors_battery()
        if b:
            battery = {
                'percent': b.percent,
                'power_plugged': b.power_plugged,
                'secsleft': b.secsleft if b.secsleft != psutil.POWER_TIME_UNLIMITED else None
            }
    except:
        pass

    gpu_info = get_gpu_info()

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
    """Returns normalized CPU usage of all running processes."""
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
# ALERT SYSTEM
# ---------------------------
def check_alerts(system_info):
    """Check for alert conditions."""
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
def background_monitoring():
    """Background thread for continuous monitoring."""
    while True:
        try:
            system_info = get_system_info()
            alerts = check_alerts(system_info)

            global cpu_history, memory_history, disk_history, network_history, gpu_history, battery_history

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

            for history in [cpu_history, memory_history, disk_history, network_history, gpu_history, battery_history]:
                if len(history) > 100:
                    history.pop(0)

            socketio.emit('system_update', {
                'system_info': system_info,
                'alerts': alerts,
                'history': {
                    'cpu': cpu_history[-20:],
                    'memory': memory_history[-20:],
                    'disk': disk_history[-20:],
                    'network': network_history[-20:],
                    'gpu': gpu_history[-20:],
                    'battery': battery_history[-20:]
                }
            })

            time.sleep(2)
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

# ---------------------------
# MAIN
# ---------------------------
if __name__ == '__main__':
    monitoring_thread = threading.Thread(target=background_monitoring, daemon=True)
    monitoring_thread.start()
    print("System Monitor Dashboard starting...")
    print("Access at: http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)

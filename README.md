# System Monitor Dashboard

A comprehensive real-time system monitoring dashboard built with Python, Flask, and psutil. Monitor CPU, GPU, memory, disk, network, temperature, and battery status with beautiful charts and configurable alerts.

## Features

- **Real-time Monitoring**: Live updates every 2 seconds
- **Multi-page Dashboard**: Dedicated pages for different system components
- **Interactive Charts**: Beautiful charts using Chart.js
- **Alert System**: Configurable thresholds with notifications
- **GPU Support**: NVIDIA GPU monitoring (requires nvidia-smi)
- **Temperature Monitoring**: System temperature sensors
- **Battery Status**: Battery level and power status (laptops)
- **Network Activity**: Real-time network I/O monitoring
- **Responsive Design**: Works on desktop and mobile devices

## Screenshots

The dashboard provides multiple views:
- **Overview**: System summary with key metrics
- **CPU**: Detailed CPU usage and per-core monitoring
- **GPU**: GPU utilization and memory usage (NVIDIA)
- **Memory**: RAM and swap usage with breakdown
- **Disk**: Storage usage and I/O activity
- **Network**: Network traffic and statistics
- **System**: Detailed system information
- **Alerts**: Alert configuration and history

## Requirements

- Python 3.7+
- Flask 2.3.3
- Flask-SocketIO 5.3.6
- psutil 5.9.6
- NVIDIA GPU with nvidia-smi (optional, for GPU monitoring)

## Installation

1. **Install Requirements**:
   \`\`\`bash
   python install_requirements.py
   \`\`\`

2. **Run the Dashboard**:
   \`\`\`bash
   python run_monitor.py
   \`\`\`

   Or run directly:
   \`\`\`bash
   python app.py
   \`\`\`

3. **Access Dashboard**:
   Open your browser to `http://localhost:5000`

## Alert Configuration

The dashboard includes a configurable alert system with the following default thresholds:

- **CPU Usage**: > 95%
- **GPU Usage**: > 95% 
- **Battery Level**: < 10%
- **Temperature**: > 40°C

Alerts can be configured through the Alerts page in the dashboard.

## GPU Monitoring

GPU monitoring requires NVIDIA GPU with nvidia-smi installed:

- **Windows**: Included with NVIDIA drivers
- **Linux**: Install nvidia-utils package
- **macOS**: Not supported (no nvidia-smi)

If nvidia-smi is not available, GPU monitoring will be disabled.

## System Compatibility

- **Windows**: Full support including GPU and temperature monitoring
- **Linux**: Full support with proper drivers and sensors
- **macOS**: Basic monitoring (no GPU support)

## Architecture

The application uses:
- **Flask**: Web framework
- **Flask-SocketIO**: Real-time communication
- **psutil**: System information gathering
- **Chart.js**: Interactive charts
- **Bootstrap 5**: Responsive UI
- **Font Awesome**: Icons

## File Structure

\`\`\`
system-monitor/
├── app.py                 # Main Flask application
├── install_requirements.py # Package installer
├── run_monitor.py         # Application launcher
├── requirements.txt       # Python dependencies
├── templates/            # HTML templates
│   ├── base.html         # Base template
│   ├── index.html        # Dashboard overview
│   ├── cpu.html          # CPU monitoring
│   ├── gpu.html          # GPU monitoring
│   ├── memory.html       # Memory monitoring
│   ├── disk.html         # Disk monitoring
│   ├── network.html      # Network monitoring
│   ├── system.html       # System information
│   └── alerts.html       # Alert management
└── README.md             # This file
\`\`\`

## Customization

### Adding New Metrics

1. Modify `get_system_info()` in `app.py` to collect new data
2. Update the relevant HTML template to display the data
3. Add chart updates in the template's JavaScript section

### Changing Update Frequency

Modify the `time.sleep(2)` value in the `background_monitoring()` function in `app.py`.

### Custom Alert Thresholds

Update the `ALERT_THRESHOLDS` dictionary in `app.py` or use the web interface.

## Troubleshooting

### Common Issues

1. **GPU not detected**: Install NVIDIA drivers and nvidia-smi
2. **Temperature sensors not working**: Install lm-sensors (Linux) or check hardware support
3. **Permission errors**: Run with appropriate permissions for system monitoring
4. **Port already in use**: Change the port in `app.py` or stop other applications using port 5000

### Performance

The dashboard is designed to be lightweight, but monitoring frequency can be adjusted based on system resources.

## License

This project is open source and available under the MIT License.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

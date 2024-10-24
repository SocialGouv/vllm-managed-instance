from flask import Flask, render_template_string
import subprocess
import time

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>NVIDIA GPU Monitor</title>
    <style>
        body {
            font-family: monospace;
            padding: 20px;
            background-color: #1a1a1a;
            color: #ffffff;
        }
        pre {
            background-color: #2d2d2d;
            padding: 15px;
            border-radius: 5px;
            white-space: pre-wrap;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .refresh-time {
            color: #888;
            margin-bottom: 10px;
        }
    </style>
    <script>
        function refreshPage() {
            location.reload();
        }
        // Refresh every 2 seconds
        setInterval(refreshPage, 2000);
    </script>
</head>
<body>
    <div class="container">
        <h1>NVIDIA GPU Status</h1>
        <div class="refresh-time">Last updated: {{ timestamp }}</div>
        <pre>{{ nvidia_smi }}</pre>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    try:
        # Execute nvidia-smi on the host (this requires the command to be available)
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
        nvidia_output = result.stdout if result.returncode == 0 else "Error running nvidia-smi"
    except Exception as e:
        nvidia_output = f"Error: {str(e)}"
    
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    return render_template_string(HTML_TEMPLATE, nvidia_smi=nvidia_output, timestamp=timestamp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

# keep_alive.py
from flask import Flask, render_template_string
from threading import Thread
import datetime

app = Flask('')

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Discord Bot Status</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .container {
            text-align: center;
            padding: 40px;
            background: rgba(255,255,255,0.1);
            border-radius: 20px;
            backdrop-filter: blur(10px);
        }
        h1 { font-size: 2.5em; margin-bottom: 20px; }
        .status { 
            font-size: 1.2em; 
            padding: 10px 20px;
            background: #4CAF50;
            border-radius: 25px;
            display: inline-block;
        }
        .time { margin-top: 20px; opacity: 0.8; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Discord Translation Bot</h1>
        <div class="status">✅ Online & Running</div>
        <div class="time">Last checked: {{ time }}</div>
    </div>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE, time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/health')
def health():
    return "OK", 200

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
    return app

if __name__ == "__main__":
    run()

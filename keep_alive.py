from flask import Flask
from threading import Thread

app = Flask("")

@app.route("/")
def home():
    print("📡 Ping received")
    return "Bot is running!", 200

def run():
    app.run(host="0.0.0.0", port=5000)

def keep_alive():
    t = Thread(target=run)
    t.start()

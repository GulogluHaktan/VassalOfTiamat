import logging
from flask import Flask
from threading import Thread

app = Flask('')
logging.getLogger('werkzeug').setLevel(logging.ERROR)

@app.route('/')
def home():
    return "Vassal of Tiamat is active and running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

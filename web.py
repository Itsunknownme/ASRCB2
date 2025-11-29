from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "Telegram Forward Bot is running on Render!", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))  # Render gives PORT automatically
    app.run(host='0.0.0.0', port=port)

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import time
import os

app = Flask(__name__, template_folder="templates")

# Flask-SocketIO with async_mode="gevent"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route("/")
def home():
    return render_template("upload.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(file_path)

    socketio.start_background_task(target=process_file, file_path=file_path)
    return jsonify({"message": "File uploaded, processing started!"})

def process_file(file_path):
    """Simulates file processing with real-time updates."""
    for i in range(101):
        socketio.emit("progress", {"progress": i})
        time.sleep(0.1)

    socketio.emit("completed", {"message": "Processing complete!", "file": file_path})

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)

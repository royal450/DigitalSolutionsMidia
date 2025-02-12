from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO
import os
import time
import threading
from gtts import gTTS
from PyPDF2 import PdfReader
import eventlet

eventlet.monkey_patch()  # For WebSockets

app = Flask(__name__)
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

UPLOAD_FOLDER = "uploads"
MP3_FOLDER = "mp3_files"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(MP3_FOLDER, exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)
    
    thread = threading.Thread(target=convert_to_mp3, args=(file.filename,))
    thread.start()
    
    return jsonify({"message": "File uploaded successfully!", "filename": file.filename})

def convert_to_mp3(filename):
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    output_mp3 = os.path.join(MP3_FOLDER, filename.replace(".pdf", ".mp3"))
    
    pdf_reader = PdfReader(pdf_path)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    
    tts = gTTS(text, lang="en")
    tts.save(output_mp3)

    for i in range(101):
        socketio.emit("progress", {"progress": i})  # Real-time Progress
        time.sleep(0.1)

    socketio.emit("complete", {"mp3_url": f"/download/{filename.replace('.pdf', '.mp3')}"})

@app.route("/download/<filename>")
def download_file(filename):
    return send_file(os.path.join(MP3_FOLDER, filename), as_attachment=True)

if __name__ == "__main__":
    socketio.run(app, debug=True)

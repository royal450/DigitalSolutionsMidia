from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO
import time
import os
from PyPDF2 import PdfReader
from gtts import gTTS
from threading import Thread

app = Flask(__name__, template_folder="templates")
socketio = SocketIO(app, async_mode="eventlet")

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "mp3_files"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    # PDF को MP3 में Convert करने के लिए Background में Process स्टार्ट करो
    thread = Thread(target=convert_pdf_to_mp3, args=(file_path,))
    thread.start()

    return jsonify({"message": "File uploaded! Processing started."})

def convert_pdf_to_mp3(file_path):
    """PDF को MP3 में Convert करके Progress भेजना"""
    try:
        pdf_reader = PdfReader(file_path)
        text = " ".join(page.extract_text() for page in pdf_reader.pages if page.extract_text())
        
        # Output MP3 Path
        output_mp3 = os.path.join(OUTPUT_FOLDER, os.path.basename(file_path).replace(".pdf", ".mp3"))

        # Text को MP3 में Convert करो
        tts = gTTS(text=text, lang="en")
        tts.save(output_mp3)

        # Progress Send करो (100%)
        socketio.emit("progress", {"progress": 100, "file": output_mp3})
    
    except Exception as e:
        socketio.emit("error", {"message": str(e)})

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", debug=True)

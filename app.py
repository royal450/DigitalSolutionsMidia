import os
import time
import json
import requests
import pdfkit
import edge_tts
import asyncio
from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
ALLOWED_EXTENSIONS = {"pdf", "html", "txt", "text"}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER
socketio = SocketIO(app, cors_allowed_origins="*")

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

def extract_text(file_path, file_ext):
    extracted_text = ""
    if file_ext == "pdf":
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            for page in reader.pages:
                extracted_text += page.extract_text() + "\n"
    elif file_ext == "html":
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            extracted_text = soup.get_text()
    else:  # For txt or text files
        with open(file_path, "r", encoding="utf-8") as f:
            extracted_text = f.read()
    return extracted_text.strip()

async def generate_audio(text, language, voice, output_path):
    voice_map = {"Male": "en-US-GuyNeural", "Female": "en-US-JennyNeural"}
    voice_option = voice_map.get(voice, "en-US-JennyNeural")

    tts = edge_tts.Communicate(text, voice_option)
    await tts.save(output_path)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return {"error": "No file part"}, 400

    file = request.files["file"]
    if file.filename == "":
        return {"error": "No selected file"}, 400

    file_ext = file.filename.rsplit(".", 1)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return {"error": "Invalid file format"}, 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)

    sid = request.args.get("sid")
    socketio.emit("progress", {"progress": 10, "status": "Extracting text..."}, room=sid)

    extracted_text = extract_text(file_path, file_ext)
    
    if not extracted_text:
        return {"error": "No text found in file"}, 400

    socketio.emit("progress", {"progress": 30, "status": "Text extracted!"}, room=sid)

    language = request.form.get("language", "en-US")
    voice = request.form.get("voice", "Female")
    output_filename = filename.rsplit(".", 1)[0] + ".mp3"
    output_path = os.path.join(app.config["OUTPUT_FOLDER"], output_filename)

    socketio.emit("progress", {"progress": 50, "status": "Generating speech..."}, room=sid)

    asyncio.run(generate_audio(extracted_text, language, voice, output_path))

    socketio.emit("progress", {"progress": 90, "status": "Finalizing..."}, room=sid)
    time.sleep(1)
    socketio.emit("progress", {"progress": 100, "status": "Completed!"}, room=sid)

    return {"extracted_text": extracted_text, "mp3_file": output_filename}

@app.route("/output/<filename>")
def get_audio(filename):
    return send_from_directory(app.config["OUTPUT_FOLDER"], filename)

if __name__ == "__main__":
    socketio.run(app, debug=True)

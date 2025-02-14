import os
import pdfkit
import asyncio
import edge_tts
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

UPLOAD_FOLDER = "static/uploads"
OUTPUT_FOLDER = "static/output"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Real-time progress updates
def update_progress(sid, progress, status):
    socketio.emit("progress", {"progress": progress, "status": status}, room=sid)

# Extract text from file
def extract_text(file_path):
    text = ""
    if file_path.endswith(".pdf"):
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            text = " ".join([page.extract_text() for page in reader.pages if page.extract_text()])
    elif file_path.endswith(".html"):
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            text = soup.get_text()
    elif file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    return text.strip()

# Convert text to speech
async def text_to_speech(text, lang, voice, output_path):
    communicate = edge_tts.Communicate(text, voice, rate="+0%", volume="+0%", pitch="+0%", lang=lang)
    await communicate.save(output_path)

# File upload API
@app.route("/upload", methods=["POST"])
def upload_file():
    sid = request.args.get("sid")
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded!"})
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected!"})
    
    filename = file.filename
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)

    update_progress(sid, 20, "🔍 Extracting text...")
    extracted_text = extract_text(file_path)
    if not extracted_text:
        return jsonify({"error": "Failed to extract text!"})

    update_progress(sid, 50, "🎙 Generating speech...")
    output_mp3 = f"{os.path.splitext(filename)[0]}.mp3"
    output_path = os.path.join(OUTPUT_FOLDER, output_mp3)

    lang = request.form.get("language", "en-US")
    voice = request.form.get("voice", "en-US-JennyNeural")
    
    asyncio.run(text_to_speech(extracted_text, lang, voice, output_path))

    update_progress(sid, 100, "✅ Done!")

    return jsonify({"mp3_file": output_mp3, "extracted_text": extracted_text})

# Serve MP3 files
@app.route("/output/<filename>")
def serve_audio(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)

# Serve the frontend
@app.route("/")
def index():
    return render_template("index.html")

# Run Flask app with SocketIO
if __name__ == "__main__":
    socketio.run(app, debug=True)

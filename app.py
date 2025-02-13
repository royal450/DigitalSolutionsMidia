import os
import json
import shutil
import asyncio
import edge_tts
import requests
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup

# 📌 Flask App Initialization
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = "uploads"
app.config['OUTPUT_FOLDER'] = "output"
app.config['SECRET_KEY'] = "your_secret_key"

# 📌 Ensure Directories Exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# 📌 Allowed Extensions
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'html'}
LANGUAGE_VOICE_MAPPING = {
    "en-US": {"Male": "en-US-GuyNeural", "Female": "en-US-JennyNeural"},
    "hi-IN": {"Male": "hi-IN-MadhurNeural", "Female": "hi-IN-SwaraNeural"},
    "fr-FR": {"Male": "fr-FR-HenriNeural", "Female": "fr-FR-DeniseNeural"},
    "es-ES": {"Male": "es-ES-AlvaroNeural", "Female": "es-ES-ElviraNeural"},
    "zh-CN": {"Male": "zh-CN-YunyangNeural", "Female": "zh-CN-XiaoxiaoNeural"}
}

# 📌 Function to Check Allowed File Type
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 📌 Function to Extract Text from PDF
def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    return " ".join([page.extract_text() for page in reader.pages if page.extract_text()])

# 📌 Function to Extract Text from HTML
def extract_text_from_html(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
        return soup.get_text()

# 📌 Function to Extract Text from TXT
def extract_text_from_txt(txt_path):
    with open(txt_path, "r", encoding="utf-8") as f:
        return f.read()

# 📌 Function to Generate Audio with Edge TTS
async def generate_audio(text, lang, voice, output_path):
    voice_id = LANGUAGE_VOICE_MAPPING.get(lang, {}).get(voice, "en-US-JennyNeural")
    
    try:
        print(f"🔹 Generating audio at: {output_path}")
        tts = edge_tts.Communicate(text, voice=voice_id)
        await tts.save(output_path)
        print(f"✅ Audio saved successfully at: {output_path}")
    except Exception as e:
        print(f"❌ Error generating audio: {e}")

# 📌 Handle File Upload
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        extracted_text = ""
        if filename.endswith(".pdf"):
            extracted_text = extract_text_from_pdf(file_path)
        elif filename.endswith(".html"):
            extracted_text = extract_text_from_html(file_path)
        elif filename.endswith(".txt"):
            extracted_text = extract_text_from_txt(file_path)

        output_audio_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{os.path.splitext(filename)[0]}.mp3")

        # 📌 Generate Audio in Background
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(generate_audio(extracted_text, "en-US", "Female", output_audio_path))

        # Send the data to frontend with SocketIO
        socketio.emit("update_data", {
            "extracted_text": extracted_text,
            "mp3_file": os.path.basename(output_audio_path)
        }, broadcast=True)

        return jsonify({
            "extracted_text": extracted_text,
            "mp3_file": os.path.basename(output_audio_path)
        })

    return jsonify({"error": "Invalid file type"}), 400

# 📌 Serve Generated Audio Files
@app.route("/output/<filename>")
def serve_audio(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename, mimetype="audio/mpeg")

# 📌 Handle Real-Time Language & Voice Update
@socketio.on("update_language_voice")
def update_language_voice(data):
    lang = data.get("language", "en-US")
    voice = data.get("voice", "Female")
    socketio.emit("update_data", {"language": lang, "voice": voice}, broadcast=True)

    # Send highlighted text & generated audio file to all clients
    if 'extracted_text' in data and 'mp3_file' in data:
        socketio.emit("update_data", {
            "extracted_text": data["extracted_text"],
            "mp3_file": data["mp3_file"]
        }, broadcast=True)

# 📌 Handle Real-Time Text Highlighting & Audio Sync
@socketio.on("sync_audio_highlight")
def sync_audio_highlight(data):
    socketio.emit("highlight_word", data, broadcast=True)

# 📌 Serve index.html
@app.route("/")
def index():
    return render_template("index.html")

# 📌 Run Flask App
if __name__ == "__main__":
    socketio.run(app, debug=True)

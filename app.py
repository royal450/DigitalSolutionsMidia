import os
import json
import time
import asyncio
import edge_tts
import socketio
import tempfile
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup

app = Flask(__name__)
sio = SocketIO(app, cors_allowed_origins="*")  # Real-time support

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# 🔥 Function: Extract Text from PDF 🔥
def extract_text_from_pdf(file_path, sid):
    reader = PdfReader(file_path)
    total_pages = len(reader.pages)
    extracted_text = []
    
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            extracted_text.append(text)
        
        progress = int(((i + 1) / total_pages) * 100)
        sio.emit("progress", {"status": f"Processing Page {i+1}/{total_pages}", "progress": progress}, room=sid)
    
    return "\n".join(extracted_text)

# 🔥 Function: Extract Text from HTML 🔥
def extract_text_from_html(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        soup = BeautifulSoup(file, "html.parser")
    return soup.get_text()

# 🔥 Function: Convert Text to Speech (Edge TTS) 🔥
async def text_to_speech(text, output_file, sid):
    voice = "en-US-AriaNeural"
    tts = edge_tts.Communicate(text, voice)
    await tts.save(output_file)

    # 🎯 ऑडियो रेडी होने के बाद यूजर को भेजो
    sio.emit("audio_ready", {"url": f"/output/output.mp3"}, room=sid)
    sio.emit("progress", {"status": "✅ TTS Conversion Complete!", "progress": 100}, room=sid)

# 🔥 Upload & Process Route 🔥
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    file_ext = file.filename.split(".")[-1].lower()
    sid = request.args.get("sid")

    temp_file = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(temp_file)

    sio.emit("progress", {"status": "📤 File Uploaded, Processing Started...", "progress": 10}, room=sid)

    if file_ext == "pdf":
        extracted_text = extract_text_from_pdf(temp_file, sid)
    elif file_ext in ["html", "htm"]:
        extracted_text = extract_text_from_html(temp_file)
    else:
        extracted_text = file.read().decode("utf-8")

    sio.emit("progress", {"status": "🎤 Converting Text to Speech...", "progress": 50}, room=sid)

    output_mp3 = os.path.join(OUTPUT_FOLDER, "output.mp3")

    # ✅ Background Task को Async तरीके से Call कर रहे हैं
    asyncio.run(text_to_speech(extracted_text, output_mp3, sid))

    return jsonify({"extracted_text": extracted_text, "mp3_file": "output.mp3"})

# 🔥 Serve Output MP3 🔥
@app.route("/output/<filename>")
def serve_audio(filename):
    file_path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found!"}), 404
    return send_from_directory(OUTPUT_FOLDER, filename)

# 🔥 Home Route: Serve index.html 🔥
@app.route("/")
def index():
    return render_template("index.html")

# 🔥 Socket.IO Connection 🔥
@sio.on("connect")
def handle_connect():
    print("Client Connected")

@sio.on("disconnect")
def handle_disconnect():
    print("Client Disconnected")

# 🔥 Run Server 🔥
if __name__ == "__main__":
    sio.run(app, host="0.0.0.0", port=5000)

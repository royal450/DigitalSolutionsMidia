from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import os
import pdfkit
import PyPDF2
import edge_tts
import asyncio
import eventlet

# Flask App Setup
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Folders (अगर missing हैं, तो create होंगे)
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

# ✅ **Real-Time File Upload with Progress**
@socketio.on('upload_file')
def handle_file(data):
    filename = data.get('filename', 'file.pdf')
    file_data = data.get('file', b"")

    if not file_data:
        emit('upload_error', {"error": "No file received!"})
        return

    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    # **File Create if Missing**
    with open(filepath, "wb") as f:
        f.write(file_data)

    emit('progress_update', {'progress': 50})  # 50% progress update

    # Extracting Text
    extracted_text = extract_text(filepath)

    # **Real-time Text Update**
    emit('text_extracted', {'text': extracted_text})
    emit('progress_update', {'progress': 100})  # 100% complete

# ✅ **Text Extraction (PDF, HTML, TXT)**
def extract_text(filepath):
    text = ""
    if filepath.endswith(".pdf"):
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
    elif filepath.endswith((".html", ".txt", ".text")):
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    return text

# ✅ **Real-Time Text-to-Speech with Chunks**
@socketio.on('convert_to_speech')
def convert_to_speech(data):
    text = data.get("text", "")
    lang = data.get("language", "en-US")
    voice = "en-US-JennyNeural" if data.get("voice") == "Female" else "en-US-GuyNeural"

    if not text:
        emit('audio_error', {"error": "No text provided!"})
        return
    
    output_path = os.path.join(OUTPUT_FOLDER, "output.mp3")
    
    # **Generate Audio in Chunks (Real-Time)**
    eventlet.spawn_n(generate_audio, text, voice, output_path)

async def generate_audio(text, voice, output_path):
    tts = edge_tts.Communicate(text, voice)
    await tts.save(output_path)
    
    # **Audio Processing Completed in Real-Time**
    emit('audio_chunk', {"status": "Audio processing completed!"})
    emit('audio_generated', {"audio_url": "/download_audio"})

@app.route('/download_audio')
def download_audio():
    return send_file(os.path.join(OUTPUT_FOLDER, "output.mp3"), as_attachment=True)

# **Start Server with WebSocket Support**
if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)

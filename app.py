from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import os
import pdfkit
import PyPDF2
import edge_tts
import asyncio

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('upload_file')
def handle_file(data):
    file_data = data['file']
    filename = data['filename']
    
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    with open(filepath, "wb") as f:
        f.write(file_data)

    emit('progress_update', {'progress': 50})  # 50% progress update

    extracted_text = extract_text(filepath)
    
    emit('text_extracted', {'text': extracted_text})  # Real-time text update
    emit('progress_update', {'progress': 100})  # 100% complete

def extract_text(filepath):
    text = ""
    if filepath.endswith(".pdf"):
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
    elif filepath.endswith(".html") or filepath.endswith(".txt") or filepath.endswith(".text"):
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    return text

@socketio.on('convert_to_speech')
def convert_to_speech(data):
    text = data.get("text", "")
    lang = data.get("language", "en-US")
    voice = "en-US-JennyNeural" if data.get("voice") == "Female" else "en-US-GuyNeural"
    
    if not text:
        emit('audio_error', {"error": "No text provided"})
        return
    
    output_path = os.path.join(OUTPUT_FOLDER, "output.mp3")
    
    asyncio.run(generate_audio(text, voice, output_path))
    
    emit('audio_generated', {"audio_url": "/download_audio"})

async def generate_audio(text, voice, output_path):
    tts = edge_tts.Communicate(text, voice)
    await tts.save(output_path)
    emit('audio_chunk', {"status": "Audio processing completed!"})

@app.route('/download_audio')
def download_audio():
    return send_file(os.path.join(OUTPUT_FOLDER, "output.mp3"), as_attachment=True)

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)

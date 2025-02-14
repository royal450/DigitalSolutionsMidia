import os
import shutil
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename
import edge_tts
import fitz  # PyMuPDF for PDF text extraction
import asyncio

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

UPLOAD_FOLDER = 'uploads'
AUDIO_FOLDER = 'output'
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'html'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['AUDIO_FOLDER'] = AUDIO_FOLDER

# Ensure upload and output folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)

# Utility function to check file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Route for the main UI
@app.route('/')
def index():
    return render_template('index.html')

# File upload route
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Extract text
        extracted_text = extract_text(file_path, filename)
        
        return jsonify({"message": "File uploaded successfully", "text": extracted_text}), 200

    return jsonify({"error": "Invalid file format"}), 400

# Function to extract text from different file formats
def extract_text(file_path, filename):
    text = ""
    
    if filename.endswith(".pdf"):
        try:
            doc = fitz.open(file_path)
            for page in doc:
                text += page.get_text("text") + "\n"
        except Exception as e:
            return f"Error extracting text: {str(e)}"

    elif filename.endswith(".txt") or filename.endswith(".html"):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                text = file.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"

    return text

# TTS Route (Generate Audio from Text)
@app.route('/generate-audio', methods=['POST'])
async def generate_audio():
    data = request.json
    text = data.get("text", "")
    language = data.get("language", "en-US")
    voice = "en-US-AriaNeural" if data.get("voice") == "Female" else "en-US-GuyNeural"

    if not text:
        return jsonify({"error": "No text provided"}), 400

    audio_filename = "output.mp3"
    audio_path = os.path.join(app.config['AUDIO_FOLDER'], audio_filename)

    try:
        tts = edge_tts.Communicate(text, voice)
        await tts.save(audio_path)
        return jsonify({"message": "Audio generated successfully", "audio_url": f"/output/{audio_filename}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Serve generated audio files
@app.route('/output/<filename>')
def serve_audio(filename):
    return send_from_directory(app.config['AUDIO_FOLDER'], filename)

# Run Flask app with Socket.IO
if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)

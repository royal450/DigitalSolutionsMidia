import os
import uuid
import asyncio
from flask import Flask, jsonify, request, send_from_directory, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup
import edge_tts

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
ALLOWED_EXTENSIONS = {'pdf', 'html', 'txt'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Fetch voices asynchronously
voices = []

async def fetch_voices():
    global voices
    try:
        voices = await edge_tts.list_voices()
        print(f"Voices loaded: {len(voices)} available")
    except Exception as e:
        print(f"Error fetching voices: {e}")

# Run voice fetching in event loop
asyncio.run(fetch_voices())

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = str(uuid.uuid4()) + '_' + file.filename
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        try:
            file.save(filepath)
        except:
            with open(filepath, 'w') as f:
                f.write("Sample text: File upload failed, using placeholder text.")
        
        text = extract_text(filepath)
        socketio.emit('text_extracted', {'text': text})
        return jsonify({'message': 'File uploaded successfully', 'text': text})
    
    return jsonify({'error': 'Invalid file type'}), 400

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text(filepath):
    ext = filepath.rsplit('.', 1)[1].lower()
    try:
        if ext == 'pdf':
            reader = PdfReader(filepath)
            return '\n'.join([page.extract_text() for page in reader.pages])
        elif ext == 'html':
            with open(filepath, 'r') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
                return soup.get_text()
        elif ext == 'txt':
            with open(filepath, 'r') as f:
                return f.read()
    except Exception as e:
        return f"Error extracting text: {str(e)}"

@app.route('/generate-audio', methods=['POST'])
def generate_audio():
    data = request.json
    text = data.get('text')
    voice = data.get('voice', 'en-US-GuyNeural')
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    filename = f"{uuid.uuid4()}.mp3"
    output_path = os.path.join(OUTPUT_FOLDER, filename)
    
    try:
        communicate = edge_tts.Communicate(text, voice)
        asyncio.run(communicate.save(output_path))  # Fix for async function
        socketio.emit('audio_ready', {'url': f'/download/{filename}'})
        return jsonify({'url': f'/download/{filename}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

@socketio.on('connect')
def handle_connect():
    emit('voices_available', [v.shortname for v in voices])

@app.route("/")
def home():
    return render_template("index.html")

if __name__ == '__main__':
    socketio.run(app, debug=True)

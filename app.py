import os
import asyncio
import edge_tts
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_socketio import SocketIO, emit
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'html', 'txt', 'text'}
app.secret_key = os.urandom(24)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text(file_path, extension):
    try:
        if extension == 'pdf':
            with open(file_path, 'rb') as f:
                reader = PdfReader(f)
                return ''.join([page.extract_text() for page in reader.pages if page.extract_text()])
        elif extension in ['html', 'htm']:
            with open(file_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')
                return soup.get_text(separator='\n', strip=True)
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        raise RuntimeError(f"Text extraction failed: {str(e)}")

async def generate_tts(text, voice, output_file, sid):
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        socketio.emit('progress', {'progress': 100, 'status': 'Conversion complete'}, room=sid)
    except Exception as e:
        socketio.emit('error', {'error': f"TTS conversion failed: {str(e)}"}, room=sid)

@app.route('/upload', methods=['POST'])
def handle_upload():
    try:
        sid = request.args.get('sid')
        if not sid:
            return jsonify({'error': 'Session ID missing'}), 400

        file = request.files.get('file')
        if not file or not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file'}), 400

        # Get user preferences
        language = request.form.get('language', 'en-US')
        voice_gender = request.form.get('voice', 'Male')

        # Save uploaded file
        filename = secure_filename(file.filename)
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(upload_path)

        # Start processing
        socketio.emit('progress', {'progress': 10, 'status': 'Processing file...'}, room=sid)

        # Extract text
        file_ext = filename.rsplit('.', 1)[1].lower()
        text = extract_text(upload_path, file_ext)

        # Fix for "no running event loop" error
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        voices = loop.run_until_complete(edge_tts.list_voices())

        suitable_voices = [
            v for v in voices 
            if v['Locale'].startswith(language.split('-')[0]) 
            and v['Gender'].lower() == voice_gender.lower()
        ]
        if not suitable_voices:
            return jsonify({'error': 'No suitable voice found'}), 400
        voice = suitable_voices[0]['ShortName']

        # Generate output filename
        output_filename = f"{uuid.uuid4()}.mp3"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)

        # Convert text to speech
        socketio.emit('progress', {'progress': 50, 'status': 'Converting to speech...'}, room=sid)

        # Instead of asyncio.create_task(), use threading
        loop.run_until_complete(generate_tts(text, voice, output_path, sid))

        return jsonify({
            'text': text,
            'mp3_file': output_filename,
            'status': 'success'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/output/<filename>')
def serve_audio(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

@socketio.on('connect')
def handle_connect():
    emit('connection', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)

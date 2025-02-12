from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from gtts import gTTS
from PyPDF2 import PdfReader

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ✅ Home Route Fix
@app.route('/')
def home():
    return jsonify({"message": "PDF to MP3 Converter API is Live!"})

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file selected!"})

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected!"})

    if file and file.filename.endswith('.pdf'):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)

        # PDF से Text निकालो
        pages_text = extract_text_from_pdf(file_path)

        # Text को Audio में बदलो
        mp3_files = convert_text_to_speech(pages_text)

        return jsonify({"mp3_files": mp3_files})

    return jsonify({"error": "Invalid file format!"})

def extract_text_from_pdf(pdf_path):
    pages_text = []
    with open(pdf_path, "rb") as file:
        reader = PdfReader(file)
        for page in reader.pages:
            pages_text.append(page.extract_text().strip() if page.extract_text() else '')
    return pages_text

def convert_text_to_speech(pages_text):
    mp3_files = []
    for i, page_text in enumerate(pages_text, start=1):
        if not page_text:
            continue

        tts = gTTS(text=page_text, lang='en')
        filename = f"page_{i}.mp3"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
        tts.save(output_path)
        mp3_files.append(filename)

    return mp3_files

@app.route('/output/<filename>')
def serve_audio(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)

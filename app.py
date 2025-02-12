from flask import Flask, render_template, request, jsonify
import os
from gtts import gTTS
from PyPDF2 import PdfReader

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    return [page.extract_text() for page in reader.pages]

def convert_text_to_speech(text_list):
    mp3_files = []
    for i, text in enumerate(text_list):
        tts = gTTS(text, lang='en')
        mp3_file = f"output_{i}.mp3"
        tts.save(os.path.join(OUTPUT_FOLDER, mp3_file))
        mp3_files.append(mp3_file)
    return mp3_files

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file selected!"})

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected!"})

    if file and file.filename.endswith('.pdf'):
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)

        pages_text = extract_text_from_pdf(file_path)
        extracted_text = " ".join(pages_text)

        mp3_files = convert_text_to_speech(pages_text)

        return jsonify({
            "mp3_files": [f"/output/{mp3}" for mp3 in mp3_files],
            "extracted_text": extracted_text
        })

    return jsonify({"error": "Invalid file format!"})

if __name__ == '__main__':
    app.run(debug=True)

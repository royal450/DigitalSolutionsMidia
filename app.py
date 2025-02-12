from flask import Flask, render_template, request, send_from_directory, jsonify
import os
from gtts import gTTS
from PyPDF2 import PdfReader
import time

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
STATUS_FILE = "status.txt"

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def update_status(status, progress):
    with open(STATUS_FILE, "w") as f:
        f.write(f"{status}|{progress}")

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
        try:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            update_status(f"📂 File uploaded: {file.filename}", 5)
            time.sleep(1)

            update_status("🔍 Extracting text from PDF...", 15)
            pages_text = extract_text_from_pdf(file_path)

            update_status("🎤 Converting text to speech...", 50)
            mp3_files = convert_text_to_speech(pages_text)

            update_status("✅ Conversion complete!", 100)

            return jsonify({"mp3_files": mp3_files})

        except Exception as e:
            return jsonify({"error": str(e)})

    return jsonify({"error": "Invalid file format!"})

@app.route('/status')
def get_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r") as f:
            status, progress = f.read().split("|")
            return jsonify({"status": status, "progress": int(progress)})
    return jsonify({"status": "Idle", "progress": 0})

def extract_text_from_pdf(pdf_path):
    pages_text = []
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)

    for page_num, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ''
        pages_text.append(page_text.strip())

        progress = int((page_num / total_pages) * 100)
        update_status(f"📖 Extracting text from page {page_num}/{total_pages}", progress)
        time.sleep(1)

    return pages_text

def convert_text_to_speech(pages_text):
    mp3_files = []
    total_pages = len(pages_text)

    for page_num, page_text in enumerate(pages_text, start=1):
        if not page_text:
            continue
        try:
            tts = gTTS(text=page_text, lang='en')
            filename = f"page_{page_num}.mp3"
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
            tts.save(output_path)
            mp3_files.append(filename)

            progress = int((page_num / total_pages) * 100)
            update_status(f"🔊 Generating audio for page {page_num}/{total_pages}", progress)
            time.sleep(1)

        except Exception as e:
            print(f"Error processing page {page_num}: {str(e)}")

    return mp3_files

@app.route('/output/<path:filename>')
def serve_audio(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)




from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import time
from gtts import gTTS
from PyPDF2 import PdfReader
import threading

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
STATUS_FILE = "status.txt"

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# 🔹 Update Progress Status
def update_status(status, progress):
    with open(STATUS_FILE, "w") as f:
        f.write(f"{status}|{progress}")

# 🔹 Delete Old Files
def clear_old_files():
    for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            try:
                os.remove(file_path)
            except Exception:
                pass

# 🔹 Extract Text from PDF, HTML, or TXT
def extract_text(file_path):
    text = ""
    if file_path.endswith('.pdf'):
        reader = PdfReader(file_path)
        text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    elif file_path.endswith('.txt'):
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    elif file_path.endswith('.html'):
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    return text.strip()

# 🔹 Convert Text to Speech (TTS)
def convert_to_speech(text, output_filename):
    tts = gTTS(text, lang="hi")  # Hindi Support
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)
    tts.save(output_path)
    return output_path

@app.route('/')
def index():
    return render_template('index.html')

# 🔹 Handle File Upload & Processing
@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file selected!"})

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected!"})

    if file and file.filename.endswith(('.pdf', '.txt', '.html')):
        try:
            clear_old_files()
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)

            update_status(f"📂 File uploaded: {file.filename}", 5)
            time.sleep(1)

            update_status("🔍 Extracting text...", 15)
            extracted_text = extract_text(file_path)

            update_status("🎤 Converting to speech...", 50)
            audio_file = convert_to_speech(extracted_text, "output.mp3")

            update_status("✅ Conversion complete!", 100)

            return jsonify({
                "mp3_file": "output.mp3",
                "extracted_text": extracted_text
            })

        except Exception as e:
            return jsonify({"error": str(e)})

    return jsonify({"error": "Invalid file format!"})

# 🔹 Serve Downloadable MP3 File
@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)

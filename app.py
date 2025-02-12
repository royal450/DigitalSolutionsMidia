from flask import Flask, render_template, request, jsonify, send_from_directory
import os
from gtts import gTTS
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup
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
    """Updates the status file for frontend progress tracking."""
    with open(STATUS_FILE, "w") as f:
        f.write(f"{status}|{progress}")

def extract_text_from_pdf(pdf_path):
    """Extracts text from a PDF file."""
    text = []
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            extracted_text = page.extract_text() or ""
            text.append(extracted_text)
        return text
    except Exception as e:
        print("Error extracting text from PDF:", e)
        return []

def extract_text_from_txt(txt_path):
    """Extracts text from a TXT file."""
    try:
        with open(txt_path, 'r', encoding='utf-8') as file:
            return file.read().splitlines()
    except Exception as e:
        print("Error extracting text from TXT:", e)
        return []

def extract_text_from_html(html_path):
    """Extracts text from an HTML file."""
    try:
        with open(html_path, 'r', encoding='utf-8') as file:
            soup = BeautifulSoup(file, 'html.parser')
            text = soup.get_text(separator="\n")
            return text.splitlines()
    except Exception as e:
        print("Error extracting text from HTML:", e)
        return []

def convert_text_to_speech(text_list):
    """Converts extracted text to speech and saves MP3 files."""
    mp3_files = []
    for i, text in enumerate(text_list):
        if text.strip():
            try:
                tts = gTTS(text, lang="en")
                mp3_filename = f"output_{i}.mp3"
                mp3_path = os.path.join(app.config['OUTPUT_FOLDER'], mp3_filename)
                tts.save(mp3_path)
                mp3_files.append(mp3_filename)
                update_status(f"Converting section {i+1} to speech...", int((i+1)/len(text_list) * 100))
                time.sleep(1)  # Simulate processing delay
                print(f"✅ Saved: {mp3_path}")
            except Exception as e:
                print(f"Error converting section {i+1} to speech:", e)
    return mp3_files

@app.route('/')
def index():
    """Serves the frontend."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    """Handles file upload, text extraction, and TTS conversion."""
    if 'file' not in request.files or request.files['file'].filename == '':
        return jsonify({"error": "No file selected!"})

    file = request.files['file']
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    update_status(f"File uploaded: {file.filename}", 5)
    time.sleep(1)

    extracted_text = ""
    if file.filename.endswith('.pdf'):
        update_status("Extracting text from PDF...", 15)
        extracted_text = "\n\n".join(extract_text_from_pdf(file_path))
    elif file.filename.endswith('.txt'):
        update_status("Extracting text from TXT...", 15)
        extracted_text = "\n\n".join(extract_text_from_txt(file_path))
    elif file.filename.endswith('.html'):
        update_status("Extracting text from HTML...", 15)
        extracted_text = "\n\n".join(extract_text_from_html(file_path))
    else:
        return jsonify({"error": "Unsupported file format!"})

    if not extracted_text.strip():
        return jsonify({"error": "No readable text found in the file!"})

    update_status("Converting text to speech...", 50)
    mp3_files = convert_text_to_speech(extracted_text.splitlines())

    update_status("Conversion complete!", 100)

    return jsonify({
        "mp3_files": mp3_files,
        "extracted_text": extracted_text
    })

@app.route('/download/<filename>')
def download(filename):
    """Serves the generated MP3 files for download."""
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_from_directory(app.config['OUTPUT_FOLDER'], filename)
    return jsonify({"error": "File not found!"}), 404

@app.route('/status')
def get_status():
    """Returns processing status."""
    try:
        with open(STATUS_FILE, "r") as f:
            status, progress = f.read().split("|")
        return jsonify({"status": status, "progress": int(progress)})
    except:
        return jsonify({"status": "Initializing...", "progress": 0})

if __name__ == '__main__':
    app.run(debug=True)

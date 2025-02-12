from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import time
from gtts import gTTS
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup

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

def extract_text_from_pdf(pdf_path):
    text = []
    reader = PdfReader(pdf_path)
    for page in reader.pages:
        text.append(page.extract_text() or "")
    return text

def extract_text_from_txt(txt_path):
    with open(txt_path, 'r', encoding='utf-8') as file:
        return file.read().splitlines()

def extract_text_from_html(html_path):
    with open(html_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'html.parser')
        text = soup.get_text(separator="\n")
        return text.splitlines()

def convert_text_to_speech(text_list):
    mp3_files = []
    for i, text in enumerate(text_list):
        if text.strip():
            tts = gTTS(text, lang="en")
            mp3_filename = f"output_{i}.mp3"
            mp3_path = os.path.join(app.config['OUTPUT_FOLDER'], mp3_filename)
            tts.save(mp3_path)
            mp3_files.append(mp3_filename)
            update_status(f"Converting page {i+1} to speech...", int((i+1)/len(text_list) * 100))
            time.sleep(1)
    return mp3_files

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files or request.files['file'].filename == '':
        return jsonify({"error": "No file selected!"})

    file = request.files['file']
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)
    
    update_status(f"File uploaded: {file.filename}", 5)
    time.sleep(1)

    if file.filename.endswith('.pdf'):
        update_status("Extracting text from PDF...", 15)
        pages_text = extract_text_from_pdf(file_path)
        extracted_text = "\n\n".join(pages_text)
    elif file.filename.endswith('.txt'):
        update_status("Extracting text from TXT...", 15)
        extracted_text = "\n\n".join(extract_text_from_txt(file_path))
    elif file.filename.endswith('.html'):
        update_status("Extracting text from HTML...", 15)
        extracted_text = "\n\n".join(extract_text_from_html(file_path))
    else:
        return jsonify({"error": "Unsupported file format!"})

    update_status("Converting text to speech...", 50)
    mp3_files = convert_text_to_speech(extracted_text.splitlines())

    update_status("✅ Conversion complete!", 100)

    return jsonify({
        "mp3_files": mp3_files,
        "extracted_text": extracted_text
    })

@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

@app.route('/status')
def get_status():
    try:
        with open(STATUS_FILE, "r") as f:
            status, progress = f.read().split("|")
        return jsonify({"status": status, "progress": int(progress)})
    except:
        return jsonify({"status": "Initializing...", "progress": 0})

if __name__ == '__main__':
    app.run(debug=True)

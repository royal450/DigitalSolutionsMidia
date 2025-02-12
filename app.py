from flask import Flask, render_template, request, jsonify, send_from_directory
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

def clear_old_files():
    # Delete previous PDF files
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        if filename.endswith('.pdf'):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Error deleting file {filename}: {e}")

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
            # Clear previous files
            clear_old_files()
            
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            update_status(f"📂 File uploaded: {file.filename}", 5)
            time.sleep(1)

            update_status("🔍 Extracting text from PDF...", 15)
            pages_text = extract_text_from_pdf(file_path)
            extracted_text = "\n".join(pages_text)

            update_status("🎤 Converting text to speech...", 50)
            mp3_files = convert_text_to_speech(pages_text)

            update_status("✅ Conversion complete!", 100)

            return jsonify({
                "mp3_files": mp3_files,
                "extracted_text": extracted_text
            })

        except Exception as e:
            return jsonify({"error": str(e)})

    return jsonify({"error": "Invalid file format!"})

@app.route('/send_text', methods=['POST'])
def receive_text():
    data = request.get_json()
    text = data.get('text', '')
    # Add your custom processing logic here
    return jsonify({
        "received_text": text,
        "message": "Text received successfully!"
    })

# ... (Keep other existing functions same as original code)

if __name__ == '__main__':
    app.run(debug=True)

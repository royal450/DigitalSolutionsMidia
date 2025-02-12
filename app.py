from flask import Flask, request, jsonify, send_from_directory
import os
from gtts import gTTS
from PyPDF2 import PdfReader  # For PDF text extraction

app = Flask(__name__)

# Ensure the upload and output directories exist
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

@app.route('/')
def index():
    return "PDF to MP3 Backend is running!"

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # Save the uploaded file
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    # Extract text from the PDF
    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
    except Exception as e:
        return jsonify({"error": f"Failed to extract text from PDF: {str(e)}"}), 500

    # Convert text to MP3 using gTTS
    mp3_filename = file.filename.replace('.pdf', '.mp3')
    mp3_path = os.path.join(app.config['OUTPUT_FOLDER'], mp3_filename)
    tts = gTTS(text)
    tts.save(mp3_path)

    # Return the extracted text and MP3 file name
    return jsonify({
        "text": text,
        "mp3_files": [mp3_filename]
    })

@app.route('/output/<filename>')
def download_file(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)

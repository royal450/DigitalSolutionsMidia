from flask import Flask, render_template, request, send_from_directory, jsonify
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

ALLOWED_EXTENSIONS = {'pdf', 'html', 'txt', 'text'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def update_status(status, progress, extracted_text=""):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        f.write(f"{status}|{progress}|{extracted_text}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "कोई फ़ाइल अपलोड नहीं की गई!"})

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "कोई फ़ाइल चयनित नहीं है!"})

    if not allowed_file(file.filename):
        return jsonify({"error": "अमान्य फ़ाइल प्रारूप! केवल PDF, HTML और TXT समर्थित हैं।"})

    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)
        update_status(f"📤 फ़ाइल अपलोड हो रही है: {file.filename}", 5)
        time.sleep(1)

        update_status("🔍 पाठ निकाल रहा है...", 15)
        extracted_text = extract_text(file_path, file.filename)

        if not extracted_text.strip():
            return jsonify({"error": "फ़ाइल में कोई पठनीय सामग्री नहीं मिली!"})

        update_status("🎤 पाठ को आवाज़ में परिवर्तित कर रहा है...", 50, extracted_text)

        # Convert text to Hindi speech
        mp3_files = convert_text_to_speech(extracted_text, lang='hi')  # Hindi language

        update_status("✅ रूपांतरण पूरा हुआ!", 100, extracted_text)

        return jsonify({"mp3_files": mp3_files, "extracted_text": extracted_text})

    except Exception as e:
        return jsonify({"error": f"त्रुटि: {str(e)}"})

@app.route('/status')
def get_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            data = f.read().split("|")
            status = data[0]
            progress = int(data[1])
            extracted_text = data[2] if len(data) > 2 else ""
            return jsonify({"status": status, "progress": progress, "extracted_text": extracted_text})
    return jsonify({"status": "Idle", "progress": 0, "extracted_text": ""})

def extract_text(file_path, filename):
    extracted_text = ""

    try:
        if filename.endswith('.pdf'):
            reader = PdfReader(file_path)
            extracted_text = "\n".join([page.extract_text() or '' for page in reader.pages])

        elif filename.endswith('.html'):
            with open(file_path, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")
                extracted_text = soup.get_text()

        elif filename.endswith(('.txt', '.text')):
            with open(file_path, "r", encoding="utf-8") as f:
                extracted_text = f.read()

    except Exception as e:
        print(f"Text extraction error: {str(e)}")
    
    return extracted_text.strip()

def convert_text_to_speech(text, lang='hi'):
    mp3_files = []
    
    if text:
        try:
            tts = gTTS(text=text, lang=lang)  # Set language to Hindi
            filename = "output.mp3"
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
            tts.save(output_path)
            mp3_files.append(filename)
        except Exception as e:
            print(f"Error during TTS conversion: {str(e)}")

    return mp3_files

@app.route('/output/<path:filename>')
def serve_audio(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True, port=5000)

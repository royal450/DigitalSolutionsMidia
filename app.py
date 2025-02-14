import os
import uuid
import asyncio
import PyPDF2
import edge_tts
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify, send_from_directory, url_for
from flask_cors import CORS
from flask_socketio import SocketIO

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

UPLOAD_FOLDER = 'static/uploads'
OUTPUT_FOLDER = 'static/output'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# 📌 PDF से टेक्स्ट निकालने का फंक्शन
def extract_text_from_pdf(file_path):
    text = ""
    with open(file_path, "rb") as pdf_file:
        reader = PyPDF2.PdfReader(pdf_file)
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
    return text.strip() if text else "No text found"

# 📌 HTML से टेक्स्ट निकालने का फंक्शन
def extract_text_from_html(file_path):
    with open(file_path, "r", encoding="utf-8") as html_file:
        soup = BeautifulSoup(html_file, "html.parser")
        return soup.get_text(separator=" ").strip()

# 📌 Edge-TTS से स्पीच जनरेट करने का async फंक्शन
async def generate_speech(text, lang, gender, filename):
    voice_map = {
        "Male": "en-US-GuyNeural",
        "Female": "en-US-JennyNeural"
    }
    voice = voice_map.get(gender, "en-US-JennyNeural")
    output_path = os.path.join(OUTPUT_FOLDER, filename)

    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)

        # 🎯 जब ऑडियो तैयार हो जाए, तो फ्रंटेंड को अपडेट भेजें
        socketio.emit("audio_ready", {
            "mp3_url": url_for("serve_output", filename=filename, _external=True)
        })
    except Exception as e:
        print(f"Error generating speech: {e}")

# 📌 फ़ाइल अपलोड API
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    file_ext = file.filename.rsplit(".", 1)[-1]
    unique_filename = f"{uuid.uuid4()}.{file_ext}"
    file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
    file.save(file_path)

    # 📌 फ़ाइल के प्रकार के आधार पर टेक्स्ट निकालें
    if file.filename.endswith(".pdf"):
        extracted_text = extract_text_from_pdf(file_path)
    elif file.filename.endswith(".html"):
        extracted_text = extract_text_from_html(file_path)
    elif file.filename.endswith(".txt") or file.filename.endswith(".text"):
        with open(file_path, "r", encoding="utf-8") as txt_file:
            extracted_text = txt_file.read()
    else:
        return jsonify({"error": "Unsupported file type"}), 400

    if not extracted_text:
        return jsonify({"error": "No text found in file"}), 400

    lang = request.args.get("lang", "en-US")
    gender = request.args.get("gender", "Female")
    mp3_filename = unique_filename.rsplit(".", 1)[0] + ".mp3"

    # 🎯 बैकग्राउंड में async टास्क चलाएं
    socketio.start_background_task(lambda: asyncio.run(generate_speech(extracted_text, lang, gender, mp3_filename)))

    return jsonify({
        "extracted_text": extracted_text,
        "mp3_file": url_for("serve_output", filename=mp3_filename, _external=True)
    })

# 📌 ऑडियो फ़ाइल सर्व करने का API
@app.route("/output/<filename>")
def serve_output(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)

# 📌 मेन पेज लोड करने का API
@app.route("/")
def index():
    return render_template("index.html")

# 📌 Flask-SocketIO सर्वर रन करें
if __name__ == "__main__":
    socketio.run(app, debug=True)

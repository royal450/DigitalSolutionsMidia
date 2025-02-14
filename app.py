import os
import asyncio
import uuid
import PyPDF2
import edge_tts
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify, send_from_directory, url_for
from flask_cors import CORS
from flask_socketio import SocketIO

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

UPLOAD_FOLDER = "static/uploads"
OUTPUT_FOLDER = "static/output"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Extract text from PDF
def extract_text_from_pdf(file_path):
    text = ""
    with open(file_path, "rb") as pdf_file:
        reader = PyPDF2.PdfReader(pdf_file)
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text += page_text + "\n"
    return text.strip() if text else "No text found"

# Extract text from HTML
def extract_text_from_html(file_path):
    with open(file_path, "r", encoding="utf-8") as html_file:
        soup = BeautifulSoup(html_file, "html.parser")
        return soup.get_text(separator=" ").strip()

# Generate speech using edge-tts (Async)
async def generate_speech(text, lang, gender, filename):
    voice_map = {
        "Male": "en-US-GuyNeural",
        "Female": "en-US-JennyNeural"
    }
    voice = voice_map.get(gender, "en-US-JennyNeural")

    output_path = os.path.join(OUTPUT_FOLDER, filename)

    try:
        tts = edge_tts.Communicate(text, voice)
        await tts.save(output_path)

        # Emit event to frontend when file is ready
        socketio.emit("audio_ready", {
            "mp3_url": url_for("serve_output", filename=filename, _external=True)
        })
    except Exception as e:
        print(f"Error generating speech: {e}")

# File Upload Route
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

    # Extract text based on file type
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

    # Run speech generation in a background task (Async)
    asyncio.create_task(generate_speech(extracted_text, lang, gender, mp3_filename))

    return jsonify({
        "extracted_text": extracted_text,
        "mp3_file": url_for("serve_output", filename=mp3_filename, _external=True)
    })

# Serve audio files
@app.route("/output/<filename>")
def serve_output(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)

# Main Route
@app.route("/")
def index():
    return render_template("index.html")

# Start Flask App
if __name__ == "__main__":
    socketio.run(app, debug=True, use_reloader=False)

from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import os
import fitz  # PyMuPDF for PDF text extraction
from bs4 import BeautifulSoup  # BeautifulSoup for HTML parsing
import gtts  # Google Text-to-Speech
import eventlet

# Flask Setup
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Uploads & Output Directory
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Allowed File Types
ALLOWED_EXTENSIONS = {"pdf", "html", "txt", "text"}

# Utility: Check File Extension
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Utility: Extract Text from PDF
def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text("text") + "\n"
    return text.strip()

# Utility: Extract Text from HTML
def extract_text_from_html(html_path):
    with open(html_path, "r", encoding="utf-8") as file:
        soup = BeautifulSoup(file, "html.parser")
        return soup.get_text(separator=" ").strip()

# Utility: Extract Text from TXT
def extract_text_from_txt(txt_path):
    with open(txt_path, "r", encoding="utf-8") as file:
        return file.read().strip()

# **📌 File Upload & Processing Route**
@app.route("/upload", methods=["POST"])
def upload_file():
    sid = request.args.get("sid")  # Client ID for real-time updates
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded!"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file!"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        # **📌 Extract Text Based on File Type**
        extracted_text = ""
        file_ext = filename.rsplit(".", 1)[1].lower()

        if file_ext == "pdf":
            extracted_text = extract_text_from_pdf(file_path)
        elif file_ext == "html":
            extracted_text = extract_text_from_html(file_path)
        elif file_ext in ["txt", "text"]:
            extracted_text = extract_text_from_txt(file_path)
        else:
            return jsonify({"error": "Unsupported file format!"}), 400

        if not extracted_text:
            return jsonify({"error": "Could not extract text!"}), 400

        # **📌 Start TTS Processing**
        emit_progress(sid, "🔊 Converting text to speech...", 50)
        output_mp3 = filename.rsplit(".", 1)[0] + ".mp3"
        output_path = os.path.join(OUTPUT_FOLDER, output_mp3)

        try:
            tts = gtts.gTTS(extracted_text, lang="en")  # Default language: English
            tts.save(output_path)

            emit_progress(sid, "✅ Conversion Complete!", 100)

            return jsonify({"extracted_text": extracted_text, "mp3_file": output_mp3})
        except Exception as e:
            return jsonify({"error": f"TTS Conversion Failed: {str(e)}"}), 500

    return jsonify({"error": "Invalid file type!"}), 400

# **📌 Serve Generated MP3 Files**
@app.route("/output/<filename>")
def get_output_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)

# **📌 Emit Real-time Progress**
def emit_progress(sid, status, progress):
    socketio.emit("progress", {"status": status, "progress": progress}, room=sid)

# **📌 Start Flask**
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)

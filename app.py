from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import shutil
import edge_tts
import asyncio
from PyPDF2 import PdfReader
import html2text

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# 📌 Extract text from PDF, HTML, or TXT
def extract_text(file_path, file_type):
    text = ""
    if file_type == "pdf":
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
    elif file_type == "html":
        with open(file_path, "r", encoding="utf-8") as f:
            text = html2text.html2text(f.read())
    elif file_type in ["txt", "text"]:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    return text.strip()

# 📌 Convert Text to Speech using Edge-TTS
async def text_to_speech(text, lang, voice, output_path):
    tts = edge_tts.Communicate(text, voice)
    await tts.save(output_path)

# 📌 Upload & Process File
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded!"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file!"}), 400
    
    file_ext = file.filename.rsplit(".", 1)[-1].lower()
    if file_ext not in ["pdf", "html", "txt", "text"]:
        return jsonify({"error": "Invalid file format!"}), 400
    
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    # 📌 Extract Text
    extracted_text = extract_text(file_path, file_ext)
    if not extracted_text:
        return jsonify({"error": "No text found in the file!"}), 400

    # 📌 Convert to Speech
    output_mp3 = os.path.join(OUTPUT_FOLDER, f"{os.path.splitext(file.filename)[0]}.mp3")
    asyncio.run(text_to_speech(extracted_text, "en-US", "en-US-JennyNeural", output_mp3))

    return jsonify({"extracted_text": extracted_text, "mp3_file": os.path.basename(output_mp3)})

# 📌 Serve Audio File
@app.route("/output/<filename>")
def serve_audio(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)

# 📌 Serve UI
@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)

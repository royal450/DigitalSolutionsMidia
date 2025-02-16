from flask import Flask, request, send_from_directory, url_for, render_template
import os, asyncio, uuid
import PyPDF2
import edge_tts
from bs4 import BeautifulSoup
from flask_cors import CORS
from flask_socketio import SocketIO

app = Flask(__name__, template_folder="templates")
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "templates/output"
STATUS_FILE = "templates/status.txt"

# ✅ Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ✅ Auto-create status file if missing
if not os.path.exists(STATUS_FILE):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        f.write("Ready!")

def update_status(text):
    """✅ Update status.txt & auto-create if missing"""
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception as e:
        print(f"⚠️ Error writing status file: {e}")

async def generate_speech(text, lang, gender, filename):
    voice_map = {"Male": "en-US-GuyNeural", "Female": "en-US-JennyNeural"}
    voice = voice_map.get(gender, "en-US-JennyNeural")
    output_path = os.path.join(OUTPUT_FOLDER, filename)

    try:
        update_status("Generating speech...")
        tts = edge_tts.Communicate(text, voice)
        await tts.save(output_path)
        socketio.emit("audio_ready", {"mp3_url": url_for("serve_output", filename=filename, _external=True)})
        update_status(f"Done! Audio ready: {filename}")
    except Exception as e:
        update_status(f"Error generating speech: {e}")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        update_status("No file uploaded. Creating default file...")
        default_text = "This is a default text because no file was uploaded."
        file_path = os.path.join(UPLOAD_FOLDER, "default.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(default_text)
        extracted_text = default_text
    else:
        file = request.files["file"]
        if file.filename == "":
            update_status("No selected file. Creating default file...")
            file_path = os.path.join(UPLOAD_FOLDER, "default.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("This is a default text because no file was selected.")
            extracted_text = "This is a default text because no file was selected."
        else:
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
                update_status("Unsupported file type, using default text.")
                extracted_text = "Unsupported file type, using default text."

    lang = request.args.get("lang", "en-US")
    gender = request.args.get("gender", "Female")
    mp3_filename = f"{uuid.uuid4()}.mp3"

    update_status("Processing text-to-speech...")

    # ✅ Use `asyncio.run()` to avoid event loop error
    asyncio.run(generate_speech(extracted_text, lang, gender, mp3_filename))

    return "Processing Started", 202

@app.route("/status")
def get_status():
    """✅ Serve status file & auto-create if missing"""
    if not os.path.exists(STATUS_FILE):
        update_status("Ready!")
    return send_from_directory("templates", "status.txt")

@app.route("/output/<filename>")
def serve_output(filename):
    """✅ Serve audio files & auto-create if missing"""
    file_path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(file_path):
        update_status("Requested audio not found, creating dummy audio...")
        with open(file_path, "wb") as f:
            f.write(b"")
    return send_from_directory(OUTPUT_FOLDER, filename)

@app.route("/")
def index():
    return render_template("index.html")  # ✅ Now serves index.html properly

if __name__ == "__main__":
    socketio.run(app, debug=True, use_reloader=False)

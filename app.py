from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import time
import os
import eventlet
import PyPDF2
from gtts import gTTS

eventlet.monkey_patch()  # Eventlet patching (important!)

app = Flask(__name__, template_folder="templates")
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "mp3_files"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(file_path)

    # Start processing in the background
    socketio.start_background_task(target=process_pdf_to_audio, file_path=file_path)
    return jsonify({"message": "File uploaded, processing started!"})


def process_pdf_to_audio(file_path):
    """Convert PDF to Audio with real-time progress updates."""
    try:
        with open(file_path, "rb") as pdf_file:
            reader = PyPDF2.PdfReader(pdf_file)
            total_pages = len(reader.pages)
            extracted_text = ""

            for i, page in enumerate(reader.pages):
                extracted_text += page.extract_text() + " "
                progress = int((i + 1) / total_pages * 100)
                socketio.emit("progress", {"progress": progress})  # Send progress
                time.sleep(0.2)  # Simulate processing delay

        # Convert text to speech
        tts = gTTS(text=extracted_text, lang="en")
        output_path = os.path.join(app.config["OUTPUT_FOLDER"], os.path.basename(file_path).replace(".pdf", ".mp3"))
        tts.save(output_path)

        socketio.emit("completed", {"message": "Processing complete!", "file": output_path})
    except Exception as e:
        socketio.emit("error", {"message": str(e)})


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))  # Render ka port set karna zaroori hai
    socketio.run(app, host="0.0.0.0", port=port)

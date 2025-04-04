from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
import edge_tts
import os
import asyncio
import uuid
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

# Flask App Setup
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Logging Configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Directory to Store Audio Files
AUDIO_PATH = os.path.join(os.getcwd(), "audio_files")
os.makedirs(AUDIO_PATH, exist_ok=True)

# Task Status Dictionary
task_status = {}

# Optimized Thread Pool
executor = ThreadPoolExecutor(max_workers=4)

async def generate_audio(text, voice):
    """ AI-Generated ऑडियो फाइल बनाता है। """
    try:
        output_file = os.path.join(AUDIO_PATH, f"audio_{uuid.uuid4().hex}.mp3")
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        return output_file
    except Exception as e:
        logging.error(f"Error generating audio: {e}")
        return None

def background_audio_generation(task_id, text, voice):
    """ बैकग्राउंड में ऑडियो जेनरेशन करता है। """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        cleanup_old_files()

        task_status[task_id] = "processing"
        output_file = loop.run_until_complete(generate_audio(text, voice))

        if output_file:
            task_status[task_id] = f"completed|/play-audio/{os.path.basename(output_file)}"
        else:
            task_status[task_id] = "failed|Error generating audio"
    except Exception as e:
        logging.error(f"Background Task Error: {e}")
        task_status[task_id] = f"failed|{str(e)}"
    finally:
        loop.close()

@app.route("/generate-audio", methods=["POST"])
def handle_audio_generation():
    data = request.json
    text = data.get("text")
    voice = data.get("voice")

    if not text or not voice:
        return jsonify({"error": "Missing text or voice"}), 400

    task_id = uuid.uuid4().hex
    task_status[task_id] = "processing"

    executor.submit(background_audio_generation, task_id, text, voice)

    return jsonify({
        "message": "ऑडियो जेनरेशन प्रोसेस में है।",
        "task_id": task_id,
        "status": "processing"
    }), 202

@app.route("/task-status/<task_id>", methods=["GET"])
def get_task_status(task_id):
    if task_id not in task_status:
        return jsonify({"error": "Invalid Task ID"}), 404

    status = task_status[task_id]

    if "completed" in status:
        _, audio_url = status.split("|")
        return jsonify({"status": "completed", "audio_url": audio_url}), 200
    elif "failed" in status:
        _, error_msg = status.split("|")
        return jsonify({"status": "failed", "error": error_msg}), 500
    elif status == "processing":
        return jsonify({"status": "processing"}), 202

@app.route("/play-audio/<filename>", methods=["GET"])
def play_audio(filename):
    try:
        file_path = os.path.join(AUDIO_PATH, filename)
        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404

        response = make_response(send_from_directory(AUDIO_PATH, filename, mimetype="audio/mpeg", as_attachment=True))
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response
    except Exception as e:
        logging.error(f"Error serving file {filename}: {e}")
        return jsonify({"error": "File not found"}), 404

def cleanup_old_files():
    try:
        for file in os.listdir(AUDIO_PATH):
            file_path = os.path.join(AUDIO_PATH, file)
            if file.startswith("audio_") and file.endswith(".mp3") and time.time() - os.path.getmtime(file_path) > 3600:
                os.remove(file_path)
                logging.info(f"Deleted Old File: {file}")
    except Exception as e:
        logging.error(f"Cleanup Error: {e}")

@app.route('/')
def index():
    return jsonify({"Message": "Hello bro, I'm in the Rock API - No Rate Limit!"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, threaded=True)

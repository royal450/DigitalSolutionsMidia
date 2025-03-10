from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
import edge_tts
import os
import asyncio
import uuid
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict

# Flask App Setup
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Logging Configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Directory to Store Audio Files
AUDIO_PATH = os.path.join(os.getcwd(), "audio_files")
os.makedirs(AUDIO_PATH, exist_ok=True)

# Rate Limiting Setup
request_counts = defaultdict(lambda: {"count": 0, "time": 0})
MAX_REQUESTS = 5  # Max 5 requests per minute
TIME_WINDOW = 60   # 60 seconds per window
RATE_LIMIT_RESET = 3600  # 1-hour reset time

# Super Key (Bypasses Rate Limits)
SUPER_KEY = "ROYAL-KEY-ROYAL"

# Background Task Status Dictionary
task_status = {}

# Thread Pool for Fast Processing
executor = ThreadPoolExecutor(max_workers=5)


def is_rate_limited(ip, api_key):
    """
    Checks if the client IP has exceeded the rate limit.
    Super Key bypasses the rate limit.
    """
    if api_key == SUPER_KEY:
        return False, MAX_REQUESTS  # Unlimited access

    current_time = time.time()

    # If more than 1 hour has passed, reset the counter
    if current_time - request_counts[ip]["time"] > RATE_LIMIT_RESET:
        request_counts[ip] = {"count": 0, "time": current_time}

    if request_counts[ip]["count"] >= MAX_REQUESTS:
        # If user already exceeded limit, check if 1 hour has passed
        if current_time - request_counts[ip]["time"] < RATE_LIMIT_RESET:
            return True, 0  # Rate limit exceeded and still within 1 hour
        else:
            # Reset after 1 hour
            request_counts[ip] = {"count": 1, "time": current_time}
            return False, MAX_REQUESTS - 1

    request_counts[ip]["count"] += 1
    remaining_requests = MAX_REQUESTS - request_counts[ip]["count"]
    return False, max(0, remaining_requests)


async def generate_audio(text, voice):
    """
    Generates AI-based speech audio asynchronously.
    """
    try:
        output_file = os.path.join(AUDIO_PATH, f"audio_{uuid.uuid4().hex}.mp3")
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        return output_file
    except Exception as e:
        logging.error(f"Error generating audio: {e}")
        return None


def background_audio_generation(task_id, text, voice):
    """
    Runs audio generation in a separate thread.
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        cleanup_old_files()  # Remove old files before generating new ones

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


@app.route("/", methods=["GET"])
def home():
    """
    Home Route - API Status Check
    """
    return jsonify({"message": "AI Voice Generator API is running"})


@app.route("/generate-audio", methods=["POST"])
def handle_audio_generation():
    """
    Handles audio generation requests with rate limiting.
    """
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    api_key = request.headers.get("Authorization", "")

    rate_limited, remaining_requests = is_rate_limited(client_ip, api_key)

    if rate_limited:
        return jsonify({
            "error": "You have reached your limit. Upgrade for unlimited access or wait 1 hour.",
            "message": "Please wait 1 hour or buy premium for ₹99.",
            "remaining_requests": 0
        }), 429

    data = request.json
    text = data.get("text")
    voice = data.get("voice")

    if not text or not voice:
        return jsonify({"error": "Missing text or voice"}), 400

    task_id = uuid.uuid4().hex
    task_status[task_id] = "processing"

    executor.submit(background_audio_generation, task_id, text, voice)

    return jsonify({
        "message": "Audio generation in progress",
        "task_id": task_id,
        "status": "processing",
        "remaining_requests": remaining_requests
    }), 202


@app.route("/task-status/<task_id>", methods=["GET"])
def get_task_status(task_id):
    """
    Returns the status of an ongoing or completed task.
    """
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
    """
    Serves the generated audio file for download.
    """
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


@app.route("/remaining-requests", methods=["GET"])
def get_remaining_requests():
    """
    Returns the remaining API requests for the client.
    """
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    api_key = request.headers.get("Authorization", "")

    if api_key == SUPER_KEY:
        return jsonify({"remaining_requests": "Unlimited"}), 200

    current_time = time.time()

    if current_time - request_counts[client_ip]["time"] > RATE_LIMIT_RESET:
        remaining_requests = MAX_REQUESTS
    else:
        remaining_requests = max(0, MAX_REQUESTS - request_counts[client_ip]["count"])

    return jsonify({"remaining_requests": remaining_requests}), 200


def cleanup_old_files():
    """
    Deletes audio files older than 1 hour.
    """
    try:
        for file in os.listdir(AUDIO_PATH):
            file_path = os.path.join(AUDIO_PATH, file)
            if file.startswith("audio_") and file.endswith(".mp3") and time.time() - os.path.getmtime(file_path) > 3600:
                os.remove(file_path)
                logging.info(f"Deleted Old File: {file}")
    except Exception as e:
        logging.error(f"Cleanup Error: {e}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
    

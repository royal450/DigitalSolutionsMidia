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
import requests
import threading

# Flask App Setup
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Logging Configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Directory to Store Audio Files
AUDIO_PATH = os.path.join(os.getcwd(), "audio_files")
os.makedirs(AUDIO_PATH, exist_ok=True)

# Rate Limiting Setup (In-Memory)
request_counts = defaultdict(lambda: {"count": 0, "time": time.time()})
MAX_REQUESTS = 5  # 1 घंटे में 5 कॉल अलाउड
RATE_LIMIT_RESET = 3600  # 1 घंटे में रीसेट
request_lock = threading.Lock()  # Thread Safety के लिए Lock

# Super Key (Bypasses Rate Limits)
SUPER_KEY = "ROYAL-KEY-ROYAL"

# Task Status Dictionary
task_status = {}

# Optimized Thread Pool for Fast Execution
executor = ThreadPoolExecutor(max_workers=4)


def is_rate_limited(ip, api_key):
    """ चेक करे कि यूज़र की API लिमिट पूरी हो चुकी है या नहीं। """
    if api_key == SUPER_KEY:
        return False, "Unlimited"

    with request_lock:  # 🔒 Lock to prevent race conditions
        current_time = time.time()
        user_data = request_counts[ip]

        if current_time - user_data["time"] > RATE_LIMIT_RESET:
            request_counts[ip] = {"count": 1, "time": current_time}
            return False, MAX_REQUESTS - 1

        if user_data["count"] >= MAX_REQUESTS:
            return True, 0

        request_counts[ip]["count"] += 1
        return False, MAX_REQUESTS - request_counts[ip]["count"]


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
    """ API कॉल के लिए रेट लिमिटिंग लागू करता है। """
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    api_key = request.headers.get("Authorization", "")

    rate_limited, remaining_requests = is_rate_limited(client_ip, api_key)

    if rate_limited:
        return jsonify({
            "error": "आपने अपनी लिमिट पूरी कर ली है। 1 घंटे बाद दोबारा ट्राई करें या ₹99 में अनलिमिटेड एक्सेस खरीदें।",
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
        "message": "ऑडियो जेनरेशन प्रोसेस में है।",
        "task_id": task_id,
        "status": "processing",
        "remaining_requests": remaining_requests
    }), 202


@app.route("/remaining-requests", methods=["GET"])
def get_remaining_requests():
    """ यूज़र को बताता है कि उसकी कितनी रिक्वेस्ट बची हैं। """
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    api_key = request.headers.get("Authorization", "")

    if api_key == SUPER_KEY:
        return jsonify({"remaining_requests": "Unlimited"}), 200

    with request_lock:  # 🔒 Thread-Safe Access
        user_data = request_counts.get(client_ip, {"count": 0, "time": time.time()})
        remaining_requests = max(0, MAX_REQUESTS - user_data["count"])

    return jsonify({"remaining_requests": remaining_requests}), 200


@app.route("/task-status/<task_id>", methods=["GET"])
def get_task_status(task_id):
    """ किसी भी टास्क का स्टेटस चेक करने के लिए। """
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
    """ जेनरेटेड ऑडियो को डाउनलोड करने का API। """
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
    """ 1 घंटे से पुराने ऑडियो फाइल्स को डिलीट करता है। """
    try:
        for file in os.listdir(AUDIO_PATH):
            file_path = os.path.join(AUDIO_PATH, file)
            if file.startswith("audio_") and file.endswith(".mp3") and time.time() - os.path.getmtime(file_path) > 3600:
                os.remove(file_path)
                logging.info(f"Deleted Old File: {file}")
    except Exception as e:
        logging.error(f"Cleanup Error: {e}")


def keep_alive():
    """ Prevents Render from sleeping by pinging the server every 30 seconds. """
    def ping_server():
        while True:
            try:
                requests.get("https://digitalsolutionsmidia.onrender.com/")
                logging.info("Keep Alive: Successfully pinged the server.")
            except Exception as e:
                logging.error(f"Keep Alive Error: {e}")
            time.sleep(30)

    thread = threading.Thread(target=ping_server, daemon=True)
    thread.start()


@app.route('/')
def index():
    return jsonify({"Message:": "Hello bro I'm In The Rock API"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, threaded=True)

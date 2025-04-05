from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
import edge_tts
import os
import asyncio
import uuid
import time
import logging
import json
import shutil
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Constants
AUDIO_PATH = os.path.join(os.getcwd(), "audio_files")
os.makedirs(AUDIO_PATH, exist_ok=True)
USAGE_FILE = "usage_data.json"
SUPER_KEY = "ROYAL-KEY-ROYAL"
MAX_FREE_REQUESTS = 2
RATE_LIMIT_RESET = 86400  # 24 hours

# Premium voice models (optimized for CPU)
PREMIUM_VOICES = {
    "natural-hindi-male": "hi-IN-Male-Natural",
    "natural-hindi-female": "hi-IN-Female-Natural",
    "premium-english-male": "en-US-GuyNeural",
    "premium-english-female": "en-US-JennyNeural",
    "emotional-hindi": "hi-IN-Emotional",
    "young-adult": "hi-IN-YoungAdult",
    "professional": "hi-IN-Professional",
    "casual": "hi-IN-Casual",
    "news-reporter": "hi-IN-News",
    "storyteller": "hi-IN-Storyteller"
}

# Thread pool for background tasks
executor = ThreadPoolExecutor(max_workers=2)  # Reduced workers for low CPU
task_status = {}

def load_usage():
    if not os.path.exists(USAGE_FILE):
        return {}
    try:
        with open(USAGE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_usage(data):
    with open(USAGE_FILE, "w") as f:
        json.dump(data, f)

def is_rate_limited(ip, api_key):
    if api_key == SUPER_KEY:
        return False, "unlimited"
    
    usage = load_usage()
    user_data = usage.get(ip, {"count": 0, "time": time.time()})
    current_time = time.time()

    # Reset counter if period has passed
    if current_time - user_data["time"] > RATE_LIMIT_RESET:
        usage[ip] = {"count": 1, "time": current_time}
        save_usage(usage)
        return False, MAX_FREE_REQUESTS - 1

    # Check if limit reached
    if user_data["count"] >= MAX_FREE_REQUESTS:
        return True, 0

    # Increment count
    usage[ip] = {
        "count": user_data["count"] + 1,
        "time": user_data["time"]  # Keep original timestamp
    }
    save_usage(usage)
    return False, MAX_FREE_REQUESTS - usage[ip]["count"]

async def generate_audio(text, voice, is_premium=False):
    try:
        output_file = os.path.join(AUDIO_PATH, f"audio_{uuid.uuid4().hex}.mp3")
        
        # Select voice model
        voice_model = PREMIUM_VOICES.get(voice, voice) if is_premium else voice
        
        # Generate with edge_tts (CPU optimized)
        communicate = edge_tts.Communicate(text, voice_model)
        await communicate.save(output_file)
        
        return output_file
    except Exception as e:
        logging.error(f"Audio generation error: {e}")
        return None

def background_task(task_id, text, voice, is_premium=False):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        task_status[task_id] = "processing"
        output_file = loop.run_until_complete(generate_audio(text, voice, is_premium))
        
        if output_file:
            filename = os.path.basename(output_file)
            task_status[task_id] = f"completed|/play-audio/{filename}"
        else:
            task_status[task_id] = "failed|Error generating audio"
    except Exception as e:
        task_status[task_id] = f"failed|{str(e)}"
    finally:
        loop.close()

def cleanup_old_files():
    try:
        now = time.time()
        for filename in os.listdir(AUDIO_PATH):
            filepath = os.path.join(AUDIO_PATH, filename)
            if filename.startswith("audio_") and filename.endswith(".mp3"):
                file_age = now - os.path.getmtime(filepath)
                if file_age > 3600:  # 1 hour
                    os.remove(filepath)
                    logging.info(f"Cleaned up: {filename}")
    except Exception as e:
        logging.error(f"Cleanup error: {e}")

@app.route("/generate-audio", methods=["POST"])
def handle_generate_audio():
    client_ip = request.remote_addr
    api_key = request.headers.get("Authorization", "")
    
    # Check rate limiting
    limited, remaining = is_rate_limited(client_ip, api_key)
    if limited:
        return jsonify({
            "error": "Daily limit reached. Upgrade for unlimited access.",
            "remaining": 0
        }), 429
    
    # Get request data
    data = request.get_json()
    if not data or "text" not in data or "voice" not in data:
        return jsonify({"error": "Missing text or voice"}), 400
    
    text = data["text"]
    voice = data["voice"]
    is_premium = api_key == SUPER_KEY  # Simple premium check
    
    # Start background task
    task_id = uuid.uuid4().hex
    executor.submit(background_task, task_id, text, voice, is_premium)
    
    return jsonify({
        "message": "Audio generation started",
        "task_id": task_id,
        "status": "processing",
        "remaining_requests": remaining
    }), 202

@app.route("/task-status/<task_id>", methods=["GET"])
def check_task_status(task_id):
    status = task_status.get(task_id)
    if not status:
        return jsonify({"error": "Invalid task ID"}), 404
    
    if status.startswith("completed|"):
        return jsonify({
            "status": "completed",
            "audio_url": status.split("|")[1]
        })
    elif status.startswith("failed|"):
        return jsonify({
            "status": "failed",
            "error": status.split("|")[1]
        }), 500
    else:
        return jsonify({"status": "processing"})

@app.route("/play-audio/<filename>", methods=["GET"])
def serve_audio(filename):
    if not filename.endswith(".mp3") or not os.path.exists(os.path.join(AUDIO_PATH, filename)):
        return jsonify({"error": "File not found"}), 404
    
    response = make_response(send_from_directory(
        AUDIO_PATH, 
        filename, 
        mimetype="audio/mpeg",
        as_attachment=False
    ))
    response.headers["Cache-Control"] = "max-age=3600"  # Cache for 1 hour
    return response

@app.route("/voices", methods=["GET"])
def list_voices():
    return jsonify({
        "standard_voices": ["hi-IN-Male", "hi-IN-Female", "en-US-Male", "en-US-Female"],
        "premium_voices": list(PREMIUM_VOICES.keys())
    })

@app.route("/remaining-requests", methods=["GET"])
def get_remaining_requests():
    client_ip = request.remote_addr
    api_key = request.headers.get("Authorization", "")
    
    if api_key == SUPER_KEY:
        return jsonify({"remaining": "unlimited"})
    
    _, remaining = is_rate_limited(client_ip, api_key)
    return jsonify({"remaining": remaining})

@app.route("/")
def home():
    return jsonify({
        "message": "RoyalDev TTS API",
        "version": "1.0",
        "features": ["Text-to-Speech", "10 Premium Voices", "Low CPU Usage"]
    })

if __name__ == "__main__":
    # Initial cleanup
    cleanup_old_files()
    
    # Start the server
    app.run(
        host="0.0.0.0",
        port=10000,
        threaded=True,
        debug=False  # Disable debug for production
)

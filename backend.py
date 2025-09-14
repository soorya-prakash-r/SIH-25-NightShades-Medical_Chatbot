import os
from flask import Flask, request, Response, jsonify
import google.generativeai as genai
from dotenv import load_dotenv
from sarvamai import SarvamAI
import requests

# ---------------- Load Keys ---------------- #
load_dotenv()
AI_KEY = os.getenv("AI_API_KEY")       # Gemini API Key
SARVAM_KEY = os.getenv("VOICE_API_KEY")  # SarvamAI Key

if not AI_KEY or not SARVAM_KEY:
    raise ValueError("API Keys not found! Please set AI_API_KEY and VOICE_API_KEY in .env")

# Configure Gemini
genai.configure(api_key=AI_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# Configure SarvamAI
client = SarvamAI(api_subscription_key=SARVAM_KEY)

# Flask App
app = Flask(__name__)
os.makedirs("static", exist_ok=True)


# ---------------- Helper Functions ---------------- #

def clean_text(text: str) -> str:
    """Clean up Gemini output for safety."""
    text = text.strip()
    text = " ".join(text.split())
    text = text.replace("*", '"')
    return text


def mitai_response(user_query: str) -> str:
    """Generate AI medical-friendly response from user query."""
    # Step 1: Summarize
    prompt = f"""
    Given a user query below, summarize it in 2–3 short lines, highlighting the main symptoms or concerns. 
    Do not give advice yet. Make it clear, concise, and easy to understand. 
    Query: "{user_query}"
    """
    report = model.generate_content(prompt).text

    # Step 2: Friendly analysis
    prompt = f"""
    Given the medical report below, provide a layperson-friendly, practical response. 
    - Include safe, evidence-based home remedies or lifestyle tips suitable for mild symptoms. 
    - Avoid giving professional diagnosis. 
    - Keep it conversational, engaging, and call the patient by name if possible. 
    - Limit to 5–7 lines. 
    - Always end with: "If symptoms worsen or persist, please consult a healthcare provider."
    Report: "{report}"
    """
    analysis = model.generate_content(prompt).text
    return clean_text(analysis)


def text_to_speech(text: str, filename: str) -> str:     
    """Convert text to speech using SarvamAI and save to static folder."""
    filepath = os.path.join("static", filename)
    response = client.text_to_speech.convert(
        text=text,
        target_language_code="en-IN",
        speaker="vidya",
        pitch=0,
        pace=1,
        loudness=1,
        speech_sample_rate=22050,
        enable_preprocessing=True,
        model="bulbul:v2"
    )
    # Save audio
    with open(filepath, "wb") as f:
        f.write(response["audio_content"])
    return filepath


def speech_to_text(audio_path: str) -> str:
    """Convert audio file to text using SarvamAI."""
    with open(audio_path, "rb") as f:
        response = client.speech_to_text.transcribe(
            file=f,
            model="saarika:v2.5",
            language_code="en-IN"
        )
    return response.get("text", "Sorry, I could not understand your speech.")


# ---------------- Routes ---------------- #

@app.route("/chat", methods=["POST"])
def chat():
    """Simple chatbot via JSON"""
    data = request.get_json()
    user_query = data.get("query")

    if not user_query:
        return jsonify({"error": "No query provided"}), 400

    reply_text = mitai_response(user_query)
    audio_file = text_to_speech(reply_text, "reply.wav")

    return jsonify({
        "MITAI": reply_text,
        "audio_path": f"/{audio_file}"
    })


@app.route("/exotel/voice", methods=["POST"])
def handle_exotel_call():
    """Handle Exotel call: get speech -> AI -> TTS -> play back"""
    call_sid = request.form.get("CallUUID")
    recording_url = request.form.get("RecordingUrl")

    user_text = "Hello!"

    if recording_url:
        wav_file = f"static/{call_sid}.wav"
        r = requests.get(recording_url)
        with open(wav_file, "wb") as f:
            f.write(r.content)
        user_text = speech_to_text(wav_file)

    reply_text = mitai_response(user_text)
    tts_file = f"{call_sid}_reply.wav"
    audio_path = text_to_speech(reply_text, tts_file)

    exotel_xml = f"""
    <Response>
        <Play>{request.url_root}{audio_path}</Play>
    </Response>
    """
    return Response(exotel_xml, mimetype="text/xml")


# ---------------- Main ---------------- #
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

import os
from flask import Flask, request, Response, jsonify
import google.generativeai as genai
from dotenv import load_dotenv
import pyttsx3
import requests
import speech_recognition as sr

# Load API key
load_dotenv()
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    raise ValueError("API Key not found! Please set API_KEY in .env file")

# Configure Gemini
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

app = Flask(__name__)
os.makedirs("static", exist_ok=True)

# ---------------- Helper Functions ---------------- #

def clean_text(text: str) -> str:
    text = text.strip()
    text = " ".join(text.split())
    text = text.replace("*", '"')
    return text

def mitai_response(user_query: str) -> str:
    # Step 1: Create short report
    prompt = f"""
    Given a user query below, summarize it in 2–3 short lines, highlighting the main symptoms or concerns. 
    Do not give advice yet. Make it clear, concise, and easy to understand. 
    Query: "{user_query}"
    """
    response = model.generate_content(prompt)
    report = response.text

    # Step 2: Create medical-friendly analysis
    prompt = f"""
    Given the medical report below, provide a layperson-friendly, practical response. 
    - Include safe, evidence-based home remedies or lifestyle tips suitable for mild symptoms. 
    - Avoid giving professional diagnosis. 
    - Keep it conversational, engaging, and call the patient by name if possible. 
    - Limit to 5–7 lines. 
    - Always end with a gentle safety note: "If symptoms worsen or persist, please consult a healthcare provider."

    Report: "{report}"
    """
    response = model.generate_content(prompt)
    analysis = response.text
    return clean_text(analysis)

def text_to_speech(text: str, filename="med_assistance.wav", voice_id=1, rate=160, volume=0.7) -> str:
    filepath = os.path.join("static", filename)
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[voice_id].id)
    engine.setProperty('rate', rate)
    engine.setProperty('volume', volume)
    engine.save_to_file(text, filepath)
    engine.runAndWait()
    return f"/static/{filename}"

def speech_to_text(audio_path: str) -> str:
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_path) as source:
        audio = recognizer.record(source)
    try:
        return recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        return "Sorry, I could not understand your speech."
    except sr.RequestError:
        return "Speech service is unavailable."

# ---------------- Routes ---------------- #

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_query = data.get("query")

    if not user_query:
        return jsonify({"error": "No query provided"}), 400

    reply_text = mitai_response(user_query)
    audio_path = text_to_speech(reply_text)  # Generate TTS

    return jsonify({
        "MITAI": reply_text,
        "audio_path": audio_path
    })

@app.route("/exotel/voice", methods=["POST"])
def handle_exotel_call():
    call_sid = request.form.get("CallUUID")
    recording_url = request.form.get("RecordingUrl")  # Exotel .wav recording

    user_text = "Hello!"  # default greeting

    if recording_url:
        wav_file = f"static/{call_sid}.wav"
        r = requests.get(recording_url)
        with open(wav_file, "wb") as f:
            f.write(r.content)
        user_text = speech_to_text(wav_file)

    reply_text = mitai_response(user_text)
    tts_file = f"static/{call_sid}_reply.wav"
    text_to_speech(reply_text, filename=f"{call_sid}_reply.wav")

    exotel_xml = f"""
    <Response>
        <Play>{request.url_root}{tts_file}</Play>
    </Response>
    """
    return Response(exotel_xml, mimetype="text/xml")

# ---------------- Main ---------------- #

if __name__ == "__main__":
    app.run(port=5000, debug=True)

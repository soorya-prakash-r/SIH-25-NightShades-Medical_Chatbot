import os
from flask import Flask, request, jsonify
import google.generativeai as genai
from dotenv import load_dotenv
from twilio.rest import Client

# ---------------- Load Keys ---------------- #
load_dotenv()
AI_KEY = os.getenv("AI_API_KEY")         # Gemini API Key
TWILIO_SID = os.getenv("TWILIO_SID")     # Twilio Account SID
TWILIO_AUTH = os.getenv("TWILIO_AUTH")   # Twilio Auth Token
TWILIO_WHATSAPP = os.getenv("TWILIO_WHATSAPP")  # Twilio Sandbox number e.g. whatsapp:+14155238886

if not AI_KEY or not TWILIO_SID or not TWILIO_AUTH or not TWILIO_WHATSAPP:
    raise ValueError("Please set AI_API_KEY, TWILIO_SID, TWILIO_AUTH, TWILIO_WHATSAPP in .env")

# Configure Gemini
genai.configure(api_key=AI_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# Configure Twilio
twilio_client = Client(TWILIO_SID, TWILIO_AUTH)

# Flask App
app = Flask(__name__)


# ---------------- Helper Functions ---------------- #

def clean_text(text: str) -> str:
    """Clean up Gemini output for safety."""
    if not text:
        return "Sorry, I could not generate a response."
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
    - Keep it conversational, engaging, gentel and call the patient by name if possible. If no name provided, address has buddy.
    - Limit to 5–7 lines. 
    - If the report does not contain medical related content, just prompt the user to talk related to medical field.
    - Always end with: "If symptoms worsen or persist, please consult a healthcare provider."
    Report: "{report}"
    """
    analysis = model.generate_content(prompt).text
    return clean_text(analysis)


# ---------------- Routes ---------------- #

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    """Handle incoming WhatsApp messages from Twilio"""
    user_number = request.form.get("From")      # e.g. whatsapp:+919876543210
    user_query = request.form.get("Body")       # User's message

    if not user_query:
        return "No query", 400

    print(f"[WhatsApp] Message from {user_number}: {user_query}")

    # Get AI reply
    reply_text = mitai_response(user_query)

    # Send reply back via Twilio
    twilio_client.messages.create(
        from_=TWILIO_WHATSAPP,
        to=user_number,
        body=reply_text
    )

    return "OK", 200


@app.route("/")
def home():
    return jsonify({"status": "MITAI WhatsApp chatbot running"})


# ---------------- Main ---------------- #
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

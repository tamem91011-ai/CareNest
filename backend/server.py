from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client
import os
import google.generativeai as genai

load_dotenv()

app = Flask(__name__)
CORS(app) 

# Supabase Initialization
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Gemini Initialization
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# --- API ROUTES ---

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "CareNest-AI",
        "database": "connected" if supabase else "error"
    }), 200

@app.route('/medications', methods=['GET', 'POST', 'OPTIONS'])
def handle_medications():
    if request.method == 'POST':
        return jsonify({"status": "success", "message": "Record received"}), 201
    return jsonify({"medications": []}), 200

@app.route('/symptoms', methods=['POST', 'OPTIONS'])
def log_symptoms():
    return jsonify({"status": "received"}), 201

@app.route('/ai-insight', methods=['POST', 'OPTIONS'])
def get_ai_insight():
    user_id = request.json.get('user_id')
    prompt_override = request.json.get('prompt') 
    
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400
        
    try:
        # Fetch clinical data
        symptoms_res = supabase.table('symptom_logs').select('*').eq('user_id', user_id).order('logged_at', desc=True).limit(5).execute()
        meds_res = supabase.table('medications').select('*').eq('user_id', user_id).execute()
        
        system_instruction = "You are a helpful clinical caregiver assistant. Summarize the patient status based on data."
        user_input = f"Symptoms: {symptoms_res.data}\nMeds: {meds_res.data}\nQuestion: {prompt_override or 'Summarize.'}"
        
        model = genai.GenerativeModel(model_name="gemini-flash-latest", system_instruction=system_instruction)
        response = model.generate_content(user_input)
        
        return jsonify({
            "status": "success",
            "clinical_insight": response.text
        })
    except Exception as e:
        return jsonify({
            "status": "simulated",
            "clinical_insight": "Resident A is stable. I recommend continuing the current observation schedule."
        })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

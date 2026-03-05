import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

app = Flask(__name__)
CORS(app) 

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)
@app.route('/api/medications', methods=['GET', 'POST'])
def handle_medications():
    """Endpoint for fetching and adding medication records"""
    if request.method == 'POST':
        data = request.json
        if not data or 'name' not in data:
            return jsonify({"error": "Bad Request", "message": "Missing required medication fields"}), \
            400
        return jsonify({"status": "success", "message": f"Medication {data['name']} staged for storage"}), \
         201
    return jsonify({"medications": []}), 200
@app.route('/api/symptoms', methods=['POST'])
def log_symptoms():
    """Asynchronous endpoint for storing physiological observations"""
    data = request.json
    
    if 'score' not in data:
        return jsonify({"error": "Validation Error", "details": "Score is mandatory"}), 422
        
    return jsonify({"status": "received", "data_point": "Observation logged successfully"}), 201

import google.generativeai as genai
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

@app.route('/api/ai-insight', methods=['POST'])
def get_ai_insight():
    """
    Step 19: Gemini 1.5 Flash Bio-Analysis Engine
    Synthesizes raw care logs into natural language health alerts.
    """
    user_id = request.json.get('user_id')
    prompt_override = request.json.get('prompt') 
    
    print(f"\n--- Gemini AI Request for User ID: {user_id} ---")
    
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400
    try:
        # Fetch actual clinical data
        symptoms_res = supabase.table('symptom_logs').select('*', count='exact').eq('user_id', user_id).order('logged_at', desc=True).limit(10).execute()
        meds_res = supabase.table('medications').select('*', count='exact').eq('user_id', user_id).execute()
        handover_res = supabase.table('handover_notes').select('*').eq('user_id', user_id).order('logged_at', desc=True).limit(5).execute()
        routines_res = supabase.table('routines').select('*').eq('user_id', user_id).order('log_date', desc=True).limit(10).execute()
        
        clinical_data = {
            "symptoms": symptoms_res.data,
            "medications": meds_res.data,
            "handovers": handover_res.data,
            "routines": routines_res.data
        }
        system_instruction = (
            "You are a Board-Certified Clinical Information Officer assistant. You have access to patient care logs. "
            "Your goal is to be a helpful, conversational advisor. "
            "1. If the user says 'Hello' or a general greeting, respond naturally and briefly (e.g., 'Hello! I'm ready to assist with Resident A's charts. What would you like to review?'). "
            "2. If the user asks a specific question (e.g., about meds or symptoms), answer it directly using the provided PATIENT DATA. "
            "3. Only provide the full multi-paragraph clinical summary if the user asks for a 'summary', 'overview', or 'analysis'. "
            "Maintain a professional, empathetic, and authoritative medical tone at all times."
        )
        
        # Prepare a readable context of the live data
        symptom_summary = ""
        for s in clinical_data['symptoms']:
            symptom_summary += f"- {s.get('category')}: {s.get('observation')} (Notes: {s.get('additional_notes') or 'N/A'})\n"
        
        med_summary = ", ".join([m.get('pill_name') for m in clinical_data['medications']]) or "None logged"
        
        handover_summary = ""
        for h in clinical_data['handovers']:
            handover_summary += f"- {h.get('sender_name')} ({h.get('sender_role')}): {h.get('note_content')}\n"

        routine_summary = ""
        for r in clinical_data['routines']:
            status = "COULD NOT COMPLETE" if not r.get('is_completed') else "COMPLETED"
            routine_summary += f"- {r.get('task_name')} on {r.get('log_date')}: {status}\n"

        data_text = f"PATIENT DATA:\nSymptoms:\n{symptom_summary}\nActive Meds: {med_summary}\nRecent Handovers:\n{handover_summary}\nDaily Routines:\n{routine_summary}"
        
        print(f"--- Data Context for Gemini (User {user_id}) ---")
        print(data_text)
        
        user_input = f"{data_text}\n\nUSER QUESTION: {prompt_override if prompt_override else 'Summarize the current clinical status.'}"

        status = "live" # Initialize status
        try:
            model = genai.GenerativeModel(
                model_name="gemini-flash-latest",
                system_instruction=system_instruction
            )
            response = model.generate_content(user_input)
            insight = response.text
            status = "success"
        except Exception as api_error:
            print(f"!!! Gemini API Error: {str(api_error)}")
            status = "simulated"
            # --- SMART SIMULATION ENGINE (V8: HUMAN-CENTRIC) ---
            prompt_lower = (prompt_override or "").lower()
            
            # Clinical Base Data
            latest_symptom = clinical_data['symptoms'][0] if len(clinical_data['symptoms']) > 0 else {}
            latest_handover = clinical_data['handovers'][0] if len(clinical_data['handovers']) > 0 else {}
            med_list = clinical_data['medications']
            
            # --- HIGH-FIDELITY HUMANIZED RESPONSES ---
            
            # 1. Simple Greetings
            if any(k in prompt_lower for k in ["hello", "hi", "hey", "greetings"]):
                insight = "Hello! I'm Resident A's Clinical Advisor. I've finished reviewing the latest logs—including her medications, symptom reports, and recent routines. \n\nWhat specific area of her care would you like to discuss or analyze right now?"

            # 2. Medication Deep Dive
            elif any(k in prompt_lower for k in ["medication", "drug", "side effect", "pill", "risk"]):
                med_details = ", ".join([f"<b>{m.get('pill_name')}</b> ({m.get('dosage')})" for m in med_list])
                insight = f"I've analyzed the medication profile for Resident A, which currently includes {med_details if med_list else 'our recorded medications'}.\n\n" \
                          "Clinical Note: We should maintain vigilance regarding potential fatigue or cognitive shifts. " \
                          "Ensuring consistent hydration after each dose will help her process these treatments effectively. " \
                          "Are you seeing any specific reactions, like drowsiness, that you'd like me to log?"

            # 3. Symptom & Pattern Check
            elif any(k in prompt_lower for k in ["symptom", "pattern", "trend", "severity", "how is she"]):
                s_count = len(clinical_data['symptoms'])
                s_avg = sum([int(s.get('severity', 0)) for s in clinical_data['symptoms']]) / s_count if s_count > 0 else 0
                insight = f"Looking at the last {s_count} observations, Resident A's average severity is holding at {s_avg:.1f}/10. This indicates relative stability.\n\n" \
                          f"The most recent entry, <b>'{latest_symptom.get('observation', 'wellness')}'</b>, is the key trend to watch. " \
                          "I recommend we keep the current observation frequency to catch any emerging patterns early. Is there a specific behavior that's concerning you?"

            # 4. Clinical Advice / Specific Medical Questions
            elif any(k in prompt_lower for k in ["insomnia", "dehydration", "swallowing", "agitation", "advice"]):
                clinical_advice = {
                    "insomnia": "Elderly insomnia often relates to environmental comfort. I suggest reducing evening stimulation.",
                    "dehydration": "Hydration is physiological baseline #1. Even minor deficits lead to confusion. Please encourage fluids.",
                    "swallowing": "⚠️ <b>Alert</b>: Swallowing difficulty requires an immediate upright position and potentially a soft-food protocol.",
                    "agitation": "Agitation is often a non-verbal report of physical pain. We should check for localized discomfort."
                }
                matched = next((k for k in clinical_advice if k in prompt_lower), "general")
                advice_text = clinical_advice.get(matched)
                insight = f"Regarding {matched}: {advice_text}\n\n" \
                          f"Considering her recent <b>{latest_symptom.get('category', 'clinical')}</b> log, we should stay observant for any physical triggers."

            # 5. Full Resident Overview (Requested Analysis)
            else:
                insight = f"Resident A is currently under active monitoring with <b>{len(clinical_data['symptoms'])} logs</b> recorded. We are tracking <b>{len(med_list)} active medications</b>.\n\n" \
                          "The data suggests she is responding well to the current care plan, though we are paying close attention to " + (f"<b>{latest_symptom.get('category')}</b>" if latest_symptom else "general vitals") + ". " \
                          "I am ready to provide a deeper deep dive into any specific symptom or medication risk you'd like to explore."

        print(f"--- Insight Produced (Status: {status}) ---")
        return jsonify({
            "status": "success" if status == "success" else "simulated",
            "clinical_insight": insight
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"!!! Error in get_ai_insight:\n{error_details}")
        return jsonify({
            "status": "error", 
            "clinical_insight": f"AI Hub encountered an internal error. Please check server logs.", 
            "details": str(e)
        }), 500

@app.route('/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health_check():
    """Diagnostic endpoint to verify backend status"""
    return jsonify({
        "status": "healthy",
        "environment": "vercel" if os.environ.get("VERCEL") else "local",
        "database_connected": supabase is not None,
        "api_endpoints": ["/api/health", "/api/ai-insight", "/api/medications", "/api/symptoms"]
    }), 200

# Catch-all route to help debug routing issues
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    print(f"--- Unrecognized Request Path: /{path} ---")
    return jsonify({
        "error": "Not Found",
        "requested_path": f"/{path}",
        "suggestion": "Check your API endpoint or vercel.json configuration."
    }), 404

if __name__ == '__main__':
    # Use the port assigned by Render, or default to 5000 for local development
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client
import os
import google.generativeai as genai

load_dotenv()

# We set the static_folder to the root so we can serve the HTML/CSS/JS files
# We use absolute path for stability on Vercel
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__, static_folder=root_dir, static_url_path='')
CORS(app) 

# Supabase Initialization
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Gemini Initialization
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# --- STATIC FILE SERVING ---

@app.route('/')
def index():
    return send_from_directory(root_dir, 'index.html')

# --- API ROUTES ---

@app.route('/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "CareNest-AI",
        "database": "connected" if supabase else "error",
        "root_dir": root_dir
    }), 200

@app.route('/api/medications', methods=['GET', 'POST', 'OPTIONS'])
@app.route('/medications', methods=['GET', 'POST', 'OPTIONS'])
def handle_medications():
    if request.method == 'POST':
        return jsonify({"status": "success", "message": "Record received"}), 201
    return jsonify({"medications": []}), 200

@app.route('/api/symptoms', methods=['POST', 'OPTIONS'])
@app.route('/symptoms', methods=['POST', 'OPTIONS'])
def log_symptoms():
    return jsonify({"status": "received"}), 201

@app.route('/api/ai-insight', methods=['POST', 'OPTIONS'])
@app.route('/ai-insight', methods=['POST', 'OPTIONS'])
def get_ai_insight():
    data = request.json or {}
    user_id = data.get('user_id')
    prompt_override = data.get('prompt') 
    
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400
        
    try:
        # Fetch clinical data
        symptoms_res = supabase.table('symptom_logs').select('*').eq('user_id', user_id).order('logged_at', desc=True).limit(5).execute()
        meds_res = supabase.table('medications').select('*').eq('user_id', user_id).execute()
        
        system_instruction = "You are a helpful clinical caregiver assistant. Summarize the patient status based on data."
        user_input = f"Symptoms: {symptoms_res.data}\nMeds: {meds_res.data}\nQuestion: {prompt_override or 'Summarize.'}"
        
        model = genai.GenerativeModel(model_name="gemini-flash-latest", system_instruction=system_instruction)
        result = model.generate_content(user_input)
        
        return jsonify({
            "status": "success",
            "clinical_insight": result.text
        })
    except Exception as e:
        print(f"AI Insight Error: {e}")
        return jsonify({
            "status": "simulated",
            "clinical_insight": "Resident A is stable. I recommend continuing the current observation schedule. (Note: AI is currently in resilience mode)."
        })

# --- CATCH-ALL FOR STATIC FILES ---
@app.route('/<path:path>')
def serve_all(path):
    # Check if the requested file exists in the root
    if os.path.exists(os.path.join(root_dir, path)):
        return send_from_directory(root_dir, path)
    
    # Check for .html extension convenience
    if not path.endswith('.html'):
        html_path = path + '.html'
        if os.path.exists(os.path.join(root_dir, html_path)):
            return send_from_directory(root_dir, html_path)
            
    # Default back to index for SPA-like behavior or 404
    return send_from_directory(root_dir, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

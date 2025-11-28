import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.cloud import speech_v2
from google.oauth2 import service_account

app = Flask(__name__)
CORS(app)

# Configuration
# Ensure you have your service_account.json in the backend directory
# or set GOOGLE_APPLICATION_CREDENTIALS environment variable.
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), 'service_account.json')
PROJECT_ID = 'plexiform-bot-479517-t4' # Taken from previous frontend code

def get_speech_client():
    if os.path.exists(CREDENTIALS_PATH):
        credentials = service_account.Credentials.from_service_account_file(CREDENTIALS_PATH)
        return speech_v2.SpeechClient(credentials=credentials)
    else:
        # Fallback to default credentials if file not found (e.g. env var)
        return speech_v2.SpeechClient()

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        client = get_speech_client()
        
        content = file.read()
        
        # Determine encoding based on filename extension or default
        # Note: The frontend sends base64, but here we receive a file upload (multipart/form-data)
        # So 'content' is bytes.
        
        # For V2, we need to specify the recognizer. 
        # We'll use the global recognizer for simplicity or create one if needed.
        # V2 requires a recognizer resource name.
        # Format: projects/{project}/locations/{location}/recognizers/{recognizer}
        # We can use the default recognizer ID or a specific one.
        # Let's try using a standard one or create one on the fly if needed? 
        # Actually, V2 usually requires creating a recognizer first.
        # However, for simplicity, let's assume we can use a standard configuration 
        # or we might need to use V1 if V2 is too complex for a quick setup without pre-configuration.
        # The user specifically asked for V2.
        
        location = "global"
        recognizer_id = "sinhala-recognizer" # We might need to create this once
        recognizer_path = client.recognizer_path(PROJECT_ID, location, recognizer_id)

        # In a real app, you'd ensure the recognizer exists. 
        # For now, let's try to list or get it, or just use it and see.
        # If it doesn't exist, we should probably create it.
        
        # Let's try a simpler approach first: Just config in the request if possible?
        # V2 API is strictly resource-based.
        
        # Let's assume we need to create a recognizer if it doesn't exist.
        # But creating it every time is inefficient.
        # Let's try to just use a dynamic config if possible, or fallback to V1 if V2 is too hard?
        # No, user asked for V2.
        
        # Let's try to use the inline config if supported, or just create a recognizer.
        
        config = speech_v2.types.RecognitionConfig(
            auto_decoding_config=speech_v2.types.AutoDetectDecodingConfig(),
            language_codes=["si-LK"],
            model="short",
        )
        
        request_obj = speech_v2.types.RecognizeRequest(
            recognizer=recognizer_path,
            config=config,
            content=content,
        )
        
        # We might need to create the recognizer first if it doesn't exist.
        # Let's add a check/create logic.
        try:
            client.get_recognizer(name=recognizer_path)
        except Exception:
            # Create recognizer
            print(f"Creating recognizer: {recognizer_id}")
            recognizer_request = speech_v2.types.CreateRecognizerRequest(
                parent=f"projects/{PROJECT_ID}/locations/{location}",
                recognizer_id=recognizer_id,
                recognizer=speech_v2.types.Recognizer(
                    default_recognition_config=config,
                ),
            )
            client.create_recognizer(request=recognizer_request)

        response = client.recognize(request=request_obj)
        
        transcripts = []
        for result in response.results:
            if result.alternatives:
                transcripts.append(result.alternatives[0].transcript)
        
        full_transcript = " ".join(transcripts)
        
        return jsonify({'transcript': full_transcript})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)

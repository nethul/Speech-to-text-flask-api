import os
import json
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.cloud import speech_v2
from google.cloud import texttospeech
from google.oauth2 import service_account

app = Flask(__name__)
CORS(app)

# Configuration
# Ensure you have your service_account.json in the backend directory
# or set GOOGLE_APPLICATION_CREDENTIALS environment variable.
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), 'service_account.json')
PROJECT_ID = 'plexiform-bot-479517-t4' # Taken from previous frontend code

def get_credentials():
    # Check for credentials in environment variable (for Heroku)
    google_credentials_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    
    if google_credentials_json:
        try:
            credentials_info = json.loads(google_credentials_json)
            return service_account.Credentials.from_service_account_info(credentials_info)
        except json.JSONDecodeError:
            print("Error: GOOGLE_CREDENTIALS_JSON is not valid JSON.")
            pass
    
    # Fallback to file
    if os.path.exists(CREDENTIALS_PATH):
        return service_account.Credentials.from_service_account_file(CREDENTIALS_PATH)
    
    return None

def get_speech_client():
    credentials = get_credentials()
    if credentials:
        return speech_v2.SpeechClient(credentials=credentials)
    return speech_v2.SpeechClient()

def get_tts_client():
    credentials = get_credentials()
    if credentials:
        return texttospeech.TextToSpeechClient(credentials=credentials)
    return texttospeech.TextToSpeechClient()

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
        
        location = "global"
        recognizer_id = "sinhala-recognizer"
        recognizer_path = client.recognizer_path(PROJECT_ID, location, recognizer_id)

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
        
        # Check/Create recognizer logic
        try:
            client.get_recognizer(name=recognizer_path)
        except Exception:
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

@app.route('/tts', methods=['POST'])
def text_to_speech():
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': 'No text provided'}), 400
    
    text = data['text']

    try:
        client = get_tts_client()

        input_text = texttospeech.SynthesisInput(text=text)

        # Note: Standard voice for Sinhala might be limited. 
        # Using a standard voice if available, or just language code.
        voice = texttospeech.VoiceSelectionParams(
            language_code="si-LK",
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        response = client.synthesize_speech(
            input=input_text, voice=voice, audio_config=audio_config
        )

        # Return base64 encoded audio
        audio_content = base64.b64encode(response.audio_content).decode('utf-8')
        
        return jsonify({'audioContent': audio_content})

    except Exception as e:
        print(f"Error in TTS: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)

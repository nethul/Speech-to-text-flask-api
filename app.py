import os
import json
import base64
import struct
import mimetypes
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.cloud import speech_v2
from google.cloud import texttospeech
from google.oauth2 import service_account
from google import genai
from google.genai import types

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
            model="long",
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

def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Generates a WAV file header for the given audio data and parameters."""
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",          # ChunkID
        chunk_size,       # ChunkSize
        b"WAVE",          # Format
        b"fmt ",          # Subchunk1ID
        16,               # Subchunk1Size (16 for PCM)
        1,                # AudioFormat (1 for PCM)
        num_channels,     # NumChannels
        sample_rate,      # SampleRate
        byte_rate,        # ByteRate
        block_align,      # BlockAlign
        bits_per_sample,  # BitsPerSample
        b"data",          # Subchunk2ID
        data_size         # Subchunk2Size
    )
    return header + audio_data

def parse_audio_mime_type(mime_type: str) -> dict:
    """Parses bits per sample and rate from an audio MIME type string."""
    bits_per_sample = 16
    rate = 24000

    parts = mime_type.split(";")
    for param in parts:
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate_str = param.split("=", 1)[1]
                rate = int(rate_str)
            except (ValueError, IndexError):
                pass
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass

    return {"bits_per_sample": bits_per_sample, "rate": rate}

@app.route('/tts', methods=['POST'])
def text_to_speech():
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': 'No text provided'}), 400
    
    text = data['text']

    try:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
             return jsonify({'error': 'GOOGLE_API_KEY not found'}), 500

        client = genai.Client(api_key=api_key)

        model = "gemini-2.5-flash-preview-tts"
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=text),
                ],
            ),
        ]
        generate_content_config = types.GenerateContentConfig(
            temperature=1,
            response_modalities=["audio"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Zephyr"
                    )
                )
            ),
        )

        combined_audio_data = b""
        last_mime_type = "audio/wav"

        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if (
                chunk.candidates is None
                or chunk.candidates[0].content is None
                or chunk.candidates[0].content.parts is None
            ):
                continue
            
            part = chunk.candidates[0].content.parts[0]
            if part.inline_data and part.inline_data.data:
                combined_audio_data += part.inline_data.data
                last_mime_type = part.inline_data.mime_type
        
        if not combined_audio_data:
            return jsonify({'error': 'No audio generated'}), 500

        final_audio = combined_audio_data
        file_extension = mimetypes.guess_extension(last_mime_type)
        
        if file_extension is None or file_extension == ".bin":
             final_audio = convert_to_wav(combined_audio_data, last_mime_type)

        audio_content = base64.b64encode(final_audio).decode('utf-8')
        return jsonify({'audioContent': audio_content})

    except Exception as e:
        print(f"Error in TTS: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)

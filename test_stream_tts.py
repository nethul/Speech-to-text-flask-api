import requests
import sys

def test_stream_tts():
    url = 'http://127.0.0.1:5000/stream_tts'
    text = "මේක සිංහල හඬ පරීක්ෂණයක්. ආයුබෝවන්!" # "This is a Sinhala voice test. Hello!"
    
    print(f"Sending request to {url} with text: {text}")
    
    try:
        response = requests.post(url, json={'text': text}, stream=True)
        
        if response.status_code == 200:
            print("Response received. Streaming audio...")
            with open('output_stream.mp3', 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
                        print(".", end="", flush=True)
            print("\nAudio saved to output_stream.mp3")
        else:
            print(f"Error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_stream_tts()

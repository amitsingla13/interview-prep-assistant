import os
import requests

def transcribe_audio_whisper(audio_path, openai_api_key):
    """Send audio file to OpenAI Whisper API and return transcription."""
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {openai_api_key}"}
    files = {"file": open(audio_path, "rb")}
    data = {"model": "whisper-1"}
    response = requests.post(url, headers=headers, files=files, data=data)
    response.raise_for_status()
    return response.json()["text"]


def synthesize_speech_openai(text, openai_api_key, voice="alloy"):
    """Send text to OpenAI TTS API and return audio content (mp3)."""
    url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json"
    }
    json_data = {
        "model": "tts-1",
        "input": text,
        "voice": voice,
        "response_format": "mp3"
    }
    response = requests.post(url, headers=headers, json=json_data)
    response.raise_for_status()
    return response.content

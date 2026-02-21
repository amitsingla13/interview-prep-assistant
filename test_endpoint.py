"""Test the /api/realtime/token endpoint via running Flask app."""
import requests
import json

r = requests.get('http://localhost:5000/api/realtime/token?mode=interview')
print(f'Status: {r.status_code}')

if r.status_code == 200:
    data = r.json()
    if 'value' in data:
        print(f'Token: {data["value"][:30]}...')
    if 'session' in data:
        print(f'Session model: {data["session"].get("model")}')
        print(f'Instructions length: {len(data["session"].get("instructions",""))}')
        audio = data['session'].get('audio', {})
        td = audio.get('input', {}).get('turn_detection', {})
        print(f'Turn detection: {td.get("type")} eagerness={td.get("eagerness")}')
        trans = audio.get('input', {}).get('transcription', {})
        print(f'Transcription: {trans}')
        print(f'Voice: {audio.get("output", {}).get("voice")}')
    print(f'Response keys: {list(data.keys())}')
else:
    print(f'Error: {r.text[:500]}')

"""Test ephemeral token creation with both model names."""
import requests, os, json, sys
sys.path.insert(0, 'src')

# Load API key
api_key = os.getenv('OPENAI_API_KEY', '')
if not api_key and os.path.exists('.env'):
    for line in open('.env'):
        line = line.strip()
        if line.startswith('OPENAI_API_KEY'):
            api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
if not api_key:
    try:
        import config
        api_key = config.OPENAI_API_KEY
    except:
        pass

print(f'API key: {api_key[:10]}...{api_key[-4:]}')

def test_model(model_name):
    cfg = {
        "session": {
            "type": "realtime",
            "model": model_name,
            "instructions": "Say hello briefly.",
            "output_modalities": ["audio"],
            "audio": {
                "input": {
                    "turn_detection": {
                        "type": "semantic_vad",
                        "eagerness": "auto",
                        "create_response": True,
                        "interrupt_response": True,
                    },
                    "transcription": {
                        "model": "whisper-1",
                        "language": "en",
                    },
                },
                "output": {
                    "voice": "marin",
                }
            },
        }
    }
    r = requests.post(
        'https://api.openai.com/v1/realtime/client_secrets',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json=cfg, timeout=10,
    )
    print(f'\n=== Model: {model_name} ===')
    print(f'Status: {r.status_code}')
    if r.status_code == 200:
        data = r.json()
        print(f'Keys: {list(data.keys())}')
        if 'client_secret' in data:
            print(f'Token: {data["client_secret"]["value"][:25]}...')
            print(f'Expires: {data["client_secret"].get("expires_at")}')
        if 'session' in data:
            sess = data['session']
            print(f'Session model: {sess.get("model")}')
            print(f'Session voice: {json.dumps(sess.get("audio", {}).get("output", {}))}')
            print(f'Session VAD: {json.dumps(sess.get("audio", {}).get("input", {}).get("turn_detection", {}))}')
            print(f'Session modalities: {sess.get("output_modalities")}')
    else:
        print(f'Error: {r.text[:500]}')

test_model('gpt-realtime')
test_model('gpt-4o-realtime-preview')
test_model('gpt-4o-realtime-preview-2025-06-03')
test_model('gpt-4o-mini-realtime-preview')

// voice.js — On-demand TTS playback & UI helpers
// Main recording/VAD/interruption is handled in index.html inline script
// This file ONLY provides: speakText(), stopTTSPlayback(), UI helpers
// IMPORTANT: Do NOT define startRecording() or stopRecordingAndSend() here
// as they would overwrite the inline VAD-based versions and break everything.

// --- Loading and error UI helpers ---
function showLoadingIndicator(msg) {
    let el = document.getElementById('voice-loading');
    if (!el) {
        el = document.createElement('div');
        el.id = 'voice-loading';
        el.style = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#fff;padding:10px 20px;border-radius:8px;box-shadow:0 2px 8px #0002;z-index:9999;font-size:15px;color:#333;';
        document.body.appendChild(el);
    }
    el.textContent = msg;
    el.style.display = '';
}

function hideLoadingIndicator() {
    const el = document.getElementById('voice-loading');
    if (el) el.style.display = 'none';
}

function showError(msg) {
    let el = document.getElementById('voice-error');
    if (!el) {
        el = document.createElement('div');
        el.id = 'voice-error';
        el.style = 'position:fixed;top:60px;left:50%;transform:translateX(-50%);background:#f8d7da;padding:10px 20px;border-radius:8px;box-shadow:0 2px 8px #0002;z-index:9999;font-size:15px;color:#721c24;';
        document.body.appendChild(el);
    }
    el.textContent = msg;
    el.style.display = '';
    setTimeout(() => { el.style.display = 'none'; }, 3500);
}

// --- On-demand TTS playback (for manual play button in input area) ---
let ttsAudioElement = null;

async function speakText(text) {
    stopTTSPlayback();
    if (!text || !text.trim()) return;
    try {
        showLoadingIndicator('Generating audio...');
        const response = await fetch('/api/voice/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        hideLoadingIndicator();
        if (!response.ok) {
            showError('Could not generate audio.');
            return;
        }
        const arrayBuffer = await response.arrayBuffer();
        const blob = new Blob([arrayBuffer], { type: 'audio/ogg; codecs=opus' });
        const url = URL.createObjectURL(blob);
        ttsAudioElement = new Audio(url);
        ttsAudioElement.onended = () => {
            ttsAudioElement = null;
            URL.revokeObjectURL(url);
        };
        await ttsAudioElement.play();
    } catch (e) {
        hideLoadingIndicator();
        console.error('TTS error:', e);
        showError('Audio playback failed.');
    }
}

function stopTTSPlayback() {
    if (ttsAudioElement) {
        ttsAudioElement.pause();
        ttsAudioElement.currentTime = 0;
        ttsAudioElement = null;
    }
}
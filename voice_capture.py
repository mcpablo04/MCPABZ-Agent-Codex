"""Record a short prompt and transcribe it locally; audio stays in memory."""
import json
import sys
import threading
from pathlib import Path

def emit(kind, **values):
    print(json.dumps({'event': kind, **values}, ensure_ascii=True), flush=True)

def main():
    try:
        import numpy as np
        import sounddevice as sd
        from faster_whisper import WhisperModel
        model_dir = Path(__file__).resolve().parent / 'voice_model'
        if not (model_dir / 'model.bin').is_file():
            raise RuntimeError('The local voice model is missing. Run the voice setup first.')
        chunks = []
        stopped = threading.Event()
        def stop_on_input():
            sys.stdin.readline()
            stopped.set()
        def callback(indata, frames, timestamp, status):
            chunks.append(indata.copy())
        threading.Thread(target=stop_on_input, daemon=True).start()
        with sd.InputStream(samplerate=16000, channels=1, dtype='float32', callback=callback):
            emit('recording')
            stopped.wait(120)
        if not chunks:
            raise RuntimeError('No microphone audio was recorded.')
        audio = np.concatenate(chunks).reshape(-1)
        if audio.size == 0 or float(np.max(np.abs(audio))) < 0.001:
            raise RuntimeError('No audible speech was detected. Check your microphone.')
        emit('transcribing')
        model = WhisperModel(str(model_dir), device='cpu', compute_type='int8', local_files_only=True)
        segments, _ = model.transcribe(audio, beam_size=5, vad_filter=True)
        text = ' '.join(segment.text.strip() for segment in segments).strip()
        if not text:
            raise RuntimeError('No speech was recognized. Please try again.')
        emit('result', text=text)
    except Exception as exc:
        emit('error', message=str(exc)[:500])
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())

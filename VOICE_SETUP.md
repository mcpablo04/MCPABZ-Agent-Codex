# Local voice typing

Voice typing records up to 2 minutes from the default microphone, then uses the multilingual faster-whisper small model on the CPU. The recording stays in memory and is not sent to a transcription service. Review the resulting text before sending it to a chat model; sending that text uses the selected provider as usual. Recognition quality and speed vary by language, microphone, and computer.

## Setup on Windows

Install Python 3.12 and run these commands from the agent folder:

```powershell
py -3.12 -m venv voice_env
.\voice_env\Scripts\python.exe -m pip install -r requirements-voice.txt
.\voice_env\Scripts\python.exe -c "from faster_whisper.utils import download_model; download_model('small', output_dir='voice_model')"
```

The setup downloads Python packages and a model of several hundred megabytes. After setup, voice typing does not need an internet connection. If the default microphone doesn't work, select it in Windows sound settings and check microphone access for desktop apps.

For a source release, include `voice_capture.py` and `requirements-voice.txt`; exclude `voice_env/`, `voice_model/`, caches, API keys, and personal conversation data. A virtual environment is specific to the machine where it was created; users must run setup on their own computers. Check the individual model and dependency licenses before redistributing them.

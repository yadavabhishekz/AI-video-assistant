from dotenv import load_dotenv
load_dotenv()

from utils.audio_processor import process_input
from core.transcriber import transcribe_all



source = "https://youtu.be/_I_HK5TrSpc"
language = "hinglish"

chunks = process_input(source= source)

transcript = transcribe_all(chunks=chunks)


print("\n### TRANSCRIPT ###\n")
print(transcript)
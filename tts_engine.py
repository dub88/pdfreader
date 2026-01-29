from AVFoundation import (
    AVSpeechSynthesizer, 
    AVSpeechUtterance, 
    AVSpeechSynthesisVoice,
    AVSpeechBoundaryImmediate
)
import time
from typing import List, Dict

class TTSEngine:
    def __init__(self):
        # AVFoundation is the modern Apple API for speech
        self._synth = AVSpeechSynthesizer.alloc().init()
        self._voice = None
        self._rate = 0.5 # Default AVFoundation rate (0.0 to 1.0)
        self._volume = 1.0
        self.is_paused = False

    def get_voices(self) -> List[Dict]:
        """Returns a list of available macOS voices with metadata."""
        voices = AVSpeechSynthesisVoice.speechVoices()
        results = []
        
        # Mapping for quality enums
        qualities = {1: "Standard", 2: "Enhanced", 3: "Premium"}
        
        # DEBUG: Print all voice IDs to console to help track down Siri Voice 4
        print(f"--- TOTAL VOICES FOUND: {len(voices)} ---")
        
        for v in voices:
            name = v.name()
            v_id = v.identifier()
            lang = v.language()
            quality_num = v.quality()
            quality = qualities.get(quality_num, "Standard")
            
            # Print each one to help user find the internal name
            print(f"ID: {v_id} | Name: {name} | Lang: {lang} | Quality: {quality}")
            
            # Siri/Personal voice detection
            is_siri = "siri" in name.lower() or "siri" in v_id.lower()
            is_personal = "personalvoice" in v_id.lower() or "personal" in name.lower()
            
            results.append({
                "id": v_id, 
                "name": name, 
                "lang": lang, 
                "quality": quality,
                "quality_val": quality_num,
                "is_siri": is_siri,
                "is_personal": is_personal
            })
        return results

    def preview(self, voice_id: str):
        """Speaks a short preview sentence using the selected voice."""
        self.stop()
        preview_text = "Hello, I am a high-quality voice on your Mac. I can read your documents with natural prosody."
        
        # Check if the voice is non-English to provide a better preview
        voice = AVSpeechSynthesisVoice.voiceWithIdentifier_(voice_id)
        if voice and not voice.language().startswith("en"):
            preview_text = "Hello, I am a native voice. I can read documents in my language, or read English with my natural accent."

        self.speak(preview_text)

    def set_rate(self, rate: float):
        """
        AVFoundation rate scale is different. 
        0.5 is normal speed. 0.0 is very slow, 1.0 is very fast.
        Input rate 1.0x -> 0.5
        Input rate 2.0x -> 0.65
        """
        # Map 0.5x-3.0x to AVFoundation's 0.0-1.0
        # Simple linear approximation:
        new_rate = 0.2 + (rate * 0.3)
        self._rate = max(0.0, min(1.0, new_rate))

    def set_volume(self, volume: float):
        self._volume = volume

    def speak(self, text: str):
        """Starts speaking text using modern AVFoundation."""
        self.is_paused = False
        utterance = AVSpeechUtterance.speechUtteranceWithString_(text)
        
        if self._voice:
            utterance.setVoice_(self._voice)
        
        utterance.setRate_(self._rate)
        utterance.setVolume_(self._volume)
        
        self._synth.speakUtterance_(utterance)

    def is_speaking(self) -> bool:
        """Checks if the synthesizer is speaking or has content in queue."""
        return self._synth.isSpeaking()

    def pause(self):
        self.is_paused = True
        self._synth.pauseSpeakingAtBoundary_(AVSpeechBoundaryImmediate)

    def resume(self):
        self.is_paused = False
        self._synth.continueSpeaking()

    def stop(self):
        self.is_paused = False
        self._synth.stopSpeakingAtBoundary_(AVSpeechBoundaryImmediate)

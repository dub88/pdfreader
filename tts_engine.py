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
        """Returns a list of available macOS voices using the modern AVFoundation API."""
        voices = AVSpeechSynthesisVoice.speechVoices()
        results = []
        for v in voices:
            name = v.name()
            v_id = v.identifier()
            # Clean up name: "Siri (com.apple.ttsvoice.siri-alex)" -> "Siri (Alex)"
            # Usually name() is already clean like "Siri" or "Samantha"
            results.append({"id": v_id, "name": name})
        return results

    def set_voice(self, voice_id: str):
        self._voice = AVSpeechSynthesisVoice.voiceWithIdentifier_(voice_id)

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

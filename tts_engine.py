from AVFoundation import (
    AVSpeechSynthesizer, 
    AVSpeechUtterance, 
    AVSpeechSynthesisVoice,
    AVSpeechBoundaryImmediate
)
import time
import os
import re
from typing import List, Dict

class TTSEngine:
    def __init__(self):
        # Using native macOS speech engine
        self._synth = AVSpeechSynthesizer.alloc().init()
        self._voice = None
        self._rate = 0.5 
        self._volume = 1.0
        self.is_paused = False

    def get_voices(self) -> List[Dict]:
        """Returns a list of available macOS voices with metadata."""
        voices = AVSpeechSynthesisVoice.speechVoices()
        results = []
        qualities = {1: "Standard", 2: "Enhanced", 3: "Premium"}
        
        # Novelty/Creepy voices (Legacy Mac voices) to be hidden
        creepy_keywords = {
            "albert", "badnews", "bahh", "bells", "boing", "bubbles", "cellos", 
            "deranged", "goodnews", "hysterical", "junior", "organ", "princess", 
            "ralph", "trinoids", "whisper", "zarvox", "eloquence", "jester", "wobble", "superstar"
        }
        
        for v in voices:
            name = v.name()
            v_id = v.identifier().lower()
            lang = v.language()
            quality_num = v.quality()
            
            is_personal = "personalvoice" in v_id or "personal" in name.lower()
            is_novelty = any(x in v_id for x in creepy_keywords) or any(x in name.lower() for x in ["bad news", "good news", "pipe organ", "jester", "wobble", "superstar"])
            is_compact = "compact" in v_id
            
            # High-Quality detection fallback for Sequoia
            is_premium = (quality_num >= 2 or is_personal or ("compact" not in v_id and not is_novelty))

            results.append({
                "id": v.identifier(), 
                "name": name, 
                "lang": lang, 
                "quality": qualities.get(quality_num, "Standard"),
                "quality_val": quality_num,
                "is_personal": is_personal,
                "is_novelty": is_novelty,
                "is_premium": is_premium
            })
        return results

    def set_voice(self, voice_id: str):
        self._voice = AVSpeechSynthesisVoice.voiceWithIdentifier_(voice_id)

    def set_rate(self, rate: float):
        # Map 0.5x-3.0x to AVFoundation's 0.0-1.0
        new_rate = 0.2 + (rate * 0.3)
        self._rate = max(0.0, min(1.0, new_rate))

    def speak(self, text: str):
        self.is_paused = False
        utterance = AVSpeechUtterance.speechUtteranceWithString_(text)
        if self._voice:
            utterance.setVoice_(self._voice)
        utterance.setRate_(self._rate)
        utterance.setVolume_(self._volume)
        self._synth.speakUtterance_(utterance)

    def is_speaking(self) -> bool:
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

    def preview(self, voice_id: str):
        old_voice = self._voice
        self.set_voice(voice_id)
        self.speak("Hello, this is my high-quality voice.")
        self._voice = old_voice

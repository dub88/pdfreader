from AVFoundation import (
    AVSpeechSynthesizer, 
    AVSpeechUtterance, 
    AVSpeechSynthesisVoice,
    AVSpeechBoundaryImmediate,
    AVSpeechSynthesizerDelegate
)
from Foundation import NSObject
import time
import os
import re
from typing import List, Dict, Callable

class TTSDelegate(NSObject):
    def initWithCallback_(self, callback: Callable):
        self = super().init()
        if self:
            self._callback = callback
        return self

    def speechSynthesizer_willSpeakRangeOfSpeechString_utterance_(self, synth, char_range, utterance):
        # char_range is an NSRange (location, length)
        if self._callback:
            self._callback(char_range.location, char_range.length)

class TTSEngine:
    def __init__(self, on_word_callback=None):
        self._synth = AVSpeechSynthesizer.alloc().init()
        self._delegate = TTSDelegate.alloc().initWithCallback_(on_word_callback)
        self._synth.setDelegate_(self._delegate)
        
        self._voice = None
        self._rate = 0.5 
        self._volume = 1.0
        self.is_paused = False

    def get_voices(self) -> List[Dict]:
        """Returns a list of available macOS voices with metadata."""
        voices = AVSpeechSynthesisVoice.speechVoices()
        results = []
        qualities = {1: "Standard", 2: "Enhanced", 3: "Premium"}
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
            is_premium = (quality_num >= 2 or is_personal or ("compact" not in v_id and not is_novelty))

            results.append({
                "id": v.identifier(), 
                "name": name, 
                "lang": lang, 
                "quality": qualities.get(quality_num, "Standard"),
                "quality_val": quality_num,
                "is_siri": False, 
                "is_personal": is_personal,
                "is_novelty": is_novelty,
                "is_premium": is_premium
            })
        return results

    def preview(self, voice_id: str):
        self.stop()
        self.speak("Hello, I am a high-quality voice on your Mac.")

    def set_voice(self, voice_id: str):
        self._voice = AVSpeechSynthesisVoice.voiceWithIdentifier_(voice_id)

    def set_rate(self, rate: float):
        new_rate = 0.2 + (rate * 0.3)
        self._rate = max(0.0, min(1.0, new_rate))

    def speak(self, text: str):
        self.is_paused = False
        
        # PRE-PROCESS: Fix Year Pronunciation (e.g. 1975 -> nineteen seventy five)
        processed_text = self._fix_years(text)
        
        utterance = AVSpeechUtterance.speechUtteranceWithString_(processed_text)
        if self._voice:
            utterance.setVoice_(self._voice)
        utterance.setRate_(self._rate)
        utterance.setVolume_(self._volume)
        self._synth.speakUtterance_(utterance)

    def _fix_years(self, text: str) -> str:
        """Regex to find 4-digit years and make them phonetic."""
        def year_repl(match):
            year = match.group(0)
            # Only process likely years (1800-2099)
            y_int = int(year)
            if 1800 <= y_int <= 2099:
                # Handle 2000-2009 differently
                if 2000 <= y_int <= 2009:
                    return f"two thousand {y_int % 100 if y_int % 100 > 0 else ''}"
                else:
                    first_half = year[:2]
                    second_half = year[2:]
                    return f"{first_half} {second_half}"
            return year
            
        return re.sub(r'\b\d{4}\b', year_repl, text)

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

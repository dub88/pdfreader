from AppKit import NSSpeechSynthesizer
from typing import List, Dict

class TTSEngine:
    def __init__(self):
        # Direct AppKit synthesizer. NO DELEGATES to avoid GIL/crashes.
        self._synth = NSSpeechSynthesizer.alloc().initWithVoice_(None)
        self.is_paused = False

    def get_voices(self) -> List[Dict]:
        """Returns a list of available macOS voices."""
        voices = list(NSSpeechSynthesizer.availableVoices())
        results = []
        for v_id in voices:
            attr = NSSpeechSynthesizer.attributesForVoice_(v_id)
            name = attr.get('VoiceName', v_id)
            results.append({"id": v_id, "name": name})
        return results

    def set_voice(self, voice_id: str):
        self._synth.setVoice_(voice_id)

    def set_rate(self, rate: float):
        # Base rate is usually 200.
        self._synth.setRate_(200 * rate)

    def set_volume(self, volume: float):
        self._synth.setVolume_(volume)

    def speak(self, text: str):
        """Starts speaking text asynchronously on the system level."""
        self.is_paused = False
        self._synth.startSpeakingString_(text)

    def is_speaking(self) -> bool:
        """Checks if the system is currently outputting speech."""
        return self._synth.isSpeaking()

    def pause(self):
        self.is_paused = True
        self._synth.pauseSpeakingAtBoundary_(0)

    def resume(self):
        self.is_paused = False
        self._synth.continueSpeaking()

    def stop(self):
        self.is_paused = False
        self._synth.stopSpeaking()

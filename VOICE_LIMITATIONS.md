# PDF Speaker - Voice Limitations on macOS

## Siri Voices Are NOT Available to Third-Party Apps

**Important:** The high-quality "Siri voices" (Aaron, Nicky, Martha, Arthur, Helena, etc.) that power Apple's Siri assistant are **NOT available** to third-party applications like PDF Speaker.

This is an intentional restriction by Apple. The `AVSpeechSynthesizer` API, which all third-party macOS apps must use for text-to-speech, explicitly excludes Siri voices.

### What This Means

- The voices you download in **System Settings → Siri & Spotlight** are for Siri only
- PDF Speaker can only access voices from **System Settings → Accessibility → Spoken Content**
- Apps like Speechify face the same limitation (they use their own cloud-based voices as a workaround)

### Available Voice Tiers

PDF Speaker can access these voice categories:

| Tier | Quality | Examples | How to Get |
|------|---------|----------|------------|
| **Enhanced** | ★★★ | Samantha (Enhanced), Daniel (Enhanced) | Accessibility → Spoken Content → Manage Voices |
| **Premium** | ★★ | Various language voices | Accessibility → Spoken Content → Manage Voices |
| **Standard** | ★ | Compact versions (pre-installed) | Pre-installed |
| **Eloquence** | ★ | Eddy, Flo, Reed, etc. | Pre-installed (accessibility focus) |

### How to Get the Best Available Voices

1. Open **System Settings** → **Accessibility** → **Spoken Content**
2. Click on **System Voice** dropdown
3. Select **Manage Voices...**
4. Expand **English (United States)** (or your preferred language)
5. Download voices marked as **(Enhanced)** - these are the highest quality available to third-party apps
6. Restart PDF Speaker after downloading

### Recommended Voices

For the best listening experience, we recommend:

- **Samantha (Enhanced)** - Female, US English, ~200MB
- **Daniel (Enhanced)** - Male, British English, ~200MB
- **Karen (Enhanced)** - Female, Australian English
- **Moira (Enhanced)** - Female, Irish English

### Technical Details

- **API Used:** `AVSpeechSynthesizer` (AVFoundation framework)
- **API Method:** `AVSpeechSynthesisVoice.speechVoices()`
- **Apple Documentation:** Siri voices are explicitly not returned by this API
- **Workaround:** None available. This is an OS-level restriction.

### macOS Sequoia Note

In macOS 15 Sequoia, Apple moved voice management to the **VoiceOver Utility** for some voice types. However, the "Spoken Content" section still controls which voices are available to third-party apps.

If voices are not appearing after download:
1. Restart the app
2. Try restarting the `SiriAUSP` process: `killall SiriAUSP` in Terminal
3. Check that voices appear in **Spoken Content** settings

---

*Last Updated: January 2026*

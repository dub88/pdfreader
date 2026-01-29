# Audile Technical Retrospective & Troubleshooting Log

## Executive Summary
This document records the technical challenges encountered during the rebranding of "PDF Speaker" to "Audile" and the subsequent stabilization release. Several critical crashes related to UI libraries (CustomTkinter) and macOS Native APIs (AVFoundation/PyObjC) were identified and resolved.

## Incident Log

### 1. CustomTkinter Transparency Crash
**Issue:**  
The application failed to launch with `ValueError: transparency is not allowed for this attribute`.
**Context:**  
Occurred in `main.py` during `CTkTabview` initialization.
**Cause:**  
We attempted to set `segmented_button_fg_color="transparent"`. While `fg_color` often accepts "transparent", the segmented button component within the tab view does not support this string value in the current version of CustomTkinter.
**Resolution:**  
Changed the attribute to `None`, which allows the default rendering behavior without triggering the validation error.

### 2. Tkinter Canvas Color Tuple Crash
**Issue:**  
Crash with `_tkinter.TclError: invalid color name "#F2F2F7 #1E1E1E"`.
**Context:**  
Occurred when initializing the PDF rendering `tk.Canvas`.
**Cause:**  
We passed a CustomTkinter-style color tuple `("#F2F2F7", "#1E1E1E")` (for Light/Dark mode auto-switching) to a standard Tkinter `Canvas` widget. Standard Tkinter widgets do not understand this tuple format.
**Resolution:**  
Implemented `darkdetect` logic to explicitly select the single hex color string corresponding to the system's current appearance mode at initialization.

### 3. Font Weight Validation Error
**Issue:**  
App crash due to `_tkinter.TclError: bad -weight value "semibold"`.
**Context:**  
Occurred when setting font properties for labels.
**Cause:**  
Tkinter's font engine typically accepts "normal" or "bold". "semibold" is not a valid standard Tkinter font weight, even though some modern wrappers might suggest it.
**Resolution:**  
Standardized all font weights to "bold".

### 4. PyObjC Protocol Import Error
**Issue:**  
`ImportError: cannot import name 'AVSpeechSynthesizerDelegate' from 'AVFoundation'`.
**Context:**  
Occurred in `tts_engine.py` when trying to implement the speech delegate.
**Cause:**  
In PyObjC, protocols (like `AVSpeechSynthesizerDelegate`) are informal properties of the Objective-C runtime and not importable python classes. You implement them by defining methods on an `NSObject` subclass, not by importing/inheriting a Python symbol for the protocol itself.
**Resolution:**  
Removed `AVSpeechSynthesizerDelegate` from the import list.

### 5. GIL Threading Crash (Fatal Python Error)
**Issue:**  
`Fatal Python error: PyEval_RestoreThread: the function must be called with the GIL held...`
**Context:**  
The application would proceed to launch but crash immediately or upon speech interaction.
**Cause:**  
The `AVSpeechSynthesizer` calls its delegate methods (like `speechSynthesizer:willSpeakRangeOfSpeechString:utterance:`) on an internal thread or the Cocoa main thread. When this callback tried to execute Python code (specifically updating the UI or even just processing logic), it conflicted with the Python Global Interpreter Lock (GIL) state required by the running Tkinter event loop. Without strict `PyObjCTools.AppHelper` usage or careful threading bridges, this causes a hard crash.
**Resolution:**  
Temporarily disabled the delegate assignment in `tts_engine.py`. This restores application stability at the cost of the experimental "word-level highlighting" feature, which will need to be re-architected (likely using a polling mechanism or `queue` based message passing) in a future release.

## Current State
The application is currently stable.
- **App Name:** Audile
- **Build Status:** Passing (PyInstaller)
- **Known Limitations:** Word-level karaoke highlighting is disabled to prevent crashes.

### 6. Regression & Persistence of Threading Issues
**Observations:**
After a `git pull` introduced new features including a re-attempt at word-level callbacks using `lambda: self.after(0, ...)` to route to the main thread, the application crashed again with the same GIL error.
**Analysis:**
Even with `self.after`, the initial entry point into the Python environment (the delegate method itself) runs on an unmanaged thread spawned by the OS audio subsystem. The crash occurs *before* `self.after` can effectively schedule the work, or simply due to the Python interpreter being invoked without the thread state being correctly set up for PyObjC.
**Final Action:**
The delegate was forcibly disabled again in `tts_engine.py`. For future implementations of word-level highlighting, we must use a polling approach (checking `output_channel` or timing estimates) or a rigorous `PyObjC` specific event loop bridge (e.g. `AppHelper.runEventLoop`), which would replace the standard Tkinter `mainloop`.

### 7. Application Icon Integration
**Action:**
Integrated `Audile-icon.png` as the official application icon.
**Process:**
Converted the high-resolution PNG to a multi-size `.icns` bundle using macOS `sips` and `iconutil` tools to ensure crisp rendering across all macOS display scales (Retina/Standard). Updated the PyInstaller build specification to include the `--icon` flag pointing to the generated `.icns` file.

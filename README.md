# PDF Speaker for macOS

PDF Speaker is a high-quality, native macOS application that reads your PDF documents aloud using Apple's premium Enhanced voices. Designed for a "listen-while-reading" experience, it features synchronized highlighting and smart text processing that rivals paid subscription services.

![App Screenshot](https://via.placeholder.com/800x600?text=PDF+Speaker+Screenshot)

## Features

*   **Premium Neural Voices**: Utilizes Apple's high-quality Enhanced voices (e.g., Samantha Enhanced) via the native macOS speech engine without requiring internet access or paid APIs. *Note: Actual Siri voices are restricted by Apple to first-party apps only.*
*   **Synchronized Highlighting**: Follow along with a yellow focus frame that moves paragraph-by-paragraph in perfect sync with the audio.
*   **Smart Text Extraction**:
    *   **Header/Footer Skipping**: Automatically ignores running headers, page numbers, and footers so your audiobook flows naturally.
    *   **Paragraph Merging**: Intelligently groups broken lines into coherent paragraphs for smooth, natural prosody.
    *   **Artifact Cleaning**: Automatically corrects common PDF optical recognition errors (e.g., "clifferent" -> "different", "I" mixed up with "1").
*   **Visual PDF Reader**:
    *   High-fidelity PDF rendering using PyMuPDF.
    *   **Fit-to-Width**: Dynamic zooming that automatically fits the page to your window size.
    *   **Auto-Scroll**: Keeps the active text centered in your view automatically.
*   **Navigation**: Jump to specific pages, skip back/forward, or browse visually.
*   **Progress Tracking**: Automatically remembers your exact position in every book, so you can close the app and pick up right where you left off.

## Tech Stack

*   **Python 3.13**
*   **CustomTkinter**: For a modern, dark-mode compatible UI.
*   **PyMuPDF (Fitz)**: For ultra-fast PDF rendering and text coordinate extraction.
*   **PyObjC**: For direct integration with the native macOS `AVSpeechSynthesizer` API (bypassing the limitations of cross-platform libraries).

## Installation

### Pre-built App
1.  Download the latest `PDF Speaker.app` from the Releases page.
2.  Drag it to your **Applications** folder.
3.  *Note*: On the first launch, you may need to right-click and select **Open** to bypass the unidentified developer warning.

### Running from Source
1.  Clone the repository:
    ```bash
    git clone https://github.com/yourusername/pdf-speaker.git
    cd pdf-speaker
    ```
2.  Create a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4.  Run the app:
    ```bash
    python3 main.py
    ```

## Building for Distribution
To package the app as a standalone macOS `.app` bundle:
```bash
pyinstaller --noconfirm --windowed --name "PDF Speaker" --add-data "venv/lib/python3.13/site-packages/customtkinter:customtkinter" main.py
```
*(Note: Adjust the path to `customtkinter` based on your local environment)*

## License
MIT License

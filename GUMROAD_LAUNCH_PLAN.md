# PDF Speaker for macOS - Gumroad Launch Plan

## 1. Storefront Details (Gumroad)

*   **Product Name**: PDF Speaker for macOS
*   **Price**: $19 (One-time payment)
*   **Tagline**: Stop paying subscriptions for text-to-speech. Use your Mac's premium Siri voices.
*   **Description**:
    PDF Speaker is a native macOS application designed for people who want to listen to their PDF documents, books, and articles without the $20/month subscription fee of tools like Speechify. 

    Powered by your Mac's built-in neural Siri voices, PDF Speaker provides a high-quality "listen-while-reading" experience with synchronized highlighting and smart text processing.

    **Key Features**:
    - **Premium Neural Voices**: Access Siri's best voices for free, offline, with no character limits.
    - **Voice Customization**: Hide voices you don't like and preview voices with a single click to find your perfect narrator.
    - **Bookmarks & Annotations**: Save noteworthy pages with custom notes to revisit your research or favorite chapters later.
    - **Synchronized Highlighting**: A visual focus frame follows the text as it’s read, perfect for deep work or learning.
    - **Smart Extraction**: Automatically skips headers, footers, and page numbers. Corrects common PDF artifacts like broken ligatures and "com- puter" hyphenation for a seamless "audiobook" flow.
    - **Native & Private**: Your documents never leave your computer. No internet required.
    - **Pick up where you left off**: Automatically remembers your position in every PDF.

---

## 2. Technical Packaging

To get the app ready for users to download, we need to package it as a standalone `.app` or a DMG.

### Build Command (PyInstaller):
```bash
# In your local environment with venv active
pip install pyinstaller pillow customtkinter pymupdf pyobjc-framework-AVFoundation pyobjc-framework-Cocoa darkdetect packaging

pyinstaller --noconfirm --windowed --name "PDF Speaker" \
--add-data "venv/lib/python3.13/site-packages/customtkinter:customtkinter" \
--hidden-import "PIL._tkinter_finder" \
--collect-all "customtkinter" \
--icon="icon.icns" \
main.py
```
*(Note: If you have a custom app icon, replace `icon.icns` with your path)*

### DMG Packaging:
1.  Create a folder named `PDF Speaker Release`.
2.  Move the generated `PDF Speaker.app` from the `dist` folder into it.
3.  Add a shortcut to the `/Applications` folder.
4.  Right-click the folder -> "Compress" (or use a tool like `create-dmg`).

---

## 3. Launch Marketing Assets

*   **Product Image**: Use a screenshot showing the "Dark Mode" UI with a PDF loaded and the yellow highlight frame active.
*   **The "Speechify Killer" Chart**: (Add this to the description)
    | Feature | PDF Speaker | Speechify / Premium TTS |
    | :--- | :--- | :--- |
    | **Price** | **$19 (Lifetime)** | $139+/year |
    | **Privacy** | Local-only | Cloud-processed |
    | **Voices** | Siri Premium | Proprietary AI |
    | **Limits** | Unlimited | Monthly character caps |

---

## 4. Next Steps for Matt

1.  **Run the Build**: Run the PyInstaller command above on your Mac to ensure the bundle works.
2.  **Zip & Upload**: Zip the `.app` bundle and upload it as the digital file on Gumroad.
3.  **Draft Storefront**: Copy-paste the description above into a new Gumroad product.
4.  **Set "Pay What You Want" (Optional)**: If you want to maximize initial reach to pay rent, set the price as `$15+` to encourage higher tips.

**Shall I help you refine the "Smart Extraction" logic or the UI design further before you build the final version?**

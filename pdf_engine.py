import fitz  # PyMuPDF
import re
from typing import List, Generator

class PDFEngine:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.doc = None
        self.total_pages = 0
        self.is_scanned = False

    def open(self) -> bool:
        """Opens the PDF document and checks if it's readable."""
        try:
            self.doc = fitz.open(self.file_path)
            self.total_pages = len(self.doc)
            
            # Check if likely scanned (very little text in first few pages)
            sample_text = ""
            for i in range(min(3, self.total_pages)):
                sample_text += self.doc[i].get_text()
            
            if len(sample_text.strip()) < 50:
                self.is_scanned = True
                
            return True
        except Exception as e:
            print(f"Error opening PDF: {e}")
            return False

    def close(self):
        if self.doc:
            self.doc.close()

    def get_page_size(self, page_num: int):
        """Returns (width, height) of the original PDF page."""
        if not self.doc or page_num < 1 or page_num > self.total_pages:
            return None, None
        page = self.doc[page_num - 1]
        return page.rect.width, page.rect.height

    def get_page_image(self, page_num: int, zoom: float = 2.0):
        """Returns a PIL image of the specified page."""
        if not self.doc or page_num < 1 or page_num > self.total_pages:
            return None
        
        page = self.doc[page_num - 1]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        from PIL import Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return img

    def get_page_data(self, page_num: int, doc_type: str = "Book"):
        """Returns coherent paragraphs with bboxes, adjusted by doc_type."""
        if not self.doc:
            return []

        page = self.doc[page_num - 1]
        page_height = page.rect.height
        
        # Adjust margin filtering based on document type
        # Books usually have large headers/footers; Papers have smaller ones.
        if doc_type == "Book":
            margin = page_height * 0.12
        elif doc_type == "Research":
            margin = page_height * 0.05
        else: # Standard Document
            margin = 0
            
        content_top, content_bottom = margin, page_height - margin

        blocks = page.get_text("dict")["blocks"]
        raw_blocks = []
        
        for b in blocks:
            if "lines" not in b: continue
            
            block_text = ""
            for line in b["lines"]:
                for span in line["spans"]:
                    block_text += span["text"]
                block_text += " "
            
            cleaned = self._clean_text(block_text)
            if cleaned:
                raw_blocks.append({
                    "text": cleaned,
                    "bbox": list(b["bbox"])
                })

        # Merge blocks that are close together (likely same paragraph)
        merged_blocks = []
        if not raw_blocks: return []
        
        current = raw_blocks[0]
        for i in range(1, len(raw_blocks)):
            next_b = raw_blocks[i]
            dist = next_b["bbox"][1] - current["bbox"][3]
            
            if 0 <= dist < 12: 
                current["text"] += " " + next_b["text"]
                current["bbox"][0] = min(current["bbox"][0], next_b["bbox"][0])
                current["bbox"][2] = max(current["bbox"][2], next_b["bbox"][2])
                current["bbox"][3] = next_b["bbox"][3]
            else:
                merged_blocks.append(current)
                current = next_b
        merged_blocks.append(current)
            
        # Final filter for headers/footers based on doc_type
        final_data = []
        for item in merged_blocks:
            y_mid = (item["bbox"][1] + item["bbox"][3]) / 2
            if content_top <= y_mid <= content_bottom:
                final_data.append(item)
            elif margin == 0: # If standard doc, keep everything
                final_data.append(item)
                
        return final_data

    def _clean_text(self, text: str) -> str:
        """Cleans up PDF artifacts and corrects font-mapping errors."""
        # Replace ligatures and specialized characters
        replacements = {
            "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
            "ﬅ": "st", "ﬆ": "st", "\u00ad": "", "\u2010": "-", "\u2011": "-",
            "\u2012": "-", "\u2013": "-", "\u2014": "--", "\u2018": "'",
            "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2026": "...",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
            
        # Remove end-of-line hyphenation (e.g. "com- puter" -> "computer")
        # Note: We look for a hyphen followed by a space because multiple spans 
        # were joined with spaces in get_page_data.
        text = re.sub(r"(\w+)-\s+(\w+)", r"\1\2", text)

        # Correct common font-mapping/OCR errors
        corrections = {
            r"\bclifferent\b": "different",
            r"\bcitYerent\b": "different",
            r"\btl1at\b": "that",
            r"\btllat\b": "that",
            r"\bvvith\b": "with",
            r"\bl\b": "I", # Standalone lowercase L as capital I
        }
        
        # Heuristic for standalone 'J' or '1' as 'I'
        text = re.sub(r"\b[J1]\b", "I", text) 
        
        for pattern, replacement in corrections.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Replace multiple spaces/newlines with single space
        text = re.sub(r"\s+", " ", text)
        
        return text.strip()

    def _split_into_sentences(self, text: str) -> List[str]:
        """Splits text into meaningful sentences/chunks for TTS."""
        # Simple regex-based sentence splitter
        # Look for punctuation followed by space and uppercase
        sentence_endings = r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])\s*$'
        sentences = re.split(sentence_endings, text)
        return [s.strip() for s in sentences if s.strip()]

if __name__ == "__main__":
    # Quick debug test
    import sys
    if len(sys.argv) > 1:
        engine = PDFEngine(sys.argv[1])
        if engine.open():
            print(f"Opened: {sys.argv[1]}, Pages: {engine.total_pages}, Scanned: {engine.is_scanned}")
            for i, block in enumerate(engine.get_blocks()):
                print(f"[{block['page']}] {block['text']}")
                if i > 10: break
            engine.close()

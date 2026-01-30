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
        """Returns paragraphs with both full text and word-level coordinate maps."""
        if not self.doc:
            return []

        page = self.doc[page_num - 1]
        page_height = page.rect.height
        
        if doc_type == "Book":
            margin = page_height * 0.12
        elif doc_type == "Research":
            margin = page_height * 0.05
        else:
            margin = 0
            
        content_top, content_bottom = margin, page_height - margin

        # Get detailed text with dictionary format for line-level control
        blocks = page.get_text("dict")["blocks"]
        final_blocks = []
        
        for b in blocks:
            if "lines" not in b: continue
            
            block_text = ""
            block_lines = []
            
            for line in b["lines"]:
                line_text = ""
                for span in line["spans"]:
                    line_text += span["text"] + " "
                
                block_text += line_text + " "
                block_lines.append({
                    "bbox": list(line["bbox"]),
                    "text": line_text.strip()
                })
            
            cleaned = self._clean_text(block_text)
            if cleaned:
                # Store the block with its internal lines for precise highlighting
                final_blocks.append({
                    "text": cleaned,
                    "bbox": list(b["bbox"]),
                    "lines": block_lines
                })

        # Merge blocks heuristic (natural paragraphs)
        merged = []
        if not final_blocks: return []
        
        curr = final_blocks[0]
        for i in range(1, len(final_blocks)):
            nxt = final_blocks[i]
            dist = nxt["bbox"][1] - curr["bbox"][3]
            
            # If blocks are close vertically, merge them into one natural speech unit
            if 0 <= dist < 12:
                curr["text"] += " " + nxt["text"]
                curr["lines"].extend(nxt["lines"])
                curr["bbox"][0] = min(curr["bbox"][0], nxt["bbox"][0])
                curr["bbox"][2] = max(curr["bbox"][2], nxt["bbox"][2])
                curr["bbox"][3] = nxt["bbox"][3]
            else:
                merged.append(curr)
                curr = nxt
        merged.append(curr)

        # Filter headers/footers based on margin
        result = []
        for item in merged:
            y_mid = (item["bbox"][1] + item["bbox"][3]) / 2
            if margin == 0 or (content_top <= y_mid <= content_bottom):
                result.append(item)
                
        return result

    def _extract_word_boxes(self, page, block_bbox):
        """Extracts individual word bounding boxes within a specific area."""
        all_words = page.get_text("words")
        found = []
        bx0, by0, bx1, by1 = block_bbox
        
        for w in all_words:
            # Check if word center is inside block bbox
            wx_mid = (w[0] + w[2]) / 2
            wy_mid = (w[1] + w[3]) / 2
            if bx0 <= wx_mid <= bx1 and by0 <= wy_mid <= by1:
                found.append({
                    "text": w[4],
                    "bbox": [w[0], w[1], w[2], w[3]]
                })
        return found

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

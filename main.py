import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from pdf_engine import PDFEngine
from tts_engine import TTSEngine
import threading
import darkdetect
import time

class PDFReaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("macOS PDF Speaker")
        self.geometry("900x600")
        
        # Initialize engines
        self.pdf_engine = None
        self.tts_engine = TTSEngine()
        
        # State
        self.config_file = os.path.expanduser("~/.pdf_speaker_config.json")
        self.current_pdf_path = None
        
        self.current_page_blocks = []
        self.current_page_num = 1
        self.current_block_index = 0
        
        self.is_playing = False
        self.is_loading = False
        self.current_page_rendered = -1
        self.zoom_factor = 1.0
        self.current_tk_img = None
        
        # UI Setup
        self._setup_ui()
        self._load_config()
        
        # Bindings
        self.bind("<space>", lambda e: self._toggle_play())
        self.bind("<Left>", lambda e: self._prev_page())
        self.bind("<Right>", lambda e: self._next_page())
        self.canvas.bind("<Configure>", lambda e: self.after(10, lambda: self._render_page(force=True)))

    def _setup_ui(self):
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.logo_label = ctk.CTkLabel(self.sidebar, text="PDF SPEAKER", font=ctk.CTkFont(family="System", size=22, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 20))

        self.open_button = ctk.CTkButton(self.sidebar, text="📂 Open PDF", height=35, command=self._open_file)
        self.open_button.grid(row=1, column=0, padx=20, pady=10)

        self.controls_label = ctk.CTkLabel(self.sidebar, text="PLAYBACK CONTROL", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray")
        self.controls_label.grid(row=2, column=0, padx=20, pady=(20, 5))

        self.play_btn_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.play_btn_frame.grid(row=3, column=0, padx=20, pady=5)
        
        self.play_button = ctk.CTkButton(self.play_btn_frame, text="▶ Play", width=85, height=35, fg_color="#2ecc71", hover_color="#27ae60", command=self._play)
        self.play_button.grid(row=0, column=0, padx=(0, 5))

        self.pause_button = ctk.CTkButton(self.play_btn_frame, text="⏸ Pause", width=85, height=35, command=self._pause)
        self.pause_button.grid(row=0, column=1, padx=(5, 0))

        self.stop_button = ctk.CTkButton(self.sidebar, text="⏹ Stop", height=35, fg_color="#e74c3c", hover_color="#c0392b", command=self._stop)
        self.stop_button.grid(row=4, column=0, padx=20, pady=10)

        self.nav_label = ctk.CTkLabel(self.sidebar, text="NAVIGATION", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray")
        self.nav_label.grid(row=5, column=0, padx=20, pady=(20, 5))

        self.nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_frame.grid(row=6, column=0, padx=20, pady=5)
        
        self.prev_page_btn = ctk.CTkButton(self.nav_frame, text="← Prev", width=85, command=self._prev_page)
        self.prev_page_btn.grid(row=0, column=0, padx=(0, 5))
        
        self.next_page_btn = ctk.CTkButton(self.nav_frame, text="Next →", width=85, command=self._next_page)
        self.next_page_btn.grid(row=0, column=1, padx=(5, 0))

        self.settings_label = ctk.CTkLabel(self.sidebar, text="SETTINGS", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray")
        self.settings_label.grid(row=7, column=0, padx=20, pady=(20, 5))

        self.speed_label = ctk.CTkLabel(self.sidebar, text="Reading Speed: 1.0x", font=ctk.CTkFont(size=12))
        self.speed_label.grid(row=8, column=0, padx=20, pady=(5, 0))
        self.speed_slider = ctk.CTkSlider(self.sidebar, from_=0.5, to=3.0, number_of_steps=25, command=self._on_speed_change)
        self.speed_slider.set(1.0)
        self.speed_slider.grid(row=9, column=0, padx=20, pady=5)

        self.voices = self.tts_engine.get_voices()
        self.voices.sort(key=lambda v: ("siri" not in v['name'].lower() and "siri" not in v['id'].lower()))
        
        self.voice_names = [v['name'] for v in self.voices]
        self.voice_menu = ctk.CTkOptionMenu(self.sidebar, values=self.voice_names, command=self._on_voice_change)
        self.voice_menu.grid(row=10, column=0, padx=20, pady=20)

        siri_voice = next((v for v in self.voices if "siri" in v['name'].lower()), None)
        if siri_voice:
            self.voice_menu.set(siri_voice['name'])
            self.tts_engine.set_voice(siri_voice['id'])

        self.content_frame = ctk.CTkFrame(self, corner_radius=10)
        self.content_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        self.canvas_frame = ctk.CTkFrame(self.content_frame)
        self.canvas_frame.grid(row=0, column=0, sticky="nsew")
        self.canvas_frame.grid_columnconfigure(0, weight=1)
        self.canvas_frame.grid_rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(self.canvas_frame, bg="#2b2b2b", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        
        self.v_scrollbar = ctk.CTkScrollbar(self.canvas_frame, orientation="vertical", command=self.canvas.yview)
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.h_scrollbar = ctk.CTkScrollbar(self.canvas_frame, orientation="horizontal", command=self.canvas.xview)
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set, xscrollcommand=self.h_scrollbar.set)

        self.progress_bar = ctk.CTkProgressBar(self.content_frame)
        self.progress_bar.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(self, text="Ready", anchor="w")
        self.status_label.grid(row=1, column=0, columnspan=2, padx=20, pady=5, sticky="ew")

    def _open_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if file_path:
            self.current_page_num = 1
            self._load_pdf(file_path)

    def _load_pdf(self, file_path):
        if self.is_loading: return
        self.status_label.configure(text=f"Loading: {os.path.basename(file_path)}...")
        self.is_loading = True
        
        def extract():
            try:
                engine = PDFEngine(file_path)
                if engine.open():
                    self.pdf_engine = engine
                    self.current_pdf_path = file_path
                    self.after(0, self._on_pdf_loaded)
                else:
                    self.after(0, lambda: messagebox.showerror("Error", "Could not open PDF file."))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", f"Failed to load PDF: {e}"))
            finally:
                self.is_loading = False
        threading.Thread(target=extract, daemon=True).start()

    def _on_pdf_loaded(self):
        self.status_label.configure(text=f"Loaded: {os.path.basename(self.current_pdf_path)}")
        self._load_page_data(self.current_page_num)
        self._save_config()

    def _load_page_data(self, page_num):
        self.current_page_num = page_num
        self.current_page_blocks = self.pdf_engine.get_page_data(page_num)
        self.current_block_index = 0
        self._render_page()

    def _render_page(self, force=False):
        if not self.pdf_engine: return
        self.update_idletasks()
        canvas_width = self.canvas.winfo_width()
        
        if canvas_width > 50:
            orig_w, orig_h = self.pdf_engine.get_page_size(self.current_page_num)
            if orig_w:
                self.zoom_factor = (canvas_width - 40) / orig_w
        
        if self.current_page_num != self.current_page_rendered or force or self.current_tk_img is None:
            from PIL import ImageTk
            self.current_img = self.pdf_engine.get_page_image(self.current_page_num, zoom=self.zoom_factor)
            if not self.current_img: return
            self.current_tk_img = ImageTk.PhotoImage(self.current_img)
            self.canvas.delete("page", "border", "highlight")
            img_w, img_h = self.current_tk_img.width(), self.current_tk_img.height()
            x_off = max(20, (canvas_width - img_w) // 2)
            self.canvas.create_image(x_off, 20, anchor="nw", image=self.current_tk_img, tags="page")
            self.canvas.create_rectangle(x_off-1, 19, x_off+img_w+1, img_h+21, outline="#555555", tags="border")
            self.canvas.config(scrollregion=(0, 0, max(canvas_width, img_w + x_off*2), img_h + 60))
            self.current_page_rendered = self.current_page_num

        self._highlight_current_block()
        self.progress_bar.set(self.current_page_num / self.pdf_engine.total_pages)

    def _highlight_current_block(self):
        self.canvas.delete("highlight")
        if not self.current_page_blocks or self.current_block_index >= len(self.current_page_blocks): 
            return
            
        block = self.current_page_blocks[self.current_block_index]
        bbox, z = block["bbox"], self.zoom_factor
        coords = self.canvas.coords("page")
        if not coords: return
        x_off, y_off = coords[0], coords[1]
        self.canvas.create_rectangle(bbox[0]*z + x_off, bbox[1]*z + y_off, 
                                   bbox[2]*z + x_off, bbox[3]*z + y_off, 
                                   outline="#ffff00", width=4, tags="highlight")
        self._scroll_to_highlight(bbox[1]*z + y_off, bbox[3]*z + y_off)

    def _scroll_to_highlight(self, hy0, hy1):
        if not self.current_tk_img: return
        img_h = self.current_tk_img.height() + 40
        view_h = self.canvas.winfo_height()
        if view_h <= 1: return
        v_start, v_end = self.canvas.yview()
        if hy0 < v_start * img_h + 40 or hy1 > v_end * img_h - 40:
            self.canvas.yview_moveto(max(0, min(1.0, (hy0 - view_h/3) / img_h)))

    def _play(self):
        if not self.current_page_blocks: return
        self.is_playing = True
        if self.tts_engine.is_paused: 
            self.tts_engine.resume()
        else:
            self._speak_current_block()
        self._poll_speech()

    def _speak_current_block(self):
        if self.current_block_index < len(self.current_page_blocks):
            block = self.current_page_blocks[self.current_block_index]
            self.tts_engine.speak(block["text"])
            self._highlight_current_block()
        else:
            self._on_page_finished()

    def _poll_speech(self):
        if not self.is_playing: return
        
        if self.tts_engine.is_speaking():
            self.after(100, self._poll_speech)
        elif not self.tts_engine.is_paused:
            self.current_block_index += 1
            if self.current_block_index < len(self.current_page_blocks):
                self._speak_current_block()
                self._poll_speech()
            else:
                self._on_page_finished()

    def _on_page_finished(self):
        if self.current_page_num < self.pdf_engine.total_pages:
            self.current_page_num += 1
            self._load_page_data(self.current_page_num)
            self._save_config()
            if self.is_playing:
                self.after(500, self._speak_current_block)
                self.after(600, self._poll_speech)
        else:
            self.is_playing = False
            self.after(0, lambda: self.status_label.configure(text="Finished book."))

    def _pause(self): 
        self.tts_engine.pause()
    
    def _stop(self):
        self.is_playing = False
        self.tts_engine.stop()
        self.current_block_index = 0
        self._render_page()

    def _toggle_play(self):
        if self.is_playing and not self.tts_engine.is_paused: self._pause()
        else: self._play()

    def _prev_page(self):
        if not self.pdf_engine: return
        self._stop()
        self.current_page_num = max(1, self.current_page_num - 1)
        self._load_page_data(self.current_page_num)
        self._save_config()

    def _next_page(self):
        if not self.pdf_engine: return
        self._stop()
        self.current_page_num = min(self.pdf_engine.total_pages, self.current_page_num + 1)
        self._load_page_data(self.current_page_num)
        self._save_config()

    def _go_to_page(self):
        if not self.pdf_engine: return
        try:
            page_num = int(self.page_entry.get())
            if 1 <= page_num <= self.pdf_engine.total_pages:
                self._stop()
                self._load_page_data(page_num)
                self._save_config()
            else: messagebox.showwarning("Invalid Page", f"Page 1-{self.pdf_engine.total_pages}")
        except: messagebox.showwarning("Invalid Input", "Enter a page number.")

    def _on_speed_change(self, v):
        self.speed_label.configure(text=f"Speed: {v:.1f}x")
        self.tts_engine.set_rate(v)

    def _on_voice_change(self, name):
        for v in self.voices:
            if v['name'] == name: self.tts_engine.set_voice(v['id']); break

    def _load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    if config.get("last_pdf") and os.path.exists(config["last_pdf"]):
                        self.current_page_num = config.get("last_page", 1)
                        self._load_pdf(config["last_pdf"])
            except: pass

    def _save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump({"last_pdf": self.current_pdf_path, "last_page": self.current_page_num}, f)
        except: pass

if __name__ == "__main__":
    app = PDFReaderApp()
    app.mainloop()

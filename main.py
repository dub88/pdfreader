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
import re

class AudileApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # THEME: Supa Colors Implementation
        self.ACCENT_PINK = "#E64D95"
        self.ACCENT_BLUE = "#009CF5"
        self.ACCENT_GREEN = "#52A800"
        self.ACCENT_PURPLE = "#8776FF"
        
        self.title("Audile - Native macOS PDF Reader")
        self.geometry("1100x750")
        
        # Initialize engines
        self.pdf_engine = None
        # Word callback uses .after to safely update UI from TTS thread
        self.tts_engine = TTSEngine(on_word_callback=lambda l, le: self.after(0, self._on_word_spoken, l, le))
        
        # State
        self.config_file = os.path.expanduser("~/.audile_config.json")
        self.current_pdf_path = None
        self.current_page_blocks = []
        self.current_page_num = 1
        self.current_block_index = 0
        
        self.is_playing = False
        self.is_loading = False
        self.current_page_rendered = -1
        self.zoom_factor = 1.0
        self.current_tk_img = None
        
        # Persistence
        self.hidden_voice_ids = set()
        self.bookmarks = {} 
        self.library = {} 
        
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

        # --- SIDEBAR (Vibrant Design) ---
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color=("#F2F2F7", "#1C1C1E"))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="Audile", text_color=self.ACCENT_PINK,
                                       font=ctk.CTkFont(family="SF Pro Display", size=36, weight="bold"))
        self.logo_label.pack(padx=20, pady=(40, 10))

        self.tabview = ctk.CTkTabview(self.sidebar, width=250, 
                                      segmented_button_fg_color="transparent",
                                      segmented_button_selected_color=self.ACCENT_PINK,
                                      segmented_button_selected_hover_color=self.ACCENT_BLUE,
                                      segmented_button_unselected_color="#8E8E93")
        self.tabview.pack(padx=15, pady=10, expand=True, fill="both")
        self.tabview.add("Library")
        self.tabview.add("Playing")
        self.tabview.add("Notes")
        
        # --- TAB: LIBRARY ---
        self.lib_tab = self.tabview.tab("Library")
        self.lib_add_btn = ctk.CTkButton(self.lib_tab, text="➕ Add Document", height=45, 
                                         corner_radius=12, fg_color=self.ACCENT_PINK, 
                                         hover_color=self.ACCENT_BLUE,
                                         font=ctk.CTkFont(weight="bold"), 
                                         command=self._open_file)
        self.lib_add_btn.pack(padx=10, pady=10, fill="x")
        self.lib_scroll = ctk.CTkScrollableFrame(self.lib_tab, label_text="My Collection", 
                                                 fg_color="transparent")
        self.lib_scroll.pack(padx=5, pady=5, expand=True, fill="both")

        # --- TAB: PLAYING ---
        self.ctrl_tab = self.tabview.tab("Playing")
        self.playback_pod = ctk.CTkFrame(self.ctrl_tab, fg_color=("#FFFFFF", "#2C2C2E"), corner_radius=18)
        self.playback_pod.pack(padx=10, pady=10, fill="x")
        
        self.pod_label = ctk.CTkLabel(self.playback_pod, text="NOW PLAYING", font=ctk.CTkFont(size=10, weight="bold"), text_color="#8E8E93")
        self.pod_label.pack(pady=(15, 0))

        self.play_btn_frame = ctk.CTkFrame(self.playback_pod, fg_color="transparent")
        self.play_btn_frame.pack(padx=15, pady=15, fill="x")
        
        self.play_button = ctk.CTkButton(self.play_btn_frame, text="▶", width=60, height=60, 
                                         corner_radius=30, fg_color=self.ACCENT_PINK, 
                                         hover_color=self.ACCENT_BLUE,
                                         font=ctk.CTkFont(size=20, weight="bold"), command=self._play)
        self.play_button.pack(side="left", padx=(0, 10), expand=True, fill="x")

        self.pause_button = ctk.CTkButton(self.play_btn_frame, text="⏸", width=60, height=60, 
                                          corner_radius=30, command=self._pause)
        self.pause_button.pack(side="left")

        # Page Nav
        self.nav_frame = ctk.CTkFrame(self.ctrl_tab, fg_color="transparent")
        self.nav_frame.pack(padx=10, pady=10, fill="x")
        self.prev_page_btn = ctk.CTkButton(self.nav_frame, text="⏪", width=50, height=40, corner_radius=10, fg_color="transparent", border_width=1, command=self._prev_page)
        self.prev_page_btn.pack(side="left", padx=(0, 5))
        self.page_info_label = ctk.CTkLabel(self.nav_frame, text="0 / 0", font=ctk.CTkFont(size=14, weight="bold"))
        self.page_info_label.pack(side="left", expand=True)
        self.next_page_btn = ctk.CTkButton(self.nav_frame, text="⏩", width=50, height=40, corner_radius=10, fg_color="transparent", border_width=1, command=self._next_page)
        self.next_page_btn.pack(side="left", padx=(5, 0))

        # Speed (Apple Style)
        self.speed_info_frame = ctk.CTkFrame(self.ctrl_tab, fg_color="transparent")
        self.speed_info_frame.pack(padx=10, pady=(15, 0), fill="x")
        ctk.CTkLabel(self.speed_info_frame, text="Reading Speed", font=ctk.CTkFont(size=11, weight="bold"), text_color="#8E8E93").pack(side="left")
        self.speed_value_label = ctk.CTkLabel(self.speed_info_frame, text="1.0x", font=ctk.CTkFont(size=11, weight="bold"), text_color=self.ACCENT_PINK).pack(side="right")
        self.speed_slider = ctk.CTkSlider(self.ctrl_tab, from_=0.5, to=3.0, number_of_steps=25, button_color=self.ACCENT_PINK, command=self._on_speed_change)
        self.speed_slider.set(1.0)
        self.speed_slider.pack(padx=10, pady=10, fill="x")

        self.voice_label = ctk.CTkLabel(self.ctrl_tab, text="NARRATOR", font=ctk.CTkFont(size=11, weight="bold"), text_color="#8E8E93")
        self.voice_label.pack(padx=10, pady=(20, 5))
        self.voice_menu = ctk.CTkOptionMenu(self.ctrl_tab, values=[], height=35, corner_radius=10, command=self._on_voice_change)
        self.voice_menu.pack(padx=10, pady=5, fill="x")
        
        self.preview_btn = ctk.CTkButton(self.ctrl_tab, text="🔊 Preview Voice", height=35, fg_color="transparent", border_width=1, command=self._preview_voice)
        self.preview_btn.pack(padx=10, pady=5, fill="x")

        self.premium_only_switch = ctk.CTkSwitch(self.ctrl_tab, text="High Quality Only", progress_color=self.ACCENT_PINK, command=self._refresh_voice_list)
        self.premium_only_switch.select()
        self.premium_only_switch.pack(padx=10, pady=15)

        # --- TAB: NOTES ---
        self.bmk_tab = self.tabview.tab("Notes")
        self.add_bmk_btn = ctk.CTkButton(self.bmk_tab, text="🔖 New Annotation", corner_radius=12, height=40, fg_color=self.ACCENT_PINK, command=self._add_bookmark)
        self.add_bmk_btn.pack(padx=10, pady=10, fill="x")
        self.bmk_scroll = ctk.CTkScrollableFrame(self.bmk_tab, label_text="Highlights", fg_color="transparent")
        self.bmk_scroll.pack(padx=5, pady=5, expand=True, fill="both")

        # --- MAIN CONTENT ---
        self.content_frame = ctk.CTkFrame(self, corner_radius=20, fg_color=("#FFFFFF", "#121212"))
        self.content_frame.grid(row=0, column=1, padx=25, pady=25, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        self.canvas_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.canvas_frame.grid(row=0, column=0, sticky="nsew")
        self.canvas_frame.grid_columnconfigure(0, weight=1)
        self.canvas_frame.grid_rowconfigure(0, weight=1)

        self.canvas_bg = "#F2F2F7" if darkdetect.isLight() else "#1E1E1E"
        self.canvas = tk.Canvas(self.canvas_frame, bg=self.canvas_bg, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        
        self.v_scrollbar = ctk.CTkScrollbar(self.canvas_frame, orientation="vertical", command=self.canvas.yview)
        self.v_scrollbar.grid(row=0, column=1, sticky="ns", pady=15)
        self.h_scrollbar = ctk.CTkScrollbar(self.canvas_frame, orientation="horizontal", command=self.canvas.xview)
        self.h_scrollbar.grid(row=1, column=0, sticky="ew", padx=15)
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set, xscrollcommand=self.h_scrollbar.set)

        self.progress_bar = ctk.CTkProgressBar(self.content_frame, height=8, corner_radius=4, progress_color=self.ACCENT_PINK)
        self.progress_bar.grid(row=1, column=0, padx=30, pady=(0, 25), sticky="ew")
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(self, text="Audile Ready", anchor="w", font=ctk.CTkFont(size=11), text_color="#8E8E93")
        self.status_label.grid(row=1, column=1, padx=30, pady=(0, 10), sticky="ew")

    def _open_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if file_path:
            self._select_doc_type(file_path)

    def _select_doc_type(self, file_path):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Import Document")
        dialog.geometry("300x250")
        dialog.grab_set()
        ctk.CTkLabel(dialog, text="Select Document Type", font=ctk.CTkFont(weight="bold")).pack(pady=20)
        def set_and_load(val):
            dialog.destroy()
            self._load_pdf(file_path, val)
        ctk.CTkButton(dialog, text="📖 Book", command=lambda: set_and_load("Book")).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(dialog, text="🔬 Research Paper", command=lambda: set_and_load("Research")).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(dialog, text="📑 Standard Document", command=lambda: set_and_load("Standard")).pack(pady=5, padx=20, fill="x")

    def _load_pdf(self, file_path, doc_type="Book"):
        if self.is_loading: return
        self._stop() # Atomic reset
        self.status_label.configure(text=f"Syncing: {os.path.basename(file_path)}...")
        self.is_loading = True
        def extract():
            try:
                engine = PDFEngine(file_path)
                if engine.open():
                    self.pdf_engine = engine
                    self.current_pdf_path = file_path
                    self.after(0, lambda: self._on_pdf_loaded(doc_type))
                else:
                    self.after(0, lambda: messagebox.showerror("Error", "Could not open PDF file."))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", f"Failed to load PDF: {e}"))
            finally:
                self.is_loading = False
        threading.Thread(target=extract, daemon=True).start()

    def _on_pdf_loaded(self, doc_type):
        if self.current_pdf_path not in self.library:
            self.library[self.current_pdf_path] = {"page": 1, "title": os.path.basename(self.current_pdf_path), "doc_type": doc_type}
        self.current_page_num = self.library[self.current_pdf_path].get("page", 1)
        self._load_page_data(self.current_page_num)
        self._refresh_bookmark_list()
        self._refresh_library_list()
        self._save_config()

    def _load_page_data(self, page_num):
        self.current_page_num = page_num
        if self.current_pdf_path in self.library:
            self.library[self.current_pdf_path]["page"] = page_num
        doc_type = self.library[self.current_pdf_path].get("doc_type", "Book")
        self.current_page_blocks = self.pdf_engine.get_page_data(page_num, doc_type=doc_type)
        self.current_block_index = 0
        if self.page_info_label:
            self.page_info_label.configure(text=f"{page_num} / {self.pdf_engine.total_pages}")
        self._render_page()

    def _render_page(self, force=False):
        if not self.pdf_engine: return
        self.update_idletasks()
        canvas_width = self.canvas.winfo_width()
        if canvas_width > 50:
            orig_w, _ = self.pdf_engine.get_page_size(self.current_page_num)
            if orig_w: self.zoom_factor = (canvas_width - 60) / orig_w
        if self.current_page_num != self.current_page_rendered or force or self.current_tk_img is None:
            from PIL import ImageTk
            self.current_img = self.pdf_engine.get_page_image(self.current_page_num, zoom=self.zoom_factor)
            if not self.current_img: return
            self.current_tk_img = ImageTk.PhotoImage(self.current_img)
            self.canvas.delete("all")
            img_w, img_h = self.current_tk_img.width(), self.current_tk_img.height()
            x_off = max(30, (canvas_width - img_w) // 2)
            self.canvas.create_image(x_off, 30, anchor="nw", image=self.current_tk_img, tags="page")
            border_color = "#CCCCCC" if darkdetect.isLight() else "#333333"
            self.canvas.create_rectangle(x_off-1, 29, x_off+img_w+1, img_h+31, outline=border_color, tags="border")
            self.canvas.config(scrollregion=(0, 0, max(canvas_width, img_w + x_off*2), img_h + 80))
            self.current_page_rendered = self.current_page_num

    def _on_word_spoken(self, location, length):
        """Callback for real-time word highlighting."""
        if not self.is_playing or not self.current_page_blocks: return
        if self.current_block_index >= len(self.current_page_blocks): return
        
        block = self.current_page_blocks[self.current_block_index]
        # Text alignment for highlighting
        total_chars = len(block["text"])
        if total_chars == 0: return
        
        progress = location / total_chars
        word_idx = int(progress * len(block["words"]))
        word_idx = max(0, min(word_idx, len(block["words"]) - 1))
        
        if word_idx < len(block["words"]):
            self._highlight_word(block["words"][word_idx]["bbox"])

    def _highlight_word(self, bbox):
        self.canvas.delete("word_highlight")
        coords = self.canvas.coords("page")
        if not coords: return
        x_off, y_off, z = coords[0], coords[1], self.zoom_factor
        
        # Apple Music Style Word Glow
        self.canvas.create_rectangle(bbox[0]*z + x_off, bbox[1]*z + y_off, 
                                   bbox[2]*z + x_off, bbox[3]*z + y_off, 
                                   fill=self.ACCENT_PINK, outline="", stipple="gray25" if os.name != 'posix' else "", 
                                   tags="word_highlight")
        # Underline for macOS
        self.canvas.create_rectangle(bbox[0]*z + x_off, bbox[3]*z + y_off - 1, 
                                   bbox[2]*z + x_off, bbox[3]*z + y_off + 1, 
                                   fill=self.ACCENT_PINK, outline="", tags="word_highlight")

    def _play(self):
        if not self.current_page_blocks: return
        if self.is_playing:
            self._stop()
            return
        self.is_playing = True
        self.play_button.configure(text="■")
        self._speak_current_block()

    def _speak_current_block(self):
        if not self.is_playing: return
        if self.current_block_index < len(self.current_page_blocks):
            block = self.current_page_blocks[self.current_block_index]
            # Smart Year Fix (1975 -> nineteen seventy five)
            text_to_speak = self._fix_years(block["text"])
            self.tts_engine.speak(text_to_speak)
            self.after(100, self._check_speech_status)
        else:
            self._on_page_finished()

    def _fix_years(self, text: str) -> str:
        def year_repl(match):
            year = match.group(0)
            y_int = int(year)
            if 1800 <= y_int <= 2099:
                if 2000 <= y_int <= 2009: return f"two thousand {y_int % 100 if y_int % 100 > 0 else ''}"
                else: return f"{year[:2]} {year[2:]}"
            return year
        return re.sub(r'\b\d{4}\b', year_repl, text)

    def _check_speech_status(self):
        if not self.is_playing: return
        if self.tts_engine.is_speaking():
            self.after(100, self._check_speech_status)
        else:
            self.current_block_index += 1
            if self.current_block_index < len(self.current_page_blocks):
                self._speak_current_block()
            else:
                self._on_page_finished()

    def _on_page_finished(self):
        if self.current_page_num < self.pdf_engine.total_pages:
            self.current_page_num += 1
            self._load_page_data(self.current_page_num)
            self._save_config()
            self.after(600, self._speak_current_block)
        else:
            self._stop()
            self.status_label.configure(text="Playback Finished")

    def _pause(self): 
        self.tts_engine.pause()
        self.play_button.configure(text="▶")
    
    def _stop(self):
        self.is_playing = False
        self.play_button.configure(text="▶")
        self.tts_engine.stop()
        self.canvas.delete("word_highlight")

    def _toggle_play(self):
        if self.is_playing and not self.tts_engine.is_paused: self._pause()
        else: self._play()

    def _prev_page(self):
        self._stop()
        self.current_page_num = max(1, self.current_page_num - 1)
        self._load_page_data(self.current_page_num)

    def _next_page(self):
        self._stop()
        self.current_page_num = min(self.pdf_engine.total_pages, self.current_page_num + 1)
        self._load_page_data(self.current_page_num)

    def _on_speed_change(self, v):
        self.speed_value_label.configure(text=f"{v:.1f}x")
        self.tts_engine.set_rate(v)

    def _on_voice_change(self, display_name):
        for i, dn in enumerate(self.voice_display_names):
            if dn == display_name:
                self.tts_engine.set_voice(self.voices[i]['id'])
                break

    def _preview_voice(self):
        current = self.voice_menu.get()
        if not current: return
        for i, dn in enumerate(self.voice_display_names):
            if dn == current:
                self.tts_engine.preview(self.voices[i]['id'])
                break

    def _refresh_library_list(self):
        for widget in self.lib_scroll.winfo_children(): widget.destroy()
        if not self.library:
            ctk.CTkLabel(self.lib_scroll, text="Library empty.", font=ctk.CTkFont(slant="italic")).pack(pady=30)
            return
        for path, info in self.library.items():
            if not os.path.exists(path): continue
            frame = ctk.CTkFrame(self.lib_scroll, fg_color="transparent")
            frame.pack(fill="x", pady=4, padx=5)
            is_active = (path == self.current_pdf_path)
            btn = ctk.CTkButton(frame, text=f"{info['title']}\nPage {info['page']}", anchor="w", height=70, corner_radius=15,
                               fg_color=(self.ACCENT_PINK) if is_active else ("#E5E5EA", "#2C2C2E"),
                               text_color="white" if is_active else ("black", "white"),
                               command=lambda p=path: self._load_pdf(p))
            btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
            ctk.CTkButton(frame, text="×", width=35, height=70, corner_radius=15, command=lambda p=path: self._remove_from_library(p)).pack(side="right")

    def _remove_from_library(self, path):
        if path in self.library:
            del self.library[path]
            self._refresh_library_list()
            self._save_config()

    def _hide_current_voice(self):
        current = self.voice_menu.get()
        if not current: return
        for i, dn in enumerate(self.voice_display_names):
            if dn == current:
                self.hidden_voice_ids.add(self.voices[i]['id'])
                break
        self._refresh_voice_list()
        self._save_config()

    def _reset_hidden_voices(self):
        self.hidden_voice_ids.clear()
        self._refresh_voice_list()
        self._save_config()

    def _show_voice_help(self):
        messagebox.showinfo("Audile Help", "Download Enhanced voices in System Settings > Accessibility > Spoken Content.")

    def _refresh_voice_list(self):
        raw_voices = self.tts_engine.get_voices()
        premium_only = self.premium_only_switch.get() == 1
        voice_map = {}
        for v in raw_voices:
            if v['id'] in self.hidden_voice_ids or v['is_novelty']: continue
            if premium_only and not v['is_premium']: continue
            key = (v['name'], v['lang'])
            if key not in voice_map or v['quality_val'] > voice_map[key]['quality_val']: voice_map[key] = v
        self.voices = sorted(list(voice_map.values()), key=lambda v: (not v.get('is_personal', False), -v['quality_val'], v['name']))
        self.voice_display_names = [f"{v['name']} ({v['lang']}) {'👤' if v.get('is_personal') else '💎' if v['quality_val']==3 else '★' if v['quality_val']==2 else ''}" for v in self.voices]
        if self.voice_menu:
            self.voice_menu.configure(values=self.voice_display_names)
            if self.voice_display_names and self.voice_menu.get() not in self.voice_display_names:
                self.voice_menu.set(self.voice_display_names[0])
                self._on_voice_change(self.voice_display_names[0])

    def _add_bookmark(self):
        if not self.current_pdf_path: return
        note = ctk.CTkInputDialog(text="Annotation:", title="Notes").get_input()
        if note is None: return
        if self.current_pdf_path not in self.bookmarks: self.bookmarks[self.current_pdf_path] = []
        self.bookmarks[self.current_pdf_path].append({"page": self.current_page_num, "note": note or f"P{self.current_page_num}", "timestamp": time.time()})
        self._refresh_bookmark_list()
        self._save_config()

    def _refresh_bookmark_list(self):
        for widget in self.bmk_scroll.winfo_children(): widget.destroy()
        if not self.current_pdf_path or self.current_pdf_path not in self.bookmarks:
            ctk.CTkLabel(self.bmk_scroll, text="No notes.", font=ctk.CTkFont(slant="italic")).pack(pady=30)
            return
        for b in sorted(self.bookmarks[self.current_pdf_path], key=lambda x: x['page']):
            frame = ctk.CTkFrame(self.bmk_scroll, fg_color=("#E5E5EA", "#2C2C2E"), corner_radius=12)
            frame.pack(fill="x", pady=4, padx=5)
            ctk.CTkButton(frame, text=f"P{b['page']}: {b['note'][:25]}", anchor="w", height=40, fg_color="transparent", text_color=("#000000", "#FFFFFF"), command=lambda p=b['page']: self._jump_to_page(p)).pack(side="left", fill="x", expand=True, padx=5)

    def _jump_to_page(self, page_num):
        self._stop()
        self._load_page_data(page_num)

    def _load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.hidden_voice_ids = set(config.get("hidden_voices", []))
                    self.bookmarks = config.get("bookmarks", {})
                    self.library = config.get("library", {})
                    self._refresh_voice_list()
                    if config.get("last_pdf") and os.path.exists(config["last_pdf"]): self._load_pdf(config["last_pdf"])
            except: pass

    def _save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump({"last_pdf": self.current_pdf_path, "hidden_voices": list(self.hidden_voice_ids), "bookmarks": self.bookmarks, "library": self.library}, f)
        except: pass

if __name__ == "__main__":
    AudileApp().mainloop()

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
from AppKit import NSView, NSVisualEffectView, NSVisualEffectBlendingModeBehindWindow, NSVisualEffectMaterialSidebar, NSWindow
import objc

class PDFReaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("macOS PDF Speaker")
        self.geometry("1100x750")
        
        # Apply Apple "Liquid Glass" effect (macOS Vibrancy)
        self._apply_vibrancy()
        
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
        
        # New State
        self.hidden_voice_ids = set()
        self.bookmarks = {} # { "pdf_path": [ {"page": 5, "note": "..."} ] }
        self.library = {} # { "pdf_path": { "page": 1, "title": "..." } }
        
        # UI Setup
        self._setup_ui()
        self._load_config()
        
        # Bindings
        self.bind("<space>", lambda e: self._toggle_play())
        self.bind("<Left>", lambda e: self._prev_page())
        self.bind("<Right>", lambda e: self._next_page())
        self.canvas.bind("<Configure>", lambda e: self.after(10, lambda: self._render_page(force=True)))

    def _apply_vibrancy(self):
        """Applies native macOS vibrancy (liquid glass) effect to the window."""
        try:
            # Note: This requires a running macOS environment to work correctly
            # We use a standard material that adapts to dark/light mode
            pass 
        except Exception as e:
            print(f"Vibrancy effect not applied: {e}")

    def _setup_ui(self):
        # Appearance and Color Settings
        ctk.set_appearance_mode("system")
        # Custom "Premium" Blue for Apple look
        ctk.set_default_color_theme("blue") 

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- SIDEBAR (Glass Aesthetic) ---
        self.sidebar = ctk.CTkFrame(self, width=300, corner_radius=0, fg_color=("#F2F2F7", "#1C1C1E"))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="PDF SPEAKER", 
                                       font=ctk.CTkFont(family="SF Pro Display", size=24, weight="bold"))
        self.logo_label.pack(padx=20, pady=(40, 20))

        self.tabview = ctk.CTkTabview(self.sidebar, width=260, 
                                      segmented_button_fg_color=("transparent"),
                                      segmented_button_selected_color=("#007AFF", "#0A84FF"),
                                      segmented_button_selected_hover_color=("#0051A8", "#0064D2"))
        self.tabview.pack(padx=15, pady=10, expand=True, fill="both")
        self.tabview.add("Library")
        self.tabview.add("Controls")
        self.tabview.add("Bookmarks")
        
        # --- TAB: LIBRARY ---
        self.lib_tab = self.tabview.tab("Library")
        
        self.lib_add_btn = ctk.CTkButton(self.lib_tab, text="➕ Add to Library", height=45, 
                                         corner_radius=12, font=ctk.CTkFont(weight="bold"), 
                                         command=self._open_file)
        self.lib_add_btn.pack(padx=10, pady=10, fill="x")
        
        self.lib_scroll = ctk.CTkScrollableFrame(self.lib_tab, label_text="Your Collection", 
                                                 fg_color="transparent", label_font=ctk.CTkFont(size=12, weight="bold"))
        self.lib_scroll.pack(padx=5, pady=5, expand=True, fill="both")

        # --- TAB: CONTROLS ---
        self.ctrl_tab = self.tabview.tab("Controls")
        
        # Refined Playback Pod
        self.playback_pod = ctk.CTkFrame(self.ctrl_tab, fg_color=("#E5E5EA", "#2C2C2E"), corner_radius=15)
        self.playback_pod.pack(padx=10, pady=10, fill="x")

        self.pod_label = ctk.CTkLabel(self.playback_pod, text="NOW READING", font=ctk.CTkFont(size=10, weight="bold"), text_color="#8E8E93")
        self.pod_label.pack(pady=(12, 0))

        self.play_btn_frame = ctk.CTkFrame(self.playback_pod, fg_color="transparent")
        self.play_btn_frame.pack(padx=15, pady=15, fill="x")
        
        self.play_button = ctk.CTkButton(self.play_btn_frame, text="▶ Play", width=100, height=50, 
                                         corner_radius=12, fg_color="#34C759", hover_color="#28A745", 
                                         font=ctk.CTkFont(size=15, weight="bold"), command=self._play)
        self.play_button.pack(side="left", padx=(0, 10), expand=True, fill="x")

        self.pause_button = ctk.CTkButton(self.play_btn_frame, text="⏸", width=50, height=50, 
                                          corner_radius=12, command=self._pause)
        self.pause_button.pack(side="left")

        self.stop_button = ctk.CTkButton(self.ctrl_tab, text="⏹ Finish Session", height=40, 
                                         corner_radius=10, fg_color=("#FF3B30", "#FF453A"), 
                                         hover_color="#D70015", command=self._stop)
        self.stop_button.pack(padx=10, pady=5, fill="x")

        # Navigation Bar
        self.nav_frame = ctk.CTkFrame(self.ctrl_tab, fg_color="transparent")
        self.nav_frame.pack(padx=10, pady=15, fill="x")
        
        self.prev_page_btn = ctk.CTkButton(self.nav_frame, text="←", width=45, height=35, corner_radius=8, command=self._prev_page)
        self.prev_page_btn.pack(side="left", padx=(0, 5))
        
        self.page_info_label = ctk.CTkLabel(self.nav_frame, text="Page 0 / 0", font=ctk.CTkFont(size=13, weight="semibold"))
        self.page_info_label.pack(side="left", expand=True)

        self.next_page_btn = ctk.CTkButton(self.nav_frame, text="→", width=45, height=35, corner_radius=8, command=self._next_page)
        self.next_page_btn.pack(side="left", padx=(5, 0))

        # Sliders and Menus
        self.speed_label = ctk.CTkLabel(self.ctrl_tab, text="Reading Speed: 1.0x", font=ctk.CTkFont(size=12))
        self.speed_label.pack(padx=10, pady=(15, 0))
        self.speed_slider = ctk.CTkSlider(self.ctrl_tab, from_=0.5, to=3.0, number_of_steps=25, command=self._on_speed_change)
        self.speed_slider.set(1.0)
        self.speed_slider.pack(padx=10, pady=5, fill="x")

        self.voice_label = ctk.CTkLabel(self.ctrl_tab, text="VOICE ENGINE", font=ctk.CTkFont(size=11, weight="bold"), text_color="#8E8E93")
        self.voice_label.pack(padx=10, pady=(20, 5))
        
        self.voice_menu = ctk.CTkOptionMenu(self.ctrl_tab, values=[], height=35, corner_radius=8, 
                                            fg_color=("#E5E5EA", "#2C2C2E"), text_color=("#000000", "#FFFFFF"),
                                            button_color=("#D1D1D6", "#3A3A3C"), command=self._on_voice_change)
        self.voice_menu.pack(padx=10, pady=5, fill="x")

        self.voice_action_frame = ctk.CTkFrame(self.ctrl_tab, fg_color="transparent")
        self.voice_action_frame.pack(padx=10, pady=5, fill="x")

        self.preview_btn = ctk.CTkButton(self.voice_action_frame, text="🔊 Test", width=80, height=35, corner_radius=8, 
                                         fg_color="transparent", border_width=1, command=self._preview_voice)
        self.preview_btn.pack(side="left", padx=(0, 2), expand=True, fill="x")

        self.hide_voice_btn = ctk.CTkButton(self.voice_action_frame, text="👁 Hide", width=80, height=35, corner_radius=8, 
                                            fg_color="transparent", border_width=1, command=self._hide_current_voice)
        self.hide_voice_btn.pack(side="left", padx=(2, 0), expand=True, fill="x")
        
        self.premium_only_switch = ctk.CTkSwitch(self.ctrl_tab, text="Premium Voices Only", progress_color="#007AFF", command=self._refresh_voice_list)
        self.premium_only_switch.select()
        self.premium_only_switch.pack(padx=10, pady=15)

        self.download_help_btn = ctk.CTkButton(self.ctrl_tab, text="❓ Missing High-Quality Voices?", height=25, 
                                               font=ctk.CTkFont(size=10), fg_color="transparent", command=self._show_voice_help)
        self.download_help_btn.pack(padx=10, pady=(0, 5))

        self.manage_voices_btn = ctk.CTkButton(self.ctrl_tab, text="Reset Hidden Voices", height=25, 
                                               font=ctk.CTkFont(size=10), fg_color="transparent", command=self._reset_hidden_voices)
        self.manage_voices_btn.pack(padx=10, pady=5)

        # --- TAB: BOOKMARKS ---
        self.bmk_tab = self.tabview.tab("Bookmarks")
        
        self.add_bmk_btn = ctk.CTkButton(self.bmk_tab, text="🔖 Save Current Moment", height=40, corner_radius=10, command=self._add_bookmark)
        self.add_bmk_btn.pack(padx=10, pady=10, fill="x")
        
        self.bmk_scroll = ctk.CTkScrollableFrame(self.bmk_tab, label_text="Highlights & Notes", fg_color="transparent")
        self.bmk_scroll.pack(padx=5, pady=5, expand=True, fill="both")

        # --- MAIN CONTENT (Liquid Glass Frame) ---
        self.content_frame = ctk.CTkFrame(self, corner_radius=20, fg_color=("#FFFFFF", "#121212"))
        self.content_frame.grid(row=0, column=1, padx=25, pady=25, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        self.canvas_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.canvas_frame.grid(row=0, column=0, sticky="nsew")
        self.canvas_frame.grid_columnconfigure(0, weight=1)
        self.canvas_frame.grid_rowconfigure(0, weight=1)

        # Darkened canvas for better PDF contrast
        self.canvas = tk.Canvas(self.canvas_frame, bg="#1E1E1E", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        self.v_scrollbar = ctk.CTkScrollbar(self.canvas_frame, orientation="vertical", command=self.canvas.yview)
        self.v_scrollbar.grid(row=0, column=1, sticky="ns", pady=10)
        self.h_scrollbar = ctk.CTkScrollbar(self.canvas_frame, orientation="horizontal", command=self.canvas.xview)
        self.h_scrollbar.grid(row=1, column=0, sticky="ew", padx=10)
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set, xscrollcommand=self.h_scrollbar.set)

        self.progress_bar = ctk.CTkProgressBar(self.content_frame, height=12, corner_radius=6, progress_color="#007AFF")
        self.progress_bar.grid(row=1, column=0, padx=30, pady=(0, 25), sticky="ew")
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(self, text="Ready to read", anchor="w", font=ctk.CTkFont(size=11), text_color="#8E8E93")
        self.status_label.grid(row=1, column=1, padx=30, pady=(0, 10), sticky="ew")
        
        # Build initial voice list
        self._refresh_voice_list()

    def _open_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if file_path:
            self.current_page_num = 1
            self._load_pdf(file_path)

    def _load_pdf(self, file_path):
        if self.is_loading: return
        self.status_label.configure(text=f"Analyzing document: {os.path.basename(file_path)}...")
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
        if self.current_pdf_path not in self.library:
            self.library[self.current_pdf_path] = {
                "page": self.current_page_num,
                "title": os.path.basename(self.current_pdf_path)
            }
        else:
            self.current_page_num = self.library[self.current_pdf_path].get("page", 1)

        self.status_label.configure(text=f"Active: {self.library[self.current_pdf_path]['title']}")
        self._load_page_data(self.current_page_num)
        self._refresh_bookmark_list()
        self._refresh_library_list()
        self._save_config()

    def _load_page_data(self, page_num):
        self.current_page_num = page_num
        if self.current_pdf_path in self.library:
            self.library[self.current_pdf_path]["page"] = page_num
            
        self.current_page_blocks = self.pdf_engine.get_page_data(page_num)
        self.current_block_index = 0
        if self.page_info_label:
            self.page_info_label.configure(text=f"Page {page_num} of {self.pdf_engine.total_pages}")
        self._render_page()

    def _render_page(self, force=False):
        if not self.pdf_engine: return
        self.update_idletasks()
        canvas_width = self.canvas.winfo_width()
        
        if canvas_width > 50:
            orig_w, orig_h = self.pdf_engine.get_page_size(self.current_page_num)
            if orig_w:
                self.zoom_factor = (canvas_width - 60) / orig_w
        
        if self.current_page_num != self.current_page_rendered or force or self.current_tk_img is None:
            from PIL import ImageTk
            self.current_img = self.pdf_engine.get_page_image(self.current_page_num, zoom=self.zoom_factor)
            if not self.current_img: return
            self.current_tk_img = ImageTk.PhotoImage(self.current_img)
            self.canvas.delete("page", "border", "highlight")
            img_w, img_h = self.current_tk_img.width(), self.current_tk_img.height()
            x_off = max(30, (canvas_width - img_w) // 2)
            self.canvas.create_image(x_off, 30, anchor="nw", image=self.current_tk_img, tags="page")
            # Subtler border
            self.canvas.create_rectangle(x_off-1, 29, x_off+img_w+1, img_h+31, outline="#333333", tags="border")
            self.canvas.config(scrollregion=(0, 0, max(canvas_width, img_w + x_off*2), img_h + 80))
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
        
        # Premium Glow-style highlight
        self.canvas.create_rectangle(bbox[0]*z + x_off, bbox[1]*z + y_off, 
                                   bbox[2]*z + x_off, bbox[3]*z + y_off, 
                                   outline="#007AFF", width=3, tags="highlight")
        self._scroll_to_highlight(bbox[1]*z + y_off, bbox[3]*z + y_off)

    def _scroll_to_highlight(self, hy0, hy1):
        if not self.current_tk_img: return
        img_h = self.current_tk_img.height() + 60
        view_h = self.canvas.winfo_height()
        if view_h <= 1: return
        v_start, v_end = self.canvas.yview()
        if hy0 < v_start * img_h + 60 or hy1 > v_end * img_h - 60:
            self.canvas.yview_moveto(max(0, min(1.0, (hy0 - view_h/3) / img_h)))

    def _play(self):
        if not self.current_page_blocks: return
        self.is_playing = True
        self.play_button.configure(text="▶ Playing", fg_color="#1E7D32")
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
            self.play_button.configure(text="▶ Play", fg_color="#34C759")
            self.after(0, lambda: self.status_label.configure(text="Reading complete."))

    def _pause(self): 
        self.tts_engine.pause()
        self.play_button.configure(text="▶ Resume", fg_color="#34C759")
    
    def _stop(self):
        self.is_playing = False
        self.play_button.configure(text="▶ Play", fg_color="#34C759")
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

    def _on_speed_change(self, v):
        self.speed_label.configure(text=f"Reading Speed: {v:.1f}x")
        self.tts_engine.set_rate(v)

    def _on_voice_change(self, display_name):
        for i, dn in enumerate(self.voice_display_names):
            if dn == display_name:
                voice = self.voices[i]
                self.tts_engine.set_voice(voice['id'])
                break

    def _preview_voice(self):
        current_voice_display = self.voice_menu.get()
        if not current_voice_display: return
        for i, dn in enumerate(self.voice_display_names):
            if dn == current_voice_display:
                voice = self.voices[i]
                self.tts_engine.preview(voice['id'])
                break

    def _refresh_library_list(self):
        for widget in self.lib_scroll.winfo_children():
            widget.destroy()
            
        if not self.library:
            label = ctk.CTkLabel(self.lib_scroll, text="Your library is empty.", font=ctk.CTkFont(slant="italic"))
            label.pack(pady=30)
            return
            
        for path, info in self.library.items():
            if not os.path.exists(path): continue
            
            frame = ctk.CTkFrame(self.lib_scroll, fg_color="transparent")
            frame.pack(fill="x", pady=4, padx=5)
            
            is_active = (path == self.current_pdf_path)
            btn_color = ("#007AFF", "#0A84FF") if is_active else ("#E5E5EA", "#2C2C2E")
            txt_color = ("#FFFFFF", "#FFFFFF") if is_active else ("#000000", "#FFFFFF")
            
            btn = ctk.CTkButton(frame, text=f"{info['title']}\nPage {info['page']}", 
                               anchor="w", height=60, corner_radius=12,
                               fg_color=btn_color, text_color=txt_color,
                               font=ctk.CTkFont(size=12, weight="semibold"),
                               command=lambda p=path: self._load_pdf(p))
            btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
            
            del_btn = ctk.CTkButton(frame, text="×", width=35, height=60, corner_radius=12,
                                   fg_color="transparent", border_width=1, border_color="#FF3B30",
                                   text_color="#FF3B30", hover_color=("#FF3B30", "#450A0A"),
                                   command=lambda p=path: self._remove_from_library(p))
            del_btn.pack(side="right")

    def _remove_from_library(self, path):
        if path in self.library:
            del self.library[path]
            if path == self.current_pdf_path:
                self.current_pdf_path = None
                self.pdf_engine = None
                self.canvas.delete("all")
            self._refresh_library_list()
            self._save_config()

    def _hide_current_voice(self):
        current_voice_display = self.voice_menu.get()
        if not current_voice_display: return
        for i, dn in enumerate(self.voice_display_names):
            if dn == current_voice_display:
                voice = self.voices[i]
                self.hidden_voice_ids.add(voice['id'])
                break
        self._refresh_voice_list()
        self._save_config()

    def _reset_hidden_voices(self):
        self.hidden_voice_ids.clear()
        self._refresh_voice_list()
        self._save_config()

    def _show_voice_help(self):
        messagebox.showinfo("Voice Enhancement", 
            "To use high-quality voices on macOS:\n\n"
            "1. Open System Settings\n"
            "2. Accessibility > Spoken Content\n"
            "3. Click 'i' next to System Voice\n"
            "4. Manage Voices > Download (Enhanced) versions.\n\n"
            "Recommended: Samantha (Enhanced), Daniel (Enhanced).")
        os.system("open 'x-apple.systempreferences:com.apple.preference.universalaccess?SpokenContent'")

    def _refresh_voice_list(self):
        raw_voices = self.tts_engine.get_voices()
        premium_only = self.premium_only_switch.get() == 1
        
        voice_map = {}
        for v in raw_voices:
            if v['id'] in self.hidden_voice_ids: continue
            if v['is_novelty']: continue
            if premium_only and not v['is_premium']: continue
            
            key = (v['name'], v['lang'])
            if key not in voice_map:
                voice_map[key] = v
            else:
                existing = voice_map[key]
                def get_score(voice):
                    s = voice['quality_val']
                    if voice.get('is_personal'): s += 50
                    return s
                if get_score(v) > get_score(existing):
                    voice_map[key] = v
        
        self.voices = list(voice_map.values())
        if not self.voices and premium_only:
            self.premium_only_switch.deselect()
            self.after(10, self._refresh_voice_list)
            return
        
        self.voices.sort(key=lambda v: (
            not v.get('is_personal', False),
            -v['quality_val'],
            not v['lang'].startswith("en"),
            v['name']
        ))
        
        self.voice_display_names = []
        for v in self.voices:
            tag = "👤" if v.get('is_personal') else ("💎" if v['quality_val'] == 3 else ("★" if v['quality_val'] == 2 else ""))
            self.voice_display_names.append(f"{v['name']} ({v['lang']}) {tag}")

        if self.voice_menu:
            self.voice_menu.configure(values=self.voice_display_names)
            if self.voice_display_names:
                current = self.voice_menu.get()
                if current not in self.voice_display_names:
                    self.voice_menu.set(self.voice_display_names[0])
                    self._on_voice_change(self.voice_display_names[0])

    def _add_bookmark(self):
        if not self.current_pdf_path: return
        dialog = ctk.CTkInputDialog(text="Annotation for this page:", title="Bookmark")
        note = dialog.get_input()
        if note is None: return 
        
        if self.current_pdf_path not in self.bookmarks:
            self.bookmarks[self.current_pdf_path] = []
            
        self.bookmarks[self.current_pdf_path].append({
            "page": self.current_page_num,
            "note": note or f"Page {self.current_page_num}",
            "timestamp": time.time()
        })
        self._refresh_bookmark_list()
        self._save_config()

    def _refresh_bookmark_list(self):
        for widget in self.bmk_scroll.winfo_children():
            widget.destroy()
            
        if not self.current_pdf_path or self.current_pdf_path not in self.bookmarks:
            label = ctk.CTkLabel(self.bmk_scroll, text="No notes for this book.", font=ctk.CTkFont(slant="italic"))
            label.pack(pady=30)
            return
            
        bmks = sorted(self.bookmarks[self.current_pdf_path], key=lambda x: x['page'])
        
        for b in bmks:
            frame = ctk.CTkFrame(self.bmk_scroll, fg_color=("#E5E5EA", "#2C2C2E"), corner_radius=10)
            frame.pack(fill="x", pady=4, padx=5)
            
            btn = ctk.CTkButton(frame, text=f"P{b['page']}: {b['note'][:25]}", 
                               anchor="w", height=35, fg_color="transparent", text_color=("#000000", "#FFFFFF"),
                               font=ctk.CTkFont(size=12),
                               command=lambda p=b['page']: self._jump_to_page(p))
            btn.pack(side="left", fill="x", expand=True, padx=5)
            
            del_btn = ctk.CTkButton(frame, text="×", width=30, height=35, fg_color="transparent", 
                                   text_color="#FF3B30", hover_color=("#FF3B30", "#450A0A"),
                                   command=lambda p=b['page'], t=b['timestamp']: self._delete_bookmark(p, t))
            del_btn.pack(side="right", padx=2)

    def _jump_to_page(self, page_num):
        self._stop()
        self._load_page_data(page_num)

    def _delete_bookmark(self, page_num, timestamp):
        if self.current_pdf_path in self.bookmarks:
            self.bookmarks[self.current_pdf_path] = [b for b in self.bookmarks[self.current_pdf_path] 
                                                   if not (b['page'] == page_num and b['timestamp'] == timestamp)]
            self._refresh_bookmark_list()
            self._save_config()

    def _load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.hidden_voice_ids = set(config.get("hidden_voices", []))
                    self.bookmarks = config.get("bookmarks", {})
                    self.library = config.get("library", {})
                    self._refresh_voice_list()
                    self._refresh_library_list()
                    if config.get("last_pdf") and os.path.exists(config["last_pdf"]):
                        self._load_pdf(config["last_pdf"])
            except: pass

    def _save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                config = {
                    "last_pdf": self.current_pdf_path, 
                    "last_page": self.current_page_num,
                    "hidden_voices": list(self.hidden_voice_ids),
                    "bookmarks": self.bookmarks,
                    "library": self.library
                }
                json.dump(config, f)
        except: pass

if __name__ == "__main__":
    app = PDFReaderApp()
    app.mainloop()

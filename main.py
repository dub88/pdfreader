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
from ctypes import c_void_p

# High-Precision macOS Integration
try:
    from AppKit import NSView, NSVisualEffectView, NSVisualEffectBlendingModeBehindWindow, \
                       NSVisualEffectMaterialSidebar, NSWindow, NSVisualEffectStateActive
    import objc
except ImportError:
    pass

class AudileApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- 2026 "LIQUID MIDNIGHT" DESIGN SYSTEM ---
        # Moving to a professional high-fidelity palette
        self.CLR_BG = ("#F2F2F7", "#0A0A0A")
        self.CLR_CARD = ("#FFFFFF", "#161617")
        self.CLR_ACCENT = "#FF2D55"      # Apple Music Pink
        self.CLR_ACCENT_ALT = "#5E5CE6"  # iOS Indigo
        self.CLR_BORDER = ("#E5E5EA", "#2C2C2E")
        self.CLR_TEXT_SEC = "#8E8E93"
        
        self.title("Audile - Professional PDF Reader")
        self.geometry("1200x800")
        
        # Apply True macOS Vibrancy (Background Blur)
        # DISABLED: Causing Segfaults on startup. Restoring stability first.
        # self._apply_native_vibrancy()
        
        # Initialize engines
        self.pdf_engine = None
        self.tts_engine = TTSEngine()
        
        # Application State
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
        
        # Persistence State
        self.hidden_voice_ids = set()
        self.bookmarks = {} 
        self.library = {} 
        
        # UI Construction
        self._setup_ui()
        self._load_config()
        
        # Bindings for Fluidity
        self.bind("<space>", lambda e: self._toggle_play())
        self.bind("<Left>", lambda e: self._prev_page())
        self.bind("<Right>", lambda e: self._next_page())

    def _apply_native_vibrancy(self):
        """Uses PyObjC to inject a native macOS blur view behind the window."""
        try:
            self.update()
            view_id = self.winfo_id()
            ns_view = objc.objc_object(c_void_p=view_id)
            ns_window = ns_view.window()
            
            content_view = ns_window.contentView()
            frame = content_view.bounds()
            
            blur_view = NSVisualEffectView.alloc().initWithFrame_(frame)
            blur_view.setAutoresizingMask_(18) # width/height Sizable
            blur_view.setMaterial_(NSVisualEffectMaterialSidebar)
            blur_view.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
            blur_view.setState_(NSVisualEffectStateActive)
            
            content_view.addSubview_positioned_relativeTo_(blur_view, -1, None)
            # Make the Tkinter frame see through to show the blur
            self.configure(fg_color="transparent")
        except Exception as e:
            print(f"Native vibrancy skipped: {e}")

    def _setup_ui(self):
        # Appearance - Default to System but allow the user's OS to dictate
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue") 

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- SIDEBAR (Editorial Style) ---
        self.sidebar = ctk.CTkFrame(self, width=300, corner_radius=0, fg_color=("#E5E5EA", "#111112"))
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 0), pady=0)
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="Audile", text_color=self.CLR_ACCENT,
                                       font=ctk.CTkFont(family="SF Pro Display", size=42, weight="bold"))
        self.logo_label.pack(anchor="w", padx=30, pady=(40, 30))

        # Functional Tabview Switcher
        self.nav_tab_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_tab_frame.pack(fill="x", padx=20)

        nav_opts = [("Library", "Library"), ("Playing", "Playing"), ("Notes", "Notes")]
        self.nav_btns = {}
        for label, target in nav_opts:
            # Force high-contrast text colors
            btn = ctk.CTkButton(self.nav_tab_frame, text=label, height=45, corner_radius=12,
                                fg_color="transparent", text_color=("#1C1C1E", "#F2F2F7"),
                                hover_color=("#D1D1D6", "#2C2C2E"), font=ctk.CTkFont(family="SF Pro Text", size=15, weight="bold"),
                                command=lambda t=target: self._switch_nav(t))
            btn.pack(pady=2, fill="x")
            self.nav_btns[target] = btn

        self.tabview = ctk.CTkTabview(self.sidebar, width=260, fg_color="transparent")
        self.tabview._segmented_button.pack_forget() # Hide default buttons
        self.tabview.pack(padx=0, pady=10, expand=True, fill="both")
        
        self.lib_tab = self.tabview.add("Library")
        self.play_tab = self.tabview.add("Playing")
        self.notes_tab = self.tabview.add("Notes")

        # --- TAB: LIBRARY ---
        self.lib_add_btn = ctk.CTkButton(self.lib_tab, text="➕ Add Document", height=50, corner_radius=15, 
                                         fg_color=self.CLR_ACCENT, hover_color=self.CLR_ACCENT_ALT,
                                         font=ctk.CTkFont(weight="bold"), command=self._open_file)
        self.lib_add_btn.pack(padx=10, pady=10, fill="x")
        
        self.lib_scroll = ctk.CTkScrollableFrame(self.lib_tab, fg_color="transparent")
        self.lib_scroll.pack(padx=5, pady=5, expand=True, fill="both")

        # --- TAB: PLAYING ---
        self.voice_menu = ctk.CTkOptionMenu(self.play_tab, values=[], height=40, corner_radius=12, 
                                            fg_color=self.CLR_CARD, button_color=self.CLR_BORDER,
                                            dropdown_hover_color=self.CLR_ACCENT, command=self._on_voice_change)
        self.voice_menu.pack(padx=10, pady=(20, 10), fill="x")
        
        self.voice_btn_frame = ctk.CTkFrame(self.play_tab, fg_color="transparent")
        self.voice_btn_frame.pack(fill="x", padx=10)
        
        self.preview_btn = ctk.CTkButton(self.voice_btn_frame, text="🔊 Preview", height=35, corner_radius=10, 
                                         fg_color="transparent", border_width=1, text_color=("#1C1C1E", "#F2F2F7"),
                                         command=self._preview_voice)
        self.preview_btn.pack(side="left", expand=True, fill="x", padx=(0, 2))
        
        self.hide_voice_btn = ctk.CTkButton(self.voice_btn_frame, text="👁 Hide", height=35, corner_radius=10, 
                                            fg_color="transparent", border_width=1, text_color=("#1C1C1E", "#F2F2F7"),
                                            command=self._hide_current_voice)
        self.hide_voice_btn.pack(side="left", expand=True, fill="x", padx=(2, 0))

        self.speed_label = ctk.CTkLabel(self.play_tab, text="Speed: 1.0x", font=ctk.CTkFont(size=12), text_color=self.CLR_TEXT_SEC)
        self.speed_label.pack(padx=10, pady=(20, 5))
        self.speed_slider = ctk.CTkSlider(self.play_tab, from_=0.5, to=3.0, button_color=self.CLR_ACCENT, 
                                          progress_color=self.CLR_ACCENT, command=self._on_speed_change)
        self.speed_slider.set(1.0)
        self.speed_slider.pack(padx=10, pady=(0, 20), fill="x")

        self.premium_only_switch = ctk.CTkSwitch(self.play_tab, text="Premium Narrators Only", progress_color=self.CLR_ACCENT,
                                                command=self._refresh_voice_list)
        self.premium_only_switch.select()
        self.premium_only_switch.pack(padx=10, pady=10)

        # Help / Reset at bottom
        self.help_frame = ctk.CTkFrame(self.play_tab, fg_color="transparent")
        self.help_frame.pack(side="bottom", pady=10)
        self.download_help_btn = ctk.CTkButton(self.help_frame, text="❓ Missing Voices?", height=20, font=ctk.CTkFont(size=10), 
                                               fg_color="transparent", text_color=("#1C1C1E", "#8E8E93"), command=self._show_voice_help)
        self.download_help_btn.pack()
        self.reset_voices_btn = ctk.CTkButton(self.help_frame, text="↺ Reset Hidden Voices", height=20, font=ctk.CTkFont(size=10), 
                                               fg_color="transparent", text_color=("#1C1C1E", "#8E8E93"), command=self._reset_hidden_voices)
        self.reset_voices_btn.pack()

        # --- TAB: NOTES ---
        self.add_bmk_btn = ctk.CTkButton(self.notes_tab, text="🔖 New Highlight", height=45, corner_radius=12,
                                         fg_color=self.CLR_ACCENT, command=self._add_bookmark)
        self.add_bmk_btn.pack(padx=10, pady=10, fill="x")
        self.bmk_scroll = ctk.CTkScrollableFrame(self.notes_tab, fg_color="transparent")
        self.bmk_scroll.pack(padx=5, pady=5, expand=True, fill="both")

        # --- MAIN VIEWING CONTAINER ---
        self.main_container = ctk.CTkFrame(self, corner_radius=32, fg_color=self.CLR_CARD, border_width=1, border_color=self.CLR_BORDER)
        self.main_container.grid(row=0, column=1, padx=25, pady=25, sticky="nsew")
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)

        # Dynamic canvas bg for light/dark mode
        canvas_bg = "#111112" if darkdetect.isDark() else "#F2F2F7"
        self.canvas = tk.Canvas(self.main_container, bg=canvas_bg, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        
        # Interactions for Canvas
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Control-MouseWheel>", self._on_pinch_zoom)
        self.canvas.bind("<Button-1>", self._on_canvas_click)  # Click to start at paragraph

        # --- THE "DYNAMIC ISLAND" PLAYBACK POD ---
        self.island = ctk.CTkFrame(self.main_container, height=80, corner_radius=40, 
                                   fg_color=("#FDFDFD", "#1D1D1F"), border_width=1, border_color=self.CLR_BORDER)
        self.island.place(relx=0.5, rely=0.92, anchor="center", relwidth=0.6)
        
        self.play_btn = ctk.CTkButton(self.island, text="▶", width=54, height=54, corner_radius=27, 
                                      fg_color=self.CLR_ACCENT, hover_color=self.CLR_ACCENT_ALT,
                                      font=ctk.CTkFont(size=22), command=self._play)
        self.play_btn.pack(side="left", padx=13)

        self.page_lbl = ctk.CTkLabel(self.island, text="Audile Pro", font=ctk.CTkFont(family="SF Pro Display", size=15, weight="bold"))
        self.page_lbl.pack(side="left", padx=10, expand=True)

        self.zoom_out_btn = ctk.CTkButton(self.island, text="−", width=36, height=36, corner_radius=18, 
                                          fg_color="transparent", text_color=("#1C1C1E", "#F2F2F7"),
                                          font=ctk.CTkFont(size=20), command=self._zoom_out)
        self.zoom_out_btn.pack(side="right", padx=2)
        
        self.zoom_in_btn = ctk.CTkButton(self.island, text="+", width=36, height=36, corner_radius=18, 
                                         fg_color="transparent", text_color=("#1C1C1E", "#F2F2F7"),
                                         font=ctk.CTkFont(size=20), command=self._zoom_in)
        self.zoom_in_btn.pack(side="right", padx=2)

        self.prev_btn = ctk.CTkButton(self.island, text="⏪", width=44, height=44, corner_radius=22, fg_color="transparent", command=self._prev_page)
        self.prev_btn.pack(side="right", padx=5)
        
        self.next_btn = ctk.CTkButton(self.island, text="⏩", width=44, height=44, corner_radius=22, fg_color="transparent", command=self._next_page)
        self.next_btn.pack(side="right", padx=(5, 13))

        # Overall Progress Bar (Hidden Slim line at the very top of main frame)
        self.progress_bar = ctk.CTkProgressBar(self.main_container, height=3, progress_color=self.CLR_ACCENT, fg_color=("#E5E5EA", "#3A3A3C"))
        self.progress_bar.grid(row=0, column=0, sticky="new", padx=40, pady=(15, 0))
        self.progress_bar.set(0)

        # Version footer
        self.version_label = ctk.CTkLabel(self.sidebar, text="Audile v1.0", font=ctk.CTkFont(size=11), text_color=self.CLR_TEXT_SEC)
        self.version_label.pack(side="bottom", pady=(0, 20))

        self._refresh_voice_list()
        self._switch_nav("Library")

    def _switch_nav(self, target):
        self.tabview.set(target)
        for t, btn in self.nav_btns.items():
            btn.configure(fg_color=self.CLR_ACCENT if t == target else "transparent",
                          text_color="white" if t == target else ("black", "white"))

    def _open_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if file_path:
            self._select_doc_type(file_path)

    def _select_doc_type(self, file_path):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Import Document")
        dialog.geometry("340x320")
        dialog.configure(fg_color=self.CLR_BG[1] if darkdetect.isDark() else self.CLR_BG[0])
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Optimize Reading For:", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=25)
        
        opts = [("📖  Literary Book", "Book"), ("🔬  Research Paper", "Research"), ("📑  Standard Document", "Standard")]
        for label, val in opts:
            btn = ctk.CTkButton(dialog, text=label, height=55, corner_radius=18, 
                                fg_color=self.CLR_CARD[1] if darkdetect.isDark() else self.CLR_CARD[0], 
                                border_width=1, border_color=self.CLR_BORDER[1] if darkdetect.isDark() else self.CLR_BORDER[0],
                                hover_color=self.CLR_ACCENT, command=lambda v=val: [dialog.destroy(), self._load_pdf(file_path, v)])
            btn.pack(pady=6, padx=35, fill="x")

    def _load_pdf(self, file_path, doc_type="Book"):
        if self.is_loading: return
        self._stop() 
        self.is_loading = True
        
        def extract():
            try:
                engine = PDFEngine(file_path)
                if engine.open():
                    self.pdf_engine = engine
                    self.current_pdf_path = file_path
                    self.after(0, lambda: self._on_pdf_loaded(doc_type))
                else:
                    self.after(0, lambda: messagebox.showerror("Error", "Unsupported PDF format."))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", f"Failed: {e}"))
            finally:
                self.is_loading = False
        threading.Thread(target=extract, daemon=True).start()

    def _on_pdf_loaded(self, doc_type):
        if self.current_pdf_path not in self.library:
            self.library[self.current_pdf_path] = {"page": 1, "title": os.path.basename(self.current_pdf_path), "doc_type": doc_type}
        
        self.current_page_num = self.library[self.current_pdf_path].get("page", 1)
        self._load_page_data(self.current_page_num)
        self._refresh_library_list()
        self._refresh_bookmark_list()
        self._save_config()
        self._switch_nav("Playing")

    def _load_page_data(self, page_num):
        self.current_page_num = page_num
        if self.current_pdf_path in self.library:
            self.library[self.current_pdf_path]["page"] = page_num
        
        doc_type = self.library[self.current_pdf_path].get("doc_type", "Book")
        self.current_page_blocks = self.pdf_engine.get_page_data(page_num, doc_type=doc_type)
        self.current_block_index = 0
        self.page_lbl.configure(text=f"Page {page_num} / {self.pdf_engine.total_pages}")
        self._render_page()

    def _render_page(self, force=False):
        if not self.pdf_engine: return
        self.update_idletasks()
        canvas_width = self.canvas.winfo_width()
        if canvas_width > 50:
            orig_w, _ = self.pdf_engine.get_page_size(self.current_page_num)
            if orig_w: self.zoom_factor = (canvas_width - 100) / orig_w
        
        if self.current_page_num != self.current_page_rendered or force or self.current_tk_img is None:
            from PIL import ImageTk
            self.current_img = self.pdf_engine.get_page_image(self.current_page_num, zoom=self.zoom_factor)
            if not self.current_img: return
            self.current_tk_img = ImageTk.PhotoImage(self.current_img)
            self.canvas.delete("all")
            img_w, img_h = self.current_tk_img.width(), self.current_tk_img.height()
            x_off = max(50, (canvas_width - img_w) // 2)
            self.canvas.create_image(x_off, 50, anchor="nw", image=self.current_tk_img, tags="page")
            self.canvas.config(scrollregion=(0, 0, max(canvas_width, img_w + x_off*2), img_h + 150))
            self.current_page_rendered = self.current_page_num

        self._highlight_current_block()
        self.progress_bar.set(self.current_page_num / self.pdf_engine.total_pages)

    def _highlight_current_block(self):
        """Draws a professional focus indicator for the active block."""
        self.canvas.delete("focus")
        if not self.current_page_blocks or self.current_block_index >= len(self.current_page_blocks): 
            return
            
        block = self.current_page_blocks[self.current_block_index]
        bbox, z = block["bbox"], self.zoom_factor
        coords = self.canvas.coords("page")
        if not coords: return
        x_off, y_off = coords[0], coords[1]
        
        # Sleek Sidebar Bar (localized to text column)
        self.canvas.create_rectangle(bbox[0]*z + x_off - 15, bbox[1]*z + y_off + 2, 
                                   bbox[0]*z + x_off - 10, bbox[3]*z + y_off - 2, 
                                   fill=self.CLR_ACCENT, outline="", tags="focus")

    def _play(self):
        if not self.current_page_blocks: return
        if self.is_playing:
            self._stop()
            return
        self.is_playing = True
        self.play_btn.configure(text="■")
        self._speak_current_block()

    def _speak_current_block(self):
        if not self.is_playing: return
        if self.current_block_index < len(self.current_page_blocks):
            block = self.current_page_blocks[self.current_block_index]
            self.tts_engine.speak(block["text"])
            self._highlight_current_block()
            self.after(100, self._check_speech_status)
        else:
            self._on_page_finished()

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
            self.page_lbl.configure(text="✓ Finished")

    def _pause(self): self.tts_engine.pause()
    def _stop(self):
        self.is_playing = False
        self.play_btn.configure(text="▶")
        self.tts_engine.stop()

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

    def _on_mousewheel(self, event):
        """Native macOS trackpad scroll support (two-finger drag)."""
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")

    def _on_pinch_zoom(self, event):
        """Pinch-to-zoom using Control+MouseWheel."""
        if event.delta > 0:
            self._zoom_in()
        else:
            self._zoom_out()
    
    def _zoom_in(self):
        self.zoom_factor = min(5.0, self.zoom_factor * 1.15)
        self._render_page(force=True)
    
    def _zoom_out(self):
        self.zoom_factor = max(0.5, self.zoom_factor * 0.85)
        self._render_page(force=True)
    
    def _on_canvas_click(self, event):
        """Click on a paragraph to start reading from there."""
        if not self.current_page_blocks:
            return
        
        # Get click position relative to page
        coords = self.canvas.coords("page")
        if not coords:
            return
        x_off, y_off = coords[0], coords[1]
        z = self.zoom_factor
        
        # Convert click to PDF coordinates
        click_x = (event.x - x_off) / z
        click_y = (event.y - y_off) / z
        
        # Find which block was clicked
        for i, block in enumerate(self.current_page_blocks):
            bbox = block["bbox"]
            if bbox[0] <= click_x <= bbox[2] and bbox[1] <= click_y <= bbox[3]:
                # Stop current playback and start from this block
                self._stop()
                self.current_block_index = i
                self._highlight_current_block()
                self.is_playing = True
                self.play_btn.configure(text="■")
                self._speak_current_block()
                return

    def _on_speed_change(self, v):
        self.tts_engine.set_rate(v)
        self.speed_label.configure(text=f"Speed: {v:.1f}x")
    def _on_voice_change(self, display_name):
        """Robustly switch narrator based on menu selection."""
        # Find voice by display name match
        for i, dn in enumerate(self.voice_display_names):
            if dn == display_name:
                self.tts_engine.set_voice(self.voices[i]['id'])
                # Auto-stop and preview if playing? No, just set.
                break

    def _refresh_library_list(self):
        for widget in self.lib_scroll.winfo_children(): widget.destroy()
        if not self.library:
            ctk.CTkLabel(self.lib_scroll, text="Collection is empty", font=ctk.CTkFont(slant="italic")).pack(pady=40)
            return
        for path, info in self.library.items():
            if not os.path.exists(path): continue
            frame = ctk.CTkFrame(self.lib_scroll, fg_color="transparent")
            frame.pack(fill="x", pady=5, padx=10)
            is_active = (path == self.current_pdf_path)
            
            btn = ctk.CTkButton(frame, text=f"• {info['title']}", anchor="w", height=65, corner_radius=15,
                               fg_color=self.CLR_BORDER[1] if is_active else "transparent",
                               text_color=self.CLR_ACCENT if is_active else "white",
                               font=ctk.CTkFont(size=14, weight="bold" if is_active else "normal"),
                               command=lambda p=path: self._load_pdf(p))
            btn.pack(side="left", fill="x", expand=True, padx=(0, 10))
            
            del_btn = ctk.CTkButton(frame, text="🗑", width=40, height=40, corner_radius=20, fg_color="transparent", 
                                   text_color=self.CLR_TEXT_SEC, hover_color="#FF3B30",
                                   command=lambda p=path: self._confirm_remove(p))
            del_btn.pack(side="right")

    def _confirm_remove(self, path):
        if messagebox.askyesno("Audile Pro", "Permanently remove this document?\n\nHighlights and library progress will be lost."):
            del self.library[path]
            if path == self.current_pdf_path:
                self.current_pdf_path = None
                self.canvas.delete("all")
            self._refresh_library_list()
            self._save_config()

    def _refresh_voice_list(self):
        raw = self.tts_engine.get_voices()
        premium_only = self.premium_only_switch.get() == 1
        voice_map = {}
        for v in raw:
            if v['id'] in self.hidden_voice_ids or v['is_novelty']: continue
            if premium_only and not v['is_premium']: continue
            key = (v['name'], v['lang'])
            if key not in voice_map or v['quality_val'] > voice_map[key]['quality_val']: voice_map[key] = v
        self.voices = sorted(list(voice_map.values()), key=lambda v: (not v.get('is_personal', False), -v['quality_val'], v['name']))
        self.voice_display_names = [f"{v['name']}  {'👤' if v.get('is_personal') else '✨' if v['quality_val']==3 else '★' if v['quality_val']==2 else ''}" for v in self.voices]
        if self.voice_menu:
            self.voice_menu.configure(values=self.voice_display_names)
            # Auto-select first voice if available
            if self.voice_display_names and not self.voice_menu.get():
                self.voice_menu.set(self.voice_display_names[0])
                self.tts_engine.set_voice(self.voices[0]['id'])

    def _add_bookmark(self):
        if not self.current_pdf_path: return
        note = ctk.CTkInputDialog(text="Personal Annotation:", title="Add Note").get_input()
        if note:
            if self.current_pdf_path not in self.bookmarks: self.bookmarks[self.current_pdf_path] = []
            self.bookmarks[self.current_pdf_path].append({"page": self.current_page_num, "note": note, "timestamp": time.time()})
            self._refresh_bookmark_list()
            self._save_config()

    def _refresh_bookmark_list(self):
        for widget in self.bmk_scroll.winfo_children(): widget.destroy()
        if not self.current_pdf_path or self.current_pdf_path not in self.bookmarks: return
        for b in sorted(self.bookmarks[self.current_pdf_path], key=lambda x: x['page']):
            btn = ctk.CTkButton(self.bmk_scroll, text=f"P{b['page']}: {b['note']}", anchor="w", height=45, corner_radius=15,
                               fg_color=self.CLR_BORDER[1], text_color="white", command=lambda p=b['page']: self._load_page_data(p))
            btn.pack(fill="x", pady=3, padx=10)

    def _preview_voice(self):
        current = self.voice_menu.get()
        for v in self.voices:
            if current.startswith(v['name']): self.tts_engine.preview(v['id']); break
    def _hide_current_voice(self):
        current = self.voice_menu.get()
        for v in self.voices:
            if current.startswith(v['name']): self.hidden_voice_ids.add(v['id']); break
        self._refresh_voice_list(); self._save_config()
    def _reset_hidden_voices(self): self.hidden_voice_ids.clear(); self._refresh_voice_list(); self._save_config()
    def _show_voice_help(self): messagebox.showinfo("Voices", "Install 'Enhanced' voices in System Settings > Accessibility > Spoken Content.")

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

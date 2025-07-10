import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import logging
import keyboard
import sv_ttk
import threading 

from privacy_engine import PrivacyEngine
from config import get_username, load_settings, save_settings
from ai import AIScreenReader

class App(tk.Tk):
    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        
        self.settings = load_settings()['DEFAULT']
        sv_ttk.set_theme(self.settings.get('theme', 'light'))

        self.title("AI Interview Assist - Batlez")
        self.geometry("500x750")

        self._last_pct = None

        self.create_widgets()

        self.update_idletasks()
        hwnd = self.winfo_id()
        self.engine = PrivacyEngine(hwnd, self.logger)
        self.ai_reader = AIScreenReader(self, self.logger)

        self.setup_hotkeys()
        self.apply_initial_settings()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(self.main_frame, text=f"Hello, {get_username()}!", font=("Segoe UI", 12, "bold")).pack(pady=5)

        toggle_frame = ttk.LabelFrame(self.main_frame, text="Privacy Toggles", padding="10")
        toggle_frame.pack(pady=10, fill=tk.X)

        self.hide_screen_var  = tk.BooleanVar(value=self.settings.getboolean('hide_from_screen', False))
        self.hide_taskbar_var = tk.BooleanVar(value=self.settings.getboolean('hide_from_taskbar', False))
        self.on_top_var       = tk.BooleanVar(value=self.settings.getboolean('always_on_top', False))

        self.add_toggle(toggle_frame, "Hide from Screen",  self.hide_screen_var,  self.toggle_hide_screen)
        self.add_toggle(toggle_frame, "Hide from Taskbar", self.hide_taskbar_var, self.toggle_hide_taskbar)
        self.add_toggle(toggle_frame, "Always on Top",     self.on_top_var,       self.toggle_on_top)

        ai_config_frame = ttk.LabelFrame(self.main_frame, text="Model & Prompt", padding="10")
        ai_config_frame.pack(pady=10, fill=tk.X)

        model_frame = ttk.Frame(ai_config_frame)
        model_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(model_frame, text="Model:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.models_with_labels = [
            ("gpt-4.1-nano", "Fastest & Cheapest"), 
            ("gpt-4o-mini",  "Faster & Cheap"),
            ("gpt-4.1-mini", "Fast & Mid-Priced"),
            ("o3-mini",      "Smart & Pricey"),
            ("o4-mini",      "Smarter & Expensive"),
            ("o1-mini",      "Smartest & Costliest"),
        ]
        
        
        self.model_display_names = [f"{model} ({label})" for model, label in self.models_with_labels]
        
        saved_model = self.settings.get('ai_model', 'gpt-4o-mini')
        
        current_display_name = next(
            (name for name in self.model_display_names if name.startswith(saved_model)), 
            self.model_display_names[2]
        )

        self.model_var = tk.StringVar(value=current_display_name)
        
        self.model_combo = ttk.Combobox(model_frame, textvariable=self.model_var, values=self.model_display_names, state='readonly')
        self.model_combo.pack(fill=tk.X, expand=True)
        self.model_combo.bind("<<ComboboxSelected>>", self.on_model_select)

        ttk.Label(ai_config_frame, text="AI Prompt:").pack(anchor="w")
        self.prompt_text = tk.Text(ai_config_frame, height=4, wrap='word', font=("Segoe UI", 9))
        self.prompt_text.pack(fill=tk.X, expand=True, pady=(5,0))
        default_prompt = "Analyze this screenshot. Describe what you see and transcribe any text in it."
        self.prompt_text.insert("1.0", self.settings.get('ai_prompt', default_prompt))

        ai_frame = ttk.LabelFrame(self.main_frame, text="AI Tools", padding="10")
        ai_frame.pack(pady=10, fill=tk.X)
        
        self.full_screen_btn = ttk.Button(ai_frame, text="Analyze Full Screen", command=self.run_ai_full_screen)
        self.full_screen_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        
        self.section_btn = ttk.Button(ai_frame, text="Analyze Screen Area", command=self.run_ai_screen_area)
        self.section_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(5, 0))

        settings_frame = ttk.Frame(self.main_frame)
        settings_frame.pack(fill=tk.X, pady=10)

        theme_frame = ttk.Frame(settings_frame)
        theme_frame.pack(fill=tk.X)
        ttk.Label(theme_frame, text="Theme:").pack(side=tk.LEFT, padx=(0,10))
        self.theme_btn = ttk.Button(theme_frame, text=self.settings.get('theme', 'light').capitalize(), command=self.on_theme_toggle)
        self.theme_btn.pack(side=tk.LEFT)

        hotkey_btn = ttk.Button(theme_frame, text="Hotkeys & Toggles", command=self.show_hotkeys)
        hotkey_btn.pack(side=tk.RIGHT)

        slider_frame = ttk.Frame(settings_frame)
        slider_frame.pack(fill=tk.X, pady=10)
        ttk.Label(slider_frame, text="Transparency:").pack(side=tk.LEFT, padx=(0,5))
        self.transparency_slider = ttk.Scale(slider_frame, from_=10, to=100, orient=tk.HORIZONTAL)
        saved_pct = float(self.settings.get('transparency', 1.0)) * 100
        self.transparency_slider.set(saved_pct)
        self.transparency_slider.pack(fill=tk.X, expand=True)
        self.transparency_slider.bind("<B1-Motion>", self.on_slider_preview)
        self.transparency_slider.bind("<ButtonRelease-1>", self.on_slider_release)

        log_frame = ttk.LabelFrame(self.main_frame, text="Event Log", padding="5")
        log_frame.pack(pady=10, fill=tk.BOTH, expand=True)
        self.log_text = tk.Text(log_frame, height=8, state='disabled', wrap='word', font=("Courier New", 8))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        handler = TextHandler(self.log_text)
        self.logger.addHandler(handler)
        self.update_log_theme()

    def on_model_select(self, event):
        self.model_combo.selection_clear()
        self.main_frame.focus()

    def add_toggle(self, parent, text, variable, command):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=2, anchor="w")
        
        chk = ttk.Checkbutton(frame, text=text, variable=variable, command=command)
        chk.pack(side=tk.LEFT)
        
        status = tk.Label(frame, text="●", font=("Segoe UI", 10))
        status.pack(side=tk.RIGHT, padx=10)

        def on_variable_change(*args):
            self.update_status_indicator(status, variable.get())
            command()

        chk.config(command=None) 
        variable.trace_add("write", on_variable_change) 

        self.update_status_indicator(status, variable.get())


    def update_status_indicator(self, indicator, is_on):
        color = "green" if is_on else "red"
        try:
            style = ttk.Style()
            bg_color = style.lookup(indicator.master.winfo_class(), 'background')
            indicator.config(fg=color, bg=bg_color)
        except tk.TclError:
            indicator.config(fg=color)
    
    def _set_ai_buttons_state(self, is_analyzing):
        state = "disabled" if is_analyzing else "normal"
        self.full_screen_btn.config(state=state)
        self.section_btn.config(state=state)

    def _start_ai_analysis(self, analysis_func):
        self._set_ai_buttons_state(is_analyzing=True)
        
        model_display_name = self.model_var.get()
        model = model_display_name.split(" ")[0]
        
        prompt = self.prompt_text.get("1.0", tk.END).strip()

        if not prompt:
            messagebox.showwarning("AI Prompt Error", "The AI prompt cannot be empty.")
            self._set_ai_buttons_state(is_analyzing=False)
            return

        def worker():
            result = analysis_func(model=model, prompt=prompt)
            self.after(0, self._on_ai_analysis_complete, result)

        threading.Thread(target=worker, daemon=True).start()

    def _on_ai_analysis_complete(self, result):
        self._set_ai_buttons_state(is_analyzing=False)
        if result:
            self.show_ai_results(result)

    def run_ai_full_screen(self):
        self.logger.info("Starting full screen analysis...")
        self._start_ai_analysis(self.ai_reader.analyze_full_screen)

    def run_ai_screen_area(self):
        self.logger.info("Starting screen area analysis...")
        self._start_ai_analysis(self.ai_reader.analyze_screen_area)

    def show_ai_results(self, text_content):
        win = tk.Toplevel(self)
        win.title("AI Analysis Results")
        win.geometry("600x400")

        text_area = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Segoe UI", 10), padx=5, pady=5)
        text_area.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        text_area.insert(tk.END, text_content)
        text_area.configure(state='disabled')
        
        copy_btn = ttk.Button(win, text="Copy to Clipboard", command=lambda: [self.clipboard_clear(), self.clipboard_append(text_content)])
        copy_btn.pack(pady=(0, 10))

        self.apply_privacy_settings_to_window(win, apply_transparency=True)

    def show_hotkeys(self):
        win = tk.Toplevel(self)
        win.title("Hotkeys & Toggles")
        win.geometry("320x200")
        win.transient(self)
        win.resizable(False, False)

        frm = ttk.Frame(win, padding="10")
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="Hotkeys:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=5)
        
        hotkeys = [
            ("Ctrl+Alt+H", "Toggle Hide from Screen"),
            ("Ctrl+Alt+T", "Toggle Hide from Taskbar"),
            ("Ctrl+Alt+Y", "Toggle Always on Top"),
            ("Ctrl+Alt+U", "Increase Transparency"),
            ("Ctrl+Alt+J", "Decrease Transparency"),
            ("Ctrl+Alt+M", "Toggle Theme"),
        ]
        
        for keys, desc in hotkeys:
            hotkey_frame = ttk.Frame(frm)
            hotkey_frame.pack(fill='x')
            ttk.Label(hotkey_frame, text=f"{keys}:", width=15, font=("Segoe UI", 9, "bold")).pack(side='left')
            ttk.Label(hotkey_frame, text=desc, font=("Segoe UI", 9)).pack(side='left')
            
        ttk.Button(frm, text="Close", command=win.destroy).pack(pady=10, side="bottom")
        self.apply_privacy_settings_to_window(win, apply_transparency=True)

    def toggle_hide_screen(self):
        state = self.hide_screen_var.get()
        self.engine.set_display_affinity(state)
        self.logger.info(f"Hide from Screen {'enabled' if state else 'disabled'}")

    def toggle_hide_taskbar(self):
        state = self.hide_taskbar_var.get()
        self.engine.set_taskbar_visibility(state)
        self.logger.info(f"Hide from Taskbar {'enabled' if state else 'disabled'}")

    def toggle_on_top(self):
        state = self.on_top_var.get()
        self.engine.set_always_on_top(state)
        self.logger.info(f"Always on Top {'enabled' if state else 'disabled'}")
    
    def setup_hotkeys(self):
        try:
            keyboard.add_hotkey('ctrl+alt+h', lambda: self.hide_screen_var.set(not self.hide_screen_var.get()))
            keyboard.add_hotkey('ctrl+alt+t', lambda: self.hide_taskbar_var.set(not self.hide_taskbar_var.get()))
            keyboard.add_hotkey('ctrl+alt+y', lambda: self.on_top_var.set(not self.on_top_var.get()))
            keyboard.add_hotkey('ctrl+alt+u', self.increase_transparency)
            keyboard.add_hotkey('ctrl+alt+j', self.decrease_transparency)
            keyboard.add_hotkey('ctrl+alt+m', lambda: self.after(0, self.on_theme_toggle))
            self.logger.info("Global hotkeys registered.")
        except Exception as e:
            self.logger.error(f"Failed to register hotkeys. May require admin rights. Error: {e}")

    def increase_transparency(self):
        pct = min(round(self.transparency_slider.get() / 5) * 5 + 5, 100)
        self.transparency_slider.set(pct)
        self.engine.set_transparency(pct)
        self.logger.info(f"Transparency set to {pct}% via hotkey")

    def decrease_transparency(self):
        pct = max(round(self.transparency_slider.get() / 5) * 5 - 5, 10)
        self.transparency_slider.set(pct)
        self.engine.set_transparency(pct)
        self.logger.info(f"Transparency set to {pct}% via hotkey")

    def on_slider_preview(self, event):
        raw = self.transparency_slider.get()
        pct = round(raw / 5) * 5
        if pct == self._last_pct: return
        self._last_pct = pct
        self.transparency_slider.set(pct)
        
        original_level = self.logger.level
        self.logger.setLevel(logging.WARNING)
        self.engine.set_transparency(pct)
        self.logger.setLevel(original_level)

    def on_slider_release(self, event):
        pct = round(self.transparency_slider.get() / 5) * 5
        self._last_pct = pct
        self.transparency_slider.set(pct)
        self.engine.set_transparency(pct)

    def apply_initial_settings(self):
        self.hide_screen_var.set(self.hide_screen_var.get())
        self.hide_taskbar_var.set(self.hide_taskbar_var.get())
        self.on_top_var.set(self.on_top_var.get())
        self.on_slider_release(None)

    def on_theme_toggle(self):
        sv_ttk.toggle_theme()
        new_theme = "dark" if "dark" in sv_ttk.get_theme() else "light"
        self.theme_btn.config(text=new_theme.capitalize())
        self.update_log_theme()
        self.after(50, lambda: self.update_status_indicator_colors(self))

    def update_status_indicator_colors(self, parent_widget):
        style = ttk.Style()
        for widget in parent_widget.winfo_children():
            if isinstance(widget, tk.Label) and "●" in widget.cget("text"):
                try:
                    bg_color = style.lookup(widget.master.winfo_class(), 'background')
                    if bg_color:
                        widget.config(bg=bg_color)
                except tk.TclError:
                    pass
            else:
                self.update_status_indicator_colors(widget)

    def update_log_theme(self):
        if hasattr(self, 'log_text'):
            is_dark = "dark" in sv_ttk.get_theme()
            bg_color = "#333333" if is_dark else "#FFFFFF"
            fg_color = "#FFFFFF" if is_dark else "#000000"
            self.log_text.configure(bg=bg_color, fg=fg_color)
            if hasattr(self, 'prompt_text'):
                self.prompt_text.configure(bg=bg_color, fg=fg_color, insertbackground=fg_color)

    def apply_privacy_settings_to_window(self, window, apply_transparency=False):
        self.logger.info(f"Applying privacy settings to window: {window.title()}")
        window.update_idletasks()
        try:
            hwnd = window.winfo_id()
            engine = PrivacyEngine(hwnd, self.logger)
            engine.set_display_affinity(self.hide_screen_var.get())
            engine.set_taskbar_visibility(self.hide_taskbar_var.get())
            engine.set_always_on_top(self.on_top_var.get())
            if apply_transparency:
                engine.set_transparency(self.transparency_slider.get())
            self.logger.info(f"Applied privacy settings to HWND: {hwnd}")
        except Exception as e:
            self.logger.error(f"Failed to apply privacy settings to window {window.title()}: {e}")

    def on_closing(self):
        self.settings['hide_from_screen']  = str(self.hide_screen_var.get())
        self.settings['hide_from_taskbar'] = str(self.hide_taskbar_var.get())
        self.settings['always_on_top']     = str(self.on_top_var.get())
        self.settings['transparency']      = str(self.transparency_slider.get()/100.0)
        self.settings['theme']             = sv_ttk.get_theme()
        
        model_display_name = self.model_var.get()
        self.settings['ai_model'] = model_display_name.split(" ")[0]
        
        self.settings['ai_prompt']         = self.prompt_text.get("1.0", tk.END).strip()
        
        cfg = load_settings()
        cfg['DEFAULT'] = self.settings
        save_settings(cfg)
        
        try:
            keyboard.unhook_all_hotkeys()
        except Exception as e:
            self.logger.warning(f"Could not unhook hotkeys: {e}")
        self.logger.info("Settings, theme & hotkeys cleaned up. Exiting.")
        self.destroy()

class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.configure(state='disabled')
            self.text_widget.yview(tk.END)
        self.text_widget.after(0, append)
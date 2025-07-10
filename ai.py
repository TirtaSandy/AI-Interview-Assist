import tkinter as tk
from tkinter import messagebox
from PIL import ImageGrab, Image
import openai
import base64
import io
from config import get_openai_api_key

class AIScreenReader:

    def __init__(self, parent_app, logger):
        self.parent_app = parent_app
        self.logger = logger
        try:
            self.client = openai.OpenAI(api_key=get_openai_api_key())
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI client: {e}")
            messagebox.showerror("OpenAI Error", f"Failed to initialize OpenAI client. Please check your API key.\n\n{e}")
            self.client = None

    def _analyze_image(self, image: Image.Image, model: str, prompt: str):
        if not self.client:
            return "OpenAI client not initialized."

        self.logger.info(f"Sending image to OpenAI for analysis using model: {model}...")
        
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                        ],
                    }
                ],
                max_tokens=1000,
            )
            self.logger.info("Received analysis from OpenAI.")
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"OpenAI API call failed: {e}")
            messagebox.showerror("OpenAI Error", f"API call failed: {e}")
            return f"Error analyzing image: {e}"

    def analyze_full_screen(self, model: str, prompt: str):
        self.logger.info("Capturing full screen...")
        
        self.parent_app.withdraw()
        self.parent_app.update_idletasks()
        
        screenshot = ImageGrab.grab(all_screens=True)
        
        self.parent_app.deiconify()
        
        return self._analyze_image(screenshot, model, prompt)

    def analyze_screen_area(self, model: str, prompt: str):
        self.logger.info("Starting screen area selection...")
        selector = ScreenAreaSelector(self.parent_app)
        
        self.parent_app.withdraw()
        self.parent_app.wait_window(selector.master)
        
        screenshot = None
        if selector.bbox:
            self.logger.info(f"Area selected: {selector.bbox}")
            
            screen_width = self.parent_app.winfo_screenwidth()
            screen_height = self.parent_app.winfo_screenheight()

            x1 = max(0, selector.bbox[0])
            y1 = max(0, selector.bbox[1])
            x2 = min(screen_width, selector.bbox[2])
            y2 = min(screen_height, selector.bbox[3])
            
            if x1 >= x2 or y1 >= y2:
                self.logger.warning("Invalid area selected (zero or negative size). Aborting.")
            else:
                clamped_bbox = (x1, y1, x2, y2)
                self.logger.info(f"Clamped bbox to: {clamped_bbox}")
                full_screenshot = ImageGrab.grab(all_screens=True)
                screenshot = full_screenshot.crop(clamped_bbox)
        
        self.parent_app.deiconify()

        if screenshot:
            return self._analyze_image(screenshot, model, prompt)
        else:
            self.logger.info("Area selection cancelled.")
            return None


class ScreenAreaSelector:
    def __init__(self, parent_app):
        self.parent_app = parent_app
        self.master = tk.Toplevel(parent_app)
        self.master.title("Screen Selector")
        self.master.attributes("-fullscreen", True)
        self.master.attributes("-alpha", 0.3)
        self.master.bind("<ButtonPress-1>", self.on_press)
        self.master.bind("<B1-Motion>", self.on_drag)
        self.master.bind("<ButtonRelease-1>", self.on_release)
        
        self.canvas = tk.Canvas(self.master, cursor="cross", bg="grey")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        if hasattr(self.parent_app, 'apply_privacy_settings_to_window'):
            self.parent_app.apply_privacy_settings_to_window(self.master, apply_transparency=False)
        
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.bbox = None

    def on_press(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2)

    def on_drag(self, event):
        cur_x, cur_y = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_release(self, event):
        end_x, end_y = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        self.bbox = (min(self.start_x, end_x), min(self.start_y, end_y),
                     max(self.start_x, end_x), max(self.start_y, end_y))
        self.master.destroy()
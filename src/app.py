import subprocess
import os
import os
import shutil
import customtkinter as ctk
from tkinter import messagebox
import os
import subprocess
from PIL import Image, ImageTk
import threading
import sys

from src.api import API
from src.check import CHECK
from src.client import Client

class App:
    def __init__(self, root):
        self.client = None  
        self.season = None
        self.root = root
        #self.precheck()
        self.seasons_data = API.get_seasons()
        self.root.after(201, lambda: self.root.iconbitmap('assets\\icon.ico'))
        self.root.title("Vextract")
        self.center_window(500, 300)

        ctk.set_appearance_mode("dark")

        self.root.grid_rowconfigure(0, weight=1)  # Row 4: No expansion
        self.root.grid_rowconfigure(4, weight=1)  # Row 4: No expansion
        self.root.grid_rowconfigure(5, weight=1)  # Row 4: No expansion

        self.root.grid_columnconfigure(0, weight=1)  # Column 0: Expand
        self.root.grid_columnconfigure(1, weight=1)  # Column 1: Expand
        self.root.grid_columnconfigure(2, weight=1)  # Column 2: Expand
        self.root.grid_columnconfigure(3, weight=1)
        

        self.team_plate = ctk.StringVar()
        self.selected_season = ctk.StringVar()
        self.selected_event = ctk.StringVar()
        self.youtube_link = ctk.StringVar()

        ctk.CTkLabel(root, text="Team Plate (ex. 3388S):").grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkEntry(root, textvariable=self.team_plate).grid(row=1, column=2, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(root, text="Select Season:").grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        self.season_combobox = ctk.CTkComboBox(root, variable=self.selected_season)
        self.season_combobox.configure(values=[season['name'] for season in self.seasons_data])
        self.season_combobox.grid(row=2, column=2, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(root, text="YouTube Link:").grid(row=3, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkEntry(root, textvariable=self.youtube_link).grid(row=3, column=2, padx=10, pady=10, sticky="ew")

        self.best_quality_checkbox = ctk.CTkCheckBox(root, text="Best quality (WARNING: MAY BE 10 GB+)", fg_color="#bf0600", hover_color="#821D1A")
        self.best_quality_checkbox.grid(row=4, column=1, columnspan=2, padx=10, pady=10, sticky="ew")

        ctk.CTkButton(root, text="Next", command=self.show_events, fg_color="#821D1A", hover_color="#bf0600").grid(row=5, column=1, columnspan=2, pady=10, sticky="ew")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def precheck(self):
        default_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
        ]

        tesseract_path = None
        for path in default_paths:
            if os.path.isfile(path):
                tesseract_path = path
                break

        if tesseract_path is None:
            tesseract_path = shutil.which("tesseract")

        if not tesseract_path:
            messagebox.showerror("Error", "Please install tesseract https://github.com/UB-Mannheim/tesseract/wiki")
            sys.exit()

        if not shutil.which("ffmpeg"):
            messagebox.showerror("Error", "Please install ffmpeg https://www.ffmpeg.org/download.html")
            sys.exit()


    def on_close(self):
        self.root.destroy()
        self.client.ocr.terminate()
        sys.exit()

    def center_window(self, width, height):
        """Center the window on the screen."""
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)

        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def show_events(self):
        if not self.selected_season.get():
            messagebox.showerror("Error", "Please fill in all fields")
            return
        if not CHECK.check_youtube(self.youtube_link.get()) or not self.youtube_link.get():
            messagebox.showerror("Error", "Invalid youtube URL")
            return
        self.client = Client(self.team_plate.get(), self.youtube_link.get(), self.best_quality_checkbox.get())
        self.client.app = self
        if not self.team_plate.get() or not self.client.id:
            messagebox.showerror("Error", "Invalid team plate")
            return
        for widget in self.root.winfo_children():
            widget.destroy()

        for i in range(0, len(self.seasons_data)):
            if self.seasons_data[i]["name"] == self.selected_season.get():
                self.season = self.seasons_data[i]["id"]
                break
        if not self.season:
            messagebox.showerror("Error", "Invalid season")
            return

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(self.root, text="Select event:").grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        self.events_combobox = ctk.CTkComboBox(self.root, variable=self.selected_event)
        self.events = API.get_events(self.client.id)
        self.events.reverse()

        self.events_combobox.configure(values=[event['name'] for event in self.events], require_redraw=True)
        self.events_combobox.grid(row=1, column=2, padx=10, pady=10, sticky="ew")

        ctk.CTkButton(self.root, text="Submit", command=self.show_loading_screen, fg_color="#821D1A", hover_color="#bf0600").grid(row=2, column=1, columnspan=2, pady=10, sticky="ew")

    def show_loading_screen(self):
        global events
        self.event = self.events_combobox.get()
        if not self.event:
            messagebox.showerror("Error", "Invalid event")
            return
        
        for i in range(0, len(self.events)):
            if self.event == self.events[i]["name"]:
                self.event_id = self.events[i]["id"]

        self.client.event = self.event
        
        self.root.withdraw()

        self.loading_window = ctk.CTkToplevel(self.root)
        self.loading_window.protocol("WM_DELETE_WINDOW", self.on_close)
        self.loading_window.title("Vextracting...")
        self.loading_window.after(201, lambda :self.loading_window.iconbitmap('assets\\icon.ico'))
        self.center_toplevel(self.loading_window, 300, 150)

        self.loading_window.grab_set()

        self.loading_label = ctk.CTkLabel(self.loading_window, text="Processing")
        self.loading_label.pack(pady=(10, 0))

        self.progress = ctk.CTkProgressBar(self.loading_window, orientation="horizontal", width=200, progress_color="#bf0600")
        self.progress.pack(pady=20)

        self.progress.set(0)

        self.download_thread = threading.Thread(target=self.download_and_process_video)
        self.download_thread.start()

        self.update_progress()

    def center_toplevel(self, toplevel, width, height):
        screen_width = toplevel.winfo_screenwidth()
        screen_height = toplevel.winfo_screenheight()

        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)

        toplevel.geometry(f"{width}x{height}+{x}+{y}")

    def download_and_process_video(self):
        self.text = "Downloading video"
        self.progress_value = 0

        self.client.download()
        self.text = "Processing OCR"

        self.client.extract(self.event_id, self)

        self.loading_window.after(0, self.show_directory_display)
        self.loading_window.after(0, self.loading_window.destroy)

    def update_progress(self):
        if hasattr(self, 'progress_value'):
            self.progress.set(self.progress_value / 100)
            self.loading_label.configure(text=f"{self.text}... {self.progress_value}%")
            self.loading_window.update_idletasks()

        if self.download_thread.is_alive():
            self.loading_window.after(100, self.update_progress)
        

    def show_directory_display(self):

        self.directory_window = ctk.CTkToplevel(self.root)
        
        self.directory_window.title("Vextract - Results")
        self.directory_window.protocol("WM_DELETE_WINDOW", self.on_close)
        self.directory_window.after(201, lambda :self.directory_window.iconbitmap('assets\\icon.ico'))

        self.center_toplevel(self.directory_window, 800, 600)

        self.directory_frame = ctk.CTkScrollableFrame(self.directory_window)
        self.directory_frame.pack(fill="both", expand=True, padx=10, pady=10)

        video_directory = self.client.event
        if not os.path.exists(video_directory):
            os.makedirs(video_directory)

        video_files = [f for f in os.listdir(video_directory) if f.endswith(".mp4")]
        
        for video in video_files:
            video_path = os.path.join(video_directory, video)

            video_frame = ctk.CTkFrame(self.directory_frame)
            video_frame.pack(fill="x", padx=10, pady=5)

            thumbnail = self.get_video_thumbnail(video_path)
            if thumbnail:
                thumbnail_label = ctk.CTkLabel(video_frame, image=thumbnail, text="")
                thumbnail_label.image = thumbnail 
                thumbnail_label.pack(side="left", padx=10)

            video_info = f"Video: {video}"
            ctk.CTkLabel(video_frame, text=video_info).pack(side="left", padx=10)

        ctk.CTkButton(self.directory_window, text="Open Directory", command=lambda: self.open_directory(video_directory), fg_color="#821D1A", hover_color="#bf0600").pack(pady=10)

    def get_video_thumbnail(self, video_path):
        try:
            thumbnail_path = "thumbnail.jpg"
            command = f'ffmpeg -i "{video_path}" -ss 00:00:01 -vframes 1 {thumbnail_path} -y'
            subprocess.run(command, shell=True, check=True)

            image = Image.open(thumbnail_path)
            image.thumbnail((100, 100))
            thumbnail = ImageTk.PhotoImage(image)

            os.remove(thumbnail_path)

            return thumbnail
        except Exception as e:
            print(f"Error generating thumbnail: {e}")
            return None

    def open_directory(self, directory):
        if os.name == "nt":
            os.startfile(directory)
        elif os.name == "posix":
            subprocess.run(["open", directory] if os.uname().sysname == "Darwin" else ["xdg-open", directory])
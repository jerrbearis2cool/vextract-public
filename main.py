import yt_dlp
import subprocess
import cv2
import numpy as np
import pytesseract
import os
import requests
import re
from dotenv import load_dotenv
import os
import shutil
import tempfile
import shutil
import ctypes
import customtkinter as ctk
from tkinter import messagebox
import os
import subprocess
from PIL import Image, ImageTk
import threading
import sys

load_dotenv()
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

url = "http://52.137.123.13:3333"

class API: 
    def get_id(plate):
        return requests.get(f"{url}/get_id", json={"plate": plate}).json()["data"]

    def get_events(id):
        combined = requests.get(f"{url}/get_events", json={"id": id}).json()["data"]
        merged_list = []
        for item in combined:
            if item not in merged_list:
                merged_list.append(item)
        return merged_list

    def get_matches(id, season, event):
        return requests.get(f"{url}/get_matches", json={"event": event, "id": id, "season": season}).json()["data"]
    
    def get_seasons():
        return requests.get(f"{url}/get_seasons").json()["data"]

class Client:
    def __init__(self, team, url):
        self.url = url
        self.team = team
        self.app = None
        self.video = f"{self.team}.mp4"
        self.id = API.get_id(team)
        self.event = ""

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            percent_str = d.get('_percent_str', '0%')
            clean_percent_str = re.sub(r'\x1b\[[0-9;]*[mK]', '', percent_str)
            self.app.progress_value = int(float(clean_percent_str.strip('%').replace(" ", "")))

    def download(self):
        zxt = self.url.strip()
        options = {
            'outtmpl': f"{self.team}.%(ext)s",
            'format': 'bestaudio+bestevideo/best',
            'merge_output_format': 'mp4',
            'progress_hooks': [self.progress_hook],
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            'postprocessor_args': [
                '-ac', '2', 
                '-ar', '44100'
            ],
        }

        if os.name == 'posix':
            options['cookiesfrombrowser'] = ('firefox', )
        
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([zxt])

    def extract(self, event, app):
        self.app = app
        self.ocr = OCR(self)
        self.ocr.perform_ocr(interval=60 * 2)
        print(self.ocr.ocr)

        matches = self.get_matches(self.app.season, event)
        print(matches)
        l = len(matches)

        self.app.text = "Seeking clips"

        for i, match in enumerate(matches):
            self.app.progress_value = int((i / l) * 100)
            self.ocr.seek(match.replace(" ", ""))
        
        return self.team
    
    def delete(self):
        current_dir = os.getcwd()
        
        folder_path = os.path.join(current_dir, self.team)
        mp4_path = os.path.join(current_dir, f"{self.team}.mp4")

        def force_delete(file_path):
            try:
                FILE_ATTRIBUTE_NORMAL = 0x80
                ctypes.windll.kernel32.SetFileAttributesW(file_path, FILE_ATTRIBUTE_NORMAL)
                os.remove(file_path)
                print(f"File '{file_path}' has been forcefully deleted.")
            except Exception as e:
                print(f"Failed to delete file '{file_path}': {e}")

        if os.path.exists(folder_path):
            try:
                shutil.rmtree(folder_path, onerror=lambda func, path, exc_info: force_delete(path))
                print(f"Folder '{self.team}' and its contents have been deleted.")
            except Exception as e:
                print(f"Failed to delete folder '{self.team}': {e}")
        else:
            print(f"Folder '{self.team}' not found.")

        if os.path.exists(mp4_path):
            try:
                os.remove(mp4_path)
                print(f"MP4 file '{self.team}.mp4' has been deleted.")
            except PermissionError:
                print(f"MP4 file '{self.team}.mp4' is locked. Attempting forced deletion.")
                force_delete(mp4_path)
        else:
            print(f"MP4 file '{self.team}.mp4' not found.")
    
    def get_matches(self, season, event):
        matches = API.get_matches(self.id, season, event)
        result = []
        for match in matches:
            if "Final" in match["name"]:
                result.append(f'FINALS {match["name"].replace("#", "")[-3]}'.replace(" ", ""))
            else:
                result.append(match["name"].replace("Qualifier", "QUAL").replace("#", "").replace(" ", ""))

        return result

class OCR:
    def __init__(self, client:Client):
        self.client = client
        self.video = self.client.video

        self.ocr = {}
        print(self.client.team)
        try:
            os.mkdir(self.client.team)
            print(f"Directory '{self.client.team}' created successfully.")
        except FileExistsError:
            pass

    def video_duration(self):

        ffprobe_cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            self.video
        ]
        try:
            result = subprocess.run(ffprobe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            duration = result.stdout.strip()
            if duration == "N/A" or not duration:
                raise ValueError("Unable to retrieve video duration. Please check the file.")
            return float(duration)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"ffprobe failed: {e.stderr.strip()}")
        except ValueError as e:
            raise ValueError(f"Error: {e}")

    def perform_ocr(self, interval=10):

        print("Getting video duration...")
        duration = self.video_duration()
        print(f"Video duration: {duration:.2f} seconds")

        current_time = 0
        self.client.app.text = "Performing OCR"

        while current_time < duration:
            self.client.app.progress_value = int((current_time / duration) * 100)
            print("Performing OCR...")
            text = self.single_ocr(current_time)
            if text:
                print(f"OCR Output:\n{text}\n{'-' * 40}")

                self.ocr[text] = current_time

            current_time += interval

        return self.ocr
    
    def match(self, input_string):
        patterns = [
            r"FINALS \d+",      
            r"QF \d+-\d+",       
            r"R\d+ \d+-\d+",    
            r"SF \d+-\d+",      
            r"QUAL ?\d+"       
        ]
        
        combined_pattern = "|".join(patterns)
        matches = re.findall(combined_pattern, input_string)
        if matches:
            return matches[0].replace(" ", "")
        else:
            return None


    def single_ocr(self, timestamp):
        crop_filter="crop=iw*0.25:ih*0.1:0:0"

        ffmpeg_cmd = [
            "ffmpeg",
            "-ss", str(timestamp),     
            "-i", self.video,       
            "-vf", crop_filter,   
            "-vframes", "1",     
            "-f", "image2pipe",       
            "-vcodec", "png",       
            "-loglevel", "error",       
            "pipe:1"                
        ]

        try:
            process = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            np_frame = np.frombuffer(process.stdout, np.uint8)
            frame = cv2.imdecode(np_frame, cv2.IMREAD_COLOR)

            if frame is None:
                raise ValueError(f"Failed to decode frame at {timestamp}s")

            return self.match(pytesseract.image_to_string(frame))

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"ffmpeg failed: {e.stderr.strip()}")

    def extract(self, start_time, end_time, output_path):
        duration = end_time - start_time
        if duration <= 0:
            raise ValueError("End time must be greater than start time.")

        ffmpeg_cmd = ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start_time), 
            "-i", self.video, 
            "-t", str(duration), 
            "-c:v", "copy",     
            "-c:a", "copy", 
            "-map", "0:v:0",     
            "-map", "0:a:0",        
            "-loglevel", "error", 
            output_path          
        ]


        try:
            subprocess.run(ffmpeg_cmd, check=True)
            print(f"Video segment saved to {output_path}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Error extracting video segment: {e.stderr.strip()}")

    def compress_video(self, input_file, target_size_mb=9.5):
        target_size_bits = target_size_mb * 8 * 1024 * 1024
        target_size_bytes = target_size_bits // 8

        current_size = os.path.getsize(input_file)
        if current_size <= target_size_bytes:
            print(f"The file is already under the target size of {target_size_mb} MB.")
            return

        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "format=duration", "-of", "csv=p=0", input_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        duration = float(result.stdout.strip())

        audio_bitrate = 128 * 1024
        target_video_bitrate = (target_size_bits - audio_bitrate * duration) / duration

        temp_output_file = None
        try:
            while True:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
                    temp_file.close()
                    temp_output_file = temp_file.name

                ffmpeg_cmd = [
                    "ffmpeg",
                    "-i", input_file,
                    "-c:v", "libx264",
                    "-b:v", f"{int(target_video_bitrate)}", 
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-y",
                    temp_output_file
                ]

                subprocess.run(ffmpeg_cmd, check=True)
                print(f"Compressed video saved to {temp_output_file}")

                compressed_size = os.path.getsize(temp_output_file)

                if compressed_size <= target_size_bytes:
                    print(f"Compression successful. The file is now under {target_size_mb} MB.")
                    break 

                print(f"Compressed video exceeds the target size of {target_size_mb} MB. Retrying with a lower bitrate.")
                target_video_bitrate *= 0.9

            destination_file = input_file
            if os.path.exists(destination_file):
                os.remove(destination_file)

            os.rename(temp_output_file, destination_file)
            print(f"Input file successfully overwritten with compressed video.")

        except subprocess.CalledProcessError as e:
            error_message = e.stderr.strip() if e.stderr else "No error message returned from FFmpeg."
            raise RuntimeError(f"Error compressing video: {error_message}")
        finally:
            if temp_output_file and os.path.exists(temp_output_file):
                os.remove(temp_output_file)

    def seek(self, item):
        try:
            time = self.ocr[item]

            i = 0
            while True:
                if not self.single_ocr(time - i) == item:
                    break
                i += 10
            low = time - i
            i = 0
            while True:
                if not self.single_ocr(time + i) == item:
                    break
                i += 10
            high = time + i
            print(low, high)
            try:
                os.mkdir(self.client.team)
                print(f"Directory '{self.client.team}' created successfully.")
            except FileExistsError:
                pass
            self.extract(low, high, f"{self.client.team}\\{item}.mp4")

            return low, high
        except KeyError:
            pass

class CHECK:
    def check_youtube(url):
        youtube_regex = (
            r'^(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
            r'(watch\?v=[\w-]+(&t=\d+s)?|playlist\?list=[\w-]+|.*?/[\w-]+)$'
        )
        return bool(re.match(youtube_regex, url))

class App:
    def __init__(self, root):
        self.client = None  
        self.season = None
        self.root = root
        self.precheck()
        self.seasons_data = API.get_seasons()
        self.root.after(201, lambda :root.iconbitmap('icon.ico'))
        self.root.title("Vextract")
        self.center_window(500, 300)
    
        ctk.set_appearance_mode("dark")

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(4, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(2, weight=1)
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

        ctk.CTkButton(root, text="Next", command=self.show_events, fg_color="#821D1A", hover_color="#bf0600").grid(row=4, column=1, columnspan=2, pady=10, sticky="ew")

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
        self.client = Client(self.team_plate.get(), self.youtube_link.get())
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

        ctk.CTkLabel(root, text="Select event:").grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        self.events_combobox = ctk.CTkComboBox(root, variable=self.selected_event)
        self.events = API.get_events(self.client.id)
        self.events.reverse()

        self.events_combobox.configure(values=[event['name'] for event in self.events], require_redraw=True)
        self.events_combobox.grid(row=1, column=2, padx=10, pady=10, sticky="ew")

        ctk.CTkButton(root, text="Submit", command=self.show_loading_screen, fg_color="#821D1A", hover_color="#bf0600").grid(row=2, column=1, columnspan=2, pady=10, sticky="ew")

    def show_loading_screen(self):
        global events
        self.event = self.events_combobox.get()
        if not self.event:
            messagebox.showerror("Error", "Invalid event")
            return
        for i in range(0, len(self.events)):
            if self.event == self.events[i]["name"]:
                self.event_id = self.events[i]["id"]
        self.root.withdraw()

        self.loading_window = ctk.CTkToplevel(self.root)
        self.loading_window.protocol("WM_DELETE_WINDOW", self.on_close)
        self.loading_window.title("Vextracting...")
        self.loading_window.after(201, lambda :root.iconbitmap('icon.ico'))
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
        self.directory_window.after(201, lambda :root.iconbitmap('icon.ico'))

        self.center_toplevel(self.directory_window, 800, 600)

        self.directory_frame = ctk.CTkScrollableFrame(self.directory_window)
        self.directory_frame.pack(fill="both", expand=True, padx=10, pady=10)

        video_directory = self.client.team
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
            command = f"ffmpeg -i {video_path} -ss 00:00:01 -vframes 1 {thumbnail_path} -y"
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

if __name__ == "__main__":
    root = ctk.CTk()
    app = App(root)
    root.mainloop()



import yt_dlp
import re
import ctypes
import os
import sys
from src.ocr import OCR
from src.api import API

import shutil

class Client:
    def __init__(self, team, url, best_quality=False):
        self.url = url
        self.team = team
        self.app = None
        self.id = API.get_id(team)
        self.event = ""
        self.best_quality = best_quality

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            percent_str = d.get('_percent_str', '0%')
            clean_percent_str = re.sub(r'\x1b\[[0-9;]*[mK]', '', percent_str)
            self.app.progress_value = int(float(clean_percent_str.strip('%').replace(" ", "")))

    def download(self):
        zxt = self.url.strip()

        base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

        if self.best_quality:
            options = {
                'outtmpl': os.path.join(base_dir, f"{self.event}.%(ext)s"),
                'format': 'bestvideo+bestaudio',
                'merge_output_format': 'mp4',
                'progress_hooks': [self.progress_hook],
                'postprocessors': [
                    {
                        'key': 'FFmpegMetadata',
                    },
                    {
                        'key': 'FFmpegEmbedSubtitle',
                    },
                ],
                'postprocessor_args': [
                    '-ac', '2',
                    '-ar', '44100',
                ],
                'verbose': True,
                'no_mtime': True,
            }
        else:
            options = {
                'outtmpl': os.path.join(base_dir, f"{self.event}.%(ext)s"),
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
        
        folder_path = os.path.join(current_dir, self.event)
        mp4_path = os.path.join(current_dir, f"{self.event}.mp4")

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
                print(f"Folder '{self.event}' and its contents have been deleted.")
            except Exception as e:
                print(f"Failed to delete folder '{self.event}': {e}")
        else:
            print(f"Folder '{self.event}' not found.")

        if os.path.exists(mp4_path):
            try:
                os.remove(mp4_path)
                print(f"MP4 file '{self.event}.mp4' has been deleted.")
            except PermissionError:
                print(f"MP4 file '{self.event}.mp4' is locked. Attempting forced deletion.")
                force_delete(mp4_path)
        else:
            print(f"MP4 file '{self.event}.mp4' not found.")
    
    def get_matches(self, season, event):
        matches = API.get_matches(self.id, season, event)
        result = []
        for match in matches:
            if "Final" in match["name"]:
                result.append(f'FINALS {match["name"].replace("#", "")[-3]}'.replace(" ", ""))
            else:
                result.append(match["name"].replace("Qualifier", "QUAL").replace("#", "").replace(" ", ""))

        return result
import ctypes
import tempfile
import cv2
import numpy as np
import subprocess
import re
import pytesseract
import os

pytesseract.pytesseract.tesseract_cmd = 'bin\\Tesseract-OCR\\tesseract.exe'

class OCR:
    def __init__(self, client):
        from src.client import Client
        self.client = client
        self.video = f"{self.client.event}.mp4"
        self.run = True

        self.ocr = {}
        try:
            os.mkdir(self.client.event)
            print(f"Directory '{self.client.event}' created successfully.")
        except FileExistsError:
            pass
    
    def terminate(self):
        self.run = False

    def video_duration(self):

        ffprobe_cmd = [
            "bin\\ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            self.video
        ]
        try:
            result = subprocess.run(ffprobe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
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
            if not self.run:
                break
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
            "bin\\ffmpeg",
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
            process = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
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
            "bin\\ffmpeg",
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
            subprocess.run(ffmpeg_cmd, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
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
            ["bin\\ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "format=duration", "-of", "csv=p=0", input_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
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
                    "bin\\ffmpeg",
                    "-i", input_file,
                    "-c:v", "libx264",
                    "-b:v", f"{int(target_video_bitrate)}", 
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-y",
                    temp_output_file
                ]

                subprocess.run(ffmpeg_cmd, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
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
                os.mkdir(self.client.event)
                print(f"Directory '{self.client.event}' created successfully.")
            except FileExistsError:
                pass
            self.extract(low, high, f"{self.client.event}\\{item}.mp4")

            return low, high
        except KeyError:
            pass
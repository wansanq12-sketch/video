import os
import torch
import numpy as np
from hashlib import sha256
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import folder_paths
import requests
import hmac
import hashlib
import io

from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
from .video_padding import pad_mp4_frames
import subprocess

class VideoEncrypt:
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE", ),
                "encrypt": ("BOOLEAN", {"default": True}),
                "key": ("STRING", {"multiline": False, "default": ""}),
                "format": (["video/h264-mp4", "video/h265-mp4", "image/gif", "image/webp"], {"default": "video/h264-mp4"}),
                "fps": ("INT", {"default": 12, "min": 1, "max": 60}),
            },
            "optional": {
                "algorithm": (["AES-GCM", "AES-CBC"], {"default": "AES-GCM"}),
                "filename_prefix": ("STRING", {"default": "VideoCrypt"}),
                "subfolder": ("STRING", {"default": "", "description": "Subfolder for encrypted videos"}),
                "image_subfolder": ("STRING", {"default": "", "description": "Subfolder for encrypted images. If empty, uses the video subfolder."}),
                "pix_fmt": (["yuv420p", "yuv420p10le", "auto"], {"default": "auto"}),
                "crf": ("INT", {"default": 23, "min": 0, "max": 51}), # Constant Rate Factor for H.264/H.265, lower is better quality
                "preset": (["ultrafast", "superfast", "veryfast", "fast", "medium", "slow", "slower", "veryslow"], {"default": "medium"}),
                "metadata_enabled": ("BOOLEAN", {"default": True}),
                "audio": ("AUDIO",),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("encrypted_file_path",)
    FUNCTION = "encrypt_video"
    CATEGORY = "VideoCrypt"

    def encrypt_video(self, images: torch.Tensor, encrypt: bool, key: str, format: str, fps: int, algorithm: str = "AES-GCM", filename_prefix: str = "VideoCrypt", subfolder: str = "", image_subfolder: str = "", pix_fmt: str = "auto", crf: int = 23, preset: str = "medium", metadata_enabled: bool = True, audio=None):
        # Adjust filename prefix and subfolder for images
        final_prefix = filename_prefix
        output_subfolder = subfolder
        if format.startswith("image/"):
            if "Video" in final_prefix:
                final_prefix = final_prefix.replace("Video", "Image")
            if image_subfolder:
                output_subfolder = image_subfolder

        # Convert tensor to a list of numpy arrays
        image_list = [np.clip(255. * img.cpu().numpy(), 0, 255).astype(np.uint8) for img in images]
        image_list = pad_mp4_frames(image_list, format)

        # Create video/gif/webp from image sequence
        file_extension = format.split('/')[-1].split('-')[-1]
        temp_video_path = os.path.join(folder_paths.get_temp_directory(), f"temp_video_for_encryption.{file_extension}")
        
        clip = ImageSequenceClip(image_list, fps=fps)
        
        ffmpeg_params = []
        if format == "video/h264-mp4":
            if pix_fmt != "auto":
                ffmpeg_params.extend(['-pix_fmt', pix_fmt])
            ffmpeg_params.extend(['-crf', str(crf)])
            ffmpeg_params.extend(['-preset', preset])
            if not metadata_enabled:
                ffmpeg_params.extend(['-map_metadata', '-1'])
            clip.write_videofile(temp_video_path, codec="libx264", ffmpeg_params=ffmpeg_params)
        elif format == "video/h265-mp4":
            h265_pix_fmt = "yuv420p" if pix_fmt == "auto" else pix_fmt
            ffmpeg_params.extend(['-pix_fmt', h265_pix_fmt])
            ffmpeg_params.extend(['-crf', str(crf)])
            ffmpeg_params.extend(['-preset', preset])
            # Use the Apple-compatible HEVC sample entry in the MP4 container.
            ffmpeg_params.extend(['-tag:v', 'hvc1'])
            if not metadata_enabled:
                ffmpeg_params.extend(['-map_metadata', '-1'])
            clip.write_videofile(temp_video_path, codec="libx265", ffmpeg_params=ffmpeg_params)
        elif format == "image/gif":
            clip.write_gif(temp_video_path)
        elif format == "image/webp":
            # -loop 0 = infinite loop (default libwebp is -loop 1, plays once)
            webp_params = ['-preset', 'default', '-loop', '0']
            if not metadata_enabled:
                webp_params.extend(['-map_metadata', '-1'])
            clip.write_videofile(temp_video_path, codec="libwebp", ffmpeg_params=webp_params)

        # Mux audio into video if provided
        # Validate audio: skip if None, missing keys, or empty waveform
        if audio is not None:
            _valid_audio = False
            if isinstance(audio, dict) and 'waveform' in audio and 'sample_rate' in audio:
                _wf = audio['waveform']
                if _wf is not None and _wf.numel() > 0:
                    _valid_audio = True
            if not _valid_audio:
                print("### VideoCrypt: Audio input is empty or invalid (source video may have no audio stream), skipping audio mux.")
                audio = None

        if audio is not None and format in ("video/h264-mp4", "video/h265-mp4"):
            try:
                import imageio_ffmpeg
                ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                ffmpeg_path = "ffmpeg"

            waveform = audio['waveform']  # (1, channels, samples)
            sample_rate = audio['sample_rate']
            channels = waveform.size(1)
            audio_data = waveform.squeeze(0).transpose(0, 1).numpy().astype(np.float32).tobytes()

            temp_muxed_path = os.path.join(folder_paths.get_temp_directory(), f"temp_video_muxed.{file_extension}")
            mux_args = [
                ffmpeg_path, "-v", "error", "-y",
                "-i", temp_video_path,
                "-ar", str(sample_rate), "-ac", str(channels),
                "-f", "f32le", "-i", "-",
                "-c:v", "copy", "-c:a", "aac",
                "-shortest", temp_muxed_path
            ]
            process = subprocess.run(mux_args, input=audio_data, capture_output=True)
            if process.returncode == 0:
                os.replace(temp_muxed_path, temp_video_path)
            else:
                print(f"### VideoCrypt: Audio mux failed: {process.stderr.decode()}")
        elif audio is not None:
            print(f"### VideoCrypt: Audio is only supported for MP4 video formats, ignoring audio for {format}")

        output_dir = os.path.join(folder_paths.get_output_directory(), output_subfolder)
        os.makedirs(output_dir, exist_ok=True)

        # --- Bypass mode: save as normal video/gif/webp ---
        if not encrypt:
            ext_map = {"video/h264-mp4": ".mp4", "video/h265-mp4": ".mp4", "image/gif": ".gif", "image/webp": ".webp"}
            ext = ext_map.get(format, ".mp4")

            counter = 1
            while True:
                file_path_check = os.path.join(output_dir, f"{final_prefix}_{counter:05}{ext}")
                if not os.path.exists(file_path_check):
                    break
                counter += 1

            file = f"{final_prefix}_{counter:05}{ext}"
            output_file_path = os.path.join(output_dir, file)
            os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

            import shutil
            shutil.move(temp_video_path, output_file_path)

            file_result = {
                "filename": file,
                "subfolder": output_subfolder,
                "type": "output"
            }

            if format.startswith("image/"):
                ui_output = {"images": [file_result]}
            else:
                file_result["format"] = format
                file_result["frame_rate"] = fps
                file_result["fullpath"] = output_file_path
                ui_output = {"gifs": [file_result]}

            return {"ui": ui_output, "result": (output_file_path,)}

        # --- Encrypt mode ---
        if not key:
            raise ValueError("A key must be provided for encryption.")

        master_key = sha256(key.encode()).digest()
        
        counter = 1
        while True:
            file_path_check = os.path.join(output_dir, f"{final_prefix}_{counter:05}.bin")
            if not os.path.exists(file_path_check):
                break
            counter += 1

        # Read the temporary video file into bytes
        with open(temp_video_path, 'rb') as f:
            video_bytes = f.read()

        # Clean up the temporary video file
        os.remove(temp_video_path)

        video_format = file_extension.upper()
        format_header = video_format.ljust(16).encode('utf-8')
        data_to_encrypt = format_header + video_bytes

        salt = os.urandom(16)
        file_key = hmac.new(master_key, salt, hashlib.sha256).digest()
        algo_header = algorithm.ljust(16).encode('utf-8')

        file = f"{final_prefix}_{counter:05}.bin"
        encrypted_file_path = os.path.join(output_dir, file)
        os.makedirs(os.path.dirname(encrypted_file_path), exist_ok=True)

        with open(encrypted_file_path, 'wb') as f:
            f.write(algo_header)
            f.write(salt)
            
            if algorithm == "AES-CBC":
                cipher = AES.new(file_key, AES.MODE_CBC)
                encrypted_bytes = cipher.encrypt(pad(data_to_encrypt, AES.block_size))
                f.write(cipher.iv)
                f.write(encrypted_bytes)
            
            elif algorithm == "AES-GCM":
                cipher = AES.new(file_key, AES.MODE_GCM)
                encrypted_bytes, tag = cipher.encrypt_and_digest(data_to_encrypt)
                f.write(cipher.nonce)
                f.write(tag)
                f.write(encrypted_bytes)
        
        file_result = {
            "filename": file,
            "subfolder": output_subfolder,
            "type": "output"
        }

        if format.startswith("image/"):
            ui_output = {"images": [file_result]}
        else:
            file_result["format"] = format
            file_result["frame_rate"] = fps
            file_result["fullpath"] = encrypted_file_path
            ui_output = {"gifs": [file_result]}

        return {"ui": ui_output, "result": (encrypted_file_path,)}

class VideoDecryptShared:
    def _decrypt_content(self, encrypted_content, key, filename_prefix="decrypted_video"):
        master_key = sha256(key.encode()).digest()
        
        algo_header_bytes = encrypted_content[:16]
        salt = encrypted_content[16:32]
        encrypted_data_with_iv = encrypted_content[32:]
        
        algorithm = algo_header_bytes.strip().decode('utf-8')
        file_key = hmac.new(master_key, salt, hashlib.sha256).digest()
        
        decrypted_bytes = b''
        if algorithm == "AES-CBC":
            iv = encrypted_data_with_iv[:16]
            encrypted_data = encrypted_data_with_iv[16:]
            cipher = AES.new(file_key, AES.MODE_CBC, iv=iv)
            decrypted_bytes = unpad(cipher.decrypt(encrypted_data), AES.block_size)
        
        elif algorithm == "AES-GCM":
            nonce = encrypted_data_with_iv[:16]
            tag = encrypted_data_with_iv[16:32]
            encrypted_data = encrypted_data_with_iv[32:]
            cipher = AES.new(file_key, AES.MODE_GCM, nonce=nonce)
            decrypted_bytes = cipher.decrypt_and_verify(encrypted_data, tag)
        
        else:
            raise ValueError(f"Unknown or unsupported encryption algorithm: {algorithm}")

        format_header = decrypted_bytes[:16].strip().decode('utf-8')
        video_bytes = decrypted_bytes[16:]

        # Save decrypted video bytes to a temporary file
        temp_video_path = os.path.join(folder_paths.get_temp_directory(), f"{filename_prefix}.{format_header.lower()}")
        with open(temp_video_path, 'wb') as f:
            f.write(video_bytes)
        
        # ComfyUI expects a video path for playback
        return (temp_video_path,)

class VideoDecryptFromFile(VideoDecryptShared):
    @classmethod
    def INPUT_TYPES(s):
        input_dir = folder_paths.get_input_directory()
        output_dir = folder_paths.get_output_directory()
        
        files = []
        for dir_path, dir_name in [(input_dir, 'input'), (output_dir, 'output')]:
            if not os.path.exists(dir_path):
                continue
            for root, _, filenames in os.walk(dir_path):
                for filename in filenames:
                    if filename.endswith('.bin'):
                        relative_path = os.path.relpath(os.path.join(root, filename), dir_path)
                        files.append(os.path.join(dir_name, relative_path))

        if not files:
            files.append("No files found")
        return {
            "required": {
                "encrypted_file": (sorted(files), ),
                "key": ("STRING", {"multiline": False, "default": ""}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_path",)
    FUNCTION = "decrypt_video"
    CATEGORY = "VideoCrypt"

    def decrypt_video(self, key: str, encrypted_file: str):
        if not key:
            raise ValueError("A key must be provided for decryption.")

        base_dir = os.path.dirname(folder_paths.get_input_directory())
        path_to_decrypt = os.path.join(base_dir, encrypted_file)

        if not os.path.exists(path_to_decrypt):
            raise FileNotFoundError(f"Encrypted file not found: {path_to_decrypt}")
        
        with open(path_to_decrypt, 'rb') as f:
            encrypted_content = f.read()
        
        filename_prefix = os.path.splitext(os.path.basename(encrypted_file))[0]
        return self._decrypt_content(encrypted_content, key, filename_prefix)

class VideoDecryptFromPath(VideoDecryptShared):
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "url_or_path": ("STRING", {"multiline": False, "default": ""}),
                "key": ("STRING", {"multiline": False, "default": ""}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_path",)
    FUNCTION = "decrypt_video"
    CATEGORY = "VideoCrypt"

    def decrypt_video(self, key: str, url_or_path: str):
        if not key:
            raise ValueError("A key must be provided for decryption.")

        path_to_decrypt = url_or_path.strip()
        if not path_to_decrypt:
            raise ValueError("URL/Path cannot be empty.")

        encrypted_content = b''
        filename_prefix = "decrypted_video"
        if path_to_decrypt.startswith("http://") or path_to_decrypt.startswith("https://"):
            try:
                response = requests.get(path_to_decrypt)
                response.raise_for_status()
                encrypted_content = response.content
                filename_prefix = os.urandom(8).hex() # Generate a random 16-char hex string
            except Exception as e:
                raise RuntimeError(f"Failed to fetch from URL: {e}")
        else:
            if not os.path.exists(path_to_decrypt):
                raise FileNotFoundError(f"Encrypted file not found: {path_to_decrypt}")
            with open(path_to_decrypt, 'rb') as f:
                encrypted_content = f.read()
            filename_prefix = os.path.splitext(os.path.basename(path_to_decrypt))[0]
        
        return self._decrypt_content(encrypted_content, key, filename_prefix)

class VideoDecryptBatch(VideoDecryptShared):
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "directory": ("STRING", {"multiline": False, "default": ""}),
                "key": ("STRING", {"multiline": False, "default": ""}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("decrypted_video_paths",)
    FUNCTION = "decrypt_batch"
    CATEGORY = "VideoCrypt"

    def decrypt_batch(self, key: str, directory: str):
        if not key:
            raise ValueError("A key must be provided for decryption.")
        
        if not os.path.isdir(directory):
            raise FileNotFoundError(f"Directory not found: {directory}")

        decrypted_video_paths = []
        for f_name in sorted(os.listdir(directory)):
            if f_name.endswith('.bin'):
                f_path = os.path.join(directory, f_name)
                with open(f_path, 'rb') as f:
                    encrypted_content = f.read()
                
                try:
                    filename_prefix = os.path.splitext(f_name)[0]
                    decrypted_video_path = self._decrypt_content(encrypted_content, key, filename_prefix)
                    decrypted_video_paths.append(decrypted_video_path[0]) # _decrypt_content returns a tuple
                except Exception as e:
                    print(f"### VideoCrypt: Failed to decrypt {f_name}, skipping. Error: {e}")

        if not decrypted_video_paths:
            return ([],)

        return (decrypted_video_paths,)

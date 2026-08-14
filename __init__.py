"""
@author: musk
@title: VideoCrypt
@nickname: VideoCrypt
@description: This extension provides nodes for encrypting and decrypting videos within ComfyUI.
"""

# Reference: https://github.com/comfyanonymous/ComfyUI_examples/blob/master/custom_nodes/example_node.py

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

try:
    from .video_crypt import VideoEncrypt, VideoDecryptFromFile, VideoDecryptFromPath, VideoDecryptBatch

    NODE_CLASS_MAPPINGS.update({
        "VideoEncrypt": VideoEncrypt,
        "VideoDecryptFromFile": VideoDecryptFromFile,
        "VideoDecryptFromPath": VideoDecryptFromPath,
        "VideoDecryptBatch": VideoDecryptBatch,
    })

    NODE_DISPLAY_NAME_MAPPINGS.update({
        "VideoEncrypt": "Video Encrypt",
        "VideoDecryptFromFile": "Video Decrypt (File)",
        "VideoDecryptFromPath": "Video Decrypt (Path/URL)",
        "VideoDecryptBatch": "Video Decrypt (Batch)",
    })

    print("### VideoCrypt: Loaded")
except ImportError as e:
    print(f"### VideoCrypt: Import failed with error: {e}")
    print("### VideoCrypt: Please check your environment and dependencies.")


__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
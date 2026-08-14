import numpy as np


MP4_VIDEO_FORMATS = {
    "video/h264-mp4",
    "video/h265-mp4",
}


def pad_mp4_frames(frames, output_format, alignment=2):
    if output_format not in MP4_VIDEO_FORMATS or not frames:
        return frames

    height, width = frames[0].shape[:2]
    pad_width = (-width) % alignment
    pad_height = (-height) % alignment
    if pad_width == 0 and pad_height == 0:
        return frames

    left = pad_width // 2
    right = pad_width - left
    top = pad_height // 2
    bottom = pad_height - top
    padding = ((top, bottom), (left, right), (0, 0))

    for index, frame in enumerate(frames):
        frames[index] = np.pad(frame, padding, mode="edge")

    padded_width = width + pad_width
    padded_height = height + pad_height
    print(
        "### VideoCrypt: Padded video frames from "
        f"{width}x{height} to {padded_width}x{padded_height} "
        "for codec compatibility."
    )
    return frames

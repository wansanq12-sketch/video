# ComfyUI-VideoCrypt

这个 ComfyUI 自定义节点提供了对图像序列和视频文件的加密与解密功能。

## 主要特性

*   **加密**: 将图像序列打包成视频或动图（MP4, GIF, WebP），并使用 AES-256 加密。
*   **解密**: 支持从文件、URL 或本地路径解密，并能批量处理整个文件夹。
*   **高度可配置**: 为 H.264/H.265 视频提供高级编码选项（CRF, Preset, Pixel Format）。
*   **智能文件管理**:
    *   自动区分图片和视频，使用不同的文件名前缀（`ImageCrypt_`, `VideoCrypt_`）。
    *   支持将加密后的图片和视频保存到不同的子目录。
    *   解密后的文件具有唯一的、可追溯的文件名。

## 安装

1.  导航到你的 `ComfyUI/custom_nodes` 目录。
2.  克隆此仓库：
    ```bash
    git clone https://gitlab.aiaipool.com/ai_accelerate/comfyui-videocrypt.git
    ```
3.  进入 `comfyui-videocrypt` 目录：
    ```bash
    cd comfyui-videocrypt
    ```
4.  安装所需的 Python 包：
    ```bash
    pip install -r requirements.txt
    ```
5.  重启 ComfyUI。

> H.265/HEVC 输出需要 ComfyUI 实际使用的 FFmpeg 包含 `libx265` 编码器。

## 提供的节点

### Video Encrypt (视频/图片加密)

将一系列图像合并成视频或动图，然后使用提供的密钥和算法对其进行加密。

**输入节点：**

*   `images` (IMAGE): 要合并的图像序列。
*   `key` (STRING): 用于加密的密钥。
*   `format` (DROPDOWN): 输出格式 (`video/h264-mp4`, `video/h265-mp4`, `image/gif`, `image/webp`)。默认值: `video/h264-mp4`。
*   `fps` (INT): 帧率。默认值: 12。
*   `algorithm` (DROPDOWN): 加密算法 (`AES-GCM`, `AES-CBC`)。`AES-GCM` 更安全，推荐使用。默认值: `AES-GCM`。
*   `filename_prefix` (STRING): 输出加密文件的前缀。如果选择图片格式，`Video` 会被自动替换为 `Image`。默认值: `VideoCrypt`。
*   `subfolder` (STRING): 用于保存**视频**的子文件夹（在 ComfyUI 的 `output` 目录下）。
*   `image_subfolder` (STRING): 用于保存**图片**（GIF/WebP）的子文件夹。如果留空，则使用 `subfolder` 的设置。
*   `pix_fmt` (DROPDOWN): H.264/H.265 的像素格式，影响颜色编码和兼容性。默认值: `auto`；H.265 使用 `auto` 时会输出兼容性更好的 `yuv420p`。
*   `crf` (INT): **恒定速率因子 (CRF)**，用于 H.264/H.265 视频。这是控制视频质量和大小的关键参数。**值越高，文件越小，但质量越低**。默认值 23 是一个很好的平衡点。建议范围 18-28。H.264 和 H.265 的 CRF 数值不能直接按相同画质比较。
*   `preset` (DROPDOWN): H.264/H.265 的编码速度预设。速度越快，压缩率越低。`medium` 是一个很好的平衡。
*   `metadata_enabled` (BOOLEAN): 是否在视频中保留元数据。默认值: `True`。

**输出：**

*   节点界面会直接显示加密后 `.bin` 文件的相对路径。

### Video Decrypt (File) (解密 - 文件)

从 ComfyUI 的 `input` 或 `output` 目录中选择一个加密文件 (`.bin`) 进行解密。

**输入节点：**

*   `encrypted_file` (DROPDOWN): 选择一个加密的 `.bin` 文件。
*   `key` (STRING): 用于解密的密钥。

**输出：**

*   `video_path` (STRING): 解密后的文件的路径。文件保存在 `temp` 目录中，会被自动清理。

### Video Decrypt (Path/URL) (解密 - 路径/URL)

从给定的绝对路径或 URL 解密一个加密文件。

**输入节点：**

*   `url_or_path` (STRING): 加密的 `.bin` 文件的绝对路径或 URL。
*   `key` (STRING): 解密密钥。

**输出：**

*   `video_path` (STRING): 解密后的文件的路径。文件保存在 `temp` 目录中，会被自动清理。

### Video Decrypt (Batch) (解密 - 批量)

解密指定目录中的所有 `.bin` 文件。

**输入节点：**

*   `directory` (STRING): 包含加密 `.bin` 文件的目录的绝对路径。
*   `key` (STRING): 解密密钥。

**输出：**

*   `decrypted_video_paths` (STRING): 所有解密后的文件路径的列表。文件保存在 `temp` 目录中，会被自动清理。

## 使用方法

1.  将 **Video Encrypt** 节点添加到你的工作流中。
2.  连接图像序列，并设置加密密钥、格式等参数。
3.  运行工作流，将在 `output` 目录中得到加密的 `.bin` 文件。
4.  要解密，请使用其中一个 **Video Decrypt** 节点，提供加密文件和相同的密钥。
5.  解密后的文件将临时保存在 `temp` 目录中，其路径可用于连接到预览节点或其他后续节点。

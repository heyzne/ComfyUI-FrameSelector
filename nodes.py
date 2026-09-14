"""Nodes:
- VideoFrameExtractor : decode EVERY frame of a video file into an IMAGE batch.
- FrameSelector       : pause the run, let the user pick images, continue with them.
"""

import io
import os
import shutil
import tempfile

import numpy as np
import torch
from PIL import Image
from server import PromptServer

from . import server as fs_server

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None


def _frame_to_jpeg(tensor_hw3: torch.Tensor, quality: int = 85) -> bytes:
    arr = (tensor_hw3.detach().cpu().clamp(0, 1).numpy() * 255.0).round().astype("uint8")
    if arr.ndim == 3 and arr.shape[2] == 4:
        arr = arr[..., :3]
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


class VideoFrameExtractor:
    """Read a video file and return every frame (optionally sub-sampled) as an IMAGE batch."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video": ("STRING", {
                    "default": "",
                    "placeholder": "absolute path to video, e.g. D:/videos/clip.mp4",
                }),
            },
            "optional": {
                "force_rate": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 120.0, "step": 1.0,
                                         "tooltip": "target fps, 0 = keep source fps"}),
                "skip_first_frames": ("INT", {"default": 0, "min": 0, "max": 10_000_000}),
                "select_every_nth": ("INT", {"default": 1, "min": 1, "max": 10_000}),
                "max_frames": ("INT", {"default": 0, "min": 0, "max": 10_000_000,
                                       "tooltip": "0 = all frames"}),
                "width": ("INT", {"default": 0, "min": 0, "max": 8192, "step": 2,
                                  "tooltip": "0 = keep original width"}),
                "height": ("INT", {"default": 0, "min": 0, "max": 8192, "step": 2,
                                   "tooltip": "0 = keep original height"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "INT", "FLOAT")
    RETURN_NAMES = ("images", "frame_count", "fps")
    FUNCTION = "extract"
    CATEGORY = "FrameSelector"
    DESCRIPTION = "Extract every frame from a video file into an IMAGE batch."

    def extract(self, video, force_rate=0.0, skip_first_frames=0, select_every_nth=1,
                max_frames=0, width=0, height=0):
        if cv2 is None:
            raise RuntimeError(
                "opencv-python is required by ComfyUI-FrameSelector. "
                "Run: pip install -r requirements.txt inside your ComfyUI environment.")

        video = (video or "").strip().strip('"').strip("'")
        if not video or not os.path.isfile(video):
            raise ValueError(f"Video file not found: {video!r}")

        tmp = None
        cap = cv2.VideoCapture(video)
        if not cap.isOpened():
            # Windows + non-ascii (e.g. Chinese) path fallback: copy to ascii temp name
            fd, tmp = tempfile.mkstemp(suffix=".mp4", prefix="fs_")
            os.close(fd)
            shutil.copyfile(video, tmp)
            cap = cv2.VideoCapture(tmp)
        if not cap.isOpened():
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
            raise ValueError(f"Cannot open video: {video!r}")

        src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        if src_fps <= 0:
            src_fps = 24.0

        rate_step = max(1, round(src_fps / float(force_rate))) if force_rate and force_rate > 0 else 1
        step = rate_step * max(1, int(select_every_nth))

        frames = []
        idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if idx >= skip_first_frames and (idx - skip_first_frames) % step == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                if width > 0 or height > 0:
                    h, w = rgb.shape[:2]
                    tw, th = int(width), int(height)
                    if tw <= 0:
                        tw = max(2, int(round(w * (th / h))))
                    if th <= 0:
                        th = max(2, int(round(h * (tw / w))))
                    rgb = cv2.resize(rgb, (tw, th), interpolation=cv2.INTER_AREA)
                frames.append(rgb)
                if max_frames and len(frames) >= max_frames:
                    idx += 1
                    break
            idx += 1
        cap.release()
        if tmp and os.path.exists(tmp):
            os.remove(tmp)

        if not frames:
            raise ValueError(f"No frames could be decoded from {video!r}")

        batch = np.ascontiguousarray(np.stack(frames), dtype=np.float32) / 255.0
        return (torch.from_numpy(batch), len(frames), src_fps)


class FrameSelector:
    """Pause the workflow and let the user choose which images continue."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "mode": (["Always Pause", "Pause If Multiple", "Never Pause"],
                         {"default": "Always Pause"}),
                "preview_rescale": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 8.0, "step": 0.05,
                                               "tooltip": "thumbnail size scale in the dialog"}),
            },
            "optional": {
                "timeout": ("INT", {"default": 0, "min": 0, "max": 86400,
                                    "tooltip": "seconds to wait for the user, 0 = wait forever"}),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("IMAGE", "INT")
    RETURN_NAMES = ("images", "count")
    FUNCTION = "select"
    CATEGORY = "FrameSelector"
    DESCRIPTION = ("Pause the workflow here, show every input image in a web dialog "
                   "and continue only with the images the user selected.")

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")  # always re-execute so the pause happens on every run

    def select(self, images, mode, preview_rescale, timeout=0, unique_id=None):
        n = int(images.shape[0])
        if mode == "Never Pause" or (mode == "Pause If Multiple" and n <= 1):
            return (images, n)

        node_id = str(unique_id)
        session = fs_server.begin_session(node_id)
        try:
            session.previews = [_frame_to_jpeg(images[i]) for i in range(n)]
            session.count = n
            session.ready = True

            PromptServer.instance.send_sync(
                "frame_selector_wait", {"node_id": node_id, "count": n})

            wait_s = float(timeout) if timeout and timeout > 0 else None
            if not session.event.wait(wait_s):
                raise RuntimeError(
                    f"FrameSelector #{node_id}: timed out after {timeout}s waiting for selection.")

            if session.result == fs_server.CANCEL:
                from comfy.model_management import InterruptProcessingException
                raise InterruptProcessingException()

            idx = sorted({int(i) for i in (session.result or []) if 0 <= int(i) < n})
            if not idx:  # safety net: empty selection passes everything through
                idx = list(range(n))
            return (images[idx], len(idx))
        finally:
            fs_server.end_session(node_id)


NODE_CLASS_MAPPINGS = {
    "VideoFrameExtractor": VideoFrameExtractor,
    "FrameSelector": FrameSelector,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoFrameExtractor": "Video Frame Extractor",
    "FrameSelector": "Image Selector",
}
"""Video → frames, so a short clip can stand in for "one or two photos".

The user's reasoning: a couple of stills are not enough to see the whole area. So a
clip is sampled into a handful of frames, and **those frames are ordinary photos** —
they go through the exact same path (`photo_paths` → `analyze` vision → `persist`),
which means the privacy consent gate, the photo dedupe, `entry.photos` and the
`observes_skin or vision_used` gate all apply unchanged. The agent never needs to know
it was a video.

Caps are a user decision (2026-09): **≤ 60 s, ≤ 100 MB, at most 6 frames**. Six frames
in one `structured_vision` call is one API request, so cost stays predictable.

## Why frames are de-duplicated

Near-identical frames buy nothing and cost vision tokens. Frames whose 32×32 greyscale
thumbnails differ by less than `DEDUPE_THRESHOLD` (mean absolute difference, 0–255) are
dropped, and the kept frames are spread across the clip so a slow pan does not collapse
into one frame. When de-duplication would leave fewer than `MIN_FRAMES`, the most
different candidates are restored — never returning nothing for a valid video.

## Decoding — why this takes a *path*, not bytes

`imageio` + `imageio-ffmpeg`. The ffmpeg binary ships **inside the wheel**, so there is
no system ffmpeg to install (this machine has none) and Docker needs nothing extra.
OpenCV was rejected: its ~50 MB wheel would buy face detection this feature deliberately
does not do yet (see `docs/product-eval-plan.md`).

The ffmpeg plugin **cannot read a `BytesIO`** — it spawns ffmpeg as a subprocess and
hands it a filename. So the clip is written to disk first and decoded from there. That
is not a workaround: "store the video locally" is a product requirement anyway, and it
happens to be what the decoder needs. Callers must therefore pass a real path.
"""
from __future__ import annotations

import io
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image

from .config import settings
from .photo import compress_image

import logging

logger = logging.getLogger(__name__)

#: User-facing text for a container ffmpeg cannot open. Deliberately short: the raw
#: `imageio_ffmpeg` exception embeds ffmpeg's **entire stdout banner** (build flags,
#: every library version, the local file path), and the upload route puts this string
#: straight into the HTTP `detail`, which the UI renders verbatim in the composer —
#: measured: a 15-byte text file uploaded as `.mp4` produced a ~1.6 KB wall of
#: "ffmpeg version 7.1 … --enable-libx265 …" in the user's face. The full text goes to
#: the log instead.
UNREADABLE_CLIP = "讀唔到呢個檔案，佢似乎唔係一段睇得到嘅影片（支援手機拍嘅 mp4／mov，最長 20 秒）。"

# Re-exported so callers can size-check before touching the disk.

import re

# Video ids are uuid4 hex from the upload route; the shape check keeps arbitrary
# paths out of the filesystem lookup (same policy as photo.py).
_VIDEO_ID = re.compile(r"^[0-9a-f]{32}$")

#: 20 s (a user decision, tightened from 30). With `MAX_FRAMES = 6` that is roughly one
#: frame every 3.3 s at the maximum length, and denser for shorter clips — the sampling
#: is "evenly spread, capped at 6" rather than a fixed grid, and the cap is on frames
#: sent to the model, not on how finely we look.
MAX_SECONDS = 20.0

#: Upload ceiling (a user decision, reinstated after a round of "no limit").
#:
#: The number is chosen from arithmetic that can be checked rather than from a quoted
#: "typical size": **100 MB over the 20 s cap is 40 Mbps**, which is far above what
#: 1080p30 needs (H.264 High ~12–17 Mbps, HEVC ~8–12 Mbps). A clip that trips it is
#: therefore almost always 4K or a high frame rate — and the error message says so,
#: instead of quoting a "typical MB" figure that this project has not measured.
MAX_BYTES = 100 * 1024 * 1024

#: Above this the clip is re-encoded down before it is kept — see `compress_video`.
#: 20 s of 1080p is a few tens of MB, so ordinary footage is stored as-is; 4K is shrunk.
COMPRESS_OVER_BYTES = 40 * 1024 * 1024

#: Longest edge after re-encoding. The vision model sees <=1024px photos anyway
#: (`photo.MAX_DIM`), so a bigger frame buys nothing.
COMPRESS_MAX_DIM = 1280
COMPRESS_CRF = 26
MAX_FRAMES = 6
MIN_FRAMES = 1

#: Mean absolute difference between 32×32 greyscale thumbnails, 0–255 scale.
DEDUPE_THRESHOLD = 6.0

#: Thumbnail size used only for the difference test (cheap, and blur-tolerant).
_THUMB = 32


class VideoError(Exception):
    """Base class so the route can map decode/cap failures to a clear status."""


class VideoTooLong(VideoError):
    pass


class VideoTooLarge(VideoError):
    pass


class VideoDecodeError(VideoError):
    pass


class VideoCompressError(VideoError):
    pass


@dataclass
class Extraction:
    frames: list[bytes] = field(default_factory=list)  # JPEG bytes, ready for save_photo
    timestamps: list[float] = field(default_factory=list)
    duration: float = 0.0
    sampled: int = 0  # how many candidate positions we looked at
    dropped: int = 0  # candidates thrown away as duplicates
    width: int = 0
    height: int = 0
    fps: float = 0.0

    @property
    def n_frames(self) -> int:
        return len(self.frames)


def _thumb(frame: np.ndarray) -> np.ndarray:
    img = Image.fromarray(frame).convert("L").resize((_THUMB, _THUMB))
    return np.asarray(img, dtype=np.float32)


def _diff(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(a - b).mean())


def _meta(reader) -> tuple[float, float, int, int]:
    """(duration_seconds, fps, width, height) — tolerant of missing metadata."""
    try:
        meta = reader.get_meta_data()
    except Exception:  # ffmpeg could not report; treat as unknown rather than fail
        meta = {}
    fps = float(meta.get("fps") or 0.0)
    duration = float(meta.get("duration") or 0.0)
    size = meta.get("size") or (0, 0)
    width, height = (int(size[0]), int(size[1])) if len(size) == 2 else (0, 0)
    return duration, fps, width, height


def extract_frames(path: str | Path, *, max_frames: int = MAX_FRAMES) -> Extraction:
    """Sample a clip on disk into at most `max_frames` de-duplicated JPEG frames.

    `path` must be a real file — see the module docstring. Raises `VideoTooLong`
    during decoding and `VideoDecodeError` if ffmpeg cannot read it; never returns an
    empty list for a video that decoded successfully.
    """
    try:
        reader = imageio.get_reader(str(path), format="ffmpeg")
    except Exception as e:  # ffmpeg missing / unreadable container
        logger.warning("video decode failed for %s: %s: %s", path, type(e).__name__, e)
        raise VideoDecodeError(UNREADABLE_CLIP) from e

    try:
        duration, fps, width, height = _meta(reader)
        if duration > MAX_SECONDS:
            raise VideoTooLong(f"{duration:.1f} 秒超過 {MAX_SECONDS:.0f} 秒上限")

        # Candidate positions. `nframes` is often missing or wrong for VFR clips, so
        # fall back to fps × duration, and to a fixed count if even that is unknown.
        try:
            nframes = int(reader.count_frames())
        except Exception:
            nframes = int(fps * duration) if fps and duration else 0
        if nframes <= 0:
            nframes = max_frames
        # Look at more positions than we keep, so de-duplication has room to work.
        candidates = min(max(nframes, 1), max_frames * 4)
        if candidates <= 1:
            indices = [0]
        else:
            step = (nframes - 1) / (candidates - 1)
            indices = [int(round(i * step)) for i in range(candidates)]
        indices = sorted(set(i for i in indices if 0 <= i < max(nframes, 1)))

        result = Extraction(duration=duration, fps=fps, width=width, height=height)
        kept_thumbs: list[np.ndarray] = []
        kept_meta: list[tuple[float, bytes]] = []
        all_thumbs: list[tuple[np.ndarray, bytes, float]] = []

        for idx in indices:
            try:
                frame = reader.get_data(idx)
            except Exception:
                continue
            result.sampled += 1
            thumb = _thumb(frame)
            all_thumbs.append((thumb, _to_jpeg(frame), (idx / fps) if fps else float(idx)))
            # Keep it only if it differs from every frame already kept.
            if all(_diff(thumb, k) >= DEDUPE_THRESHOLD for k in kept_thumbs):
                kept_thumbs.append(thumb)
                kept_meta.append((all_thumbs[-1][2], all_thumbs[-1][1]))

        # Too few survivors (a near-static clip): restore the most different candidates
        # so a valid video never comes back with no frames at all.
        if len(kept_meta) < MIN_FRAMES and all_thumbs:
            kept_meta = [(all_thumbs[0][2], all_thumbs[0][1])]
            if len(all_thumbs) > 1:
                kept_meta.append((all_thumbs[-1][2], all_thumbs[-1][1]))

        # Spread the kept frames across the clip. Taking the first `max_frames` of the
        # survivors biased everything to the start (a 3 s clip returned frames from
        # 0.0–1.3 s only) — which is exactly wrong for the use case: the user pans the
        # camera across their face, so the later frames are different parts of it.
        if len(kept_meta) > max_frames:
            span = len(kept_meta) - 1
            picks = sorted({round(i * span / (max_frames - 1)) for i in range(max_frames)})
            kept_meta = [kept_meta[i] for i in picks]

        result.dropped = max(0, result.sampled - len(kept_meta))
        result.frames = [jpeg for _, jpeg in kept_meta]
        result.timestamps = [round(t, 2) for t, _ in kept_meta]
        if not result.frames:
            raise VideoDecodeError("解唔到任何一格（段片可能係空或者損壞）")
        return result
    finally:
        try:
            reader.close()
        except Exception:  # noqa: BLE001 — closing must never mask the real error
            pass


def _to_jpeg(frame: np.ndarray) -> bytes:
    """Encode one decoded frame as a JPEG, using the same compression as photos."""
    img = Image.fromarray(frame)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return compress_image(buf.getvalue())


def compress_video(path: str | Path) -> tuple[Path, int, int]:
    """Re-encode an oversized clip in place-ish, returning (new_path, before, after).

    **No size limit is imposed on the user** — a phone produces what it produces. When
    the clip is bigger than `COMPRESS_OVER_BYTES` it is re-encoded instead:

    * scaled so the longest edge is `COMPRESS_MAX_DIM` — the vision model only ever sees
      photos capped at `photo.MAX_DIM` (1024 px), so a larger frame buys nothing;
    * CRF `COMPRESS_CRF` (lossy but generous);
    * **audio dropped** (`-an`). The app never analyses audio, so keeping it would be
      storing a recording of the user's voice for no purpose — this is a privacy win as
      well as a size one.

    The original is deleted on success, so the data dir keeps one copy. A failure here
    is never fatal: the caller keeps the original and reports it.

    Deliberately writes next to the source and deletes the source, mirroring
    `photo.save_photo`, which also stores an already-compressed image rather than the
    raw upload.
    """
    src = Path(path)
    before = src.stat().st_size
    if before <= COMPRESS_OVER_BYTES:
        return src, before, before

    exe = _ffmpeg_exe()
    out = src.with_name(f"{src.stem}.c{src.suffix}")
    cmd = [
        exe, "-y", "-loglevel", "error",
        "-i", str(src),
        "-vf", f"scale='min({COMPRESS_MAX_DIM},iw)':-2",
        "-c:v", "libx264", "-crf", str(COMPRESS_CRF), "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-an",  # no audio: never analysed, and a voice recording has no business here
        "-movflags", "+faststart",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        out.unlink(missing_ok=True)
        raise VideoCompressError(
            f"壓縮失敗（ffmpeg exit {proc.returncode}）：{proc.stderr.decode(errors='replace')[:200]}"
        )
    after = out.stat().st_size
    if after >= before:  # re-encoding made it bigger — not worth keeping
        out.unlink(missing_ok=True)
        return src, before, before
    src.unlink(missing_ok=True)
    return out, before, after


def _ffmpeg_exe() -> str:
    """The ffmpeg binary that ships inside the `imageio-ffmpeg` wheel.

    Using it directly (rather than through imageio's reader) is what lets us re-encode;
    there is no system ffmpeg to rely on.
    """
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def probe(path: str | Path) -> Extraction:
    """Metadata only — same caps, no frame decoding."""
    try:
        reader = imageio.get_reader(str(path), format="ffmpeg")
    except Exception as e:
        logger.warning("video probe failed for %s: %s: %s", path, type(e).__name__, e)
        raise VideoDecodeError(UNREADABLE_CLIP) from e
    try:
        duration, fps, width, height = _meta(reader)
        if duration > MAX_SECONDS:
            raise VideoTooLong(f"{duration:.1f} 秒超過 {MAX_SECONDS:.0f} 秒上限")
        return Extraction(duration=duration, fps=fps, width=width, height=height)
    finally:
        try:
            reader.close()
        except Exception:  # noqa: BLE001
            pass


# Container suffixes we accept. ffmpeg sniffs by content, so the suffix is for the
# user's benefit (and for the export zip), not for decoding.
_ALLOWED_SUFFIX = (".mp4", ".mov", ".m4v", ".webm")


def check_size(nbytes: int) -> None:
    """Ceiling on what the user may upload.

    The message deliberately names the limit and the likely cause rather than a
    "typical MB" figure: the honest, checkable statement is that 100 MB over 20 s is
    40 Mbps, so a rejected clip is almost certainly 4K or high-frame-rate.
    """
    if nbytes > MAX_BYTES:
        raise VideoTooLarge(
            f"段片 {nbytes / 1e6:.0f} MB，超過 {MAX_BYTES // (1024 * 1024)} MB 上限"
            "（20 秒上限約等於 40 Mbps，一般 1080p 唔會咁大）。"
            "可以喺相機設定改返 1080p／30fps，或者剪短啲再上載。"
        )


def video_path(video_id: str, suffix: str = ".mp4") -> Path:
    """Where a clip with this id lives — without writing anything.

    The upload route needs the destination before it has the bytes (it streams them),
    so path computation and writing are separate.
    """
    if suffix.lower() not in _ALLOWED_SUFFIX:
        suffix = ".mp4"
    return Path(settings.data_dir) / "videos" / f"{video_id}{suffix.lower()}"


def save_video(video_id: str, data: bytes, suffix: str = ".mp4") -> str:
    """Persist the raw clip and return its path relative to the data dir.

    The original is kept (a user requirement) — and the decoder needs a real file
    anyway, so it is written before any frame is read.
    """
    path = video_path(video_id, suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path.relative_to(settings.data_dir))


def _clip_candidates(video_id: str) -> list[Path]:
    """Every spelling a clip with this id could have on disk.

    `compress_video` writes `<id>.c<ext>` and then deletes the original, so a clip that
    was re-encoded is **not** at `<id>.<ext>`. Looking only at the plain name (as an
    earlier version did) meant a compressed clip could not be found — so it could not be
    deleted either, and `DELETE /api/videos/<id>` silently reported nothing to remove.
    """
    videos_dir = Path(settings.data_dir) / "videos"
    plain = [videos_dir / f"{video_id}{s}" for s in _ALLOWED_SUFFIX]
    compressed = [videos_dir / f"{video_id}.c{s}" for s in _ALLOWED_SUFFIX]
    return plain + compressed


def video_file(video_id: str) -> Path | None:
    """Path of a stored clip (id-shape checked), or None."""
    if not _VIDEO_ID.match(video_id):
        return None
    for p in _clip_candidates(video_id):
        if p.exists():
            return p
    return None


def delete_video(video_id: str) -> bool:
    """Remove every stored file for this clip id; True if anything was removed."""
    if not _VIDEO_ID.match(video_id):
        return False
    removed = False
    for p in _clip_candidates(video_id):
        if p.exists():
            p.unlink(missing_ok=True)
            removed = True
    return removed

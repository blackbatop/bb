import ctypes
import time
import pyray as rl
from PIL import Image
from pathlib import Path
from typing import Optional, Union
from importlib.resources import files, as_file


class GifPlayer:
  """Plays a GIF animation as Raylib textures, one frame at a time."""

  def __init__(self, gif_path: str, size: int = 0):
    self._frames: list[rl.Texture] = []
    self._frame_count: int = 0
    self._current_frame: int = 0
    self._frame_delay: float = 0.05  # seconds per frame
    self._last_tick: float = 0.0
    self._playing: bool = False
    self._loaded: bool = False
    self._gif_path = gif_path
    self._size = size

  def _ensure_loaded(self):
    if self._loaded:
      return
    self._loaded = True

    path = Path(self._gif_path)
    if not path.exists():
      return

    try:
      img = Image.open(path)
    except Exception:
      return

    if getattr(img, "n_frames", 1) > 1:
      # GIF with multiple frames
      total_ms = 0
      for i in range(img.n_frames):
        img.seek(i)
        frame = img.convert("RGBA")
        if self._size > 0 and frame.size != (self._size, self._size):
          frame = frame.resize((self._size, self._size), Image.LANCZOS)
        self._frames.append(self._make_texture(frame))
        total_ms += img.info.get("duration", 50)
      self._frame_delay = max(0.02, total_ms / (img.n_frames * 1000.0))
    else:
      # Static image
      frame = img.convert("RGBA")
      if self._size > 0 and frame.size != (self._size, self._size):
        frame = frame.resize((self._size, self._size), Image.LANCZOS)
      self._frames.append(self._make_texture(frame))
      self._frame_delay = 0.05

    self._frame_count = len(self._frames)

  @staticmethod
  def _make_texture(pil_img: Image.Image) -> rl.Texture:
    raw = pil_img.tobytes("raw", "RGBA")
    data = (ctypes.c_uint8 * len(raw)).from_buffer_copy(raw)
    img = rl.Image(
      rl.ffi.from_buffer(data),
      pil_img.width,
      pil_img.height,
      1,
      rl.PixelFormat.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8,
    )
    tex = rl.load_texture_from_image(img)
    rl.set_texture_filter(tex, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)
    rl.set_texture_wrap(tex, rl.TextureWrap.TEXTURE_WRAP_CLAMP)
    return tex

  def play(self):
    self._ensure_loaded()
    if self._frame_count > 1 and not self._playing:
      self._playing = True
      self._last_tick = time.monotonic()

  def stop(self):
    self._playing = False
    self._current_frame = 0

  def update(self):
    if not self._playing or self._frame_count <= 1:
      return
    now = time.monotonic()
    if now - self._last_tick >= self._frame_delay:
      self._current_frame = (self._current_frame + 1) % self._frame_count
      self._last_tick = now

  def current_texture(self) -> Optional[rl.Texture]:
    self._ensure_loaded()
    if self._frame_count == 0:
      return None
    return self._frames[self._current_frame]

  @property
  def texture(self) -> Optional[rl.Texture]:
    return self.current_texture()

  @property
  def frame_count(self) -> int:
    self._ensure_loaded()
    return self._frame_count

  def unload(self):
    for tex in self._frames:
      rl.unload_texture(tex)
    self._frames.clear()
    self._frame_count = 0


class StaticTexture:
  """Wraps a single PNG as a texture, matching GifPlayer interface."""

  def __init__(self, path: str, size: int = 0):
    self._texture: Optional[rl.Texture] = None
    self._loaded = False
    self._path = path
    self._size = size

  def _ensure_loaded(self):
    if self._loaded:
      return
    self._loaded = True
    path = Path(self._path)
    if not path.exists():
      return
    try:
      img = Image.open(path).convert("RGBA")
      if self._size > 0 and img.size != (self._size, self._size):
        img = img.resize((self._size, self._size), Image.LANCZOS)
      self._texture = GifPlayer._make_texture(img)
    except Exception:
      pass

  def current_texture(self) -> Optional[rl.Texture]:
    self._ensure_loaded()
    return self._texture

  @property
  def texture(self) -> Optional[rl.Texture]:
    return self.current_texture()

  def update(self):
    pass

  def play(self):
    pass

  def stop(self):
    pass

  def unload(self):
    if self._texture:
      rl.unload_texture(self._texture)
      self._texture = None


def load_starpilot_asset(rel_path: str, size: int = 0) -> Union[GifPlayer, StaticTexture]:
  """Load a GIF or PNG from frogpilot/assets/."""
  frogpilot_assets = files("openpilot.frogpilot").joinpath("assets")
  with as_file(frogpilot_assets.joinpath(rel_path)) as fspath:
    full_path = str(fspath)

  if full_path.lower().endswith(".gif"):
    return GifPlayer(full_path, size)
  return StaticTexture(full_path, size)

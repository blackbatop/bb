import atexit
import os
import struct
import time
from collections import deque
from glob import glob

import pyray as rl

EVENT_FORMAT = "llHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)
EV_KEY = 0x01

KEY_LEFTSHIFT = 42
KEY_RIGHTSHIFT = 54
KEY_CAPSLOCK = 58

LINUX_TO_RL_KEY = {
  1: rl.KEY_ESCAPE,
  14: rl.KEY_BACKSPACE,
  28: rl.KEY_ENTER,
  96: rl.KEY_ENTER,  # keypad enter
  102: rl.KEY_HOME,
  103: rl.KEY_UP,
  105: rl.KEY_LEFT,
  106: rl.KEY_RIGHT,
  107: rl.KEY_END,
  108: rl.KEY_DOWN,
  111: rl.KEY_DELETE,
}

LETTER_BY_CODE = {
  16: "q", 17: "w", 18: "e", 19: "r", 20: "t", 21: "y", 22: "u", 23: "i", 24: "o", 25: "p",
  30: "a", 31: "s", 32: "d", 33: "f", 34: "g", 35: "h", 36: "j", 37: "k", 38: "l",
  44: "z", 45: "x", 46: "c", 47: "v", 48: "b", 49: "n", 50: "m",
}

UNSHIFTED_BY_CODE = {
  2: "1", 3: "2", 4: "3", 5: "4", 6: "5", 7: "6", 8: "7", 9: "8", 10: "9", 11: "0",
  12: "-", 13: "=",
  26: "[", 27: "]",
  39: ";", 40: "'", 41: "`", 43: "\\",
  51: ",", 52: ".", 53: "/",
  57: " ",
}

SHIFTED_BY_CODE = {
  2: "!", 3: "@", 4: "#", 5: "$", 6: "%", 7: "^", 8: "&", 9: "*", 10: "(", 11: ")",
  12: "_", 13: "+",
  26: "{", 27: "}",
  39: ":", 40: "\"", 41: "~", 43: "|",
  51: "<", 52: ">", 53: "?",
  57: " ",
}


class USBKeyboard:
  """Fallback keyboard reader for platforms where raylib keyboard input is unavailable."""
  def __init__(self):
    self._fds: dict[str, int] = {}
    self._last_scan_t = 0.0
    self._left_shift_down = False
    self._right_shift_down = False
    self._caps_lock_on = False
    self._key_queue: deque[int] = deque(maxlen=128)
    self._char_queue: deque[int] = deque(maxlen=256)
    atexit.register(self.close)

  def _device_paths(self) -> list[str]:
    paths = []
    paths.extend(glob("/dev/input/by-id/*-kbd"))
    paths.extend(glob("/dev/input/by-path/*-kbd"))
    # Keep deterministic order and de-duplicate paths if both globs resolve to same target.
    return sorted(set(paths))

  def _refresh_devices(self) -> None:
    now = time.monotonic()
    if (now - self._last_scan_t) < 1.0:
      return

    self._last_scan_t = now
    current_paths = set(self._device_paths())

    for path in list(self._fds):
      if path not in current_paths:
        try:
          os.close(self._fds[path])
        except OSError:
          pass
        del self._fds[path]

    for path in current_paths:
      if path in self._fds:
        continue
      try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
      except OSError:
        continue
      self._fds[path] = fd

  def _key_to_char(self, code: int) -> str | None:
    shift = self._left_shift_down or self._right_shift_down

    if code in LETTER_BY_CODE:
      c = LETTER_BY_CODE[code]
      return c.upper() if (self._caps_lock_on ^ shift) else c

    if code in UNSHIFTED_BY_CODE:
      if shift and code in SHIFTED_BY_CODE:
        return SHIFTED_BY_CODE[code]
      return UNSHIFTED_BY_CODE[code]

    return None

  def _process_event(self, event_type: int, code: int, value: int) -> None:
    if event_type != EV_KEY:
      return

    if code == KEY_LEFTSHIFT:
      self._left_shift_down = value != 0
      return
    if code == KEY_RIGHTSHIFT:
      self._right_shift_down = value != 0
      return
    if code == KEY_CAPSLOCK and value == 1:
      self._caps_lock_on = not self._caps_lock_on
      return

    # Linux key events: 0=release, 1=press, 2=repeat
    if value not in (1, 2):
      return

    key = LINUX_TO_RL_KEY.get(code)
    if key is not None:
      self._key_queue.append(key)

    char = self._key_to_char(code)
    if char is not None:
      self._char_queue.append(ord(char))

  def _poll(self) -> None:
    self._refresh_devices()

    for path, fd in list(self._fds.items()):
      while True:
        try:
          data = os.read(fd, EVENT_SIZE * 32)
        except BlockingIOError:
          break
        except OSError:
          try:
            os.close(fd)
          except OSError:
            pass
          del self._fds[path]
          break

        if not data:
          break

        valid_bytes = len(data) - (len(data) % EVENT_SIZE)
        for i in range(0, valid_bytes, EVENT_SIZE):
          _, _, event_type, code, value = struct.unpack_from(EVENT_FORMAT, data, i)
          self._process_event(event_type, code, value)

        if len(data) < (EVENT_SIZE * 32):
          break

  def get_key_pressed(self) -> int:
    self._poll()
    return self._key_queue.popleft() if self._key_queue else 0

  def get_char_pressed(self) -> int:
    self._poll()
    return self._char_queue.popleft() if self._char_queue else 0

  def close(self) -> None:
    for fd in self._fds.values():
      try:
        os.close(fd)
      except OSError:
        pass
    self._fds.clear()


_usb_keyboard = USBKeyboard()


def get_usb_key_pressed() -> int:
  return _usb_keyboard.get_key_pressed()


def get_usb_char_pressed() -> int:
  return _usb_keyboard.get_char_pressed()

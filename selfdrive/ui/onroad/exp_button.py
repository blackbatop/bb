import time
import pyray as rl
from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets import Widget

# Status-aware background colors
_BG_AOL = rl.Color(145, 155, 149, 204)  # Always on lateral: grey-green
_BG_CEM = rl.Color(0xDA, 0x6F, 0x25, 204)  # Conditional experimental: orange
_BG_TRAFFIC = rl.Color(0xC9, 0x22, 0x31, 204)  # Traffic mode: red


class ExpButton(Widget):
  def __init__(self, button_size: int, icon_size: int):
    super().__init__()
    self._params = Params()
    self._params_memory = Params(memory=True)
    self._experimental_mode: bool = False
    self._engageable: bool = False
    self._icon_size = icon_size

    # State hold mechanism
    self._hold_duration = 2.0  # seconds
    self._held_mode: bool | None = None
    self._hold_end_time: float | None = None

    self._white_color: rl.Color = rl.Color(255, 255, 255, 255)
    self._black_bg: rl.Color = rl.Color(0, 0, 0, 166)
    self._txt_wheel: rl.Texture = gui_app.texture('icons/chffr_wheel.png', icon_size, icon_size)
    self._txt_exp: rl.Texture = gui_app.texture('icons/experimental.png', icon_size, icon_size)

    # FrogPilot custom wheel (lazy loaded)
    self._custom_wheel: rl.Texture | None = None
    self._custom_wheel_loaded: bool = False

    self._rect = rl.Rectangle(0, 0, button_size, button_size)

  def set_rect(self, rect: rl.Rectangle) -> None:
    self._rect.x, self._rect.y = rect.x, rect.y

  def _update_state(self) -> None:
    selfdrive_state = ui_state.sm["selfdriveState"]
    self._toggles = ui_state.frogpilot_toggles

    # Conditional experimental mode: use CEStatus instead of ExperimentalMode
    if self._toggles.get("conditional_experimental_mode", False):
      self._experimental_mode = self._params_memory.get_int("CEStatus", default=0) >= 2
    else:
      self._experimental_mode = selfdrive_state.experimentalMode

    self._engageable = selfdrive_state.engageable or selfdrive_state.enabled

    # FrogPilot: hot-reload custom wheel image
    if self._params_memory.get_bool("UpdateWheelImage"):
      self._custom_wheel = None
      self._custom_wheel_loaded = False
      self._params_memory.put_bool("UpdateWheelImage", False)

  def _handle_mouse_release(self, _):
    super()._handle_mouse_release(_)
    if self._is_toggle_allowed():
      new_mode = not self._experimental_mode
      self._params.put_bool("ExperimentalMode", new_mode)

      # Hold new state temporarily
      self._held_mode = new_mode
      self._hold_end_time = time.monotonic() + self._hold_duration

  def _render(self, rect: rl.Rectangle) -> None:
    center_x = int(self._rect.x + self._rect.width // 2)
    center_y = int(self._rect.y + self._rect.height // 2)
    t = self._toggles

    self._white_color.a = 180 if self.is_pressed or not self._engageable else 255

    # Status-aware background color
    bg = self._black_bg
    if ui_state.traffic_mode_enabled:
      bg = _BG_TRAFFIC
    elif ui_state.always_on_lateral_active:
      bg = _BG_AOL
    elif self._held_or_actual_mode():
      ce_status = self._params_memory.get_int("CEStatus", default=0) if t.get("conditional_experimental_mode", False) else 0
      if ce_status >= 2:
        bg = _BG_CEM

    # Custom wheel image or stock
    if self._held_or_actual_mode():
      texture = self._txt_exp
    elif t.get("wheel_image", False):
      texture = self._get_custom_wheel()
    else:
      texture = self._txt_wheel

    rl.draw_circle(center_x, center_y, self._rect.width / 2, bg)

    # Rotating wheel support
    if t.get("rotating_wheel", False) and not self._held_or_actual_mode():
      self._draw_rotated_wheel(texture, center_x, center_y)
    else:
      rl.draw_texture(texture, center_x - texture.width // 2, center_y - texture.height // 2, self._white_color)

  def _get_custom_wheel(self) -> rl.Texture:
    if not self._custom_wheel_loaded:
      self._custom_wheel_loaded = True
      try:
        self._custom_wheel = gui_app.starpilot_texture("active_theme/steering_wheel/wheel.png", self._icon_size, self._icon_size)
      except Exception:
        self._custom_wheel = None
    return self._custom_wheel if self._custom_wheel is not None else self._txt_wheel

  def _draw_rotated_wheel(self, texture: rl.Texture, center_x: int, center_y: int) -> None:
    """Draw the wheel texture rotated by steering angle."""
    car_state = ui_state.sm["carState"]
    angle = car_state.steeringAngleDeg
    # Clamp to reasonable range and normalize to texture rotation
    rotation = max(-90.0, min(90.0, angle))

    source = rl.Rectangle(0, 0, texture.width, texture.height)
    dest = rl.Rectangle(center_x, center_y, texture.width, texture.height)
    origin = rl.Vector2(texture.width / 2, texture.height / 2)
    rl.draw_texture_pro(texture, source, dest, origin, rotation, self._white_color)

  def _held_or_actual_mode(self):
    now = time.monotonic()
    if self._hold_end_time and now < self._hold_end_time:
      return self._held_mode

    if self._hold_end_time and now >= self._hold_end_time:
      self._hold_end_time = self._held_mode = None

    return self._experimental_mode

  def _is_toggle_allowed(self):
    if not self._params.get_bool("ExperimentalModeConfirmed"):
      return False

    # Mirror exp mode toggle using persistent car params
    return ui_state.has_longitudinal_control

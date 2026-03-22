import pyray as rl
import socket
import time
from dataclasses import dataclass
from collections.abc import Callable
from cereal import log
from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.selfdrive.ui.onroad.gif_player import load_starpilot_asset
from openpilot.system.ui.lib.application import gui_app, FontWeight, MousePos, FONT_SCALE
from openpilot.system.ui.lib.multilang import tr, tr_noop
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets import Widget

SIDEBAR_WIDTH = 300
METRIC_HEIGHT = 126
METRIC_WIDTH = 240
METRIC_MARGIN = 30
FONT_SIZE = 35

SETTINGS_BTN = rl.Rectangle(50, 35, 200, 117)
HOME_BTN = rl.Rectangle(60, 860, 180, 180)

# FrogPilot click regions (for metric cycling)
FP_TEMP_REGION = rl.Rectangle(30, 338, 240, 126)
FP_COMPUTE_REGION = rl.Rectangle(30, 496, 240, 126)
FP_STORAGE_REGION = rl.Rectangle(30, 654, 240, 126)

ThermalStatus = log.DeviceState.ThermalStatus
NetworkType = log.DeviceState.NetworkType


# Color scheme
class Colors:
  WHITE = rl.WHITE
  WHITE_DIM = rl.Color(255, 255, 255, 85)
  GRAY = rl.Color(84, 84, 84, 255)

  # Status colors
  GOOD = rl.WHITE
  WARNING = rl.Color(218, 202, 37, 255)
  DANGER = rl.Color(201, 34, 49, 255)

  # UI elements
  METRIC_BORDER = rl.Color(255, 255, 255, 85)
  BUTTON_NORMAL = rl.WHITE
  BUTTON_PRESSED = rl.Color(255, 255, 255, 166)


NETWORK_TYPES = {
  NetworkType.none: tr_noop("--"),
  NetworkType.wifi: tr_noop("Wi-Fi"),
  NetworkType.ethernet: tr_noop("ETH"),
  NetworkType.cell2G: tr_noop("2G"),
  NetworkType.cell3G: tr_noop("3G"),
  NetworkType.cell4G: tr_noop("LTE"),
  NetworkType.cell5G: tr_noop("5G"),
}


@dataclass(slots=True)
class MetricData:
  label: str
  value: str
  color: rl.Color

  def update(self, label: str, value: str, color: rl.Color):
    self.label = label
    self.value = value
    self.color = color


class Sidebar(Widget):
  def __init__(self):
    super().__init__()
    self._net_type = NETWORK_TYPES.get(NetworkType.none)
    self._net_strength = 0

    self._temp_status = MetricData(tr_noop("TEMP"), tr_noop("GOOD"), Colors.GOOD)
    self._panda_status = MetricData(tr_noop("VEHICLE"), tr_noop("ONLINE"), Colors.GOOD)
    self._connect_status = MetricData(tr_noop("CONNECT"), tr_noop("OFFLINE"), Colors.WARNING)
    self._recording_audio = False

    # FrogPilot metrics (replaces stock slots when toggles are on)
    self._fp_temp = MetricData(tr_noop("TEMP"), tr_noop("--"), Colors.GOOD)
    self._fp_compute = MetricData(tr_noop("CPU"), tr_noop("--"), Colors.GOOD)
    self._fp_storage = MetricData(tr_noop("MEM"), tr_noop("--"), Colors.GOOD)

    # FrogPilot click-to-cycle state (0=stock, then 1..N for options)
    self._fp_temp_cycle = 0  # 0=temp, 1=numerical temp
    self._fp_compute_cycle = 0  # 0=stock, 1=CPU, 2=GPU
    self._fp_storage_cycle = 0  # 0=stock, 1=memory, 2=storage left, 3=storage used

    self._toggles: dict = {}

    # IP address (cached, refreshed rarely)
    self._ip_address: str = ""
    self._ip_refresh_time: float = 0.0

    self._home_img = gui_app.texture("images/button_home.png", HOME_BTN.width, HOME_BTN.height)
    self._flag_img = gui_app.texture("images/button_flag.png", HOME_BTN.width, HOME_BTN.height)
    self._settings_img = gui_app.texture("images/button_settings.png", SETTINGS_BTN.width, SETTINGS_BTN.height)
    self._mic_img = gui_app.texture("icons/microphone.png", 30, 30)
    self._mic_indicator_rect = rl.Rectangle(0, 0, 0, 0)

    # FrogPilot: theme GIF buttons (lazy loaded)
    self._home_gif = None
    self._flag_gif = None
    self._settings_gif = None
    self._gifs_loaded = False

    self._font_regular = gui_app.font(FontWeight.NORMAL)
    self._font_bold = gui_app.font(FontWeight.SEMI_BOLD)

    # Callbacks
    self._on_settings_click: Callable | None = None
    self._on_flag_click: Callable | None = None
    self._open_settings_callback: Callable | None = None

  def set_callbacks(self, on_settings: Callable | None = None, on_flag: Callable | None = None, open_settings: Callable | None = None):
    self._on_settings_click = on_settings
    self._on_flag_click = on_flag
    self._open_settings_callback = open_settings

  def _render(self, rect: rl.Rectangle):
    # Background
    rl.draw_rectangle_rec(rect, rl.BLACK)

    self._draw_buttons(rect)
    self._draw_network_indicator(rect)
    self._draw_metrics(rect)

  def _update_state(self):
    sm = ui_state.sm
    self._toggles = ui_state.frogpilot_toggles

    # FrogPilot: load theme GIFs on first update
    if not self._gifs_loaded:
      self._gifs_loaded = True
      try:
        self._home_gif = load_starpilot_asset("active_theme/icons/button_home.gif", int(HOME_BTN.width))
      except Exception:
        self._home_gif = None
      try:
        self._flag_gif = load_starpilot_asset("active_theme/icons/button_flag.gif", int(HOME_BTN.width))
      except Exception:
        self._flag_gif = None
      try:
        self._settings_gif = load_starpilot_asset("active_theme/icons/button_settings.gif", int(SETTINGS_BTN.width))
      except Exception:
        self._settings_gif = None

    # Advance GIF animations
    for gif in (self._home_gif, self._flag_gif, self._settings_gif):
      if gif is not None:
        gif.play()

    if not sm.updated['deviceState']:
      return

    device_state = sm['deviceState']

    self._recording_audio = ui_state.recording_audio
    self._update_network_status(device_state)
    self._update_temperature_status(device_state)
    self._update_connection_status(device_state)
    self._update_panda_status()
    self._update_frogpilot_metrics(device_state)

    # Refresh IP address rarely
    now = time.monotonic()
    if now - self._ip_refresh_time > 30.0:
      self._ip_refresh_time = now
      try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        self._ip_address = s.getsockname()[0]
        s.close()
      except Exception:
        self._ip_address = ""

  def _update_network_status(self, device_state):
    self._net_type = NETWORK_TYPES.get(device_state.networkType.raw, tr_noop("Unknown"))
    strength = device_state.networkStrength
    self._net_strength = max(0, min(5, strength.raw + 1)) if strength.raw > 0 else 0

  def _update_temperature_status(self, device_state):
    thermal_status = device_state.thermalStatus

    if thermal_status == ThermalStatus.green:
      self._temp_status.update(tr_noop("TEMP"), tr_noop("GOOD"), Colors.GOOD)
    elif thermal_status == ThermalStatus.yellow:
      self._temp_status.update(tr_noop("TEMP"), tr_noop("OK"), Colors.WARNING)
    else:
      self._temp_status.update(tr_noop("TEMP"), tr_noop("HIGH"), Colors.DANGER)

  def _update_connection_status(self, device_state):
    last_ping = device_state.lastAthenaPingTime
    if last_ping == 0:
      self._connect_status.update(tr_noop("CONNECT"), tr_noop("OFFLINE"), Colors.WARNING)
    elif time.monotonic_ns() - last_ping < 80_000_000_000:  # 80 seconds in nanoseconds
      self._connect_status.update(tr_noop("CONNECT"), tr_noop("ONLINE"), Colors.GOOD)
    else:
      self._connect_status.update(tr_noop("CONNECT"), tr_noop("ERROR"), Colors.DANGER)

  def _update_panda_status(self):
    if ui_state.panda_type == log.PandaState.PandaType.unknown:
      self._panda_status.update(tr_noop("NO"), tr_noop("PANDA"), Colors.DANGER)
    else:
      self._panda_status.update(tr_noop("VEHICLE"), tr_noop("ONLINE"), Colors.GOOD)

  def _update_frogpilot_metrics(self, device_state):
    t = self._toggles
    is_metric = ui_state.is_metric

    # --- Temperature slot: numerical temp or stock ---
    dev_ui = t.get("developer_ui", False)
    if dev_ui and t.get("numerical_temp", False):
      temps_c = list(device_state.cpuTempC) if device_state.cpuTempC else []
      temp_c = max(temps_c) if temps_c else 0.0
      if t.get("fahrenheit", False):
        val = f"{temp_c * 9 / 5 + 32:.0f}F"
      else:
        val = f"{temp_c:.0f}C"
      color = Colors.DANGER if temp_c >= 90 else Colors.WARNING if temp_c >= 75 else Colors.GOOD
      custom = t.get("sidebar_color1")
      if custom:
        color = self._parse_color(custom)
      self._fp_temp.update(tr_noop("TEMP"), val, color)
    else:
      self._fp_temp = self._temp_status

    # --- Compute slot: CPU/GPU or stock ---
    show_cpu = t.get("show_cpu", False)
    show_gpu = t.get("show_gpu", False)
    if show_cpu or show_gpu:
      if show_gpu:
        gpu_pct = device_state.gpuUsagePercent if device_state.gpuUsagePercent else 0
        val = f"{gpu_pct}%"
        color = Colors.DANGER if gpu_pct >= 85 else Colors.WARNING if gpu_pct >= 70 else Colors.GOOD
        self._fp_compute.update(tr_noop("GPU"), val, color)
      else:
        cpu_loads = list(device_state.cpuUsagePercent) if device_state.cpuUsagePercent else []
        avg = sum(cpu_loads) / max(len(cpu_loads), 1) if cpu_loads else 0
        val = f"{int(avg)}%"
        color = Colors.DANGER if avg >= 85 else Colors.WARNING if avg >= 70 else Colors.GOOD
        self._fp_compute.update(tr_noop("CPU"), val, color)
      custom = t.get("sidebar_color2")
      if custom:
        self._fp_compute.color = self._parse_color(custom)
    else:
      self._fp_compute = self._panda_status

    # --- Storage slot: memory/storage or stock ---
    show_mem = t.get("show_memory_usage", False)
    show_storage_left = t.get("show_storage_left", False)
    show_storage_used = t.get("show_storage_used", False)
    if show_mem:
      mem_pct = device_state.memoryUsagePercent if device_state.memoryUsagePercent else 0
      val = f"{mem_pct}%"
      color = Colors.DANGER if mem_pct >= 85 else Colors.WARNING if mem_pct >= 70 else Colors.GOOD
      self._fp_storage.update(tr_noop("MEM"), val, color)
    elif show_storage_left or show_storage_used:
      if sm_valid := ui_state.sm.valid.get("frogpilotDeviceState", False):
        fp_dev = ui_state.sm["frogpilotDeviceState"]
        gb = fp_dev.freeSpace if show_storage_left else fp_dev.usedSpace
        label = tr_noop("SSD LEFT") if show_storage_left else tr_noop("SSD USED")
        val = f"{gb:.0f} GB"
        color = Colors.DANGER if (show_storage_left and gb < 5) else Colors.WARNING if (show_storage_left and gb < 25) else Colors.GOOD
        self._fp_storage.update(label, val, color)
      else:
        self._fp_storage = self._connect_status
    else:
      self._fp_storage = self._connect_status
    custom = t.get("sidebar_color3")
    if custom:
      self._fp_storage.color = self._parse_color(custom)

  @staticmethod
  def _parse_color(color_str: str) -> rl.Color:
    s = color_str.lstrip('#')
    if len(s) == 8:
      return rl.Color(int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16), int(s[0:2], 16))
    if len(s) == 6:
      return rl.Color(int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)
    return rl.Color(255, 255, 255, 255)

  def _handle_mouse_release(self, mouse_pos: MousePos):
    if rl.check_collision_point_rec(mouse_pos, SETTINGS_BTN):
      if self._on_settings_click:
        self._on_settings_click()
    elif rl.check_collision_point_rec(mouse_pos, HOME_BTN) and ui_state.started:
      if self._on_flag_click:
        self._on_flag_click()
    elif self._recording_audio and rl.check_collision_point_rec(mouse_pos, self._mic_indicator_rect):
      if self._open_settings_callback:
        self._open_settings_callback()
    # FrogPilot: click-to-cycle metrics when developer_ui is on
    elif self._toggles.get("developer_ui", False):
      if rl.check_collision_point_rec(mouse_pos, FP_TEMP_REGION):
        self._fp_temp_cycle = (self._fp_temp_cycle + 1) % 3
        p = Params()
        p.put_bool("Fahrenheit", self._fp_temp_cycle == 2)
        p.put_bool("NumericalTemp", self._fp_temp_cycle >= 1)
      elif rl.check_collision_point_rec(mouse_pos, FP_COMPUTE_REGION):
        self._fp_compute_cycle = (self._fp_compute_cycle + 1) % 3
        p = Params()
        p.put_bool("ShowCPU", self._fp_compute_cycle == 1)
        p.put_bool("ShowGPU", self._fp_compute_cycle == 2)
      elif rl.check_collision_point_rec(mouse_pos, FP_STORAGE_REGION):
        self._fp_storage_cycle = (self._fp_storage_cycle + 1) % 4
        p = Params()
        p.put_bool("ShowMemoryUsage", self._fp_storage_cycle == 1)
        p.put_bool("ShowStorageLeft", self._fp_storage_cycle == 2)
        p.put_bool("ShowStorageUsed", self._fp_storage_cycle == 3)

  def _draw_buttons(self, rect: rl.Rectangle):
    mouse_pos = rl.get_mouse_position()
    mouse_down = self.is_pressed and rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT)

    # Settings button (GIF theme or stock)
    settings_down = mouse_down and rl.check_collision_point_rec(mouse_pos, SETTINGS_BTN)
    tint = Colors.BUTTON_PRESSED if settings_down else Colors.BUTTON_NORMAL
    gif_tex = self._settings_gif.texture if self._settings_gif is not None else None
    settings_tex = gif_tex if gif_tex is not None else self._settings_img
    rl.draw_texture(settings_tex, int(SETTINGS_BTN.x), int(SETTINGS_BTN.y), tint)

    # Home/Flag button (GIF theme or stock)
    flag_pressed = mouse_down and rl.check_collision_point_rec(mouse_pos, HOME_BTN)
    if ui_state.started:
      gif_tex = self._flag_gif.texture if self._flag_gif is not None else None
      button_tex = gif_tex if gif_tex is not None else self._flag_img
    else:
      gif_tex = self._home_gif.texture if self._home_gif is not None else None
      button_tex = gif_tex if gif_tex is not None else self._home_img

    tint = Colors.BUTTON_PRESSED if (ui_state.started and flag_pressed) else Colors.BUTTON_NORMAL
    rl.draw_texture(button_tex, int(HOME_BTN.x), int(HOME_BTN.y), tint)

    # Microphone button
    if self._recording_audio:
      self._mic_indicator_rect = rl.Rectangle(rect.x + rect.width - 130, rect.y + 245, 75, 40)

      mic_pressed = mouse_down and rl.check_collision_point_rec(mouse_pos, self._mic_indicator_rect)
      bg_color = rl.Color(Colors.DANGER.r, Colors.DANGER.g, Colors.DANGER.b, int(255 * 0.65)) if mic_pressed else Colors.DANGER

      rl.draw_rectangle_rounded(self._mic_indicator_rect, 1, 10, bg_color)
      rl.draw_texture(
        self._mic_img,
        int(self._mic_indicator_rect.x + (self._mic_indicator_rect.width - self._mic_img.width) / 2),
        int(self._mic_indicator_rect.y + (self._mic_indicator_rect.height - self._mic_img.height) / 2),
        Colors.WHITE,
      )

  def _draw_network_indicator(self, rect: rl.Rectangle):
    # FrogPilot: IP address replaces signal dots
    if self._toggles.get("ip_metrics", False) and self._ip_address:
      text_pos = rl.Vector2(rect.x + 58, rect.y + 200)
      rl.draw_text_ex(self._font_regular, self._ip_address, text_pos, 30, 0, Colors.WHITE)
      # Still show network type below
      text_pos2 = rl.Vector2(rect.x + 58, rect.y + 247)
      rl.draw_text_ex(self._font_regular, tr(self._net_type), text_pos2, FONT_SIZE, 0, Colors.WHITE)
      return

    # Signal strength dots
    x_start = rect.x + 58
    y_pos = rect.y + 196
    dot_size = 27
    dot_spacing = 37

    for i in range(5):
      color = Colors.WHITE if i < self._net_strength else Colors.GRAY
      x = int(x_start + i * dot_spacing + dot_size // 2)
      y = int(y_pos + dot_size // 2)
      rl.draw_circle(x, y, dot_size // 2, color)

    # Network type text
    text_y = rect.y + 247
    text_pos = rl.Vector2(rect.x + 58, text_y)
    rl.draw_text_ex(self._font_regular, tr(self._net_type), text_pos, FONT_SIZE, 0, Colors.WHITE)

  def _draw_metrics(self, rect: rl.Rectangle):
    t = self._toggles
    use_fp = (
      t.get("numerical_temp", False)
      or t.get("show_cpu", False)
      or t.get("show_gpu", False)
      or t.get("show_memory_usage", False)
      or t.get("show_storage_left", False)
      or t.get("show_storage_used", False)
    )

    if use_fp:
      metrics = [(self._fp_temp, 338), (self._fp_compute, 496), (self._fp_storage, 654)]
    else:
      metrics = [(self._temp_status, 338), (self._panda_status, 496), (self._connect_status, 654)]

    for metric, y_offset in metrics:
      self._draw_metric(rect, metric, rect.y + y_offset)

  def _draw_metric(self, rect: rl.Rectangle, metric: MetricData, y: float):
    metric_rect = rl.Rectangle(rect.x + METRIC_MARGIN, y, METRIC_WIDTH, METRIC_HEIGHT)
    # Draw colored left edge (clipped rounded rectangle)
    edge_rect = rl.Rectangle(metric_rect.x + 4, metric_rect.y + 4, 100, 118)
    rl.begin_scissor_mode(int(metric_rect.x + 4), int(metric_rect.y), 18, int(metric_rect.height))
    rl.draw_rectangle_rounded(edge_rect, 0.3, 10, metric.color)
    rl.end_scissor_mode()

    # Draw border
    rl.draw_rectangle_rounded_lines_ex(metric_rect, 0.3, 10, 2, Colors.METRIC_BORDER)

    # Draw label and value
    labels = [tr(metric.label), tr(metric.value)]
    text_y = metric_rect.y + (metric_rect.height / 2 - len(labels) * FONT_SIZE * FONT_SCALE)
    for text in labels:
      text_size = measure_text_cached(self._font_bold, text, FONT_SIZE)
      text_y += text_size.y
      text_pos = rl.Vector2(metric_rect.x + 22 + (metric_rect.width - 22 - text_size.x) / 2, text_y)
      rl.draw_text_ex(self._font_bold, text, text_pos, FONT_SIZE, 0, Colors.WHITE)

import time
import pyray as rl
from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets import Widget

METRIC_HEIGHT = 126
METRIC_WIDTH = 275
SIDEBAR_WIDTH = 300
FONT_SIZE = 32


def _fmt(v, decimals=2):
  return f"{v:.{decimals}f}" if isinstance(v, float) else str(v)


class DeveloperSidebar(Widget):
  def __init__(self):
    super().__init__()
    self._params = Params()
    self._font_bold = gui_app.font(FontWeight.SEMI_BOLD)
    self._font_normal = gui_app.font(FontWeight.NORMAL)

    # Engagement tracking
    self._lat_time = 0.0
    self._long_time = 0.0
    self._total_time = 0.0
    self._last_update_time: float = time.monotonic()

    # Peak tracking
    self._max_steer_angle = 0.0
    self._max_torque = 0.0

  def _update_state(self):
    sm = ui_state.sm

    now = time.monotonic()
    dt = now - self._last_update_time
    self._last_update_time = now

    # Engagement time tracking (only when onroad and not standstill)
    if ui_state.started and sm.valid.get("carControl", False) and sm.valid.get("carState", False):
      cc = sm["carControl"]
      cs = sm["carState"]
      if not cs.standstill and cs.gearShifter != 3:  # not reverse
        self._total_time += dt
        if cc.latActive:
          self._lat_time += dt
        if cc.longActive:
          self._long_time += dt

    # Peak tracking
    if sm.valid.get("carControl", False):
      torque = abs(sm["carControl"].actuators.torque)
      if torque > self._max_torque:
        self._max_torque = torque
    if sm.valid.get("carState", False):
      angle = abs(sm["carState"].steeringAngleDeg)
      if angle > self._max_steer_angle:
        self._max_steer_angle = angle

  def reset_engagement(self):
    self._lat_time = 0.0
    self._long_time = 0.0
    self._total_time = 0.0
    self._max_steer_angle = 0.0
    self._max_torque = 0.0

  def _get_metric_value(self, metric_id: int) -> tuple[str, str]:
    """Return (label, value_string) for a metric ID (1-16)."""
    sm = ui_state.sm
    is_metric = ui_state.is_metric
    conv = 1.0 if is_metric else 3.281  # m/s^2 to ft/s^2

    if metric_id == 1:  # ACCEL
      a = sm["carState"].aEgo * conv if sm.valid.get("carState", False) else 0
      return ("ACCEL", f"{a:.2f}")
    elif metric_id == 2:  # MAX ACCEL
      return ("MAX ACCEL", "-")
    elif metric_id == 3:  # STEER DELAY
      d = sm["liveDelay"].lateralDelay if sm.valid.get("liveDelay", False) else 0
      return ("STEER DELAY", f"{d:.5f}")
    elif metric_id == 4:  # FRICTION
      f = sm["liveTorqueParameters"].frictionCoefficientFiltered if sm.valid.get("liveTorqueParameters", False) else 0
      return ("FRICTION", f"{f:.5f}")
    elif metric_id == 5:  # LAT ACCEL
      l = sm["liveTorqueParameters"].latAccelFactorFiltered if sm.valid.get("liveTorqueParameters", False) else 0
      return ("LAT ACCEL", f"{l:.5f}")
    elif metric_id == 6:  # STEER RATIO
      r = sm["liveParameters"].steerRatio if sm.valid.get("liveParameters", False) else 0
      return ("STEER RATIO", f"{r:.5f}")
    elif metric_id == 7:  # STEER STIFF
      s = sm["liveParameters"].stiffnessFactor if sm.valid.get("liveParameters", False) else 0
      return ("STEER STIFF", f"{s:.5f}")
    elif metric_id == 8:  # LATERAL %
      pct = self._lat_time * 100 / max(self._total_time, 1)
      return ("LATERAL %", f"{pct:.2f}%")
    elif metric_id == 9:  # LONG %
      pct = self._long_time * 100 / max(self._total_time, 1)
      return ("LONG %", f"{pct:.2f}%")
    elif metric_id == 10:  # STEER ANGLE
      if sm.valid.get("carState", False):
        angle = sm["carState"].steeringAngleDeg
        if abs(self._max_torque) >= 50:
          return ("STEER ANGLE", f"{angle:.0f} - ({self._max_steer_angle:.0f})")
        return ("STEER ANGLE", f"{angle:.0f}")
      return ("STEER ANGLE", "-")
    elif metric_id == 11:  # TORQUE %
      if sm.valid.get("carControl", False):
        torque = sm["carControl"].actuators.torque
        if abs(torque) >= 50:
          return ("TORQUE %", f"{torque:.0f} - ({self._max_torque:.0f})")
        return ("TORQUE %", f"{torque:.0f}")
      return ("TORQUE %", "-")
    elif metric_id == 12:  # ACT ACCEL
      a = sm["carControl"].actuators.accel * conv if sm.valid.get("carControl", False) else 0
      return ("ACT ACCEL", f"{a:.2f}")
    elif metric_id == 13:  # DANGER %
      if sm.valid.get("frogpilotPlan", False):
        d = sm["frogpilotPlan"].dangerFactor * 100
        return ("DANGER %", f"{d:.2f}%")
      return ("DANGER %", "-")
    elif metric_id == 14:  # ACCEL JERK
      j = sm["frogpilotPlan"].accelerationJerk if sm.valid.get("frogpilotPlan", False) else 0
      return ("ACCEL JERK", f"{j}")
    elif metric_id == 15:  # DANGER JERK
      j = sm["frogpilotPlan"].dangerJerk if sm.valid.get("frogpilotPlan", False) else 0
      return ("DANGER JERK", f"{j}")
    elif metric_id == 16:  # SPEED JERK
      j = sm["frogpilotPlan"].speedJerk if sm.valid.get("frogpilotPlan", False) else 0
      return ("SPEED JERK", f"{j}")
    return ("", "")

  def _render(self, rect: rl.Rectangle):
    t = ui_state.frogpilot_toggles
    if not t.get("developer_sidebar", False):
      return

    # Read slot assignments (1-7 map to metric IDs 1-16, 0 = empty)
    slots = []
    for i in range(1, 8):
      mid = t.get(f"developer_sidebar_metric{i}", 0)
      if mid and 1 <= mid <= 16:
        slots.append(mid)

    if not slots:
      return

    count = len(slots)
    spacing = (rect.height - count * METRIC_HEIGHT) / max(count + 1, 1)
    y = rect.y + spacing
    custom_color = t.get("sidebar_color1", None)

    for mid in slots:
      label, value = self._get_metric_value(mid)
      if not label:
        continue
      self._draw_metric(rect.x + 12, y, METRIC_WIDTH, METRIC_HEIGHT, label, value, custom_color)
      y += METRIC_HEIGHT + spacing

  def _draw_metric(self, x, y, w, h, label, value, custom_color=None):
    metric_rect = rl.Rectangle(x, y, w, h)

    # Accent bar on right side (like QT developer sidebar)
    accent_color = rl.Color(0x17, 0x86, 0x44, 255)  # Green default
    if custom_color:
      s = custom_color.lstrip('#')
      if len(s) >= 6:
        accent_color = rl.Color(int(s[-6:-4], 16), int(s[-4:-2], 16), int(s[-2:], 16), 255)

    edge_rect = rl.Rectangle(x + w - 100, y + 4, 100, h - 8)
    rl.begin_scissor_mode(int(x + w - 18), int(y), 18, int(h))
    rl.draw_rectangle_rounded(edge_rect, 0.3, 10, accent_color)
    rl.end_scissor_mode()

    # Border
    rl.draw_rectangle_rounded_lines_ex(metric_rect, 0.3, 10, 2, rl.Color(255, 255, 255, 85))

    # Text
    text = f"{label}\n{value}"
    ts = measure_text_cached(self._font_bold, text, FONT_SIZE)
    text_x = x + 22 + (w - 22 - ts.x) / 2
    text_y = y + (h - ts.y) / 2
    rl.draw_text_ex(self._font_bold, text, rl.Vector2(text_x, text_y), FONT_SIZE, 0, rl.WHITE)

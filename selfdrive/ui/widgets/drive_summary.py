import json
import pyray as rl
from dataclasses import dataclass
from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets import Widget

METER_TO_MILE = 0.000621371
MS_TO_KPH = 3.6
MS_TO_MPH = 2.237

# Random events: (json_key, display_name)
RANDOM_EVENTS = [
  ("accel30", "UwUs"),
  ("accel35", "Loch Ness Encounters"),
  ("accel40", "Visits to 1955"),
  ("dejaVuCurve", "Deja Vu Moments"),
  ("firefoxSteerSaturated", "Internet Explorer Weeeeeeees"),
  ("hal9000", "HAL 9000 Denials"),
  ("openpilotCrashedRandomEvent", "openpilot Crashes"),
  ("thisIsFineSteerSaturated", "This Is Fine Moments"),
  ("toBeContinued", "To Be Continued Moments"),
  ("vCruise69", "Noices"),
  ("yourFrogTriedToKillMe", "Attempted Frog Murders"),
  ("youveGotMail", "Total Mail Received"),
]


@dataclass
class StatBox:
  label: str = ""
  value: str = "-"


class DriveSummary(Widget):
  def __init__(self, show_random_events: bool = False):
    super().__init__()
    self._params = Params()
    self._show_random_events = show_random_events
    self._previous_stats: dict = {}
    self._current_stats: dict = {}
    self._stat_boxes: list[StatBox] = []
    self._random_events: list[tuple[str, int]] = []
    self._sorted_events: list[tuple[str, int]] = []

    if show_random_events:
      self._title = "Random Events Summary"
    else:
      self._title = "Drive Summary"

  def show_event(self):
    """Called when widget becomes visible. Snapshot current stats."""
    raw = self._params.get("FrogPilotStats")
    if raw:
      try:
        self._current_stats = json.loads(raw)
      except (json.JSONDecodeError, TypeError):
        self._current_stats = {}
    else:
      self._current_stats = {}

    self._previous_stats = dict(self._current_stats)

    # Pre-compute sorted random events (data is immutable while visible)
    if self._show_random_events:
      cur_events = self._current_stats.get("RandomEvents", {})
      prev_events = self._previous_stats.get("RandomEvents", {})
      self._sorted_events = []
      for key, name in RANDOM_EVENTS:
        diff = cur_events.get(key, 0) - prev_events.get(key, 0)
        if diff > 0:
          self._sorted_events.append((name, diff))
      self._sorted_events.sort(key=lambda x: (-x[1], x[0]))

  def set_previous_stats(self, stats: dict):
    """Set the baseline stats snapshot (taken when last went onroad)."""
    self._previous_stats = stats

  def _render(self, rect: rl.Rectangle):
    font_bold = gui_app.font(FontWeight.BOLD)
    font_normal = gui_app.font(FontWeight.NORMAL)

    ox, oy = rect.x, rect.y
    w = rect.width

    # Title
    title_size = 48
    ts = measure_text_cached(font_bold, self._title, title_size)
    rl.draw_text_ex(font_bold, self._title, rl.Vector2(ox + (w - ts.x) / 2, oy), title_size, 0, rl.WHITE)

    y = oy + ts.y + 30

    if self._show_random_events:
      self._render_random_events(font_bold, font_normal, ox, y, w)
    else:
      self._render_drive_stats(font_bold, font_normal, ox, y, w)

  def _render_drive_stats(self, font_bold, font_normal, ox, y, w):
    cur = self._current_stats
    prev = self._previous_stats

    tracked_time = cur.get("TrackedTime", 0) - prev.get("TrackedTime", 0)
    engaged_time = (cur.get("AOLTime", 0) - prev.get("AOLTime", 0)) + (cur.get("LongitudinalTime", 0) - prev.get("LongitudinalTime", 0))
    exp_time = cur.get("ExperimentalModeTime", 0) - prev.get("ExperimentalModeTime", 0)
    meters = cur.get("FrogPilotMeters", 0) - prev.get("FrogPilotMeters", 0)

    is_metric = ui_state.is_metric

    # Engagement %
    eng_pct = f"{engaged_time * 100 / max(tracked_time, 1):.0f}%" if tracked_time > 0 else "-"

    # Distance
    if is_metric:
      dist = f"{meters / 1000:.1f} km"
    else:
      dist = f"{meters * METER_TO_MILE:.1f} mi"

    # Time
    mins = tracked_time / 60
    hours = int(mins // 60)
    rem_mins = int(mins % 60)
    if hours > 0:
      time_str = f"{hours}h {rem_mins}m"
    else:
      time_str = f"{rem_mins}m"

    # Exp %
    exp_pct = f"{exp_time * 100 / max(tracked_time, 1):.0f}%" if tracked_time > 0 else "-"

    stats = [
      ("Engagement", eng_pct),
      ("Distance", dist),
      ("Drive Time", time_str),
      ("Experimental", exp_pct),
    ]

    box_w = (w - 30) / 2
    box_h = 180

    for i, (label, value) in enumerate(stats):
      col = i % 2
      row = i // 2
      bx = ox + col * (box_w + 10)
      by = y + row * (box_h + 10)
      self._draw_stat_box(font_bold, font_normal, bx, by, box_w, box_h, label, value)

  def _render_random_events(self, font_bold, font_normal, ox, y, w):
    if not self._sorted_events:
      text = "No Random Events Played!"
      ts = measure_text_cached(font_normal, text, 36)
      rl.draw_text_ex(font_normal, text, rl.Vector2(ox + (w - ts.x) / 2, y + 100), 36, 0, rl.Color(255, 255, 255, 150))
      return

    box_w = (w - 20) / 3
    box_h = 140

    for i, (name, count) in enumerate(self._sorted_events[:12]):
      col = i % 3
      row = i // 3
      bx = ox + col * (box_w + 10)
      by = y + row * (box_h + 10)
      self._draw_stat_box(font_bold, font_normal, bx, by, box_w, box_h, name, str(count))

  def _draw_stat_box(self, font_bold, font_normal, x, y, w, h, label, value):
    rect = rl.Rectangle(x, y, w, h)
    rl.draw_rectangle_rounded(rect, 0.15, 10, rl.Color(57, 57, 57, 255))
    rl.draw_rectangle_rounded_lines_ex(rect, 0.15, 10, 2, rl.Color(255, 255, 255, 50))

    # Label (top)
    label_size = 28
    ls = measure_text_cached(font_normal, label, label_size)
    lx = x + (w - ls.x) / 2
    ly = y + h * 0.15
    rl.draw_text_ex(font_normal, label, rl.Vector2(lx, ly), label_size, 0, rl.Color(170, 170, 170, 255))

    # Value (center)
    val_size = 56
    vs = measure_text_cached(font_bold, value, val_size)
    vx = x + (w - vs.x) / 2
    vy = y + h * 0.45
    rl.draw_text_ex(font_bold, value, rl.Vector2(vx, vy), val_size, 0, rl.WHITE)

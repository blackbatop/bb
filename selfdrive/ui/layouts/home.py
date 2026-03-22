import json
import time
import datetime
import pyray as rl
from collections.abc import Callable
from enum import IntEnum
from openpilot.common.params import Params
from openpilot.selfdrive.ui.widgets.offroad_alerts import UpdateAlert, OffroadAlert
from openpilot.selfdrive.ui.widgets.exp_mode_button import ExperimentalModeButton
from openpilot.selfdrive.ui.widgets.prime import PrimeWidget
from openpilot.selfdrive.ui.widgets.setup import SetupWidget
from openpilot.selfdrive.ui.widgets.drive_summary import DriveSummary, RANDOM_EVENTS
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.lib.application import gui_app, FontWeight, MousePos
from openpilot.system.ui.lib.multilang import tr, trn
from openpilot.system.ui.widgets.label import gui_label
from openpilot.system.ui.widgets import Widget

HEADER_HEIGHT = 80
HEAD_BUTTON_FONT_SIZE = 40
CONTENT_MARGIN = 40
SPACING = 25
RIGHT_COLUMN_WIDTH = 750
REFRESH_INTERVAL = 10.0


class HomeLayoutState(IntEnum):
  HOME = 0
  UPDATE = 1
  ALERTS = 2


class HomeLayout(Widget):
  def __init__(self):
    super().__init__()
    self.params = Params()

    self.update_alert = UpdateAlert()
    self.offroad_alert = OffroadAlert()

    self._layout_widgets = {HomeLayoutState.UPDATE: self.update_alert, HomeLayoutState.ALERTS: self.offroad_alert}

    self.current_state = HomeLayoutState.HOME
    self.last_refresh = 0
    self.settings_callback: callable | None = None

    self.update_available = False
    self.alert_count = 0
    self._version_text = ""
    self._prev_update_available = False
    self._prev_alerts_present = False

    self.header_rect = rl.Rectangle(0, 0, 0, 0)
    self.content_rect = rl.Rectangle(0, 0, 0, 0)
    self.left_column_rect = rl.Rectangle(0, 0, 0, 0)
    self.right_column_rect = rl.Rectangle(0, 0, 0, 0)

    self.update_notif_rect = rl.Rectangle(0, 0, 200, HEADER_HEIGHT - 10)
    self.alert_notif_rect = rl.Rectangle(0, 0, 220, HEADER_HEIGHT - 10)

    self._prime_widget = PrimeWidget()
    self._setup_widget = SetupWidget()

    self._drive_summary = DriveSummary(show_random_events=False)
    self._random_events_summary = DriveSummary(show_random_events=True)
    self._drive_summary_active = False
    self._random_events_active = False
    self._last_onroad_stats: dict = {}

    ui_state.add_offroad_transition_callback(self._on_offroad_transition)

    self._exp_mode_button = ExperimentalModeButton()
    self._setup_callbacks()

  def show_event(self):
    self._exp_mode_button.show_event()
    self.last_refresh = time.monotonic()
    self._refresh()

  def _setup_callbacks(self):
    self.update_alert.set_dismiss_callback(lambda: self._set_state(HomeLayoutState.HOME))
    self.offroad_alert.set_dismiss_callback(lambda: self._set_state(HomeLayoutState.HOME))
    self._exp_mode_button.set_click_callback(lambda: self.settings_callback() if self.settings_callback else None)

  def _on_offroad_transition(self):
    """Called when transitioning from onroad to offroad."""
    raw = self.params.get("FrogPilotStats")
    if raw:
      try:
        current_stats = json.loads(raw)
        prev = self._last_onroad_stats or {}
        # Show drive summary if there's new drive data
        if current_stats.get("TrackedTime", 0) > prev.get("TrackedTime", 0):
          self._drive_summary.set_previous_stats(prev)
          self._drive_summary.show_event()
          self._drive_summary_active = True
          # Random events
          if ui_state.frogpilot_toggles.get("random_events", False):
            cur_ev = current_stats.get("RandomEvents", {})
            prev_ev = prev.get("RandomEvents", {})
            if any(cur_ev.get(k, 0) > prev_ev.get(k, 0) for k, _ in RANDOM_EVENTS):
              self._random_events_summary.set_previous_stats(prev)
              self._random_events_summary.show_event()
              self._random_events_active = True
        self._last_onroad_stats = dict(current_stats)
      except (json.JSONDecodeError, TypeError):
        pass

  def _dismiss_drive_summary(self):
    self._drive_summary_active = False
    self._random_events_active = False

  def set_settings_callback(self, callback: Callable):
    self.settings_callback = callback

  def _set_state(self, state: HomeLayoutState):
    # propagate show/hide events
    if state != self.current_state:
      if state == HomeLayoutState.HOME:
        self._exp_mode_button.show_event()

      if state in self._layout_widgets:
        self._layout_widgets[state].show_event()
      if self.current_state in self._layout_widgets:
        self._layout_widgets[self.current_state].hide_event()

    self.current_state = state

  def _render(self, rect: rl.Rectangle):
    current_time = time.monotonic()
    if current_time - self.last_refresh >= REFRESH_INTERVAL:
      self._refresh()
      self.last_refresh = current_time

    self._render_header()

    # Render content based on current state
    if self.current_state == HomeLayoutState.HOME:
      self._render_home_content()
    elif self.current_state == HomeLayoutState.UPDATE:
      self._render_update_view()
    elif self.current_state == HomeLayoutState.ALERTS:
      self._render_alerts_view()

  def _update_state(self):
    self.header_rect = rl.Rectangle(self._rect.x + CONTENT_MARGIN, self._rect.y + CONTENT_MARGIN, self._rect.width - 2 * CONTENT_MARGIN, HEADER_HEIGHT)

    content_y = self._rect.y + CONTENT_MARGIN + HEADER_HEIGHT + SPACING
    content_height = self._rect.height - CONTENT_MARGIN - HEADER_HEIGHT - SPACING - CONTENT_MARGIN

    self.content_rect = rl.Rectangle(self._rect.x + CONTENT_MARGIN, content_y, self._rect.width - 2 * CONTENT_MARGIN, content_height)

    left_width = self.content_rect.width - RIGHT_COLUMN_WIDTH - SPACING

    self.left_column_rect = rl.Rectangle(self.content_rect.x, self.content_rect.y, left_width, self.content_rect.height)

    self.right_column_rect = rl.Rectangle(self.content_rect.x + left_width + SPACING, self.content_rect.y, RIGHT_COLUMN_WIDTH, self.content_rect.height)

    self.update_notif_rect.x = self.header_rect.x
    self.update_notif_rect.y = self.header_rect.y + (self.header_rect.height - 60) // 2

    notif_x = self.header_rect.x + (220 if self.update_available else 0)
    self.alert_notif_rect.x = notif_x
    self.alert_notif_rect.y = self.header_rect.y + (self.header_rect.height - 60) // 2

  def _handle_mouse_release(self, mouse_pos: MousePos):
    super()._handle_mouse_release(mouse_pos)

    # Dismiss drive summary on click anywhere in content area
    if self._drive_summary_active:
      if rl.check_collision_point_rec(mouse_pos, self.left_column_rect) or rl.check_collision_point_rec(mouse_pos, self.right_column_rect):
        self._dismiss_drive_summary()
      return

    if self.update_available and rl.check_collision_point_rec(mouse_pos, self.update_notif_rect):
      self._set_state(HomeLayoutState.UPDATE)
    elif self.alert_count > 0 and rl.check_collision_point_rec(mouse_pos, self.alert_notif_rect):
      self._set_state(HomeLayoutState.ALERTS)

  def _render_header(self):
    font = gui_app.font(FontWeight.MEDIUM)

    version_text_width = self.header_rect.width

    # FrogPilot: date display (left-aligned)
    date_text = datetime.datetime.now().strftime("%A, %B %-d")
    date_font = gui_app.font(FontWeight.NORMAL)
    date_size = 32
    date_ts = measure_text_cached(date_font, date_text, date_size)
    date_x = self.header_rect.x
    date_y = self.header_rect.y + (self.header_rect.height - date_ts.y) // 2
    rl.draw_text_ex(date_font, date_text, rl.Vector2(int(date_x), int(date_y)), date_size, 0, rl.Color(255, 255, 255, 150))

    # Update notification button
    if self.update_available:
      version_text_width -= self.update_notif_rect.width

      # Highlight if currently viewing updates
      highlight_color = rl.Color(75, 95, 255, 255) if self.current_state == HomeLayoutState.UPDATE else rl.Color(54, 77, 239, 255)
      rl.draw_rectangle_rounded(self.update_notif_rect, 0.3, 10, highlight_color)

      text = tr("UPDATE")
      text_size = measure_text_cached(font, text, HEAD_BUTTON_FONT_SIZE)
      text_x = self.update_notif_rect.x + (self.update_notif_rect.width - text_size.x) // 2
      text_y = self.update_notif_rect.y + (self.update_notif_rect.height - text_size.y) // 2
      rl.draw_text_ex(font, text, rl.Vector2(int(text_x), int(text_y)), HEAD_BUTTON_FONT_SIZE, 0, rl.WHITE)

    # Alert notification button
    if self.alert_count > 0:
      version_text_width -= self.alert_notif_rect.width

      # Highlight if currently viewing alerts
      highlight_color = rl.Color(255, 70, 70, 255) if self.current_state == HomeLayoutState.ALERTS else rl.Color(226, 44, 44, 255)
      rl.draw_rectangle_rounded(self.alert_notif_rect, 0.3, 10, highlight_color)

      alert_text = trn("{} ALERT", "{} ALERTS", self.alert_count).format(self.alert_count)
      text_size = measure_text_cached(font, alert_text, HEAD_BUTTON_FONT_SIZE)
      text_x = self.alert_notif_rect.x + (self.alert_notif_rect.width - text_size.x) // 2
      text_y = self.alert_notif_rect.y + (self.alert_notif_rect.height - text_size.y) // 2
      rl.draw_text_ex(font, alert_text, rl.Vector2(int(text_x), int(text_y)), HEAD_BUTTON_FONT_SIZE, 0, rl.WHITE)

    # Version text (right aligned)
    if self.update_available or self.alert_count > 0:
      version_text_width -= SPACING * 1.5

    version_rect = rl.Rectangle(
      self.header_rect.x + self.header_rect.width - version_text_width, self.header_rect.y, version_text_width, self.header_rect.height
    )
    gui_label(version_rect, self._version_text, 48, rl.WHITE, alignment=rl.GuiTextAlignment.TEXT_ALIGN_RIGHT)

  def _render_home_content(self):
    self._render_left_column()
    self._render_right_column()

  def _render_update_view(self):
    self.update_alert.render(self.content_rect)

  def _render_alerts_view(self):
    self.offroad_alert.render(self.content_rect)

  def _render_left_column(self):
    if self._drive_summary_active:
      self._drive_summary.render(self.left_column_rect)
    else:
      self._prime_widget.render(self.left_column_rect)
      self._render_frogpilot_stats()

  def _render_right_column(self):
    if self._random_events_active:
      self._random_events_summary.render(self.right_column_rect)
      return

    exp_height = 125
    exp_rect = rl.Rectangle(self.right_column_rect.x, self.right_column_rect.y, self.right_column_rect.width, exp_height)
    self._exp_mode_button.render(exp_rect)

    setup_rect = rl.Rectangle(
      self.right_column_rect.x,
      self.right_column_rect.y + exp_height + SPACING,
      self.right_column_rect.width,
      self.right_column_rect.height - exp_height - SPACING,
    )
    self._setup_widget.render(setup_rect)

  def _render_frogpilot_stats(self):
    """Render FrogPilot lifetime stats (Drives/Distance/Hours) at bottom of left column."""
    raw = self.params.get("FrogPilotStats")
    if not raw:
      return
    try:
      stats = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
      return

    drives = stats.get("FrogPilotDrives", 0)
    meters = stats.get("FrogPilotMeters", 0)
    hours = int(stats.get("FrogPilotSeconds", 0) / 3600)

    if ui_state.is_metric:
      dist_str = f"{meters / 1000:.0f} km"
    else:
      dist_str = f"{meters * 0.000621371:.0f} mi"

    font = gui_app.font(FontWeight.NORMAL)
    label_size = 24
    val_size = 36
    green = rl.Color(0x17, 0x86, 0x44, 255)

    # Position at bottom of left column
    y = self.left_column_rect.y + self.left_column_rect.height - 100
    x = self.left_column_rect.x
    col_w = self.left_column_rect.width / 3

    stats_data = [("Drives", str(drives)), ("Distance", dist_str), ("Hours", str(hours))]

    for i, (label, value) in enumerate(stats_data):
      cx = x + col_w * i + col_w / 2
      # Value
      vs = measure_text_cached(font, value, val_size)
      rl.draw_text_ex(font, value, rl.Vector2(cx - vs.x / 2, y), val_size, 0, rl.WHITE)
      # Label
      ls = measure_text_cached(font, label, label_size)
      rl.draw_text_ex(font, label, rl.Vector2(cx - ls.x / 2, y + val_size + 5), label_size, 0, green)

  def _refresh(self):
    self._version_text = self._get_version_text()
    update_available = self.update_alert.refresh()
    alert_count = self.offroad_alert.refresh()
    alerts_present = alert_count > 0

    # Show panels on transition from no alert/update to any alerts/update
    if not update_available and not alerts_present:
      self._set_state(HomeLayoutState.HOME)
    elif update_available and ((not self._prev_update_available) or (not alerts_present and self.current_state == HomeLayoutState.ALERTS)):
      self._set_state(HomeLayoutState.UPDATE)
    elif alerts_present and ((not self._prev_alerts_present) or (not update_available and self.current_state == HomeLayoutState.UPDATE)):
      self._set_state(HomeLayoutState.ALERTS)

    self.update_available = update_available
    self.alert_count = alert_count
    self._prev_update_available = update_available
    self._prev_alerts_present = alerts_present

  def _get_version_text(self) -> str:
    brand = "openpilot"
    description = self.params.get("UpdaterCurrentDescription")
    return f"{brand} {description}" if description else brand

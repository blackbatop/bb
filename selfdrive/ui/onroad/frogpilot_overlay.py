import colorsys
import json
import math
import time
import pyray as rl
from dataclasses import dataclass
from cereal import log
from openpilot.common.params import Params
from openpilot.selfdrive.ui import UI_BORDER_SIZE
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.selfdrive.ui.onroad.gif_player import load_starpilot_asset
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets import Widget

MS_TO_MPH = 2.23694
MS_TO_KPH = 3.6
METER_TO_FOOT = 3.28084

# Asset sizes for rendering
_ASSET_SIZE = 200  # Native pixel size of FrogPilot PNG/GIF assets
_ICON_SIZE = 60  # Small icon size for speed limit sources
_SIGN_ASSET_SIZE = 150  # Size for speed limit sign assets

# Speed limit sign dimensions (screen pixels)
_US_SIGN_HEIGHT = 186
_EU_SIGN_SIZE = 176
_SIGN_MARGIN = 12

# Bottom bar widget size
_WIDGET_SIZE = 159  # img_size(144) + UI_BORDER_SIZE(30)/2

# Curve speed box dimensions
_CSC_SIZE = 130

# Standstill timer thresholds (seconds)
_STANDSTILL_GREEN = 60
_STANDSTILL_ORANGE = 150
_STANDSTILL_RED = 300

# Border colors matching QT bg_colors (selfdrive/ui/ui.h)
_GREEN = rl.Color(0x17, 0x86, 0x44, 0xF1)  # STATUS_ENGAGED (23, 134, 68, 241)
_YELLOW = rl.Color(0xFF, 0xFF, 0x00, 0xF1)  # STATUS_CEM_DISABLED (255, 255, 0, 241)
_ORANGE = rl.Color(0xDA, 0x6F, 0x25, 0xF1)  # STATUS_EXPERIMENTAL_MODE_ENABLED (218, 111, 37, 241)
_RED = rl.Color(0xC9, 0x22, 0x31, 0xF1)  # STATUS_TRAFFIC_MODE_ENABLED (201, 34, 49, 241)
_TEAL = rl.Color(0x0A, 0xBA, 0xB5, 0xF1)  # STATUS_ALWAYS_ON_LATERAL_ACTIVE (10, 186, 181, 241)

_BLACK_T = rl.Color(0, 0, 0, 166)  # Translucent black background
_WHITE = rl.WHITE


@dataclass
class Stopwatch:
  _start: float = -1.0

  def start(self):
    if self._start < 0:
      self._start = time.monotonic()

  def stop(self):
    self._start = -1.0

  @property
  def running(self) -> bool:
    return self._start >= 0

  @property
  def elapsed_ms(self) -> float:
    if self._start < 0:
      return 0
    return (time.monotonic() - self._start) * 1000.0

  @property
  def elapsed_s(self) -> float:
    if self._start < 0:
      return 0
    return time.monotonic() - self._start


class FrogPilotOverlay(Widget):
  """All 27 StarPilot onroad overlay features."""

  def __init__(self, model_renderer, hud_renderer, driver_state_renderer):
    super().__init__()
    self._model = model_renderer
    self._hud = hud_renderer
    self._dm = driver_state_renderer
    self._params_memory = Params(memory=True)

    # Toggles cache
    self._toggles: dict = {}

    # GPS cache (avoids per-frame json.loads in compass)
    self._cached_gps_raw: bytes = b""
    self._cached_bearing: int = 0

    # Pre-computed gradient constants (avoids per-frame allocation)
    from openpilot.system.ui.lib.shader_polygon import Gradient

    self._blind_spot_gradient = Gradient(
      start=(0.0, 1.0),
      end=(0.0, 0.0),
      colors=[rl.Color(201, 34, 49, 102), rl.Color(201, 34, 49, 89), rl.Color(201, 34, 49, 0)],
      stops=[0.0, 0.5, 1.0],
    )

    # Speed limit state
    self._speed_limit: float = 0
    self._speed_limit_str: str = "–"
    self._speed_limit_offset_str: str = "–"
    self._slc_overridden_speed: float = 0
    self._speed_limit_changed: bool = False
    self._unconfirmed_speed: float = 0
    self._speed_limit_source: str = ""
    self._dashboard_sl: float = 0
    self._map_sl: float = 0
    self._mapbox_sl: float = 0
    self._next_sl: float = 0
    self._speed_limit_rect = rl.Rectangle(0, 0, 0, 0)

    # Curve speed state
    self._csc_controlling: bool = False
    self._csc_speed: float = 0
    self._csc_training: bool = False
    self._road_curvature: float = 0

    # Turn signal state
    self._blinker_left: bool = False
    self._blinker_right: bool = False
    self._blindspot_left: bool = False
    self._blindspot_right: bool = False
    self._signal_style: str = "None"
    self._signal_anim_frame: int = 0
    self._signal_anim_tick: float = 0
    self._signal_anim_length: float = 0.05

    # Bottom bar state
    self._lateral_paused: bool = False
    self._longitudinal_paused: bool = False
    self._force_coast: bool = False
    self._weather_id: int = 0
    self._weather_daytime: bool = True
    self._road_name: str = ""
    self._hide_bottom_icons: bool = False

    # Standstill timer
    self._standstill_timer = Stopwatch()
    self._standstill_duration: int = 0

    # Stopping point
    self._red_light: bool = False
    self._stopping_distance: float = 0

    # Pending speed limit
    self._pending_timer = Stopwatch()

    # CSC glow animation
    self._glow_timer = Stopwatch()

    # Pedal state
    self._acceleration_ego: float = 0
    self._brake_lights: bool = False

    # Speed conversion
    self._speed_conversion: float = MS_TO_MPH
    self._speed_unit: str = "mph"
    self._distance_conversion: float = METER_TO_FOOT
    self._distance_unit: str = " feet"
    self._speed: float = 0
    self._is_cruise_set: bool = False

    # FPS tracking
    from collections import deque

    self._fps_times: deque = deque(maxlen=60)
    self._fps_last_time: float = 0.0

    # Steering torque
    self._torque: float = 0
    self._smoothed_torque: float = 0

    # GIF players (lazily loaded)
    self._gif_cem_curve = None
    self._gif_cem_lead = None
    self._gif_cem_speed = None
    self._gif_cem_stop = None
    self._gif_cem_turn = None
    self._gif_chill = None
    self._gif_experimental = None
    self._gif_weather_day = None
    self._gif_weather_night = None
    self._gif_weather_rain = None
    self._gif_weather_snow = None
    self._gif_weather_fog = None
    self._gif_signal_left = None
    self._gif_signal_right = None

    # Static textures (lazily loaded)
    self._tex_brake_pedal = None
    self._tex_gas_pedal = None
    self._tex_curve_speed = None
    self._tex_stop_sign = None
    self._tex_paused = None
    self._tex_speed_icon = None
    self._tex_turn_icon = None
    self._tex_dashboard_icon = None
    self._tex_mapbox_icon = None
    self._tex_map_data_icon = None
    self._tex_next_maps_icon = None

    # Personality button textures (lazily loaded)
    self._tex_traffic = None
    self._tex_aggressive = None
    self._tex_standard = None
    self._tex_relaxed = None

    # Font cache
    self._font_bold = gui_app.font(FontWeight.BOLD)
    self._font_semi = gui_app.font(FontWeight.SEMI_BOLD)
    self._font_demi = gui_app.font(FontWeight.NORMAL)

    # Constants
    self._btn_size = 192

  # --- Asset loading ---

  def _ensure_assets(self):
    """Lazily load all assets on first render."""
    if self._tex_brake_pedal is not None:
      return
    self._tex_brake_pedal = gui_app.starpilot_texture("other_images/brake_pedal.png", self._btn_size, self._btn_size)
    self._tex_gas_pedal = gui_app.starpilot_texture("other_images/gas_pedal.png", self._btn_size, self._btn_size)
    self._tex_curve_speed = gui_app.starpilot_texture("other_images/curve_speed.png", self._btn_size, self._btn_size)
    self._tex_stop_sign = gui_app.starpilot_texture("other_images/stop_sign.png", self._btn_size, self._btn_size)
    self._tex_paused = gui_app.starpilot_texture("other_images/paused_icon.png", _WIDGET_SIZE, _WIDGET_SIZE)
    self._tex_speed_icon = gui_app.starpilot_texture("other_images/speed_icon.png", _WIDGET_SIZE, _WIDGET_SIZE)
    self._tex_turn_icon = gui_app.starpilot_texture("other_images/turn_icon.png", _WIDGET_SIZE, _WIDGET_SIZE)
    self._tex_dashboard_icon = gui_app.starpilot_texture("other_images/dashboard_icon.png", _ICON_SIZE, _ICON_SIZE)
    self._tex_mapbox_icon = gui_app.starpilot_texture("other_images/mapbox_icon.png", _ICON_SIZE, _ICON_SIZE)
    self._tex_map_data_icon = gui_app.starpilot_texture("other_images/offline_maps_icon.png", _ICON_SIZE, _ICON_SIZE)
    self._tex_next_maps_icon = gui_app.starpilot_texture("other_images/offline_maps_icon.png", _ICON_SIZE, _ICON_SIZE)
    self._tex_next_maps_icon = gui_app.starpilot_texture("other_images/next_maps_icon.png", _ICON_SIZE, _ICON_SIZE)

    # Personality button icons
    self._tex_traffic = gui_app.starpilot_texture("active_theme/distance_icons/traffic.png", self._btn_size, self._btn_size)
    self._tex_aggressive = gui_app.starpilot_texture("active_theme/distance_icons/aggressive.png", self._btn_size, self._btn_size)
    self._tex_standard = gui_app.starpilot_texture("active_theme/distance_icons/standard.png", self._btn_size, self._btn_size)
    self._tex_relaxed = gui_app.starpilot_texture("active_theme/distance_icons/relaxed.png", self._btn_size, self._btn_size)

    # GIF players
    self._gif_cem_curve = load_starpilot_asset("other_images/curve_icon.gif", _WIDGET_SIZE)
    self._gif_cem_lead = load_starpilot_asset("other_images/lead_icon.gif", _WIDGET_SIZE)
    self._gif_cem_speed = load_starpilot_asset("other_images/speed_icon.gif", _WIDGET_SIZE)
    self._gif_cem_stop = load_starpilot_asset("other_images/light_icon.gif", _WIDGET_SIZE)
    self._gif_cem_turn = load_starpilot_asset("other_images/turn_icon.gif", _WIDGET_SIZE)
    self._gif_chill = load_starpilot_asset("other_images/chill_mode_icon.gif", _WIDGET_SIZE)
    self._gif_experimental = load_starpilot_asset("other_images/experimental_mode_icon.gif", _WIDGET_SIZE)
    self._gif_weather_day = load_starpilot_asset("other_images/weather_clear_day.gif", _WIDGET_SIZE)
    self._gif_weather_night = load_starpilot_asset("other_images/weather_clear_night.gif", _WIDGET_SIZE)
    self._gif_weather_rain = load_starpilot_asset("other_images/weather_rain.gif", _WIDGET_SIZE)
    self._gif_weather_snow = load_starpilot_asset("other_images/weather_snow.gif", _WIDGET_SIZE)
    self._gif_weather_fog = load_starpilot_asset("other_images/weather_low_visibility.gif", _WIDGET_SIZE)

    # Start all GIF animations
    for gif in [
      self._gif_cem_curve,
      self._gif_cem_lead,
      self._gif_cem_speed,
      self._gif_cem_stop,
      self._gif_cem_turn,
      self._gif_chill,
      self._gif_experimental,
      self._gif_weather_day,
      self._gif_weather_night,
      self._gif_weather_rain,
      self._gif_weather_snow,
      self._gif_weather_fog,
    ]:
      gif.play()

  # --- State update ---

  def _update_state(self):
    sm = ui_state.sm
    new_toggles = ui_state.frogpilot_toggles
    if new_toggles is not self._toggles:
      self._toggles = new_toggles

    # Speed/distance units
    if ui_state.is_metric or self._toggles.get("use_si_metrics", False):
      self._speed_conversion = 1.0 if self._toggles.get("use_si_metrics", False) else MS_TO_KPH
      self._speed_unit = " m/s" if self._toggles.get("use_si_metrics", False) else ("km/h" if ui_state.is_metric else "mph")
      self._distance_conversion = 1.0
      self._distance_unit = " meters"
      if not ui_state.is_metric and not self._toggles.get("use_si_metrics", False):
        self._speed_conversion = MS_TO_MPH
        self._speed_unit = "mph"
    else:
      self._speed_conversion = MS_TO_MPH
      self._speed_unit = "mph"
      self._distance_conversion = METER_TO_FOOT
      self._distance_unit = " feet"

    # Car state
    car_state = sm["carState"]
    self._speed = max(0.0, car_state.vEgo * self._speed_conversion)
    self._blinker_left = car_state.leftBlinker
    self._blinker_right = car_state.rightBlinker
    self._blindspot_left = car_state.leftBlindspot
    self._blindspot_right = car_state.rightBlindspot
    self._acceleration_ego = car_state.aEgo

    # Cruise state
    controls = sm["controlsState"]
    v_cruise = car_state.vCruiseCluster
    set_speed = controls.vCruiseDEPRECATED if v_cruise == 0.0 else v_cruise
    self._is_cruise_set = 0 < set_speed < 255

    # FrogPilot plan data
    fp_plan = ui_state.frogpilot_plan
    if fp_plan is not None:
      slc_overridden = fp_plan.slcOverriddenSpeed
      self._slc_overridden_speed = slc_overridden
      raw_limit = slc_overridden if slc_overridden != 0 else fp_plan.slcSpeedLimit
      if slc_overridden == 0 and not self._toggles.get("show_speed_limit_offset", False):
        raw_limit += fp_plan.slcSpeedLimitOffset
      raw_limit *= MS_TO_KPH if ui_state.is_metric else MS_TO_MPH
      self._speed_limit = raw_limit
      self._speed_limit_str = str(round(raw_limit)) if raw_limit > 1 else "–"

      offset_val = fp_plan.slcSpeedLimitOffset * self._speed_conversion
      if offset_val != 0:
        sign = "+" if offset_val > 0 else "-"
        self._speed_limit_offset_str = f"{sign}{abs(round(offset_val))}"
      else:
        self._speed_limit_offset_str = "–"

      self._speed_limit_changed = fp_plan.speedLimitChanged
      self._unconfirmed_speed = fp_plan.unconfirmedSlcSpeedLimit
      if self._unconfirmed_speed > 1:
        self._unconfirmed_speed *= MS_TO_KPH if ui_state.is_metric else MS_TO_MPH
      self._speed_limit_source = fp_plan.slcSpeedLimitSource
      self._map_sl = fp_plan.slcMapSpeedLimit
      self._mapbox_sl = fp_plan.slcMapboxSpeedLimit
      self._next_sl = fp_plan.slcNextSpeedLimit
      if not ui_state.is_metric:
        self._map_sl *= MS_TO_MPH
        self._mapbox_sl *= MS_TO_MPH
        self._next_sl *= MS_TO_MPH
      else:
        self._map_sl *= MS_TO_KPH
        self._mapbox_sl *= MS_TO_KPH
        self._next_sl *= MS_TO_KPH

      # Curve speed
      self._csc_controlling = fp_plan.cscControllingSpeed
      self._csc_speed = fp_plan.cscSpeed
      self._csc_training = fp_plan.cscTraining
      self._road_curvature = fp_plan.roadCurvature

      # Road name
      try:
        self._road_name = sm["mapdOut"].roadName if sm.valid.get("mapdOut", False) else ""
      except Exception:
        self._road_name = ""

      # Weather
      self._weather_id = fp_plan.weatherId
      self._weather_daytime = fp_plan.weatherDaytime

      # Stopping
      self._red_light = fp_plan.redLight
      model = sm["modelV2"]
      pos_x = model.position.x
      self._stopping_distance = pos_x[32] if len(pos_x) > 32 else 0.0

    # FrogPilot car state
    if sm.valid.get("frogpilotCarState", False):
      fp_cs = sm["frogpilotCarState"]
      self._lateral_paused = fp_cs.pauseLateral
      self._longitudinal_paused = fp_cs.pauseLongitudinal
      self._force_coast = fp_cs.forceCoast
      self._brake_lights = fp_cs.brakeLights
      self._dashboard_sl = fp_cs.dashboardSpeedLimit * self._speed_conversion
    else:
      self._lateral_paused = False
      self._longitudinal_paused = False
      self._force_coast = False
      self._brake_lights = False

    # Torque (from carControl)
    if sm.valid.get("carControl", False):
      self._torque = -sm["carControl"].actuators.torque
      abs_t = abs(self._torque)
      self._smoothed_torque = 0.25 * abs_t + 0.75 * self._smoothed_torque
      if abs(self._smoothed_torque - abs_t) < 0.01:
        self._smoothed_torque = abs_t

    # Hide bottom icons when alerts are showing
    ss_alert = sm["selfdriveState"].alertSize
    self._hide_bottom_icons = ss_alert != log.SelfdriveState.AlertSize.none
    if sm.valid.get("frogpilotSelfdriveState", False):
      fp_alert = sm["frogpilotSelfdriveState"].alertSize
      self._hide_bottom_icons |= fp_alert != log.FrogPilotSelfdriveState.AlertSize.none
    self._hide_bottom_icons |= self._signal_style.startswith("traditional") and (self._blinker_left or self._blinker_right)

    # Standstill timer
    is_standstill = car_state.standstill
    if is_standstill and self._toggles.get("stopped_timer", False):
      self._standstill_timer.start()
      self._standstill_duration = int(self._standstill_timer.elapsed_s)
    else:
      self._standstill_timer.stop()
      self._standstill_duration = 0

    # Pending speed limit timer
    if self._speed_limit_changed:
      self._pending_timer.start()
    else:
      self._pending_timer.stop()

    # CSC training glow
    if self._csc_training:
      self._glow_timer.start()
    else:
      self._glow_timer.stop()

    # Signal animation
    if (self._blinker_left or self._blinker_right) and self._signal_style != "None":
      now = time.monotonic()
      if now - self._signal_anim_tick >= self._signal_anim_length:
        self._signal_anim_frame += 1
        self._signal_anim_tick = now
    else:
      self._signal_anim_frame = 0

  # --- Main render ---

  def _render(self, rect: rl.Rectangle):
    if not ui_state.started:
      return
    self._ensure_assets()

    t = self._toggles

    # Bottom bar icons (ordered by position cascade)
    if not self._hide_bottom_icons and t.get("cem_status", False):
      self._draw_cem_status()

    if not self._hide_bottom_icons and t.get("compass", False):
      self._draw_compass()

    if t.get("csc_status", False) and not self._speed_limit_changed:
      if self._csc_training:
        self._draw_curve_speed_training()
      elif self._is_cruise_set and self._csc_controlling:
        self._draw_curve_speed()

    if not self._hide_bottom_icons and self._lateral_paused:
      self._draw_lateral_paused()

    if not self._hide_bottom_icons and (self._force_coast or self._longitudinal_paused):
      self._draw_longitudinal_paused()

    if t.get("pedals_on_ui", False):
      self._draw_pedal_icons()

    if self._speed_limit_changed:
      self._draw_pending_speed_limit()

    if t.get("radar_tracks", False):
      self._draw_radar_tracks()

    if t.get("road_name_ui", False):
      self._draw_road_name()

    hide_sl = not self._speed_limit_changed and t.get("hide_speed_limit", False)
    if not hide_sl and (t.get("show_speed_limits", False) or t.get("speed_limit_controller", False)):
      self._draw_speed_limit()
    else:
      self._speed_limit_rect = rl.Rectangle(0, 0, 0, 0)

    if t.get("speed_limit_sources", False):
      self._draw_speed_limit_sources()

    if self._standstill_duration != 0:
      self._draw_standstill_timer()

    if t.get("show_stopping_point", False) and self._red_light:
      self._draw_stopping_point()

    if (self._blinker_left or self._blinker_right) and self._signal_style != "None":
      self._draw_turn_signals()

    if not self._hide_bottom_icons:
      self._draw_weather()

    # Border effects
    if t.get("steering_metrics", False):
      self._draw_steering_torque_border(rect)

    if t.get("signal_metrics", False) or t.get("blind_spot_metrics", False):
      self._draw_turn_signal_border(rect)

    # FPS
    if t.get("show_fps", False):
      self._draw_fps(rect)

    # Lead metrics text
    if t.get("lead_info", False):
      self._draw_lead_metrics()

    # Driving personality button
    if t.get("onroad_distance_button", False):
      self._draw_driving_personality_button()

  # --- Mouse handling for pending speed limit ---

  def _handle_mouse_release(self, mouse_pos):
    if self._speed_limit_changed and self._speed_limit_rect.width > 0:
      if rl.check_collision_point_rec(mouse_pos, self._speed_limit_rect):
        self._params_memory.put_bool("SpeedLimitAccepted", True)

  # --- Drawing helpers ---

  def _draw_rounded_box(self, x, y, w, h, radius=24, bg=None, border_color=None, border_width=10):
    """Draw a rounded rectangle with optional border."""
    r = rl.Rectangle(x, y, w, h)
    if bg:
      rl.draw_rectangle_rounded(r, 0.15, 10, bg)
    if border_color:
      rl.draw_rectangle_rounded_lines_ex(r, 0.15, 10, border_width, border_color)

  def _draw_text_outlined(self, text, x, y, font, size, color, outline_color=rl.BLACK, outline_w=3):
    """Draw text with a dark outline for readability."""
    rl.draw_text_ex(font, text, rl.Vector2(x + outline_w, y + outline_w), size, 0, outline_color)
    rl.draw_text_ex(font, text, rl.Vector2(x, y), size, 0, color)

  def _draw_texture_centered(self, tex, cx, cy):
    """Draw a texture centered at (cx, cy)."""
    rl.draw_texture(tex, int(cx - tex.width / 2), int(cy - tex.height / 2), _WHITE)

  def _draw_texture_in_box(self, tex, box_x, box_y, box_w, box_h):
    """Draw a texture centered within a box."""
    self._draw_texture_centered(tex, box_x + box_w / 2, box_y + box_h / 2)

  # --- Feature 1: Speed Limit Sign ---

  def _draw_speed_limit(self):
    ssr = self._hud.set_speed_rect
    if ssr.width <= 0:
      return

    # Translate from content-local to screen-absolute
    ox, oy = self._rect.x, self._rect.y
    is_us = not self._toggles.get("speed_limit_vienna", False)
    sl_str = self._speed_limit_str

    if is_us:
      sign_h = _US_SIGN_HEIGHT
      sign_w = ssr.width - 2 * _SIGN_MARGIN
      sign_x = ox + ssr.x + _SIGN_MARGIN
      sign_y = oy + ssr.y + ssr.height - sign_h - _SIGN_MARGIN
    else:
      sign_h = _EU_SIGN_SIZE
      sign_w = sign_h
      sign_x = ox + ssr.x + (ssr.width - sign_w) / 2
      sign_y = oy + ssr.y + ssr.height - sign_h - _SIGN_MARGIN

    self._speed_limit_rect = rl.Rectangle(sign_x, sign_y, sign_w, sign_h)
    is_override = self._slc_overridden_speed != 0
    alpha_mult = 0.25 if is_override else 1.0

    if is_us:
      # US style: white rect with black inner border
      rl.draw_rectangle_rounded(self._speed_limit_rect, 0.15, 10, rl.WHITE)
      rl.draw_rectangle_rounded_lines_ex(self._speed_limit_rect, 0.15, 10, 6, rl.Color(0, 0, 0, int(255 * alpha_mult)))

      show_offset = self._toggles.get("show_speed_limit_offset", False) and not is_override
      if show_offset:
        self._draw_label_centered("LIMIT", sign_x, sign_y + 22, sign_w, self._font_demi, 28, alpha_mult)
        self._draw_label_centered(sl_str, sign_x, sign_y + 51, sign_w, self._font_bold, 70, alpha_mult)
        self._draw_label_centered(self._speed_limit_offset_str, sign_x, sign_y + 120, sign_w, self._font_demi, 50, alpha_mult)
      else:
        self._draw_label_centered("SPEED", sign_x, sign_y + 22, sign_w, self._font_demi, 28, alpha_mult)
        self._draw_label_centered("LIMIT", sign_x, sign_y + 51, sign_w, self._font_demi, 28, alpha_mult)
        self._draw_label_centered(sl_str, sign_x, sign_y + 85, sign_w, self._font_bold, 70, alpha_mult)
    else:
      # EU style: white circle with red border
      center = rl.Vector2(sign_x + sign_w / 2, sign_y + sign_h / 2)
      rl.draw_circle(int(center.x), int(center.y), sign_w / 2, rl.WHITE)
      rl.draw_circle(int(center.x), int(center.y), sign_w / 2 - 16, rl.Color(201, 34, 49, int(255 * alpha_mult)))

      show_offset = self._toggles.get("show_speed_limit_offset", False) and not is_override
      if show_offset:
        self._draw_label_centered(sl_str, sign_x, sign_y + 20, sign_w, self._font_bold, 60, alpha_mult)
        self._draw_label_centered(self._speed_limit_offset_str, sign_x, sign_y + 100, sign_w, self._font_demi, 40, alpha_mult)
      else:
        self._draw_label_centered(sl_str, sign_x, sign_y, sign_w, self._font_bold, 70, alpha_mult)

  def _draw_label_centered(self, text, x, y, w, font, size, alpha_mult=1.0):
    ts = measure_text_cached(font, text, size)
    tx = x + (w - ts.x) / 2
    color = rl.Color(0, 0, 0, int(255 * alpha_mult))
    rl.draw_text_ex(font, text, rl.Vector2(tx, y), size, 0, color)

  # --- Feature 2: Pending Speed Limit ---

  def _draw_pending_speed_limit(self):
    if self._speed_limit_rect.width <= 0:
      self._draw_speed_limit()
    if self._speed_limit_rect.width <= 0:
      return

    psl = rl.Rectangle(
      self._speed_limit_rect.x + self._speed_limit_rect.width + _SIGN_MARGIN,
      self._speed_limit_rect.y,
      self._speed_limit_rect.width,
      self._speed_limit_rect.height,
    )
    is_vienna = self._toggles.get("speed_limit_vienna", False)
    pending_str = str(round(self._unconfirmed_speed)) if self._unconfirmed_speed > 1 else "–"

    # Blinking border: 500ms on/off
    blink_on = int(self._pending_timer.elapsed_ms) % 1000 < 500
    border_c = rl.Color(0, 0, 0, 255) if blink_on else rl.Color(201, 34, 49, 255)

    if not is_vienna:
      rl.draw_rectangle_rounded(psl, 0.15, 10, rl.WHITE)
      rl.draw_rectangle_rounded_lines_ex(psl, 0.15, 10, 6, border_c)
      self._draw_label_centered("PENDING", psl.x, psl.y + 22, psl.width, self._font_demi, 28)
      self._draw_label_centered("LIMIT", psl.x, psl.y + 51, psl.width, self._font_demi, 28)
      self._draw_label_centered(pending_str, psl.x, psl.y + 85, psl.width, self._font_bold, 70)
    else:
      center = rl.Vector2(psl.x + psl.width / 2, psl.y + psl.height / 2)
      rl.draw_circle(int(center.x), int(center.y), psl.width / 2, rl.WHITE)
      rl.draw_circle(int(center.x), int(center.y), psl.width / 2 - 16, rl.Color(201, 34, 49, 255))
      font_size = 60 if len(pending_str) >= 3 else 70
      self._draw_label_centered(pending_str, psl.x, psl.y + 20, psl.width, self._font_bold, font_size)

  # --- Feature 3: Speed Limit Sources ---

  def _draw_speed_limit_sources(self):
    if self._speed_limit_rect.width <= 0:
      return

    sx = self._speed_limit_rect.x - _SIGN_MARGIN
    sy = self._speed_limit_rect.y + self._speed_limit_rect.height + UI_BORDER_SIZE
    sw = 450
    sh = 60
    gap = UI_BORDER_SIZE / 2

    sources = [
      ("Dashboard", self._tex_dashboard_icon, self._dashboard_sl),
      ("Map Data", self._tex_map_data_icon, self._map_sl),
      ("Mapbox", self._tex_mapbox_icon, self._mapbox_sl),
      ("Upcoming", self._tex_next_maps_icon, self._next_sl),
    ]

    for i, (title, icon, speed_val) in enumerate(sources):
      ry = sy + i * (sh + gap)
      is_active = self._speed_limit_source == title and speed_val != 0
      bg_c = rl.Color(201, 34, 49, 166) if is_active else _BLACK_T
      self._draw_rounded_box(sx, ry, sw, sh, bg=bg_c, border_color=rl.Color(0, 0, 0, 0) if not is_active else rl.Color(201, 34, 49, 255))

      if icon:
        rl.draw_texture(icon, int(sx + 10), int(ry + (sh - icon.height) / 2), _WHITE)

      speed_text = f"{round(speed_val)} {self._speed_unit}" if speed_val != 0 else "N/A"
      full_text = f"{title} - {speed_text}"
      font = self._font_bold if is_active else self._font_demi
      fs = 35
      ts = measure_text_cached(font, full_text, fs)
      text_x = sx + _ICON_SIZE + 20
      text_y = ry + (sh - ts.y) / 2
      if is_active:
        self._draw_text_outlined(full_text, text_x, text_y, font, fs, _WHITE)
      else:
        rl.draw_text_ex(font, full_text, rl.Vector2(text_x, text_y), fs, 0, _WHITE)

  # --- Feature 5: Curve Speed Control ---

  def _draw_curve_speed(self):
    ssr = self._hud.set_speed_rect
    ox, oy = self._rect.x, self._rect.y
    csc_x = ox + ssr.x + ssr.width + UI_BORDER_SIZE
    csc_y = oy + ssr.y
    csc_w = _CSC_SIZE
    csc_h = _CSC_SIZE

    # Curve icon
    tex = self._tex_curve_speed
    if tex:
      if self._road_curvature >= 0:
        # Mirror horizontally for right curves
        src = rl.Rectangle(0, 0, -tex.width, tex.height)
        rl.draw_texture_rec(tex, src, rl.Vector2(csc_x, csc_y), _WHITE)
      else:
        self._draw_texture_in_box(tex, csc_x, csc_y, csc_w, csc_h)

    # Speed text box
    box_y = csc_y + csc_h + 10
    self._draw_rounded_box(csc_x, box_y, csc_w, 50, bg=rl.Color(0, 0, 255, 166), border_color=rl.Color(0, 0, 255, 255))
    csc_spd = min(self._speed, self._csc_speed * self._speed_conversion)
    text = f"{round(csc_spd)}{self._speed_unit}"
    rl.draw_text_ex(self._font_bold, text, rl.Vector2(csc_x + 20, box_y + 10), 45, 0, _WHITE)

  # --- Feature 6: Curve Speed Training ---

  def _draw_curve_speed_training(self):
    ssr = self._hud.set_speed_rect
    ox, oy = self._rect.x, self._rect.y
    csc_x = ox + ssr.x + ssr.width + UI_BORDER_SIZE
    csc_y = oy + ssr.y

    # Pulsing glow
    phase = (self._glow_timer.elapsed_ms % 2000) / 2000.0 * 2 * math.pi
    alpha_factor = 0.5 + 0.5 * math.sin(phase)
    glow_alpha = int(255 * (0.3 + 0.7 * alpha_factor))
    glow_w = 8 + int(2 * alpha_factor)
    glow_c = rl.Color(0, 0, 255, glow_alpha)

    # Box with glow border
    self._draw_rounded_box(csc_x, csc_y, _CSC_SIZE, _CSC_SIZE, bg=_BLACK_T, border_color=glow_c, border_width=glow_w)

    tex = self._tex_curve_speed
    if tex:
      if self._road_curvature >= 0:
        src = rl.Rectangle(0, 0, -tex.width, tex.height)
        rl.draw_texture_rec(tex, src, rl.Vector2(csc_x, csc_y), _WHITE)
      else:
        self._draw_texture_in_box(tex, csc_x, csc_y, _CSC_SIZE, _CSC_SIZE)

    # Training label
    box_y = csc_y + _CSC_SIZE + 10
    self._draw_rounded_box(csc_x, box_y, _CSC_SIZE, 40, bg=_BLACK_T)
    rl.draw_text_ex(self._font_bold, "Training...", rl.Vector2(csc_x + 20, box_y + 8), 35, 0, _WHITE)

  # --- Feature 7: Turn Signals ---

  def _draw_turn_signals(self):
    if self._standstill_duration != 0 and self._signal_style == "static":
      return

    content = self._rect
    is_left = self._blinker_left

    # Load signal images on first use
    if self._gif_signal_left is None:
      self._load_signal_images()

    # Determine which frames to use
    frames = self._gif_signal_left if is_left else self._gif_signal_right
    if not frames:
      # Fallback: use turn_icon as static
      tex = self._tex_turn_icon
      if not tex:
        return
      sx = content.x + (content.width * 0.375 - tex.width) if is_left else content.x + content.width * 0.625
      sy = content.y
      if self._signal_style == "static":
        sy += tex.height / 2
      else:
        sy += content.height - tex.height
      rl.draw_texture(tex, int(sx), int(sy), _WHITE)
      return

    frame_idx = self._signal_anim_frame % len(frames)
    tex = frames[frame_idx]

    if self._signal_style == "static":
      sx = content.x + (content.width * 0.375 - tex.width) if is_left else content.x + content.width * 0.625
      sy = content.y + tex.height / 2
    else:
      if is_left:
        sx = content.x + content.width - (frame_idx + 1) * tex.width
      else:
        sx = content.x + frame_idx * tex.width
      sy = content.y + content.height - tex.height

    rl.draw_texture(tex, int(sx), int(sy), _WHITE)

  def _load_signal_images(self):
    """Load theme-based signal images from active_theme/signals/."""
    self._gif_signal_left = []
    self._gif_signal_right = []
    try:
      from importlib.resources import files, as_file
      import os

      frogpilot_assets = files("openpilot.frogpilot").joinpath("assets")
      signals_dir = frogpilot_assets.joinpath("active_theme/signals")
      with as_file(signals_dir) as d:
        path = str(d)
        if os.path.isdir(path):
          files_list = sorted(os.listdir(path))
          for f in files_list:
            fp = os.path.join(path, f)
            if f.lower().endswith(".gif"):
              from openpilot.selfdrive.ui.onroad.gif_player import GifPlayer

              gp = GifPlayer(fp, _ASSET_SIZE)
              gp.play()
              for i in range(gp.frame_count):
                self._gif_signal_left.append(gp._frames[i])
              # Right = flipped (we'll just reuse left for now)
              self._gif_signal_right = self._gif_signal_left
              self._signal_style = "traditional_gif"
              self._signal_anim_length = 0.05
              return
            elif f.lower().endswith(".png"):
              from openpilot.selfdrive.ui.onroad.gif_player import StaticTexture

              st = StaticTexture(fp, _ASSET_SIZE)
              tex = st.current_texture()
              if tex:
                self._gif_signal_left.append(tex)
                self._gif_signal_right.append(tex)
              self._signal_style = "traditional"
            elif "_" in f:
              parts = f.split("_")
              if len(parts) == 2:
                self._signal_style = parts[0]
                try:
                  self._signal_anim_length = int(parts[1]) / 1000.0
                except ValueError:
                  pass
      if not self._gif_signal_left:
        self._signal_style = "None"
    except Exception:
      self._signal_style = "None"

  # --- Feature 8: Turn Signal Border ---

  def _draw_turn_signal_border(self, rect: rl.Rectangle):
    show_blindspot = (self._blindspot_left or self._blindspot_right) and self._toggles.get("blind_spot_metrics", False)
    show_signal = (self._blinker_left or self._blinker_right) and self._toggles.get("signal_metrics", False)

    if not show_blindspot and not show_signal:
      return

    flicker_on = int(time.monotonic() * 2) % 2 == 0  # ~500ms flicker

    def get_color(blindspot, turn_signal):
      if turn_signal and show_signal:
        if blindspot:
          return _RED if flicker_on else _YELLOW
        return _ORANGE if flicker_on else rl.Color(0, 0, 0, 0)
      elif blindspot and show_blindspot:
        return _RED
      return rl.Color(0, 0, 0, 0)

    left_c = get_color(self._blindspot_left, self._blinker_left)
    right_c = get_color(self._blindspot_right, self._blinker_right)

    half_w = rect.width / 2
    if left_c.a > 0:
      rl.draw_rectangle(int(rect.x), int(rect.y), int(half_w), int(rect.height), left_c)
    if right_c.a > 0:
      rl.draw_rectangle(int(rect.x + half_w), int(rect.y), int(half_w), int(rect.height), right_c)

  # --- Feature 9: Blind Spot Path ---

  def draw_blind_spot_path(self, left_vertices, right_vertices):
    if not self._toggles.get("blind_spot_path", False):
      return
    from openpilot.system.ui.lib.shader_polygon import draw_polygon

    if self._blindspot_left and left_vertices.size > 0:
      draw_polygon(self._rect, left_vertices, gradient=self._blind_spot_gradient)
    if self._blindspot_right and right_vertices.size > 0:
      draw_polygon(self._rect, right_vertices, gradient=self._blind_spot_gradient)

  # --- Feature 10: Adjacent Paths ---

  def draw_adjacent_paths(self, left_vertices, right_vertices, lane_width_left, lane_width_right):
    if not self._toggles.get("adjacent_path_metrics", False):
      return
    from openpilot.system.ui.lib.shader_polygon import draw_polygon, Gradient

    def paint_path(vertices, is_left, is_blindspot, lane_width):
      if lane_width == 0 or vertices.size == 0:
        return
      if is_blindspot and self._toggles.get("blind_spot_path", False):
        draw_polygon(self._rect, vertices, gradient=self._blind_spot_gradient)
      else:
        lane_det = self._toggles.get("lane_detection_width", 3.5)
        ratio = min(lane_width / max(lane_det, 0.1), 1.0)
        hue = (ratio * ratio) * (120.0 / 360.0)
        colors = [
          rl.Color(int(255 * hue), int(255 * (1 - hue)), 0, 102),
          rl.Color(int(255 * hue), int(255 * (1 - hue)), 0, 89),
          rl.Color(int(255 * hue), int(255 * (1 - hue)), 0, 0),
        ]
        g = Gradient(start=(0.0, 1.0), end=(0.0, 0.0), colors=colors, stops=[0.0, 0.5, 1.0])
        draw_polygon(self._rect, vertices, gradient=g)

      # Width text
      text = f"{lane_width * self._distance_conversion:.2f}{self._distance_unit}"
      mid = len(vertices) // 2
      anchor = vertices[mid // 2] if is_left else vertices[mid + (len(vertices) - mid) // 2]
      self._draw_text_outlined(text, anchor[0], anchor[1], self._font_demi, 45, _WHITE)

    paint_path(left_vertices, True, self._blindspot_left, lane_width_left)
    paint_path(right_vertices, False, self._blindspot_right, lane_width_right)

  # --- Feature 11: Compass ---

  def _draw_compass(self):
    dm_x, dm_y = self._dm.dm_icon_position
    if dm_x == 0 and dm_y == 0:
      return

    ox, oy = self._rect.x, self._rect.y
    rhd = self._dm.is_right_hand_drive
    compass_x = ox + (UI_BORDER_SIZE if rhd else (self._rect.width - UI_BORDER_SIZE - _WIDGET_SIZE))
    compass_y = oy + dm_y - _WIDGET_SIZE / 2

    # Draw background
    self._draw_rounded_box(compass_x, compass_y, _WIDGET_SIZE, _WIDGET_SIZE, bg=_BLACK_T, border_color=rl.BLACK)

    # Get bearing (cached — json.loads only when param changes)
    raw = self._params_memory.get("LastGPSPosition", b"{}") or b"{}"
    if raw != self._cached_gps_raw:
      self._cached_gps_raw = raw
      try:
        self._cached_bearing = round(json.loads(raw).get("bearing", 0.0)) % 360
      except (json.JSONDecodeError, TypeError):
        self._cached_bearing = 0
    bearing = self._cached_bearing

    # Simplified compass: draw cardinal direction text
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    dir_idx = round(bearing / 45) % 8
    label = directions[dir_idx]

    # Center triangle pointer
    tri_x = compass_x + _WIDGET_SIZE / 2
    tri_y = compass_y + _WIDGET_SIZE - 10
    rl.draw_triangle(
      rl.Vector2(tri_x, tri_y - 30),
      rl.Vector2(tri_x - 15, tri_y),
      rl.Vector2(tri_x + 15, tri_y),
      _WHITE,
    )

    # Direction label
    ts = measure_text_cached(self._font_bold, label, 65)
    rl.draw_text_ex(
      self._font_bold,
      label,
      rl.Vector2(
        compass_x + (_WIDGET_SIZE - ts.x) / 2,
        compass_y + (_WIDGET_SIZE - 40 - ts.y) / 2,
      ),
      65,
      0,
      _WHITE,
    )

  # --- Feature 12: Road Name ---

  def _draw_road_name(self):
    if not self._road_name:
      return
    ts = measure_text_cached(self._font_demi, self._road_name, 40)
    rw = ts.x + 100
    rh = 50
    rx = self._rect.x + (self._rect.width - rw) / 2
    ry = self._rect.y + self._rect.height - rh - 5
    self._draw_rounded_box(rx, ry, rw, rh, bg=_BLACK_T, border_color=rl.BLACK)
    rl.draw_text_ex(
      self._font_demi,
      self._road_name,
      rl.Vector2(
        rx + (rw - ts.x) / 2,
        ry + (rh - ts.y) / 2,
      ),
      40,
      0,
      _WHITE,
    )

  # --- Feature 13: Weather ---

  def _draw_weather(self):
    if self._weather_id == 0:
      return

    dm_x, dm_y = self._dm.dm_icon_position
    if dm_x == 0 and dm_y == 0:
      return

    # Position relative to compass or DM icon
    rhd = self._dm.is_right_hand_drive
    ox, oy = self._rect.x, self._rect.y
    wx = ox + (UI_BORDER_SIZE if rhd else (self._rect.width - UI_BORDER_SIZE - _WIDGET_SIZE))
    wy = oy + dm_y - _WIDGET_SIZE / 2

    # Offset from compass if visible
    if self._toggles.get("compass", False):
      wx += (_WIDGET_SIZE + UI_BORDER_SIZE) if rhd else -(_WIDGET_SIZE + UI_BORDER_SIZE)

    self._draw_rounded_box(wx, wy, _WIDGET_SIZE, _WIDGET_SIZE, bg=_BLACK_T, border_color=rl.BLACK)

    # Select weather GIF
    gif = self._gif_weather_day if self._weather_daytime else self._gif_weather_night
    wid = self._weather_id
    if 200 <= wid <= 232 or 300 <= wid <= 321 or 500 <= wid <= 531:
      gif = self._gif_weather_rain
    elif 600 <= wid <= 622:
      gif = self._gif_weather_snow
    elif 701 <= wid <= 762:
      gif = self._gif_weather_fog

    if gif:
      gif.update()
      tex = gif.current_texture()
      if tex:
        self._draw_texture_in_box(tex, wx, wy, _WIDGET_SIZE, _WIDGET_SIZE)

  # --- Feature 14: Standstill Timer ---

  def _draw_standstill_timer(self):
    dur = self._standstill_duration

    # Color transition
    if dur < _STANDSTILL_GREEN:
      color = _GREEN
    elif dur < _STANDSTILL_ORANGE:
      t = (dur - _STANDSTILL_GREEN) / (_STANDSTILL_ORANGE - _STANDSTILL_GREEN)
      color = rl.Color(
        int(_GREEN.r + t * (_ORANGE.r - _GREEN.r)),
        int(_GREEN.g + t * (_ORANGE.g - _GREEN.g)),
        int(_GREEN.b + t * (_ORANGE.b - _GREEN.b)),
        255,
      )
    elif dur < _STANDSTILL_RED:
      t = (dur - _STANDSTILL_ORANGE) / (_STANDSTILL_RED - _STANDSTILL_ORANGE)
      color = rl.Color(
        int(_ORANGE.r + t * (_RED.r - _ORANGE.r)),
        int(_ORANGE.g + t * (_RED.g - _ORANGE.g)),
        int(_ORANGE.b + t * (_RED.b - _ORANGE.b)),
        255,
      )
    else:
      color = _RED

    minutes = dur // 60
    seconds = dur % 60
    min_text = f"{minutes} minute{'s' if minutes != 1 else ''}"
    sec_text = f"{seconds} second{'s' if seconds != 1 else ''}"

    # Minutes - large centered text
    ts = measure_text_cached(self._font_bold, min_text, 176)
    self._draw_text_outlined(min_text, self._rect.x + (self._rect.width - ts.x) / 2, self._rect.y + 170, self._font_bold, 176, color)

    # Seconds - smaller text below
    ts2 = measure_text_cached(self._font_demi, sec_text, 66)
    self._draw_text_outlined(sec_text, self._rect.x + (self._rect.width - ts2.x) / 2, self._rect.y + 260, self._font_demi, 66, _WHITE)

  # --- Feature 15: Stopping Point ---

  def _draw_stopping_point(self):
    path_pts = self._model.path_points
    if path_pts.size < 2:
      return

    # Center of path front
    cx = (path_pts[0][0] + path_pts[-1][0]) / 2
    cy = (path_pts[0][1] + path_pts[-1][1]) / 2

    if self._tex_stop_sign:
      sx = cx - self._tex_stop_sign.width / 2
      sy = cy - self._tex_stop_sign.height
      rl.draw_texture(self._tex_stop_sign, int(sx), int(sy), _WHITE)

      if self._toggles.get("show_stopping_point_metrics", False):
        dist = self._stopping_distance * self._distance_conversion
        dist_text = f"{round(dist)}{self._distance_unit}"
        ts = measure_text_cached(self._font_demi, dist_text, 45)
        self._draw_text_outlined(dist_text, cx - ts.x / 2, sy - ts.y - 5, self._font_demi, 45, _WHITE)

  # --- Feature 16: CEM Status ---

  def _draw_cem_status(self):
    dm_x, dm_y = self._dm.dm_icon_position
    if dm_x == 0 and dm_y == 0:
      return

    ox, oy = self._rect.x, self._rect.y
    rhd = self._dm.is_right_hand_drive
    cem_x = ox + dm_x + (-_WIDGET_SIZE - _WIDGET_SIZE if rhd else _WIDGET_SIZE)
    cem_y = oy + dm_y - _WIDGET_SIZE / 2

    cond_status = ui_state.conditional_status
    exp_mode = ui_state.sm["selfdriveState"].experimentalMode

    # Border color
    if cond_status == 1:
      border_c = _YELLOW
    elif exp_mode:
      border_c = _ORANGE
    else:
      border_c = rl.BLACK

    self._draw_rounded_box(cem_x, cem_y, _WIDGET_SIZE, _WIDGET_SIZE, bg=rl.Color(0, 0, 0, 166), border_color=border_c, border_width=10)

    # Select icon
    gif = self._gif_chill
    if exp_mode:
      if cond_status == 1:
        gif = self._gif_chill
      elif cond_status == 2:
        gif = self._gif_experimental
      elif cond_status == 3:
        gif = self._gif_cem_curve
      elif cond_status == 4:
        gif = self._gif_cem_lead
      elif cond_status == 5:
        gif = self._gif_cem_turn
      elif cond_status in (6, 7):
        gif = self._gif_cem_speed
      elif cond_status == 8:
        gif = self._gif_cem_stop
      else:
        gif = self._gif_experimental

    if gif:
      gif.update()
      tex = gif.current_texture()
      if tex:
        self._draw_texture_in_box(tex, cem_x, cem_y, _WIDGET_SIZE, _WIDGET_SIZE)

  # --- Feature 17: Lateral Paused ---

  def _draw_lateral_paused(self):
    dm_x, dm_y = self._dm.dm_icon_position
    if dm_x == 0 and dm_y == 0:
      return

    ox, oy = self._rect.x, self._rect.y
    rhd = self._dm.is_right_hand_drive
    # Position after CEM status or next to DM icon
    if ui_state.conditional_status > 0:
      base_x = dm_x + (-_WIDGET_SIZE - _WIDGET_SIZE if rhd else _WIDGET_SIZE)
    else:
      base_x = dm_x
    lat_x = ox + base_x + (-UI_BORDER_SIZE - _WIDGET_SIZE - UI_BORDER_SIZE if rhd else UI_BORDER_SIZE + _WIDGET_SIZE + UI_BORDER_SIZE)
    lat_y = oy + dm_y - _WIDGET_SIZE / 2

    self._draw_rounded_box(lat_x, lat_y, _WIDGET_SIZE, _WIDGET_SIZE, bg=_BLACK_T, border_color=_ORANGE, border_width=10)

    if self._tex_turn_icon:
      rl.draw_texture(self._tex_turn_icon, int(lat_x), int(lat_y), rl.Color(255, 255, 255, 128))
    if self._tex_paused:
      rl.draw_texture(self._tex_paused, int(lat_x), int(lat_y), rl.Color(255, 255, 255, 191))

  # --- Feature 18: Longitudinal Paused ---

  def _draw_longitudinal_paused(self):
    dm_x, dm_y = self._dm.dm_icon_position
    if dm_x == 0 and dm_y == 0:
      return

    ox, oy = self._rect.x, self._rect.y
    rhd = self._dm.is_right_hand_drive
    # Position after lateral paused
    if self._lateral_paused:
      base_x = dm_x + (-UI_BORDER_SIZE - _WIDGET_SIZE - UI_BORDER_SIZE if rhd else UI_BORDER_SIZE + _WIDGET_SIZE + UI_BORDER_SIZE)
    elif ui_state.conditional_status > 0:
      base_x = dm_x + (-_WIDGET_SIZE - _WIDGET_SIZE if rhd else _WIDGET_SIZE)
    else:
      base_x = dm_x
    lon_x = ox + base_x + (-UI_BORDER_SIZE - _WIDGET_SIZE - UI_BORDER_SIZE if rhd else UI_BORDER_SIZE + _WIDGET_SIZE + UI_BORDER_SIZE)
    lon_y = oy + dm_y - _WIDGET_SIZE / 2

    self._draw_rounded_box(lon_x, lon_y, _WIDGET_SIZE, _WIDGET_SIZE, bg=_BLACK_T, border_color=_ORANGE, border_width=10)

    if self._tex_speed_icon:
      rl.draw_texture(self._tex_speed_icon, int(lon_x), int(lon_y), rl.Color(255, 255, 255, 128))
    if self._tex_paused:
      rl.draw_texture(self._tex_paused, int(lon_x), int(lon_y), rl.Color(255, 255, 255, 191))

  # --- Feature 19: Pedal Icons ---

  def _draw_pedal_icons(self):
    exp_r = self._hud.exp_button_rect
    ox, oy = self._rect.x, self._rect.y
    start_x = ox + exp_r.x
    start_y = oy + exp_r.y + exp_r.height + UI_BORDER_SIZE

    brake_opacity = 1.0
    gas_opacity = 1.0

    if self._toggles.get("dynamic_pedals_on_ui", False):
      is_standstill = self._standstill_duration > 0 or ui_state.sm["carState"].standstill
      brake_opacity = 1.0 if is_standstill else (max(0.25, abs(self._acceleration_ego)) if self._acceleration_ego < -0.25 else 0.25)
      gas_opacity = max(0.25, self._acceleration_ego)
    elif self._toggles.get("static_pedals_on_ui", False):
      is_standstill = self._standstill_duration > 0 or ui_state.sm["carState"].standstill
      brake_opacity = 1.0 if (is_standstill or self._brake_lights or self._acceleration_ego < -0.25) else 0.25
      gas_opacity = 1.0 if self._acceleration_ego > 0.25 else 0.25

    if self._tex_brake_pedal:
      rl.draw_texture(self._tex_brake_pedal, int(start_x), int(start_y), rl.Color(255, 255, 255, int(255 * brake_opacity)))
    if self._tex_gas_pedal:
      rl.draw_texture(self._tex_gas_pedal, int(start_x + self._btn_size / 2), int(start_y), rl.Color(255, 255, 255, int(255 * gas_opacity)))

  # --- Feature 20: FPS Counter ---

  def _draw_fps(self, rect: rl.Rectangle):
    now = time.monotonic()
    self._fps_times.append(now)
    if len(self._fps_times) < 2:
      return
    last_delta = self._fps_times[-1] - self._fps_times[-2]
    if last_delta <= 0:
      return
    fps_current = 1.0 / last_delta
    # Min/max over the deque (small fixed size, fast iteration)
    max_dt = 0.0
    min_dt = float("inf")
    for i in range(1, len(self._fps_times)):
      dt = self._fps_times[i] - self._fps_times[i - 1]
      if dt > 0:
        if dt > max_dt:
          max_dt = dt
        if dt < min_dt:
          min_dt = dt
    fps_min = 1.0 / max_dt if max_dt > 0 else 0
    fps_max = 1.0 / min_dt if min_dt < float("inf") else 0
    text = f"FPS: {fps_current:.0f} (min: {fps_min:.0f}, max: {fps_max:.0f})"
    ts = measure_text_cached(self._font_demi, text, 35)
    x = rect.x + (rect.width - ts.x) / 2
    y = rect.y + rect.height - ts.y - 5
    self._draw_text_outlined(text, x, y, self._font_demi, 35, _WHITE)

  # --- Feature 21: Steering Torque Border ---

  def _draw_steering_torque_border(self, rect: rl.Rectangle):
    torque_pct = min(abs(self._smoothed_torque) / 100.0, 1.0)
    if torque_pct < 0.01:
      return
    if torque_pct < 0.5:
      r = int(255 * (torque_pct * 2))
      g = 255
    else:
      r = 255
      g = int(255 * (1.0 - (torque_pct - 0.5) * 2))
    color = rl.Color(r, g, 0, 120)
    bw = UI_BORDER_SIZE
    rx, ry = int(rect.x), int(rect.y)
    rw, rh = int(rect.width), int(rect.height)
    rl.draw_rectangle(rx, ry, rw, bw, color)
    rl.draw_rectangle(rx, ry + rh - bw, rw, bw, color)
    rl.draw_rectangle(rx, ry, bw, rh, color)
    rl.draw_rectangle(rx + rw - bw, ry, bw, rh, color)

  # --- Feature 22: Radar Tracks ---

  def _draw_radar_tracks(self):
    sm = ui_state.sm
    if not sm.valid.get("liveTracks", False):
      return
    points = sm["liveTracks"].liveTracks.points
    if not points:
      return
    for pt in points:
      screen_pt = self._model.project_point(pt.dRel, -pt.yRel, 0)
      if screen_pt is not None:
        rl.draw_circle(int(screen_pt[0]), int(screen_pt[1]), 12.5, rl.Color(201, 34, 49, 255))

  # --- Feature 23: Lead Metrics ---

  def _draw_lead_metrics(self):
    """Draw lead distance, speed, and time gap below the lead chevron."""
    sm = ui_state.sm
    radar_state = sm["radarState"] if sm.valid.get("radarState", False) else None
    if not radar_state:
      return
    lead = radar_state.leadOne
    if not lead or not lead.status:
      return

    d_rel = lead.dRel  # meters
    v_rel = lead.vRel  # m/s
    car_state = sm["carState"]
    v_ego = car_state.vEgo

    # Time gap: distance / speed
    time_gap = d_rel / max(v_ego, 0.1)

    # Convert units
    if ui_state.is_metric:
      dist_text = f"{d_rel:.0f} m"
      speed_text = f"{v_rel * 3.6:.0f} km/h"
    else:
      dist_text = f"{d_rel * 3.281:.0f} ft"
      speed_text = f"{v_rel * 2.237:.0f} mph"
    gap_text = f"{time_gap:.1f} s"

    # Position below lead chevron
    sm = ui_state.sm
    live_calib = sm["liveCalibration"] if sm.valid.get("liveCalibration", False) else None
    z_offset = live_calib.height[0] if live_calib and live_calib.height else 1.22
    point = self._model.project_point(d_rel, 0, z_offset)
    if point is None:
      return

    ox, oy = self._rect.x, self._rect.y
    x = point[0] - ox
    y = point[1] - oy + 40  # Below chevron

    font = self._font_semi
    size = 28
    spacing = 4

    # Draw three metric texts
    texts = [dist_text, speed_text, gap_text]
    total_w = sum(measure_text_cached(font, t, size).x for t in texts) + spacing * (len(texts) - 1)
    start_x = x - total_w / 2

    for i, text in enumerate(texts):
      tw = measure_text_cached(font, text, size).x
      self._draw_text_outlined(text, start_x, y, font, size, _WHITE)
      start_x += tw + spacing

  # --- Feature 24: Path Edges ---

  def _draw_path_edges(self):
    """Draw colored path edge gradients based on conditional status.

    This renders a semi-transparent overlay on the path to indicate the active mode.
    The actual path edge polygon width is controlled by model_renderer via path_edge_width toggle.
    This method adds the color overlay.
    """
    points = self._model.path_points
    if points is None or len(points) == 0:
      return

    # Color based on conditional status
    cs = ui_state.conditional_status
    if ui_state.always_on_lateral_active:
      edge_color = rl.Color(0, 180, 180, 60)  # Teal for AOL
    elif cs >= 2:
      edge_color = rl.Color(255, 165, 0, 60)  # Orange for experimental
    elif cs >= 1:
      edge_color = rl.Color(255, 255, 0, 60)  # Yellow for CEM active
    elif ui_state.traffic_mode_enabled:
      edge_color = rl.Color(201, 34, 49, 60)  # Red for traffic
    else:
      return  # No overlay in default state

    from openpilot.system.ui.lib.shader_polygon import draw_polygon

    draw_polygon(self._rect, points, edge_color)

  # --- Feature 25: Rainbow Path ---

  def _draw_rainbow_path(self):
    """Draw rainbow gradient on path using speed-based HSL rotation."""
    from openpilot.system.ui.lib.shader_polygon import draw_polygon, Gradient

    points = self._model.path_points
    if points is None or len(points) == 0:
      return

    car_state = ui_state.sm["carState"]
    speed = abs(car_state.vEgo)  # m/s
    max_speed = 35.0  # ~80 mph
    t = min(speed / max_speed, 1.0)

    # Create rainbow gradient that shifts with speed
    n_stops = 5
    colors = []
    stops = []
    for i in range(n_stops):
      frac = i / (n_stops - 1)
      hue = (frac * 0.8 + t * 0.2) % 1.0  # Shift hue with speed
      r, g, b = colorsys.hls_to_rgb(hue, 0.5, 1.0)
      alpha = int(60 * (1.0 - frac * 0.5))  # Fade toward end
      colors.append(rl.Color(int(r * 255), int(g * 255), int(b * 255), alpha))
      stops.append(frac)

    gradient = Gradient(
      start=(0.0, 1.0),
      end=(0.0, 0.0),
      colors=colors,
      stops=stops,
    )
    draw_polygon(self._rect, points, gradient=gradient)

  # --- Feature 26: Driving Personality Button ---

  def _draw_driving_personality_button(self):
    """Draw 4-mode personality icon (traffic/aggressive/standard/relaxed) with themed icons."""
    if not ui_state.sm.valid.get("frogpilotCarState", False):
      return

    fp_cs = ui_state.sm["frogpilotCarState"]
    if fp_cs.trafficModeEnabled:
      tex = self._tex_traffic
    else:
      personality = ui_state.personality
      from cereal.log import LongitudinalPersonality

      if personality == LongitudinalPersonality.aggressive:
        tex = self._tex_aggressive
      elif personality == LongitudinalPersonality.relaxed:
        tex = self._tex_relaxed
      else:
        tex = self._tex_standard

    if tex is None:
      return

    # Position: bottom-left, above exp button area
    ox, oy = self._rect.x, self._rect.y
    btn_size = self._btn_size
    x = ox + UI_BORDER_SIZE + 10
    y = oy + self._rect.height - btn_size - UI_BORDER_SIZE - 10

    self._draw_rounded_box(x, y, btn_size, btn_size, bg=rl.Color(0, 0, 0, 100))
    self._draw_texture_in_box(tex, x, y, btn_size, btn_size)

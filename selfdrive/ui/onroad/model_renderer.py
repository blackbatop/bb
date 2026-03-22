import colorsys
import numpy as np
import pyray as rl
from cereal import messaging, car
from dataclasses import dataclass, field
from openpilot.common.filter_simple import FirstOrderFilter
from openpilot.common.params import Params
from openpilot.selfdrive.locationd.calibrationd import HEIGHT_INIT
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.lib.shader_polygon import draw_polygon, Gradient
from openpilot.system.ui.widgets import Widget

CLIP_MARGIN = 500
MIN_DRAW_DISTANCE = 10.0
MAX_DRAW_DISTANCE = 100.0

THROTTLE_COLORS = [
  rl.Color(13, 248, 122, 102),  # HSLF(148/360, 0.94, 0.51, 0.4)
  rl.Color(114, 255, 92, 89),  # HSLF(112/360, 1.0, 0.68, 0.35)
  rl.Color(114, 255, 92, 0),  # HSLF(112/360, 1.0, 0.68, 0.0)
]

NO_THROTTLE_COLORS = [
  rl.Color(242, 242, 242, 102),  # HSLF(148/360, 0.0, 0.95, 0.4)
  rl.Color(242, 242, 242, 89),  # HSLF(112/360, 0.0, 0.95, 0.35)
  rl.Color(242, 242, 242, 0),  # HSLF(112/360, 0.0, 0.95, 0.0)
]


@dataclass
class ModelPoints:
  raw_points: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=np.float32))
  projected_points: np.ndarray = field(default_factory=lambda: np.empty((0, 2), dtype=np.float32))


@dataclass
class LeadVehicle:
  glow: list[float] = field(default_factory=list)
  chevron: list[float] = field(default_factory=list)
  fill_alpha: int = 0


class ModelRenderer(Widget):
  def __init__(self):
    super().__init__()
    self._longitudinal_control = False
    self._experimental_mode = False
    self._blend_filter = FirstOrderFilter(1.0, 0.25, 1 / gui_app.target_fps)
    self._prev_allow_throttle = True
    self._lane_line_probs = np.zeros(4, dtype=np.float32)
    self._road_edge_stds = np.zeros(2, dtype=np.float32)
    self._lead_vehicles = [LeadVehicle(), LeadVehicle(), LeadVehicle(), LeadVehicle()]
    self._adjacent_lead_count = 0
    self._path_offset_z = HEIGHT_INIT[0]

    # Initialize ModelPoints objects
    self._path = ModelPoints()
    self._path_edge = ModelPoints()
    self._adjacent_left = ModelPoints()
    self._adjacent_right = ModelPoints()
    self._lane_lines = [ModelPoints() for _ in range(4)]
    self._road_edges = [ModelPoints() for _ in range(2)]
    self._acceleration_x = np.empty((0,), dtype=np.float32)

    # Transform matrix (3x3 for car space to screen space)
    self._car_space_transform = np.zeros((3, 3), dtype=np.float32)
    self._transform_dirty = True
    self._clip_region = None
    self._lead_data_raw = [None, None]

    self._exp_gradient = Gradient(
      start=(0.0, 1.0),  # Bottom of path
      end=(0.0, 0.0),  # Top of path
      colors=[],
      stops=[],
    )

    # Get longitudinal control setting from car parameters
    if car_params := Params().get("CarParams"):
      cp = messaging.log_from_bytes(car_params, car.CarParams)
      self._longitudinal_control = cp.openpilotLongitudinalControl

    # FrogPilot state
    self._toggles: dict = {}
    self._model_ui: bool = False
    self._accel_path_active: bool = False

    # Gradient caches (avoids per-frame object allocation)
    self._rainbow_cache: Gradient | None = None
    self._rainbow_speed_key: float = -1.0
    self._blend_gradient_cache: Gradient | None = None
    self._blend_factor_cache: float = -1.0

  def set_transform(self, transform: np.ndarray):
    self._car_space_transform = transform.astype(np.float32)
    self._transform_dirty = True

  @property
  def car_space_transform(self) -> np.ndarray:
    return self._car_space_transform

  def project_point(self, x: float, y: float, z: float) -> tuple[float, float] | None:
    """Project a car-space (x, y, z) point to screen coordinates."""
    return self._map_to_screen(x, y, z)

  @property
  def path_points(self) -> np.ndarray:
    """Projected screen-space path polygon points."""
    return self._path.projected_points

  @property
  def path_raw_points(self) -> np.ndarray:
    """Raw car-space path points (Nx3)."""
    return self._path.raw_points

  @property
  def road_edge_points(self) -> list[np.ndarray]:
    """Projected screen-space road edge polygons."""
    return [e.projected_points for e in self._road_edges]

  @property
  def lane_line_points(self) -> list[np.ndarray]:
    """Projected screen-space lane line polygons."""
    return [l.projected_points for l in self._lane_lines]

  @property
  def adjacent_left_points(self) -> np.ndarray:
    """Projected left adjacent lane polygon."""
    return self._adjacent_left.projected_points

  @property
  def adjacent_right_points(self) -> np.ndarray:
    """Projected right adjacent lane polygon."""
    return self._adjacent_right.projected_points

  @property
  def lead_vehicles(self) -> list[LeadVehicle]:
    return self._lead_vehicles

  @property
  def lead_data(self) -> list:
    """Raw radarState lead data (from last render)."""
    return self._lead_data_raw

  def _render(self, rect: rl.Rectangle):
    sm = ui_state.sm
    t = ui_state.frogpilot_toggles
    self._toggles = t
    self._model_ui = t.get("model_ui", False)

    # Check if data is up-to-date
    if sm.recv_frame["liveCalibration"] < ui_state.started_frame or sm.recv_frame["modelV2"] < ui_state.started_frame:
      return

    # Set up clipping region
    self._clip_region = rl.Rectangle(rect.x - CLIP_MARGIN, rect.y - CLIP_MARGIN, rect.width + 2 * CLIP_MARGIN, rect.height + 2 * CLIP_MARGIN)

    # Update state
    self._experimental_mode = sm['selfdriveState'].experimentalMode
    # Acceleration path: allow acceleration coloring independent of exp mode
    self._accel_path_active = self._experimental_mode or t.get("acceleration_path", False)

    live_calib = sm['liveCalibration']
    self._path_offset_z = live_calib.height[0] if live_calib.height else HEIGHT_INIT[0]

    if sm.updated['carParams']:
      self._longitudinal_control = sm['carParams'].openpilotLongitudinalControl

    model = sm['modelV2']
    radar_state = sm['radarState'] if sm.valid['radarState'] else None
    lead_one = radar_state.leadOne if radar_state else None
    render_lead_indicator = self._longitudinal_control and radar_state is not None

    # Hide lead marker toggle
    if t.get("hide_lead_marker", False):
      render_lead_indicator = False

    # Update model data when needed
    model_updated = sm.updated['modelV2']
    if model_updated or sm.updated['radarState'] or self._transform_dirty:
      if model_updated:
        self._update_raw_points(model)

      path_x_array = self._path.raw_points[:, 0]
      if path_x_array.size == 0:
        return

      self._update_model(lead_one, path_x_array)
      if render_lead_indicator:
        self._update_leads(radar_state, path_x_array)
      self._transform_dirty = False

    # Draw elements
    self._draw_lane_lines()
    self._draw_path(sm)

    if render_lead_indicator and radar_state:
      self._draw_lead_indicator()

  def _update_raw_points(self, model):
    """Update raw 3D points from model data"""
    self._path.raw_points = np.array([model.position.x, model.position.y, model.position.z], dtype=np.float32).T

    # Model outputs can vary by branch/model family; keep renderer bounded to
    # the fixed number of lane/edge slots used by the UI.
    for lane_line in self._lane_lines:
      lane_line.raw_points = np.empty((0, 3), dtype=np.float32)
    for i, lane_line in enumerate(model.laneLines[: len(self._lane_lines)]):
      self._lane_lines[i].raw_points = np.array([lane_line.x, lane_line.y, lane_line.z], dtype=np.float32).T

    for road_edge in self._road_edges:
      road_edge.raw_points = np.empty((0, 3), dtype=np.float32)
    for i, road_edge in enumerate(model.roadEdges[: len(self._road_edges)]):
      self._road_edges[i].raw_points = np.array([road_edge.x, road_edge.y, road_edge.z], dtype=np.float32).T

    lane_line_probs = np.array(model.laneLineProbs, dtype=np.float32)
    self._lane_line_probs = np.zeros(len(self._lane_lines), dtype=np.float32)
    self._lane_line_probs[: min(len(self._lane_lines), len(lane_line_probs))] = lane_line_probs[: len(self._lane_lines)]

    road_edge_stds = np.array(model.roadEdgeStds, dtype=np.float32)
    self._road_edge_stds = np.ones(len(self._road_edges), dtype=np.float32)
    self._road_edge_stds[: min(len(self._road_edges), len(road_edge_stds))] = road_edge_stds[: len(self._road_edges)]
    self._acceleration_x = np.array(model.acceleration.x, dtype=np.float32)

  def _update_leads(self, radar_state, path_x_array):
    """Update positions of lead vehicles"""
    for lv in self._lead_vehicles:
      lv.glow = []
      lv.chevron = []
      lv.fill_alpha = 0
    self._adjacent_lead_count = 0
    self._lead_data_raw = [None, None]
    leads = [radar_state.leadOne, radar_state.leadTwo]

    # FrogPilot: lead detection probability threshold
    t = self._toggles
    prob_threshold = t.get("lead_detection_probability", 0.0) if self._model_ui else 0.0

    for i, lead_data in enumerate(leads):
      if lead_data and lead_data.status:
        # Apply lead detection probability threshold
        if prob_threshold > 0 and hasattr(lead_data, 'prob') and lead_data.prob < prob_threshold:
          continue
        self._lead_data_raw[i] = lead_data
        d_rel, y_rel, v_rel = lead_data.dRel, lead_data.yRel, lead_data.vRel
        idx = self._get_path_length_idx(path_x_array, d_rel)

        # Get z-coordinate from path at the lead vehicle position
        z = self._path.raw_points[idx, 2] if idx < len(self._path.raw_points) else 0.0
        point = self._map_to_screen(d_rel, -y_rel, z + self._path_offset_z)
        if point:
          self._lead_vehicles[i] = self._update_lead_vehicle(d_rel, v_rel, point, self._rect)

    # FrogPilot: adjacent lead tracking from radar
    if t.get("adjacent_leads_ui", False) and ui_state.sm.valid.get("frogpilotRadarState", False):
      fp_radar = ui_state.sm["frogpilotRadarState"]
      adj_idx = 2  # slots 2 and 3 are for adjacent leads
      for adj_lead in [fp_radar.leadLeft, fp_radar.leadRight]:
        if adj_lead and adj_lead.status:
          d_rel, y_rel, v_rel = adj_lead.dRel, adj_lead.yRel, adj_lead.vRel
          idx = self._get_path_length_idx(path_x_array, d_rel)
          z = self._path.raw_points[idx, 2] if idx < len(self._path.raw_points) else 0.0
          point = self._map_to_screen(d_rel, -y_rel, z + self._path_offset_z)
          if point and adj_idx < len(self._lead_vehicles):
            self._lead_vehicles[adj_idx] = self._update_lead_vehicle(d_rel, v_rel, point, self._rect)
            self._adjacent_lead_count += 1
        adj_idx += 1

  def _update_model(self, lead, path_x_array):
    """Update model visualization data based on model message"""
    t = self._toggles
    model_ui = self._model_ui

    # FrogPilot custom widths
    lane_width = t.get("lane_line_width", 0.025) if model_ui else 0.025
    edge_width = t.get("road_edge_width", 0.025) if model_ui else 0.025
    path_width = t.get("path_width", 0.9) if model_ui else 0.9

    # Dynamic path width: scale by engagement
    if model_ui and t.get("dynamic_path_width", False):
      if ui_state.always_on_lateral_active:
        path_width *= 0.75
      elif not ui_state.sm["selfdriveState"].enabled:
        path_width *= 0.5

    max_distance = np.clip(path_x_array[-1], MIN_DRAW_DISTANCE, MAX_DRAW_DISTANCE)
    max_idx = self._get_path_length_idx(self._lane_lines[0].raw_points[:, 0], max_distance)

    # Update lane lines using raw points
    for i, lane_line in enumerate(self._lane_lines):
      lane_line.projected_points = self._map_line_to_polygon(lane_line.raw_points, lane_width * self._lane_line_probs[i], 0.0, max_idx, max_distance)

    # Update road edges using raw points
    for road_edge in self._road_edges:
      road_edge.projected_points = self._map_line_to_polygon(road_edge.raw_points, edge_width, 0.0, max_idx, max_distance)

    # Update path using raw points
    if lead and lead.status:
      lead_d = lead.dRel * 2.0
      max_distance = np.clip(lead_d - min(lead_d * 0.35, 10.0), 0.0, max_distance)

    max_idx = self._get_path_length_idx(path_x_array, max_distance)
    self._path.projected_points = self._map_line_to_polygon(self._path.raw_points, path_width, self._path_offset_z, max_idx, max_distance, allow_invert=False)

    # FrogPilot: path edge polygon (full-width outer polygon for edge rendering)
    if model_ui and t.get("path_edge_width", 0) > 0:
      self._path_edge.projected_points = self._map_line_to_polygon(self._path.raw_points, 0.9, self._path_offset_z, max_idx, max_distance, allow_invert=False)
    else:
      self._path_edge.projected_points = np.empty((0, 2), dtype=np.float32)

    # FrogPilot: adjacent lane polygons (averaged from lane line pairs)
    if t.get("adjacent_paths", False) or t.get("adjacent_path_metrics", False) or t.get("blind_spot_path", False):
      fp_plan = ui_state.frogpilot_plan
      if fp_plan and len(self._lane_lines) >= 4:
        lane_w_left = fp_plan.laneWidthLeft / 2.0 if fp_plan.laneWidthLeft else 1.75
        lane_w_right = fp_plan.laneWidthRight / 2.0 if fp_plan.laneWidthRight else 1.75
        self._adjacent_left.projected_points = self._map_averaged_line_to_polygon(
          self._lane_lines[0].raw_points, self._lane_lines[1].raw_points, lane_w_left, 0.0, max_idx
        )
        self._adjacent_right.projected_points = self._map_averaged_line_to_polygon(
          self._lane_lines[2].raw_points, self._lane_lines[3].raw_points, lane_w_right, 0.0, max_idx
        )
      else:
        self._adjacent_left.projected_points = np.empty((0, 2), dtype=np.float32)
        self._adjacent_right.projected_points = np.empty((0, 2), dtype=np.float32)
    else:
      self._adjacent_left.projected_points = np.empty((0, 2), dtype=np.float32)
      self._adjacent_right.projected_points = np.empty((0, 2), dtype=np.float32)

    self._update_experimental_gradient()

  def _update_experimental_gradient(self):
    """Pre-calculate experimental mode gradient colors"""
    if not self._experimental_mode:
      return

    max_len = min(len(self._path.projected_points) // 2, len(self._acceleration_x))

    segment_colors = []
    gradient_stops = []

    i = 0
    while i < max_len:
      # Some points (screen space) are out of frame (rect space)
      track_y = self._path.projected_points[i][1]
      if track_y < self._rect.y or track_y > (self._rect.y + self._rect.height):
        i += 1
        continue

      # Calculate color based on acceleration (0 is bottom, 1 is top)
      lin_grad_point = 1 - (track_y - self._rect.y) / self._rect.height

      # speed up: 120, slow down: 0
      path_hue = np.clip(60 + self._acceleration_x[i] * 35, 0, 120)

      saturation = min(abs(self._acceleration_x[i] * 1.5), 1)
      lightness = np.interp(saturation, [0.0, 1.0], [0.95, 0.62])
      alpha = np.interp(lin_grad_point, [0.75 / 2.0, 0.75], [0.4, 0.0])

      # Use HSL to RGB conversion
      color = self._hsla_to_color(path_hue / 360.0, saturation, lightness, alpha)

      gradient_stops.append(lin_grad_point)
      segment_colors.append(color)

      # Skip a point, unless next is last
      i += 1 + (1 if (i + 2) < max_len else 0)

    # Store the gradient in the path object
    self._exp_gradient = Gradient(
      start=(0.0, 1.0),  # Bottom of path
      end=(0.0, 0.0),  # Top of path
      colors=segment_colors,
      stops=gradient_stops,
    )

  def _build_rainbow_gradient(self) -> Gradient:
    """Build a rainbow gradient for the path based on current speed (cached)."""
    speed = abs(ui_state.sm["carState"].vEgo)
    speed_key = round(speed, 1)
    if speed_key == self._rainbow_speed_key and self._rainbow_cache is not None:
      return self._rainbow_cache

    self._rainbow_speed_key = speed_key
    t = min(speed / 35.0, 1.0)  # ~80 mph max

    n_stops = 5
    colors = []
    stops = []
    for i in range(n_stops):
      frac = i / (n_stops - 1)
      hue = (frac * 0.8 + t * 0.2) % 1.0
      r, g, b = colorsys.hls_to_rgb(hue, 0.5, 1.0)
      alpha = int(80 * (1.0 - frac * 0.5))
      colors.append(rl.Color(int(r * 255), int(g * 255), int(b * 255), alpha))
      stops.append(frac)

    self._rainbow_cache = Gradient(start=(0.0, 1.0), end=(0.0, 0.0), colors=colors, stops=stops)
    return self._rainbow_cache

  def _update_lead_vehicle(self, d_rel, v_rel, point, rect):
    speed_buff, lead_buff = 10.0, 40.0

    # Calculate fill alpha
    fill_alpha = 0
    if d_rel < lead_buff:
      fill_alpha = 255 * (1.0 - (d_rel / lead_buff))
      if v_rel < 0:
        fill_alpha += 255 * (-1 * (v_rel / speed_buff))
      fill_alpha = min(fill_alpha, 255)

    # Calculate size and position
    sz = np.clip((25 * 30) / (d_rel / 3 + 30), 15.0, 30.0) * 2.35
    x = np.clip(point[0], 0.0, rect.width - sz / 2)
    y = min(point[1], rect.height - sz * 0.6)

    g_xo = sz / 5
    g_yo = sz / 10

    glow = [(x + (sz * 1.35) + g_xo, y + sz + g_yo), (x, y - g_yo), (x - (sz * 1.35) - g_xo, y + sz + g_yo)]
    chevron = [(x + (sz * 1.25), y + sz), (x, y), (x - (sz * 1.25), y + sz)]

    return LeadVehicle(glow=glow, chevron=chevron, fill_alpha=int(fill_alpha))

  def _draw_lane_lines(self):
    """Draw lane lines and road edges"""
    t = self._toggles
    model_ui = self._model_ui
    custom_scheme = model_ui and t.get("color_scheme", "stock") != "stock"

    # Custom lane line color
    lane_color_override = None
    if custom_scheme and t.get("lane_lines_color"):
      lane_color_override = self._parse_color(t["lane_lines_color"])

    for i, lane_line in enumerate(self._lane_lines):
      if lane_line.projected_points.size == 0:
        continue

      alpha = np.clip(self._lane_line_probs[i], 0.0, 0.7)
      if lane_color_override:
        color = rl.Color(lane_color_override.r, lane_color_override.g, lane_color_override.b, int(alpha * 255))
      else:
        color = rl.Color(255, 255, 255, int(alpha * 255))
      draw_polygon(self._rect, lane_line.projected_points, color)

    for i, road_edge in enumerate(self._road_edges):
      if road_edge.projected_points.size == 0:
        continue

      alpha = np.clip(1.0 - self._road_edge_stds[i], 0.0, 1.0)
      color = rl.Color(255, 0, 0, int(alpha * 255))
      draw_polygon(self._rect, road_edge.projected_points, color)

  def _draw_path(self, sm):
    """Draw path with dynamic coloring based on mode and throttle state."""
    if not self._path.projected_points.size:
      return

    t = self._toggles
    model_ui = self._model_ui
    custom_scheme = model_ui and t.get("color_scheme", "stock") != "stock"

    # Custom path color (applied when acceleration is low)
    path_color_override = None
    if custom_scheme and t.get("path_color"):
      path_color_override = self._parse_color(t["path_color"])

    # FrogPilot: draw path edge polygon first (status-colored outer layer)
    edge_pts = self._path_edge.projected_points
    if edge_pts.size > 0:
      cs = ui_state.conditional_status
      # Alpha tuned for Raylib shader polygon renderer (C++ uses 241 via QPainter)
      _EDGE_ALPHA = 120
      if ui_state.always_on_lateral_active:
        edge_color = rl.Color(0x0A, 0xBA, 0xB5, _EDGE_ALPHA)
      elif cs >= 2:
        edge_color = rl.Color(0xDA, 0x6F, 0x25, _EDGE_ALPHA)
      elif cs >= 1:
        edge_color = rl.Color(0xFF, 0xFF, 0x00, _EDGE_ALPHA)
      elif ui_state.traffic_mode_enabled:
        edge_color = rl.Color(0xC9, 0x22, 0x31, _EDGE_ALPHA)
      else:
        edge_color = rl.Color(255, 255, 255, 30)
      if custom_scheme and t.get("path_edges_color"):
        edge_color = self._parse_color(t["path_edges_color"])
      draw_polygon(self._rect, edge_pts, edge_color)

    allow_throttle = sm['longitudinalPlan'].allowThrottle or not self._longitudinal_control
    self._blend_filter.update(int(allow_throttle))

    # FrogPilot: rainbow path (speed-based HSL gradient, integrated into path rendering)
    if t.get("rainbow_path", False) and not t.get("acceleration_path", False):
      rainbow = self._build_rainbow_gradient()
      draw_polygon(self._rect, self._path.projected_points, gradient=rainbow)

    elif self._accel_path_active:
      # Draw with acceleration coloring (experimental or acceleration_path toggle)
      if len(self._exp_gradient.colors) > 1:
        draw_polygon(self._rect, self._path.projected_points, gradient=self._exp_gradient)
      else:
        draw_polygon(self._rect, self._path.projected_points, rl.Color(255, 255, 255, 30))
    else:
      # Blend throttle/no throttle colors based on transition
      blend_factor = round(self._blend_filter.x * 100) / 100

      # Custom path color override: use when not accelerating
      if path_color_override and blend_factor < 0.5:
        c = path_color_override
        draw_polygon(self._rect, self._path.projected_points, rl.Color(c.r, c.g, c.b, 102))
      else:
        if blend_factor != self._blend_factor_cache:
          self._blend_factor_cache = blend_factor
          blended_colors = self._blend_colors(NO_THROTTLE_COLORS, THROTTLE_COLORS, blend_factor)
          self._blend_gradient_cache = Gradient(
            start=(0.0, 1.0),
            end=(0.0, 0.0),
            colors=blended_colors,
            stops=[0.0, 0.5, 1.0],
          )
        draw_polygon(self._rect, self._path.projected_points, gradient=self._blend_gradient_cache)

    # FrogPilot: adjacent lane paths (green-to-red based on width)
    t = self._toggles
    if t.get("adjacent_paths", False):
      for pts in [self._adjacent_left.projected_points, self._adjacent_right.projected_points]:
        if pts.size > 0:
          draw_polygon(self._rect, pts, rl.Color(0, 255, 100, 50))
    if t.get("blind_spot_path", False):
      for pts in [self._adjacent_left.projected_points, self._adjacent_right.projected_points]:
        if pts.size > 0:
          draw_polygon(self._rect, pts, rl.Color(201, 34, 49, 80))

  def _draw_lead_indicator(self):
    t = self._toggles
    # Custom lead marker color
    glow_color = rl.Color(218, 202, 37, 255)
    chevron_color_base = rl.Color(201, 34, 49, 255)
    if self._model_ui and t.get("lead_marker_color"):
      custom = self._parse_color(t["lead_marker_color"])
      glow_color = rl.Color(custom.r, custom.g, custom.b, 255)
      chevron_color_base = rl.Color(custom.r, custom.g, custom.b, 255)

    # Draw lead vehicles if available
    for lead in self._lead_vehicles:
      if not lead.glow or not lead.chevron:
        continue

      rl.draw_triangle_fan(lead.glow, len(lead.glow), glow_color)
      rl.draw_triangle_fan(lead.chevron, len(lead.chevron), rl.Color(chevron_color_base.r, chevron_color_base.g, chevron_color_base.b, lead.fill_alpha))

  @staticmethod
  def _get_path_length_idx(pos_x_array: np.ndarray, path_distance: float) -> int:
    """Get the index corresponding to the given path distance"""
    if len(pos_x_array) == 0:
      return 0
    indices = np.where(pos_x_array <= path_distance)[0]
    return indices[-1] if indices.size > 0 else 0

  def _map_to_screen(self, in_x, in_y, in_z):
    """Project a point in car space to screen space"""
    if self._clip_region is None:
      return None

    input_pt = np.array([in_x, in_y, in_z])
    pt = self._car_space_transform @ input_pt

    if abs(pt[2]) < 1e-6:
      return None

    x, y = pt[0] / pt[2], pt[1] / pt[2]

    clip = self._clip_region
    if not (clip.x <= x <= clip.x + clip.width and clip.y <= y <= clip.y + clip.height):
      return None

    return (x, y)

  def _map_line_to_polygon(self, line: np.ndarray, y_off: float, z_off: float, max_idx: int, max_distance: float, allow_invert: bool = True) -> np.ndarray:
    """Convert 3D line to 2D polygon for rendering."""
    if line.shape[0] == 0:
      return np.empty((0, 2), dtype=np.float32)

    # Slice points and filter non-negative x-coordinates
    points = line[: max_idx + 1]

    # Interpolate around max_idx so path end is smooth (max_distance is always >= p0.x)
    if 0 < max_idx < line.shape[0] - 1:
      p0 = line[max_idx]
      p1 = line[max_idx + 1]
      x0, x1 = p0[0], p1[0]
      interp_y = np.interp(max_distance, [x0, x1], [p0[1], p1[1]])
      interp_z = np.interp(max_distance, [x0, x1], [p0[2], p1[2]])
      interp_point = np.array([max_distance, interp_y, interp_z], dtype=points.dtype)
      points = np.concatenate((points, interp_point[None, :]), axis=0)

    points = points[points[:, 0] >= 0]
    if points.shape[0] == 0:
      return np.empty((0, 2), dtype=np.float32)

    N = points.shape[0]
    # Generate left and right 3D points in one array using broadcasting
    offsets = np.array([[0, -y_off, z_off], [0, y_off, z_off]], dtype=np.float32)
    points_3d = points[None, :, :] + offsets[:, None, :]  # Shape: 2xNx3
    points_3d = points_3d.reshape(2 * N, 3)  # Shape: (2*N)x3

    # Transform all points to projected space in one operation
    proj = self._car_space_transform @ points_3d.T  # Shape: 3x(2*N)
    proj = proj.reshape(3, 2, N)
    left_proj = proj[:, 0, :]
    right_proj = proj[:, 1, :]

    # Filter points where z is sufficiently large
    valid_proj = (np.abs(left_proj[2]) >= 1e-6) & (np.abs(right_proj[2]) >= 1e-6)
    if not np.any(valid_proj):
      return np.empty((0, 2), dtype=np.float32)

    # Compute screen coordinates
    left_screen = left_proj[:2, valid_proj] / left_proj[2, valid_proj][None, :]
    right_screen = right_proj[:2, valid_proj] / right_proj[2, valid_proj][None, :]

    # Define clip region bounds
    clip = self._clip_region
    x_min, x_max = clip.x, clip.x + clip.width
    y_min, y_max = clip.y, clip.y + clip.height

    # Filter points within clip region
    left_in_clip = (left_screen[0] >= x_min) & (left_screen[0] <= x_max) & (left_screen[1] >= y_min) & (left_screen[1] <= y_max)
    right_in_clip = (right_screen[0] >= x_min) & (right_screen[0] <= x_max) & (right_screen[1] >= y_min) & (right_screen[1] <= y_max)
    both_in_clip = left_in_clip & right_in_clip

    if not np.any(both_in_clip):
      return np.empty((0, 2), dtype=np.float32)

    # Select valid and clipped points
    left_screen = left_screen[:, both_in_clip]
    right_screen = right_screen[:, both_in_clip]

    # Handle Y-coordinate inversion on hills
    if not allow_invert and left_screen.shape[1] > 1:
      y = left_screen[1, :]  # y-coordinates
      keep = y == np.minimum.accumulate(y)
      if not np.any(keep):
        return np.empty((0, 2), dtype=np.float32)
      left_screen = left_screen[:, keep]
      right_screen = right_screen[:, keep]

    return np.vstack((left_screen.T, right_screen[:, ::-1].T)).astype(np.float32)

  def _map_averaged_line_to_polygon(self, line1: np.ndarray, line2: np.ndarray, y_off: float, z_off: float, max_idx: int) -> np.ndarray:
    """Convert two averaged 3D lane lines to a 2D polygon (center-of-lane path).

    Averages the Y coordinates of line1 and line2, then creates left/right points
    at avg_y -/+ y_off. Uses X and Z from line1.
    """
    if line1.shape[0] == 0 or line2.shape[0] == 0:
      return np.empty((0, 2), dtype=np.float32)

    n = min(max_idx + 1, line1.shape[0], line2.shape[0])
    if n == 0:
      return np.empty((0, 2), dtype=np.float32)

    # Build averaged points: X from line1, Y averaged, Z from line1
    points = np.zeros((n, 3), dtype=np.float32)
    points[:, 0] = line1[:n, 0]  # X from line1
    points[:, 1] = (line1[:n, 1] + line2[:n, 1]) / 2.0  # Y averaged
    points[:, 2] = line1[:n, 2]  # Z from line1

    # Filter non-negative X
    points = points[points[:, 0] >= 0]
    if points.shape[0] < 2:
      return np.empty((0, 2), dtype=np.float32)

    N = points.shape[0]
    offsets = np.array([[0, -y_off, z_off], [0, y_off, z_off]], dtype=np.float32)
    points_3d = points[None, :, :] + offsets[:, None, :]
    points_3d = points_3d.reshape(2 * N, 3)

    proj = self._car_space_transform @ points_3d.T
    proj = proj.reshape(3, 2, N)
    left_proj = proj[:, 0, :]
    right_proj = proj[:, 1, :]

    valid_proj = (np.abs(left_proj[2]) >= 1e-6) & (np.abs(right_proj[2]) >= 1e-6)
    if not np.any(valid_proj):
      return np.empty((0, 2), dtype=np.float32)

    left_screen = left_proj[:2, valid_proj] / left_proj[2, valid_proj][None, :]
    right_screen = right_proj[:2, valid_proj] / right_proj[2, valid_proj][None, :]

    clip = self._clip_region
    x_min, x_max = clip.x, clip.x + clip.width
    y_min, y_max = clip.y, clip.y + clip.height

    left_in_clip = (left_screen[0] >= x_min) & (left_screen[0] <= x_max) & (left_screen[1] >= y_min) & (left_screen[1] <= y_max)
    right_in_clip = (right_screen[0] >= x_min) & (right_screen[0] <= x_max) & (right_screen[1] >= y_min) & (right_screen[1] <= y_max)
    both_in_clip = left_in_clip & right_in_clip

    if not np.any(both_in_clip):
      return np.empty((0, 2), dtype=np.float32)

    left_screen = left_screen[:, both_in_clip]
    right_screen = right_screen[:, both_in_clip]

    result = np.vstack((left_screen.T, right_screen[:, ::-1].T)).astype(np.float32)

    # Ground the path: extend bottom vertices to screen bottom (matches C++ mapAveragedLineToPolygon)
    if result.shape[0] >= 4:
      mid = result.shape[0] // 2
      screen_h = self._rect.y + self._rect.height

      # Extend left-bottom pair to screen bottom
      for idx in [mid - 1, mid - 2]:
        if 0 <= idx < result.shape[0] - 1:
          dy = result[idx, 1] - result[idx + 1, 1]
          if abs(dy) > 0.1:
            slope = (result[idx, 0] - result[idx + 1, 0]) / dy
            result[idx, 0] += (screen_h - result[idx, 1]) * slope
            result[idx, 1] = screen_h

      # Extend right-bottom pair to screen bottom
      for idx in [mid, mid + 1]:
        if 0 < idx < result.shape[0]:
          dy = result[idx, 1] - result[idx - 1, 1]
          if abs(dy) > 0.1:
            slope = (result[idx, 0] - result[idx - 1, 0]) / dy
            result[idx, 0] += (screen_h - result[idx, 1]) * slope
            result[idx, 1] = screen_h

    return result

  @staticmethod
  def _hsla_to_color(h, s, l, a):
    rgb = colorsys.hls_to_rgb(h, l, s)
    return rl.Color(int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255), int(a * 255))

  @staticmethod
  def _blend_colors(begin_colors, end_colors, t):
    if t >= 1.0:
      return end_colors
    if t <= 0.0:
      return begin_colors

    inv_t = 1.0 - t
    return [
      rl.Color(int(inv_t * start.r + t * end.r), int(inv_t * start.g + t * end.g), int(inv_t * start.b + t * end.b), int(inv_t * start.a + t * end.a))
      for start, end in zip(begin_colors, end_colors, strict=True)
    ]

  @staticmethod
  def _parse_color(color_str: str) -> rl.Color:
    """Parse a hex color string (e.g., '#FF0000' or 'FF0000') to rl.Color."""
    s = color_str.lstrip('#')
    if len(s) == 8:  # ARGB
      return rl.Color(int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16), int(s[0:2], 16))
    if len(s) == 6:  # RGB
      return rl.Color(int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)
    return rl.Color(255, 255, 255, 255)

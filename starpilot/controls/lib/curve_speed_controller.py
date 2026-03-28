#!/usr/bin/env python3
import numpy as np

from openpilot.common.realtime import DT_MDL

from openpilot.starpilot.common.starpilot_variables import CRUISING_SPEED, DEFAULT_LATERAL_ACCELERATION, PLANNER_TIME

CALIBRATION_PROGRESS_THRESHOLD = 10 / DT_MDL
MAX_CURVATURE = 0.1
MIN_CURVATURE = 0.001
PERCENTILE = 90
ROUNDING_PRECISION = 5
STEP = 0.001


class CurveSpeedController:
  def __init__(self, StarPilotVCruise):
    self.starpilot_planner = StarPilotVCruise.starpilot_planner

    self.enable_training = False
    self.target_set = False

    self.training_timer = 0

    curvature_data = self.starpilot_planner.params.get("CurvatureData")
    self.curvature_data = curvature_data if isinstance(curvature_data, dict) else {}

    self.required_curvatures = [str(round(road_curvature, ROUNDING_PRECISION)) for road_curvature in np.arange(MIN_CURVATURE, MAX_CURVATURE + STEP, STEP)]

    self.update_lateral_acceleration()

  def log_data(self, v_ego, sm):
    self.enable_training = v_ego > CRUISING_SPEED
    self.enable_training &= not self.starpilot_planner.tracking_lead
    self.enable_training &= not sm["carControl"].longActive

    if self.enable_training:
      self.training_timer += DT_MDL

      if self.training_timer >= PLANNER_TIME and self.starpilot_planner.driving_in_curve and not (sm["carState"].leftBlinker or sm["carState"].rightBlinker):
        lateral_acceleration = abs(self.starpilot_planner.lateral_acceleration)
        road_curvature = abs(round(self.starpilot_planner.road_curvature, ROUNDING_PRECISION))

        key = str(road_curvature)
        if key in self.curvature_data:
          data = self.curvature_data[key]

          average = data["average"]
          count = data["count"]

          self.curvature_data[key] = {
            "average": ((average * count) + lateral_acceleration) / (count + 1),
            "count": count + 1
          }
        else:
          self.curvature_data[key] = {
            "average": lateral_acceleration,
            "count": 1
          }

        self.update_lateral_acceleration()
      else:
        self.enable_training = False

    elif self.training_timer >= PLANNER_TIME:
      progress = 0.0
      for key in self.required_curvatures:
        if key in self.curvature_data:
          progress += min(self.curvature_data[key]["count"] / CALIBRATION_PROGRESS_THRESHOLD, 1.0)

      self.starpilot_planner.params.put_nonblocking("CalibrationProgress", (progress / len(self.required_curvatures)) * 100)
      self.starpilot_planner.params.put_nonblocking("CurvatureData", self.curvature_data)

      self.enable_training = False
      self.training_timer = 0

    else:
      self.enable_training = False
      self.training_timer = 0

  def update_lateral_acceleration(self):
    if self.curvature_data:
      all_samples = [data["average"] for data in self.curvature_data.values()]
      self.lateral_acceleration = float(np.percentile(all_samples, PERCENTILE))
    else:
      self.lateral_acceleration = DEFAULT_LATERAL_ACCELERATION

    self.starpilot_planner.params.put_nonblocking("CalibratedLateralAcceleration", self.lateral_acceleration)

  def update_target(self, v_ego):
    lateral_acceleration = self.lateral_acceleration
    if self.starpilot_planner.starpilot_weather.weather_id != 0:
      lateral_acceleration -= self.lateral_acceleration * self.starpilot_planner.starpilot_weather.reduce_lateral_acceleration

    if self.target_set:
      csc_speed = (lateral_acceleration / abs(self.starpilot_planner.road_curvature))**0.5
      decel_rate = (v_ego - csc_speed) / self.starpilot_planner.time_to_curve

      self.target -= decel_rate * DT_MDL
      self.target = float(np.clip(self.target, CRUISING_SPEED, csc_speed))
    else:
      self.target_set = True
      self.target = v_ego

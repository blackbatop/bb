from types import SimpleNamespace

from openpilot.common.constants import CV
from openpilot.starpilot.controls.lib.conditional_experimental_mode import ConditionalExperimentalMode


def make_cem(*, model_length: float, model_stopped: bool = False, tracking_lead: bool = False):
  planner = SimpleNamespace(
    params=None,
    params_memory=None,
    model_length=model_length,
    model_stopped=model_stopped,
    tracking_lead=tracking_lead,
  )
  return ConditionalExperimentalMode(planner)


def make_sm(traffic_mode_enabled: bool = False):
  return {
    "starpilotCarState": SimpleNamespace(trafficModeEnabled=traffic_mode_enabled),
  }


def test_low_speed_cruise_does_not_trigger_stop_light_from_model_stopped():
  v_ego = 10 * CV.MPH_TO_MS
  model_length = v_ego * 10.0

  cem = make_cem(model_length=model_length, model_stopped=True)
  cem.stop_sign_and_light(v_ego, make_sm(), model_time=7.0)

  assert not cem.stop_light_detected


def test_predicted_stop_within_threshold_triggers_stop_light():
  v_ego = 30 * CV.MPH_TO_MS
  model_length = v_ego * 4.0

  cem = make_cem(model_length=model_length)
  cem.stop_sign_and_light(v_ego, make_sm(), model_time=7.0)

  assert cem.stop_light_detected

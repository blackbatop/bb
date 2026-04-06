from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


LOW_SPEED_MANEUVER_DESCRIPTIONS = (
  "come to stop",
  "start from stop",
  "creep: alternate between +1m/s^2 and -1m/s^2",
)


@dataclass(frozen=True)
class LongitudinalManeuverSupport:
  openpilotLongitudinalControl: bool
  fullStopAndGo: bool
  autoResumeFromStop: bool
  requiresResumeAssist: bool
  expectedToReachZero: bool
  minEnableSpeed: float
  stopAccel: float
  caveats: tuple[str, ...]
  skippedManeuvers: tuple[str, ...]

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


def get_longitudinal_maneuver_support(CP: Any) -> LongitudinalManeuverSupport:
  openpilot_longitudinal = bool(getattr(CP, "openpilotLongitudinalControl", False))
  auto_resume_supported = bool(getattr(CP, "autoResumeSng", False))

  min_enable_speed = float(getattr(CP, "minEnableSpeed", 0.0) or 0.0)
  stop_accel = float(getattr(CP, "stopAccel", 0.0) or 0.0)

  # CarParams does not expose a dedicated "won't fully brake to zero" flag,
  # so low-speed engagement support is the closest reliable proxy.
  full_stop_and_go = min_enable_speed <= 0.0
  auto_resume_from_stop = full_stop_and_go and auto_resume_supported
  expected_to_reach_zero = full_stop_and_go
  requires_resume_assist = expected_to_reach_zero and not auto_resume_from_stop

  caveats: list[str] = []
  if not openpilot_longitudinal:
    caveats.append("openpilot longitudinal is disabled, so the maneuver suite cannot drive longitudinal tests on this platform.")

  if not expected_to_reach_zero:
    caveats.append("This car is not expected to reach a true standstill in the suite. Stop, start, and creep maneuvers will be skipped.")
  elif requires_resume_assist:
    caveats.append("This car can reach a stop, but restart-from-stop needs resume assistance. Zero-speed maneuvers will allow cruise standstill instead of treating it as setup failure.")

  skipped_maneuvers = LOW_SPEED_MANEUVER_DESCRIPTIONS if not expected_to_reach_zero else ()

  return LongitudinalManeuverSupport(
    openpilotLongitudinalControl=openpilot_longitudinal,
    fullStopAndGo=full_stop_and_go,
    autoResumeFromStop=auto_resume_from_stop,
    requiresResumeAssist=requires_resume_assist,
    expectedToReachZero=expected_to_reach_zero,
    minEnableSpeed=min_enable_speed,
    stopAccel=stop_accel,
    caveats=tuple(caveats),
    skippedManeuvers=tuple(skipped_maneuvers),
  )


def get_maneuver_skip_reason(description: str, support: LongitudinalManeuverSupport) -> str | None:
  if not support.openpilotLongitudinalControl:
    return "openpilot longitudinal is disabled"

  if description in LOW_SPEED_MANEUVER_DESCRIPTIONS and not support.expectedToReachZero:
    return "vehicle is not expected to reach a true standstill"

  return None

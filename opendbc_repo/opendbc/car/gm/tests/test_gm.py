import pytest
from parameterized import parameterized

from opendbc.car.car_helpers import interfaces
from opendbc.car.common.conversions import Conversions as CV
from opendbc.car.gm.fingerprints import FINGERPRINTS
from opendbc.car.gm.values import CAMERA_ACC_CAR, CAR, CC_ONLY_CAR, GM_RX_OFFSET

CAMERA_DIAGNOSTIC_ADDRESS = 0x24b
VOLT_CARS = (
  CAR.CHEVROLET_VOLT,
  CAR.CHEVROLET_VOLT_2019,
  CAR.CHEVROLET_VOLT_ASCM,
  CAR.CHEVROLET_VOLT_CAMERA,
  CAR.CHEVROLET_VOLT_CC,
)


def _empty_fingerprint():
  return {bus: {} for bus in range(8)}


class TestGMFingerprint:
  @parameterized.expand(FINGERPRINTS.items())
  def test_can_fingerprints(self, car_model, fingerprints):
    assert len(fingerprints) > 0

    assert all(len(finger) for finger in fingerprints)

    # The camera can sometimes be communicating on startup
    if car_model in CAMERA_ACC_CAR - CC_ONLY_CAR:
      for finger in fingerprints:
        for required_addr in (CAMERA_DIAGNOSTIC_ADDRESS, CAMERA_DIAGNOSTIC_ADDRESS + GM_RX_OFFSET):
          assert finger.get(required_addr) == 8, required_addr


class TestGMInterface:
  @parameterized.expand(VOLT_CARS)
  def test_volt_min_steer_speed_is_7_mph(self, car_model):
    CarInterface = interfaces[car_model]
    car_params = CarInterface.get_params(car_model, _empty_fingerprint(), [], alpha_long=False, is_release=False, docs=False)

    assert car_params.minSteerSpeed == pytest.approx(7 * CV.MPH_TO_MS)

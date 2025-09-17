import os
from openpilot.system.hardware import HARDWARE, TICI
from openpilot.selfdrive.modeld.runners.runmodel_pyx import RunModel, Runtime
assert Runtime

SNPE_SUPPORTED_DEVICE_TYPES = {"tici", "tizi"}

USE_THNEED = int(os.getenv('USE_THNEED', str(int(TICI))))
default_use_snpe = int(TICI and HARDWARE.get_device_type() in SNPE_SUPPORTED_DEVICE_TYPES)
USE_SNPE = int(os.getenv('USE_SNPE', str(default_use_snpe)))

class ModelRunner(RunModel):
  THNEED = 'THNEED'
  SNPE = 'SNPE'
  ONNX = 'ONNX'

  def __new__(cls, paths, *args, **kwargs):
    if ModelRunner.THNEED in paths and USE_THNEED:
      from openpilot.selfdrive.modeld.runners.thneedmodel_pyx import ThneedModel as Runner
      runner_type = ModelRunner.THNEED
    elif ModelRunner.SNPE in paths and USE_SNPE:
      from openpilot.selfdrive.modeld.runners.snpemodel_pyx import SNPEModel as Runner
      runner_type = ModelRunner.SNPE
    elif ModelRunner.ONNX in paths:
      from openpilot.selfdrive.modeld.runners.onnxmodel import ONNXModel as Runner
      runner_type = ModelRunner.ONNX
    else:
      raise Exception("Couldn't select a model runner, make sure to pass at least one valid model path")

    return Runner(str(paths[runner_type]), *args, **kwargs)

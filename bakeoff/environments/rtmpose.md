# RTMPose Animal environment

Keep this environment separate from the lightweight bake-off core.

The adapter targets MMPose 1.x and its `animal` inferencer alias. OpenMMLab's declared
compatibility requires:

- MMPose 1.x;
- MMDetection >=3.0.0,<3.3.0;
- MMCV 2.x;
- MMEngine <1.0.

The real-cat smoke workflow pins a conservative CPU stack to make the experiment
reproducible rather than following whichever dependency versions happen to be newest:

```text
Python 3.10
NumPy 1.26.4
PyTorch 2.0.1 CPU
TorchVision 0.15.2 CPU
MMCV 2.1.0
MMDetection 3.2.0
MMPose 1.3.2
```

The workflow uses OpenMIM for OpenMMLab packages and runs only a handful of frames. It
is a functionality smoke test, not a throughput benchmark. Production latency should be
measured later on the intended GPU/TensorRT runtime.

References:

- https://github.com/open-mmlab/mmpose/blob/main/docs/en/installation.md
- https://github.com/open-mmlab/mmpose/blob/main/requirements/mminstall.txt

Checkpoint and source-dataset rights remain separately gated by Issue #9.

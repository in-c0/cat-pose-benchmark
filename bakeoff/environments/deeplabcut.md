# DeepLabCut research-baseline environment

This environment is intentionally isolated from any eventual commercial runtime.

Two adapters use the current DeepLabCut model-zoo API:

```python
video_inference_superanimal(...)
```

## SuperAnimal-Quadruped

Initial zero-shot baseline:

```text
superanimal_name = superanimal_quadruped
model_name = hrnet_w32
detector_name = fasterrcnn_resnet50_fpn_v2
video_adapt = false
```

The provided SuperAnimal weights are treated as `research_only` in CatPose. Do not use
their outputs as product-training labels until derived-data rights have been reviewed.

## FMPose3D Animals

Current DeepLabCut integration:

```text
superanimal_name = quadruped
model_name = fmpose3d_animals
fmpose_return_3d = true
max_individuals = 1
```

The returned payload contains both `df_2d` and `df_3d`. CatPose preserves the 3D
coordinate system as `model_native` until its semantics are independently verified; it
does not relabel those coordinates as world-space or camera-space simply because they
are 3D.

FMPose3D's current animal topology contains 26 points including a tail root, tail tip,
generic left/right ear points, paws and limb joints. Generic ear points are not silently
promoted to feline ear-tip ground truth.

References:

- https://github.com/DeepLabCut/DeepLabCut/blob/main/deeplabcut/modelzoo/video_inference.py
- https://github.com/DeepLabCut/DeepLabCut/blob/main/deeplabcut/pose_estimation_pytorch/modelzoo/fmpose_3d/fmpose3d.py

See Issue #9 for model-weight and contamination policy.

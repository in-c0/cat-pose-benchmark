using System;
using System.Collections.Generic;
using UnityEngine;

namespace CatPose.Stage0
{
    public static class Stage0Geometry
    {
        private const float Epsilon = 1e-7f;

        /// <summary>
        /// Repository coordinates are x=right, y=forward, z=up.
        /// Unity coordinates are x=right, y=up, z=forward.
        /// Swapping y and z changes handedness intentionally.
        /// </summary>
        public static Vector3 RepositoryToUnity(Vector3 repositoryPoint)
        {
            return new Vector3(repositoryPoint.x, repositoryPoint.z, repositoryPoint.y);
        }

        public static Vector3 UnityToRepository(Vector3 unityPoint)
        {
            return new Vector3(unityPoint.x, unityPoint.z, unityPoint.y);
        }

        public static Vector3 ReflectPoint(
            Vector3 point,
            Vector3 planePoint,
            Vector3 planeNormal)
        {
            Vector3 normal = Normalized(planeNormal, nameof(planeNormal));
            return point - 2f * normal * Vector3.Dot(normal, point - planePoint);
        }

        public static Vector3 VirtualCameraCentre(
            CameraConfig camera,
            MirrorConfig mirror)
        {
            return ReflectPoint(
                camera.centreM.ToVector3(nameof(camera.centreM)),
                mirror.planePointM.ToVector3(nameof(mirror.planePointM)),
                mirror.planeNormal.ToVector3(nameof(mirror.planeNormal)));
        }

        public static void MirrorBasis(
            MirrorConfig mirror,
            out Vector3 horizontal,
            out Vector3 vertical,
            out Vector3 normal)
        {
            normal = Normalized(
                mirror.planeNormal.ToVector3(nameof(mirror.planeNormal)),
                nameof(mirror.planeNormal));
            Vector3 requestedVertical = mirror.verticalAxis.ToVector3(
                nameof(mirror.verticalAxis));
            vertical = requestedVertical - normal * Vector3.Dot(requestedVertical, normal);
            vertical = Normalized(vertical, nameof(mirror.verticalAxis));
            horizontal = Normalized(Vector3.Cross(vertical, normal), "mirror horizontal axis");
        }

        public static Vector3[] MirrorCorners(MirrorConfig mirror)
        {
            Vector2 size = mirror.sizeM.ToVector2(nameof(mirror.sizeM));
            Vector3 centre = mirror.planePointM.ToVector3(nameof(mirror.planePointM));
            MirrorBasis(mirror, out Vector3 horizontal, out Vector3 vertical, out _);
            Vector3 halfHorizontal = horizontal * (size.x * 0.5f);
            Vector3 halfVertical = vertical * (size.y * 0.5f);

            return new[]
            {
                centre - halfHorizontal - halfVertical,
                centre + halfHorizontal - halfVertical,
                centre + halfHorizontal + halfVertical,
                centre - halfHorizontal + halfVertical,
            };
        }

        public static bool TryReflectionPoint(
            Vector3 objectPoint,
            Vector3 physicalCameraCentre,
            MirrorConfig mirror,
            out Vector3 reflectionPoint,
            out float interpolation)
        {
            Vector3 planePoint = mirror.planePointM.ToVector3(nameof(mirror.planePointM));
            Vector3 normal = Normalized(
                mirror.planeNormal.ToVector3(nameof(mirror.planeNormal)),
                nameof(mirror.planeNormal));
            Vector3 virtualCamera = ReflectPoint(
                physicalCameraCentre,
                planePoint,
                normal);
            float denominator = Vector3.Dot(normal, virtualCamera - objectPoint);

            if (Mathf.Abs(denominator) <= Epsilon)
            {
                reflectionPoint = default;
                interpolation = float.NaN;
                return false;
            }

            interpolation = Vector3.Dot(normal, planePoint - objectPoint) / denominator;
            reflectionPoint = objectPoint + interpolation * (virtualCamera - objectPoint);
            return interpolation > 0f && interpolation < 1f;
        }

        public static bool IsInsideFiniteMirror(
            Vector3 reflectionPoint,
            MirrorConfig mirror,
            float tolerance = 1e-5f)
        {
            Vector2 size = mirror.sizeM.ToVector2(nameof(mirror.sizeM));
            Vector3 centre = mirror.planePointM.ToVector3(nameof(mirror.planePointM));
            MirrorBasis(mirror, out Vector3 horizontal, out Vector3 vertical, out _);
            Vector3 offset = reflectionPoint - centre;

            return Mathf.Abs(Vector3.Dot(offset, horizontal)) <= size.x * 0.5f + tolerance
                && Mathf.Abs(Vector3.Dot(offset, vertical)) <= size.y * 0.5f + tolerance;
        }

        public static IEnumerable<Vector3> SampleCaptureVolume(CaptureVolumeConfig volume)
        {
            Vector3 minimum = volume.minM.ToVector3(nameof(volume.minM));
            Vector3 maximum = volume.maxM.ToVector3(nameof(volume.maxM));
            Vector3Int counts = volume.samplesXyz.ToVector3Int(nameof(volume.samplesXyz));

            if (counts.x < 1 || counts.y < 1 || counts.z < 1)
            {
                throw new ArgumentOutOfRangeException(
                    nameof(volume.samplesXyz),
                    "Every capture-volume sample count must be positive.");
            }

            for (int x = 0; x < counts.x; x++)
            {
                float tx = counts.x == 1 ? 0.5f : x / (float)(counts.x - 1);
                for (int y = 0; y < counts.y; y++)
                {
                    float ty = counts.y == 1 ? 0.5f : y / (float)(counts.y - 1);
                    for (int z = 0; z < counts.z; z++)
                    {
                        float tz = counts.z == 1 ? 0.5f : z / (float)(counts.z - 1);
                        yield return new Vector3(
                            Mathf.Lerp(minimum.x, maximum.x, tx),
                            Mathf.Lerp(minimum.y, maximum.y, ty),
                            Mathf.Lerp(minimum.z, maximum.z, tz));
                    }
                }
            }
        }

        public static Bounds CaptureBoundsInUnity(CaptureVolumeConfig volume)
        {
            Vector3 minimum = RepositoryToUnity(
                volume.minM.ToVector3(nameof(volume.minM)));
            Vector3 maximum = RepositoryToUnity(
                volume.maxM.ToVector3(nameof(volume.maxM)));
            Vector3 boundsMin = Vector3.Min(minimum, maximum);
            Vector3 boundsMax = Vector3.Max(minimum, maximum);
            Bounds bounds = new();
            bounds.SetMinMax(boundsMin, boundsMax);
            return bounds;
        }

        public static float VirtualCameraErrorMetres(
            CameraConfig camera,
            MirrorConfig mirror)
        {
            Vector3 calculated = VirtualCameraCentre(camera, mirror);
            Vector3 expected = mirror.expectedVirtualCameraCentreM.ToVector3(
                nameof(mirror.expectedVirtualCameraCentreM));
            return Vector3.Distance(calculated, expected);
        }

        private static Vector3 Normalized(Vector3 value, string fieldName)
        {
            if (value.sqrMagnitude <= Epsilon * Epsilon)
            {
                throw new ArgumentException($"{fieldName} cannot be zero length.");
            }

            return value.normalized;
        }
    }
}

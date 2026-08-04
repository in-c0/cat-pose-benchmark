using System;
using UnityEngine;

namespace CatPose.Stage0
{
    [Serializable]
    public sealed class Stage0Config
    {
        public string schemaVersion = string.Empty;
        public string sourceLayoutSchemaVersion = string.Empty;
        public string sourceReportSchemaVersion = string.Empty;
        public string units = string.Empty;
        public RepositoryCoordinateSystem repositoryCoordinateSystem = new();
        public string[] repositoryToUnityAxisMap = Array.Empty<string>();
        public CameraConfig camera = new();
        public CaptureVolumeConfig captureVolume = new();
        public LayoutConfig[] layouts = Array.Empty<LayoutConfig>();

        public LayoutConfig FindLayout(string layoutId)
        {
            if (layouts == null)
            {
                return null;
            }

            foreach (LayoutConfig layout in layouts)
            {
                if (layout != null && string.Equals(layout.id, layoutId, StringComparison.Ordinal))
                {
                    return layout;
                }
            }

            return null;
        }
    }

    [Serializable]
    public sealed class RepositoryCoordinateSystem
    {
        public string x = string.Empty;
        public string y = string.Empty;
        public string z = string.Empty;
    }

    [Serializable]
    public sealed class CameraConfig
    {
        public string className = string.Empty;
        public int[] resolutionPx = Array.Empty<int>();
        public int frameRateFps;
        public float fxPx;
        public float fyPx;
        public float cxPx;
        public float cyPx;
        public float[] centreM = Array.Empty<float>();
        public float[] lookAtM = Array.Empty<float>();
        public float pixelSigmaPx;
    }

    [Serializable]
    public sealed class CaptureVolumeConfig
    {
        public float[] minM = Array.Empty<float>();
        public float[] maxM = Array.Empty<float>();
        public int[] samplesXyz = Array.Empty<int>();
    }

    [Serializable]
    public sealed class LayoutConfig
    {
        public string id = string.Empty;
        public string description = string.Empty;
        public float[] nominalFrameM = Array.Empty<float>();
        public ViewSummary directView = new();
        public MirrorConfig[] mirrors = Array.Empty<MirrorConfig>();
        public float combinedCoverageFraction;
        public float combinedP95RadialStandardDeviationMm;
        public float combinedP95Anisotropy;
    }

    [Serializable]
    public class ViewSummary
    {
        public string name = string.Empty;
        public string reflectionParity = string.Empty;
        public float coverageFraction;
        public float[] roiMinPx = Array.Empty<float>();
        public float[] roiMaxPx = Array.Empty<float>();
    }

    [Serializable]
    public sealed class MirrorConfig : ViewSummary
    {
        public float[] sizeM = Array.Empty<float>();
        public float[] planePointM = Array.Empty<float>();
        public float[] planeNormal = Array.Empty<float>();
        public float[] verticalAxis = Array.Empty<float>();
        public float[] expectedVirtualCameraCentreM = Array.Empty<float>();
    }

    public static class Stage0ConfigExtensions
    {
        public static Vector3 ToVector3(this float[] values, string fieldName)
        {
            if (values == null || values.Length != 3)
            {
                throw new ArgumentException($"{fieldName} must contain exactly three values.");
            }

            return new Vector3(values[0], values[1], values[2]);
        }

        public static Vector2 ToVector2(this float[] values, string fieldName)
        {
            if (values == null || values.Length != 2)
            {
                throw new ArgumentException($"{fieldName} must contain exactly two values.");
            }

            return new Vector2(values[0], values[1]);
        }

        public static Vector2Int ToVector2Int(this int[] values, string fieldName)
        {
            if (values == null || values.Length != 2)
            {
                throw new ArgumentException($"{fieldName} must contain exactly two values.");
            }

            return new Vector2Int(values[0], values[1]);
        }

        public static Vector3Int ToVector3Int(this int[] values, string fieldName)
        {
            if (values == null || values.Length != 3)
            {
                throw new ArgumentException($"{fieldName} must contain exactly three values.");
            }

            return new Vector3Int(values[0], values[1], values[2]);
        }
    }
}

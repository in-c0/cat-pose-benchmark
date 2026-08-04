using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace CatPose.StageS0
{
    /// <summary>
    /// Produces a deterministic software-only annotation fixture from Unity runtime
    /// transforms. The proxy is deliberately simple: the first milestone validates the
    /// annotation handshake, not visual realism or real-cat accuracy.
    /// </summary>
    public static class StageS0SyntheticExporter
    {
        private const int Seed = 17;
        private const int FrameCount = 5;
        private const long FixedTimestepNs = 100_000_000;
        private const float FixedTimestepSeconds = 0.1f;
        private const int ImageWidth = 640;
        private const int ImageHeight = 480;
        private const float VerticalFieldOfView = 60.0f;
        private const string SequenceId = "stage-s0-proxy-v0";
        private const string SubjectId = "proxy-cat-001";
        private const string ExporterVersion = "StageS0SyntheticExporter-v0.1";

        private sealed class LandmarkFrame
        {
            public string Name;
            public Vector3 World;
            public Vector3 Camera;
            public Vector2 Image;
            public string Visibility;
        }

        private sealed class FrameData
        {
            public int FrameIndex;
            public long TimestampNs;
            public Vector3 RootWorld;
            public Vector3 VelocityWorld;
            public readonly List<LandmarkFrame> Landmarks = new();
            public readonly List<Vector3> TailCurveWorld = new();
        }

        private readonly struct LandmarkDefinition
        {
            public LandmarkDefinition(string name, Vector3 localPosition)
            {
                Name = name;
                LocalPosition = localPosition;
            }

            public string Name { get; }
            public Vector3 LocalPosition { get; }
        }

        private static readonly LandmarkDefinition[] StaticLandmarks =
        {
            new("nose", new Vector3(0.0f, 0.55f, 0.65f)),
            new("left_ear_tip", new Vector3(-0.16f, 0.82f, 0.48f)),
            new("right_ear_tip", new Vector3(0.16f, 0.82f, 0.48f)),
            new("left_front_paw", new Vector3(-0.18f, 0.0f, 0.38f)),
            new("right_front_paw", new Vector3(0.18f, 0.0f, 0.38f)),
            new("left_hind_paw", new Vector3(-0.18f, 0.0f, -0.35f)),
            new("right_hind_paw", new Vector3(0.18f, 0.0f, -0.35f)),
            new("tail_base", new Vector3(0.0f, 0.35f, -0.55f))
        };

        [MenuItem("CatPose/Generate Stage S0 Synthetic Fixture")]
        public static void ExportFromMenu()
        {
            string path = DefaultOutputPath();
            Export(path);
            AssetDatabase.Refresh();
            Debug.Log($"Stage S0 fixture exported to {path}");
        }

        public static void ExportFromCommandLine()
        {
            string outputArgument = CommandLineValue("-catposeOutput");
            string path = string.IsNullOrWhiteSpace(outputArgument)
                ? DefaultOutputPath()
                : Path.GetFullPath(outputArgument);
            Export(path);
            Debug.Log($"Stage S0 fixture exported to {path}");
        }

        public static void Export(string outputPath)
        {
            UnityEngine.Random.InitState(Seed);

            GameObject rootObject = null;
            GameObject cameraObject = null;
            RenderTexture renderTexture = null;

            try
            {
                rootObject = BuildProxy();
                cameraObject = BuildCamera(out Camera camera, out renderTexture);
                List<FrameData> frames = BuildFrames(rootObject.transform, camera);
                string json = BuildJson(frames, camera);

                string directory = Path.GetDirectoryName(outputPath);
                if (string.IsNullOrWhiteSpace(directory))
                {
                    throw new InvalidOperationException("Output path has no directory.");
                }

                Directory.CreateDirectory(directory);
                File.WriteAllText(outputPath, json, new UTF8Encoding(false));
            }
            finally
            {
                if (renderTexture != null)
                {
                    renderTexture.Release();
                    UnityEngine.Object.DestroyImmediate(renderTexture);
                }
                if (cameraObject != null)
                {
                    UnityEngine.Object.DestroyImmediate(cameraObject);
                }
                if (rootObject != null)
                {
                    UnityEngine.Object.DestroyImmediate(rootObject);
                }
            }
        }

        private static GameObject BuildProxy()
        {
            GameObject root = new("Stage S0 Procedural Feline Proxy")
            {
                hideFlags = HideFlags.HideAndDontSave
            };

            CreatePrimitive("body", PrimitiveType.Capsule, root.transform,
                new Vector3(0.0f, 0.38f, 0.0f), new Vector3(0.55f, 0.45f, 1.15f));
            CreatePrimitive("head", PrimitiveType.Sphere, root.transform,
                new Vector3(0.0f, 0.58f, 0.50f), new Vector3(0.48f, 0.42f, 0.46f));

            CreatePrimitive("box-left", PrimitiveType.Cube, null,
                new Vector3(-0.8f, 0.25f, 0.4f), new Vector3(0.35f, 0.5f, 0.35f));
            CreatePrimitive("box-right", PrimitiveType.Cube, null,
                new Vector3(0.8f, 0.25f, 0.4f), new Vector3(0.35f, 0.5f, 0.35f));

            return root;
        }

        private static GameObject CreatePrimitive(
            string name,
            PrimitiveType type,
            Transform parent,
            Vector3 position,
            Vector3 scale)
        {
            GameObject item = GameObject.CreatePrimitive(type);
            item.name = name;
            item.hideFlags = HideFlags.HideAndDontSave;
            if (parent != null)
            {
                item.transform.SetParent(parent, false);
                item.transform.localPosition = position;
            }
            else
            {
                item.transform.position = position;
            }
            item.transform.localScale = scale;
            return item;
        }

        private static GameObject BuildCamera(out Camera camera, out RenderTexture renderTexture)
        {
            GameObject cameraObject = new("Stage S0 Synthetic Camera")
            {
                hideFlags = HideFlags.HideAndDontSave
            };
            camera = cameraObject.AddComponent<Camera>();
            camera.fieldOfView = VerticalFieldOfView;
            camera.nearClipPlane = 0.01f;
            camera.farClipPlane = 100.0f;
            camera.aspect = (float)ImageWidth / ImageHeight;
            cameraObject.transform.position = new Vector3(0.0f, 1.1f, -3.0f);
            cameraObject.transform.rotation = Quaternion.LookRotation(
                new Vector3(0.0f, 0.4f, 0.0f) - cameraObject.transform.position,
                Vector3.up);

            renderTexture = new RenderTexture(ImageWidth, ImageHeight, 24)
            {
                hideFlags = HideFlags.HideAndDontSave
            };
            camera.targetTexture = renderTexture;
            return cameraObject;
        }

        private static List<FrameData> BuildFrames(Transform subjectRoot, Camera camera)
        {
            List<FrameData> frames = new(FrameCount);
            Vector3 declaredVelocity = new(0.2f, 0.0f, 0.0f);

            for (int frameIndex = 0; frameIndex < FrameCount; frameIndex++)
            {
                subjectRoot.position = new Vector3(0.02f * frameIndex, 0.0f, 0.0f);
                subjectRoot.rotation = Quaternion.identity;

                FrameData frame = new()
                {
                    FrameIndex = frameIndex,
                    TimestampNs = frameIndex * FixedTimestepNs,
                    RootWorld = subjectRoot.position,
                    VelocityWorld = declaredVelocity
                };

                foreach (LandmarkDefinition definition in StaticLandmarks)
                {
                    Vector3 world = subjectRoot.TransformPoint(definition.LocalPosition);
                    frame.Landmarks.Add(ProjectLandmark(definition.Name, world, camera));
                }

                float swing = Mathf.Sin(0.7f * frameIndex);
                frame.TailCurveWorld.Add(subjectRoot.TransformPoint(
                    new Vector3(0.0f, 0.35f, -0.55f)));
                frame.TailCurveWorld.Add(subjectRoot.TransformPoint(
                    new Vector3(0.05f * swing, 0.42f, -0.80f)));
                frame.TailCurveWorld.Add(subjectRoot.TransformPoint(
                    new Vector3(0.12f * swing, 0.48f, -1.00f)));
                frame.TailCurveWorld.Add(subjectRoot.TransformPoint(
                    new Vector3(0.20f * swing, 0.55f, -1.15f)));

                frame.Landmarks.Add(ProjectLandmark(
                    "tail_tip",
                    frame.TailCurveWorld[^1],
                    camera));

                frames.Add(frame);
            }

            return frames;
        }

        private static LandmarkFrame ProjectLandmark(string name, Vector3 world, Camera camera)
        {
            Vector3 cameraPoint = camera.transform.InverseTransformPoint(world);
            Vector3 screen = camera.WorldToScreenPoint(world);
            bool visible = screen.z > 0.0f
                && screen.x >= 0.0f && screen.x <= ImageWidth
                && screen.y >= 0.0f && screen.y <= ImageHeight;

            return new LandmarkFrame
            {
                Name = name,
                World = world,
                Camera = cameraPoint,
                Image = new Vector2(screen.x, screen.y),
                Visibility = visible ? "visible" : "out_of_frame"
            };
        }

        private static string BuildJson(IReadOnlyList<FrameData> frames, Camera camera)
        {
            StringBuilder builder = new(32_768);
            builder.AppendLine("{");
            Property(builder, 1, "schema_version", "0.1.0", true);
            Property(builder, 1, "sequence_id", SequenceId, true);
            Property(builder, 1, "subject_id", SubjectId, true);
            Property(builder, 1, "evidence_tier", "S", true);
            Property(builder, 1, "quality", "gold", true);
            Property(builder, 1, "units", "metres", true);

            Indent(builder, 1).AppendLine("\"engine\": {");
            Property(builder, 2, "name", "Unity", true);
            Property(builder, 2, "project", "cat-pose-benchmark/unity-viewer", true);
            Property(builder, 2, "required_editor", Application.unityVersion, true);
            Property(builder, 2, "exporter", ExporterVersion, false);
            Indent(builder, 1).AppendLine("},");

            Indent(builder, 1).AppendLine("\"determinism\": {");
            NumberProperty(builder, 2, "seed", Seed, true);
            NumberProperty(builder, 2, "fixed_timestep_ns", FixedTimestepNs, true);
            NumberProperty(builder, 2, "frame_count", FrameCount, true);
            Property(builder, 2, "coordinate_convention",
                "unity-left-handed-x-right-y-up-z-forward", false);
            Indent(builder, 1).AppendLine("},");

            Indent(builder, 1).AppendLine("\"camera\": {");
            Property(builder, 2, "camera_id", "synthetic-camera-0", true);
            Indent(builder, 2).Append("\"resolution_px\": [")
                .Append(ImageWidth).Append(", ").Append(ImageHeight).AppendLine("],");
            NumberProperty(builder, 2, "vertical_fov_degrees", VerticalFieldOfView, true);
            VectorProperty(builder, 2, "position_world_m", camera.transform.position, true);
            VectorProperty(builder, 2, "look_at_world_m", new Vector3(0.0f, 0.4f, 0.0f), true);
            Property(builder, 2, "screen_origin", "bottom_left", false);
            Indent(builder, 1).AppendLine("},");

            AppendScene(builder);
            Indent(builder, 1).AppendLine("\"lineage\": [");
            StringArrayValue(builder, 2, "generator:procedural-proxy-v0.1", true);
            StringArrayValue(builder, 2, $"seed:{Seed}", true);
            StringArrayValue(builder, 2, $"fixed-timestep-ns:{FixedTimestepNs}", false);
            Indent(builder, 1).AppendLine("],");

            Indent(builder, 1).AppendLine("\"frames\": [");
            for (int index = 0; index < frames.Count; index++)
            {
                AppendFrame(builder, frames[index], index < frames.Count - 1);
            }
            Indent(builder, 1).AppendLine("]");
            builder.AppendLine("}");
            return builder.ToString();
        }

        private static void AppendScene(StringBuilder builder)
        {
            Indent(builder, 1).AppendLine("\"scene\": {");
            Indent(builder, 2).AppendLine("\"support_surfaces\": [");
            Indent(builder, 3).AppendLine("{");
            Property(builder, 4, "object_id", "floor", true);
            Indent(builder, 4).AppendLine("\"plane_world\": {");
            VectorProperty(builder, 5, "normal", Vector3.up, true);
            NumberProperty(builder, 5, "offset_m", 0.0f, false);
            Indent(builder, 4).AppendLine("}");
            Indent(builder, 3).AppendLine("}");
            Indent(builder, 2).AppendLine("],");
            Indent(builder, 2).AppendLine("\"objects\": [");
            AppendSceneObject(builder, "box-left", new Vector3(-0.8f, 0.25f, 0.4f), true);
            AppendSceneObject(builder, "box-right", new Vector3(0.8f, 0.25f, 0.4f), false);
            Indent(builder, 2).AppendLine("]");
            Indent(builder, 1).AppendLine("},");
        }

        private static void AppendSceneObject(
            StringBuilder builder,
            string objectId,
            Vector3 position,
            bool comma)
        {
            Indent(builder, 3).AppendLine("{");
            Property(builder, 4, "object_id", objectId, true);
            Property(builder, 4, "type", "box", true);
            VectorProperty(builder, 4, "position_world_m", position, false);
            Indent(builder, 3).AppendLine(comma ? "}," : "}");
        }

        private static void AppendFrame(StringBuilder builder, FrameData frame, bool comma)
        {
            Indent(builder, 2).AppendLine("{");
            NumberProperty(builder, 3, "frame_index", frame.FrameIndex, true);
            NumberProperty(builder, 3, "timestamp_ns", frame.TimestampNs, true);
            VectorProperty(builder, 3, "subject_root_world_m", frame.RootWorld, true);
            VectorProperty(builder, 3, "subject_velocity_world_mps", frame.VelocityWorld, true);

            Indent(builder, 3).AppendLine("\"landmarks\": [");
            for (int index = 0; index < frame.Landmarks.Count; index++)
            {
                AppendLandmark(builder, frame.Landmarks[index], index < frame.Landmarks.Count - 1);
            }
            Indent(builder, 3).AppendLine("],");

            Indent(builder, 3).AppendLine("\"tail_curve_world_m\": [");
            for (int index = 0; index < frame.TailCurveWorld.Count; index++)
            {
                Indent(builder, 4);
                AppendVector(builder, frame.TailCurveWorld[index]);
                builder.AppendLine(index < frame.TailCurveWorld.Count - 1 ? "," : string.Empty);
            }
            Indent(builder, 3).AppendLine("],");

            AppendContacts(builder);
            Indent(builder, 3).AppendLine("\"spatial_relations\": [");
            Indent(builder, 4).AppendLine("{");
            Property(builder, 5, "subject_id", SubjectId, true);
            Property(builder, 5, "relation", "on", true);
            Property(builder, 5, "object_id", "floor", false);
            Indent(builder, 4).AppendLine("}");
            Indent(builder, 3).AppendLine("]");
            Indent(builder, 2).AppendLine(comma ? "}," : "}");
        }

        private static void AppendLandmark(
            StringBuilder builder,
            LandmarkFrame landmark,
            bool comma)
        {
            Indent(builder, 4).AppendLine("{");
            Property(builder, 5, "semantic_name", landmark.Name, true);
            VectorProperty(builder, 5, "world_m", landmark.World, true);
            VectorProperty(builder, 5, "camera_m", landmark.Camera, true);
            Vector2Property(builder, 5, "image_px", landmark.Image, true);
            Property(builder, 5, "visibility", landmark.Visibility, false);
            Indent(builder, 4).AppendLine(comma ? "}," : "}");
        }

        private static void AppendContacts(StringBuilder builder)
        {
            string[] contactNames =
            {
                "left_front_paw_contact",
                "right_front_paw_contact",
                "left_hind_paw_contact",
                "right_hind_paw_contact"
            };

            Indent(builder, 3).AppendLine("\"contacts\": [");
            for (int index = 0; index < contactNames.Length; index++)
            {
                Indent(builder, 4).AppendLine("{");
                Property(builder, 5, "semantic_name", contactNames[index], true);
                BooleanProperty(builder, 5, "active", true, true);
                Property(builder, 5, "support_surface_id", "floor", false);
                Indent(builder, 4).AppendLine(index < contactNames.Length - 1 ? "}," : "}");
            }
            Indent(builder, 3).AppendLine("],");
        }

        private static void Property(
            StringBuilder builder,
            int depth,
            string name,
            string value,
            bool comma)
        {
            Indent(builder, depth).Append('"').Append(Escape(name)).Append("\": \"")
                .Append(Escape(value)).Append('"');
            builder.AppendLine(comma ? "," : string.Empty);
        }

        private static void NumberProperty(
            StringBuilder builder,
            int depth,
            string name,
            long value,
            bool comma)
        {
            Indent(builder, depth).Append('"').Append(Escape(name)).Append("\": ")
                .Append(value.ToString(CultureInfo.InvariantCulture));
            builder.AppendLine(comma ? "," : string.Empty);
        }

        private static void NumberProperty(
            StringBuilder builder,
            int depth,
            string name,
            float value,
            bool comma)
        {
            Indent(builder, depth).Append('"').Append(Escape(name)).Append("\": ")
                .Append(Format(value));
            builder.AppendLine(comma ? "," : string.Empty);
        }

        private static void BooleanProperty(
            StringBuilder builder,
            int depth,
            string name,
            bool value,
            bool comma)
        {
            Indent(builder, depth).Append('"').Append(Escape(name)).Append("\": ")
                .Append(value ? "true" : "false");
            builder.AppendLine(comma ? "," : string.Empty);
        }

        private static void VectorProperty(
            StringBuilder builder,
            int depth,
            string name,
            Vector3 value,
            bool comma)
        {
            Indent(builder, depth).Append('"').Append(Escape(name)).Append("\": ");
            AppendVector(builder, value);
            builder.AppendLine(comma ? "," : string.Empty);
        }

        private static void Vector2Property(
            StringBuilder builder,
            int depth,
            string name,
            Vector2 value,
            bool comma)
        {
            Indent(builder, depth).Append('"').Append(Escape(name)).Append("\": [")
                .Append(Format(value.x)).Append(", ").Append(Format(value.y)).Append(']');
            builder.AppendLine(comma ? "," : string.Empty);
        }

        private static void AppendVector(StringBuilder builder, Vector3 value)
        {
            builder.Append('[')
                .Append(Format(value.x)).Append(", ")
                .Append(Format(value.y)).Append(", ")
                .Append(Format(value.z)).Append(']');
        }

        private static void StringArrayValue(
            StringBuilder builder,
            int depth,
            string value,
            bool comma)
        {
            Indent(builder, depth).Append('"').Append(Escape(value)).Append('"');
            builder.AppendLine(comma ? "," : string.Empty);
        }

        private static StringBuilder Indent(StringBuilder builder, int depth)
        {
            return builder.Append(' ', depth * 2);
        }

        private static string Format(float value)
        {
            if (float.IsNaN(value) || float.IsInfinity(value))
            {
                throw new InvalidOperationException("Cannot export a non-finite value.");
            }
            return value.ToString("R", CultureInfo.InvariantCulture);
        }

        private static string Escape(string value)
        {
            return value.Replace("\\", "\\\\").Replace("\"", "\\\"");
        }

        private static string DefaultOutputPath()
        {
            return Path.GetFullPath(Path.Combine(
                Application.dataPath,
                "..",
                "..",
                "synthetic",
                "fixtures",
                "stage-s0-unity-export.json"));
        }

        private static string CommandLineValue(string key)
        {
            string[] args = Environment.GetCommandLineArgs();
            for (int index = 0; index < args.Length - 1; index++)
            {
                if (string.Equals(args[index], key, StringComparison.Ordinal))
                {
                    return args[index + 1];
                }
            }
            return null;
        }
    }
}

using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace CatPose.StageS0
{
    /// <summary>
    /// Exports a deterministic software-only annotation fixture from Unity runtime
    /// transforms. The procedural proxy validates the annotation handshake, not visual
    /// realism or real-cat accuracy.
    /// </summary>
    public static class StageS0SyntheticExporter
    {
        private const int Seed = 17;
        private const int FrameCount = 5;
        private const long FixedTimestepNs = 100_000_000;
        private const int ImageWidth = 640;
        private const int ImageHeight = 480;
        private const float VerticalFieldOfView = 60.0f;
        private const string SequenceId = "stage-s0-proxy-v0";
        private const string SubjectId = "proxy-cat-001";
        private const string ExporterVersion = "StageS0SyntheticExporter-v0.2";

        [Serializable]
        private sealed class EngineData
        {
            public string name;
            public string project;
            public string required_editor;
            public string exporter;
        }

        [Serializable]
        private sealed class DeterminismData
        {
            public int seed;
            public long fixed_timestep_ns;
            public int frame_count;
            public string coordinate_convention;
        }

        [Serializable]
        private sealed class CameraData
        {
            public string camera_id;
            public int[] resolution_px;
            public float vertical_fov_degrees;
            public Vector3 position_world_m;
            public Vector3 look_at_world_m;
            public string screen_origin;
        }

        [Serializable]
        private sealed class PlaneData
        {
            public Vector3 normal;
            public float offset_m;
        }

        [Serializable]
        private sealed class SupportSurfaceData
        {
            public string object_id;
            public PlaneData plane_world;
        }

        [Serializable]
        private sealed class SceneObjectData
        {
            public string object_id;
            public string type;
            public Vector3 position_world_m;
        }

        [Serializable]
        private sealed class SceneData
        {
            public SupportSurfaceData[] support_surfaces;
            public SceneObjectData[] objects;
        }

        [Serializable]
        private sealed class LandmarkData
        {
            public string semantic_name;
            public Vector3 world_m;
            public Vector3 camera_m;
            public Vector2 image_px;
            public string visibility;
        }

        [Serializable]
        private sealed class ContactData
        {
            public string semantic_name;
            public bool active;
            public string support_surface_id;
        }

        [Serializable]
        private sealed class SpatialRelationData
        {
            public string subject_id;
            public string relation;
            public string object_id;
        }

        [Serializable]
        private sealed class FrameData
        {
            public int frame_index;
            public long timestamp_ns;
            public Vector3 subject_root_world_m;
            public Vector3 subject_velocity_world_mps;
            public LandmarkData[] landmarks;
            public Vector3[] tail_curve_world_m;
            public ContactData[] contacts;
            public SpatialRelationData[] spatial_relations;
        }

        [Serializable]
        private sealed class SequenceData
        {
            public string schema_version;
            public string sequence_id;
            public string subject_id;
            public string evidence_tier;
            public string quality;
            public string units;
            public EngineData engine;
            public DeterminismData determinism;
            public CameraData camera;
            public SceneData scene;
            public string[] lineage;
            public FrameData[] frames;
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
            new LandmarkDefinition("nose", new Vector3(0.0f, 0.55f, 0.65f)),
            new LandmarkDefinition("left_ear_tip", new Vector3(-0.16f, 0.82f, 0.48f)),
            new LandmarkDefinition("right_ear_tip", new Vector3(0.16f, 0.82f, 0.48f)),
            new LandmarkDefinition("left_front_paw", new Vector3(-0.18f, 0.0f, 0.38f)),
            new LandmarkDefinition("right_front_paw", new Vector3(0.18f, 0.0f, 0.38f)),
            new LandmarkDefinition("left_hind_paw", new Vector3(-0.18f, 0.0f, -0.35f)),
            new LandmarkDefinition("right_hind_paw", new Vector3(0.18f, 0.0f, -0.35f)),
            new LandmarkDefinition("tail_base", new Vector3(0.0f, 0.35f, -0.55f))
        };

        [MenuItem("CatPose/Generate Stage S0 Synthetic Fixture")]
        public static void ExportFromMenu()
        {
            string path = DefaultOutputPath();
            Export(path);
            AssetDatabase.Refresh();
            Debug.Log("Stage S0 fixture exported to " + path);
        }

        public static void ExportFromCommandLine()
        {
            string outputArgument = CommandLineValue("-catposeOutput");
            string path = string.IsNullOrWhiteSpace(outputArgument)
                ? DefaultOutputPath()
                : Path.GetFullPath(outputArgument);
            Export(path);
            Debug.Log("Stage S0 fixture exported to " + path);
        }

        public static void Export(string outputPath)
        {
            UnityEngine.Random.InitState(Seed);

            GameObject sceneRoot = null;
            GameObject cameraObject = null;
            RenderTexture renderTexture = null;

            try
            {
                sceneRoot = BuildProxyScene(out Transform subjectRoot);
                cameraObject = BuildCamera(out Camera camera, out renderTexture);
                SequenceData sequence = BuildSequence(subjectRoot, camera);

                string directory = Path.GetDirectoryName(outputPath);
                if (string.IsNullOrWhiteSpace(directory))
                {
                    throw new InvalidOperationException("Output path has no directory.");
                }

                Directory.CreateDirectory(directory);
                string json = JsonUtility.ToJson(sequence, true) + Environment.NewLine;
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
                if (sceneRoot != null)
                {
                    UnityEngine.Object.DestroyImmediate(sceneRoot);
                }
            }
        }

        private static GameObject BuildProxyScene(out Transform subjectRoot)
        {
            GameObject sceneRoot = new GameObject("Stage S0 Temporary Scene");
            sceneRoot.hideFlags = HideFlags.HideAndDontSave;

            GameObject subject = new GameObject("Stage S0 Procedural Feline Proxy");
            subject.hideFlags = HideFlags.HideAndDontSave;
            subject.transform.SetParent(sceneRoot.transform, false);
            subjectRoot = subject.transform;

            CreatePrimitive(
                "body",
                PrimitiveType.Capsule,
                subjectRoot,
                new Vector3(0.0f, 0.38f, 0.0f),
                new Vector3(0.55f, 0.45f, 1.15f));
            CreatePrimitive(
                "head",
                PrimitiveType.Sphere,
                subjectRoot,
                new Vector3(0.0f, 0.58f, 0.50f),
                new Vector3(0.48f, 0.42f, 0.46f));
            CreatePrimitive(
                "floor",
                PrimitiveType.Cube,
                sceneRoot.transform,
                new Vector3(0.0f, -0.01f, 0.0f),
                new Vector3(3.0f, 0.02f, 4.0f));
            CreatePrimitive(
                "box-left",
                PrimitiveType.Cube,
                sceneRoot.transform,
                new Vector3(-0.8f, 0.25f, 0.4f),
                new Vector3(0.35f, 0.5f, 0.35f));
            CreatePrimitive(
                "box-right",
                PrimitiveType.Cube,
                sceneRoot.transform,
                new Vector3(0.8f, 0.25f, 0.4f),
                new Vector3(0.35f, 0.5f, 0.35f));

            return sceneRoot;
        }

        private static void CreatePrimitive(
            string name,
            PrimitiveType type,
            Transform parent,
            Vector3 localPosition,
            Vector3 localScale)
        {
            GameObject item = GameObject.CreatePrimitive(type);
            item.name = name;
            item.hideFlags = HideFlags.HideAndDontSave;
            item.transform.SetParent(parent, false);
            item.transform.localPosition = localPosition;
            item.transform.localScale = localScale;
        }

        private static GameObject BuildCamera(out Camera camera, out RenderTexture renderTexture)
        {
            GameObject cameraObject = new GameObject("Stage S0 Synthetic Camera");
            cameraObject.hideFlags = HideFlags.HideAndDontSave;
            camera = cameraObject.AddComponent<Camera>();
            camera.fieldOfView = VerticalFieldOfView;
            camera.nearClipPlane = 0.01f;
            camera.farClipPlane = 100.0f;
            camera.aspect = (float)ImageWidth / ImageHeight;
            cameraObject.transform.position = new Vector3(0.0f, 1.1f, -3.0f);
            cameraObject.transform.rotation = Quaternion.LookRotation(
                new Vector3(0.0f, 0.4f, 0.0f) - cameraObject.transform.position,
                Vector3.up);

            renderTexture = new RenderTexture(ImageWidth, ImageHeight, 24);
            renderTexture.hideFlags = HideFlags.HideAndDontSave;
            camera.targetTexture = renderTexture;
            return cameraObject;
        }

        private static SequenceData BuildSequence(Transform subjectRoot, Camera camera)
        {
            FrameData[] frames = new FrameData[FrameCount];
            Vector3 declaredVelocity = new Vector3(0.2f, 0.0f, 0.0f);

            for (int frameIndex = 0; frameIndex < FrameCount; frameIndex++)
            {
                subjectRoot.position = new Vector3(0.02f * frameIndex, 0.0f, 0.0f);
                subjectRoot.rotation = Quaternion.identity;

                List<LandmarkData> landmarks = new List<LandmarkData>();
                foreach (LandmarkDefinition definition in StaticLandmarks)
                {
                    Vector3 world = subjectRoot.TransformPoint(definition.LocalPosition);
                    landmarks.Add(ProjectLandmark(definition.Name, world, camera));
                }

                float swing = Mathf.Sin(0.7f * frameIndex);
                Vector3[] tailCurve =
                {
                    subjectRoot.TransformPoint(new Vector3(0.0f, 0.35f, -0.55f)),
                    subjectRoot.TransformPoint(new Vector3(0.05f * swing, 0.42f, -0.80f)),
                    subjectRoot.TransformPoint(new Vector3(0.12f * swing, 0.48f, -1.00f)),
                    subjectRoot.TransformPoint(new Vector3(0.20f * swing, 0.55f, -1.15f))
                };
                landmarks.Add(ProjectLandmark("tail_tip", tailCurve[tailCurve.Length - 1], camera));

                frames[frameIndex] = new FrameData
                {
                    frame_index = frameIndex,
                    timestamp_ns = frameIndex * FixedTimestepNs,
                    subject_root_world_m = subjectRoot.position,
                    subject_velocity_world_mps = declaredVelocity,
                    landmarks = landmarks.ToArray(),
                    tail_curve_world_m = tailCurve,
                    contacts = BuildContacts(),
                    spatial_relations = new[]
                    {
                        new SpatialRelationData
                        {
                            subject_id = SubjectId,
                            relation = "on",
                            object_id = "floor"
                        }
                    }
                };
            }

            return new SequenceData
            {
                schema_version = "0.1.0",
                sequence_id = SequenceId,
                subject_id = SubjectId,
                evidence_tier = "S",
                quality = "gold",
                units = "metres",
                engine = new EngineData
                {
                    name = "Unity",
                    project = "cat-pose-benchmark/unity-viewer",
                    required_editor = Application.unityVersion,
                    exporter = ExporterVersion
                },
                determinism = new DeterminismData
                {
                    seed = Seed,
                    fixed_timestep_ns = FixedTimestepNs,
                    frame_count = FrameCount,
                    coordinate_convention = "unity-left-handed-x-right-y-up-z-forward"
                },
                camera = new CameraData
                {
                    camera_id = "synthetic-camera-0",
                    resolution_px = new[] { ImageWidth, ImageHeight },
                    vertical_fov_degrees = VerticalFieldOfView,
                    position_world_m = camera.transform.position,
                    look_at_world_m = new Vector3(0.0f, 0.4f, 0.0f),
                    screen_origin = "bottom_left"
                },
                scene = new SceneData
                {
                    support_surfaces = new[]
                    {
                        new SupportSurfaceData
                        {
                            object_id = "floor",
                            plane_world = new PlaneData
                            {
                                normal = Vector3.up,
                                offset_m = 0.0f
                            }
                        }
                    },
                    objects = new[]
                    {
                        new SceneObjectData
                        {
                            object_id = "box-left",
                            type = "box",
                            position_world_m = new Vector3(-0.8f, 0.25f, 0.4f)
                        },
                        new SceneObjectData
                        {
                            object_id = "box-right",
                            type = "box",
                            position_world_m = new Vector3(0.8f, 0.25f, 0.4f)
                        }
                    }
                },
                lineage = new[]
                {
                    "generator:procedural-proxy-v0.2",
                    "seed:" + Seed,
                    "fixed-timestep-ns:" + FixedTimestepNs
                },
                frames = frames
            };
        }

        private static LandmarkData ProjectLandmark(string name, Vector3 world, Camera camera)
        {
            Vector3 cameraPoint = camera.transform.InverseTransformPoint(world);
            Vector3 screen = camera.WorldToScreenPoint(world);
            bool visible = screen.z > 0.0f
                && screen.x >= 0.0f && screen.x <= ImageWidth
                && screen.y >= 0.0f && screen.y <= ImageHeight;

            return new LandmarkData
            {
                semantic_name = name,
                world_m = world,
                camera_m = cameraPoint,
                image_px = new Vector2(screen.x, screen.y),
                visibility = visible ? "visible" : "out_of_frame"
            };
        }

        private static ContactData[] BuildContacts()
        {
            return new[]
            {
                Contact("left_front_paw_contact"),
                Contact("right_front_paw_contact"),
                Contact("left_hind_paw_contact"),
                Contact("right_hind_paw_contact")
            };
        }

        private static ContactData Contact(string name)
        {
            return new ContactData
            {
                semantic_name = name,
                active = true,
                support_surface_id = "floor"
            };
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

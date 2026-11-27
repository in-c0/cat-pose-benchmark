using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace CatPose.S0B
{
    [Serializable]
    public class Vec2Record
    {
        public float x;
        public float y;

        public Vec2Record(Vector2 value)
        {
            x = value.x;
            y = value.y;
        }
    }

    [Serializable]
    public class Vec3Record
    {
        public float x;
        public float y;
        public float z;

        public Vec3Record(Vector3 value)
        {
            x = value.x;
            y = value.y;
            z = value.z;
        }
    }

    [Serializable]
    public class CameraRecord
    {
        public string camera_id;
        public Vec3Record position_world_m;
        public int width_px;
        public int height_px;
        public float fx_px;
        public float fy_px;
        public float cx_px;
        public float cy_px;
    }

    [Serializable]
    public class LandmarkRecord
    {
        public string name;
        public Vec3Record world_m;
        public Vec2Record image_px;
        public string visibility;
    }

    [Serializable]
    public class ContactRecord
    {
        public string paw_name;
        public bool floor_contact;
    }

    [Serializable]
    public class FrameRecord
    {
        public int frame_index;
        public long timestamp_ns;
        public Vec3Record root_world_m;
        public Vec3Record occluder_world_m;
        public LandmarkRecord[] landmarks;
        public Vec3Record[] tail_world_m;
        public Vec2Record[] tail_image_px;
        public ContactRecord[] contacts;
    }

    [Serializable]
    public class UnityExportRecord
    {
        public string export_version;
        public string unity_editor_version;
        public string runtime_source;
        public string reference_bundle_version;
        public string sequence_id;
        public string subject_id;
        public float dt_seconds;
        public long start_timestamp_ns;
        public CameraRecord camera;
        public Vec3Record occluder_half_extents_m;
        public int frame_count;
        public FrameRecord[] frames;
    }

    public static class S0BProxyExportCommand
    {
        public const string ExportVersion = "S0B-unity-raw-v0";
        public const string ReferenceBundleVersion = "S0A-proxy-handshake-v0";
        public const string SequenceId = "s0a-proxy-sequence-0001";
        public const string SubjectId = "synthetic-cat-proxy-0001";
        public const float DtSeconds = 0.1f;
        public const int FrameCount = 5;
        public const long StartTimestampNs = 1700000000000000000L;

        private const int WidthPx = 640;
        private const int HeightPx = 480;
        private const float FxPx = 500.0f;
        private const float FyPx = 500.0f;
        private const float CxPx = 320.0f;
        private const float CyPx = 240.0f;
        private const float FloorY = 0.0f;
        private const float ContactTolerance = 1e-6f;

        private static readonly Vector3 CameraWorld = new Vector3(0.0f, 0.8f, 0.0f);
        private static readonly Vector3 OccluderHalfExtents = new Vector3(0.08f, 0.15f, 0.10f);

        private static readonly string[] LandmarkNames =
        {
            "nose_tip",
            "left_ear_tip",
            "right_ear_tip",
            "withers_visible",
            "sacrum_visible",
            "left_front_paw_center",
            "right_front_paw_center",
            "left_hind_paw_center",
            "right_hind_paw_center",
        };

        private static readonly Vector3[] LandmarkLocalPositions =
        {
            new Vector3(0.0f, 0.15f, 0.35f),
            new Vector3(-0.14f, 0.32f, 0.15f),
            new Vector3(0.14f, 0.32f, 0.15f),
            new Vector3(0.0f, 0.22f, 0.0f),
            new Vector3(0.0f, 0.18f, -0.35f),
            new Vector3(-0.12f, -0.40f, 0.18f),
            new Vector3(0.12f, -0.40f, 0.18f),
            new Vector3(-0.12f, -0.40f, -0.28f),
            new Vector3(0.12f, -0.40f, -0.28f),
        };

        private static readonly Vector3[] TailLocalPositions =
        {
            new Vector3(0.0f, 0.15f, -0.45f),
            new Vector3(0.0f, 0.18f, -0.62f),
            new Vector3(0.0f, 0.20f, -0.79f),
            new Vector3(0.0f, 0.19f, -0.96f),
        };

        private static readonly string[] PawNames =
        {
            "left_front_paw_center",
            "right_front_paw_center",
            "left_hind_paw_center",
            "right_hind_paw_center",
        };

        [MenuItem("CatPose/S0B/Export deterministic proxy")]
        public static void Run()
        {
            string outputPath = ResolveOutputPath();
            GameObject root = null;
            GameObject cameraObject = null;
            GameObject floorObject = null;
            GameObject occluderObject = null;

            try
            {
                root = new GameObject("S0B-ProxyRoot");
                cameraObject = new GameObject("S0B-Camera");
                floorObject = new GameObject("S0B-Floor");
                occluderObject = new GameObject("S0B-Occluder");

                root.transform.position = RootPosition(0);
                root.transform.rotation = Quaternion.identity;

                cameraObject.transform.position = CameraWorld;
                cameraObject.transform.rotation = Quaternion.identity;
                Camera cameraComponent = cameraObject.AddComponent<Camera>();
                cameraComponent.enabled = false;

                floorObject.transform.position = new Vector3(0.0f, FloorY, 0.0f);
                floorObject.transform.rotation = Quaternion.identity;

                occluderObject.transform.position = OccluderPosition(0);
                occluderObject.transform.rotation = Quaternion.identity;
                BoxCollider occluderCollider = occluderObject.AddComponent<BoxCollider>();
                occluderCollider.center = Vector3.zero;
                occluderCollider.size = 2.0f * OccluderHalfExtents;

                Dictionary<string, Transform> landmarks = CreateLandmarks(root.transform);
                Transform[] tail = CreateTail(root.transform);

                UnityExportRecord export = new UnityExportRecord
                {
                    export_version = ExportVersion,
                    unity_editor_version = Application.unityVersion,
                    runtime_source = "unity_editor",
                    reference_bundle_version = ReferenceBundleVersion,
                    sequence_id = SequenceId,
                    subject_id = SubjectId,
                    dt_seconds = DtSeconds,
                    start_timestamp_ns = StartTimestampNs,
                    camera = new CameraRecord
                    {
                        camera_id = "camera-main",
                        position_world_m = new Vec3Record(cameraObject.transform.position),
                        width_px = WidthPx,
                        height_px = HeightPx,
                        fx_px = FxPx,
                        fy_px = FyPx,
                        cx_px = CxPx,
                        cy_px = CyPx,
                    },
                    occluder_half_extents_m = new Vec3Record(OccluderHalfExtents),
                    frame_count = FrameCount,
                    frames = new FrameRecord[FrameCount],
                };

                for (int frameIndex = 0; frameIndex < FrameCount; frameIndex++)
                {
                    ApplyFrame(frameIndex, root.transform, landmarks, tail, occluderObject.transform);
                    export.frames[frameIndex] = CaptureFrame(
                        frameIndex,
                        root.transform,
                        cameraObject.transform,
                        floorObject.transform,
                        occluderCollider,
                        occluderObject.transform,
                        landmarks,
                        tail
                    );
                }

                Directory.CreateDirectory(Path.GetDirectoryName(outputPath) ?? ".");
                File.WriteAllText(outputPath, JsonUtility.ToJson(export, true) + Environment.NewLine);
                Debug.Log("S0B Unity export written to: " + outputPath);
            }
            finally
            {
                DestroyImmediateIfPresent(occluderObject);
                DestroyImmediateIfPresent(floorObject);
                DestroyImmediateIfPresent(cameraObject);
                DestroyImmediateIfPresent(root);
            }
        }

        private static Dictionary<string, Transform> CreateLandmarks(Transform root)
        {
            Dictionary<string, Transform> result = new Dictionary<string, Transform>();
            for (int index = 0; index < LandmarkNames.Length; index++)
            {
                GameObject point = new GameObject(LandmarkNames[index]);
                point.transform.SetParent(root, false);
                point.transform.localPosition = LandmarkLocalPositions[index];
                point.transform.localRotation = Quaternion.identity;
                result.Add(LandmarkNames[index], point.transform);
            }
            return result;
        }

        private static Transform[] CreateTail(Transform root)
        {
            Transform[] result = new Transform[TailLocalPositions.Length];
            for (int index = 0; index < TailLocalPositions.Length; index++)
            {
                GameObject point = new GameObject("tail_point_" + index.ToString("00", CultureInfo.InvariantCulture));
                point.transform.SetParent(root, false);
                point.transform.localPosition = TailLocalPositions[index];
                point.transform.localRotation = Quaternion.identity;
                result[index] = point.transform;
            }
            return result;
        }

        private static void ApplyFrame(
            int frameIndex,
            Transform root,
            Dictionary<string, Transform> landmarks,
            Transform[] tail,
            Transform occluder
        )
        {
            root.position = RootPosition(frameIndex);

            for (int index = 0; index < LandmarkNames.Length; index++)
            {
                string name = LandmarkNames[index];
                Vector3 local = LandmarkLocalPositions[index];
                if (name == "left_hind_paw_center" && (frameIndex == 2 || frameIndex == 3))
                {
                    local.y += 0.08f;
                }
                landmarks[name].localPosition = local;
            }

            float bend = 0.015f * frameIndex;
            for (int index = 0; index < tail.Length; index++)
            {
                Vector3 local = TailLocalPositions[index];
                local.x += bend * index;
                tail[index].localPosition = local;
            }

            occluder.position = OccluderPosition(frameIndex);
            Physics.SyncTransforms();
        }

        private static FrameRecord CaptureFrame(
            int frameIndex,
            Transform root,
            Transform cameraTransform,
            Transform floorTransform,
            BoxCollider occluderCollider,
            Transform occluderTransform,
            Dictionary<string, Transform> landmarks,
            Transform[] tail
        )
        {
            LandmarkRecord[] landmarkRecords = new LandmarkRecord[LandmarkNames.Length];
            for (int index = 0; index < LandmarkNames.Length; index++)
            {
                string name = LandmarkNames[index];
                Vector3 world = landmarks[name].position;
                landmarkRecords[index] = new LandmarkRecord
                {
                    name = name,
                    world_m = new Vec3Record(world),
                    image_px = new Vec2Record(Project(cameraTransform, world)),
                    visibility = Visibility(cameraTransform, occluderCollider, world),
                };
            }

            Vec3Record[] tailWorld = new Vec3Record[tail.Length];
            Vec2Record[] tailImage = new Vec2Record[tail.Length];
            for (int index = 0; index < tail.Length; index++)
            {
                Vector3 world = tail[index].position;
                tailWorld[index] = new Vec3Record(world);
                tailImage[index] = new Vec2Record(Project(cameraTransform, world));
            }

            ContactRecord[] contacts = new ContactRecord[PawNames.Length];
            for (int index = 0; index < PawNames.Length; index++)
            {
                string pawName = PawNames[index];
                float dy = Mathf.Abs(landmarks[pawName].position.y - floorTransform.position.y);
                contacts[index] = new ContactRecord
                {
                    paw_name = pawName,
                    floor_contact = dy <= ContactTolerance,
                };
            }

            return new FrameRecord
            {
                frame_index = frameIndex,
                timestamp_ns = StartTimestampNs + frameIndex * 100000000L,
                root_world_m = new Vec3Record(root.position),
                occluder_world_m = new Vec3Record(occluderTransform.position),
                landmarks = landmarkRecords,
                tail_world_m = tailWorld,
                tail_image_px = tailImage,
                contacts = contacts,
            };
        }

        private static Vector3 RootPosition(int frameIndex)
        {
            double t = frameIndex * 0.1;
            double x = 0.15 * t + 0.1 * t * t;
            return new Vector3((float)x, 0.40f, 3.00f);
        }

        private static Vector3 OccluderPosition(int frameIndex)
        {
            float x = (frameIndex == 2 || frameIndex == 3) ? -0.05f : 0.80f;
            return new Vector3(x, 0.75f, 1.50f);
        }

        private static Vector2 Project(Transform cameraTransform, Vector3 world)
        {
            Vector3 camera = cameraTransform.InverseTransformPoint(world);
            if (camera.z <= 0.0f)
            {
                throw new InvalidOperationException("S0B point is not in front of the camera");
            }
            float u = FxPx * camera.x / camera.z + CxPx;
            float v = CyPx - FyPx * camera.y / camera.z;
            return new Vector2(u, v);
        }

        private static string Visibility(
            Transform cameraTransform,
            BoxCollider occluderCollider,
            Vector3 world
        )
        {
            Vector2 image = Project(cameraTransform, world);
            if (image.x < 0.0f || image.x >= WidthPx || image.y < 0.0f || image.y >= HeightPx)
            {
                return "out_of_frame";
            }

            Vector3 delta = world - cameraTransform.position;
            float distance = delta.magnitude;
            if (distance <= 0.0f)
            {
                throw new InvalidOperationException("S0B landmark coincides with camera position");
            }
            Ray ray = new Ray(cameraTransform.position, delta / distance);
            if (occluderCollider.bounds.IntersectRay(ray, out float hitDistance)
                && hitDistance > 0.0f
                && hitDistance < distance - 1e-6f)
            {
                return "fully_occluded";
            }
            return "visible";
        }

        private static string ResolveOutputPath()
        {
            string[] args = Environment.GetCommandLineArgs();
            for (int index = 0; index < args.Length - 1; index++)
            {
                if (args[index] == "-s0Output")
                {
                    return Path.GetFullPath(args[index + 1]);
                }
            }
            return Path.GetFullPath(Path.Combine(Application.dataPath, "..", "S0B-export.json"));
        }

        private static void DestroyImmediateIfPresent(GameObject value)
        {
            if (value != null)
            {
                UnityEngine.Object.DestroyImmediate(value);
            }
        }
    }
}

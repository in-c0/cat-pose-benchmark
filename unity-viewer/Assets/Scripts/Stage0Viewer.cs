using System;
using System.IO;
using UnityEngine;

namespace CatPose.Stage0
{
    [Serializable]
    public sealed class Vec2Dto
    {
        public float x;
        public float y;
    }

    [Serializable]
    public sealed class Vec3Dto
    {
        public float x;
        public float y;
        public float z;
    }

    [Serializable]
    public sealed class BoundsDto
    {
        public Vec3Dto min_m;
        public Vec3Dto max_m;
    }

    [Serializable]
    public sealed class MirrorDto
    {
        public string name;
        public Vec3Dto plane_point_m;
        public Vec3Dto plane_normal;
        public Vec3Dto vertical_axis;
        public Vec2Dto size_m;
    }

    [Serializable]
    public sealed class CameraDto
    {
        public string name;
        public string kind;
        public Vec3Dto position_m;
        public Vec3Dto look_at_m;
    }

    [Serializable]
    public sealed class RayDto
    {
        public string name;
        public string kind;
        public Vec3Dto[] points_m;
    }

    [Serializable]
    public sealed class Stage0SceneDto
    {
        public string schema_version;
        public string source_layout_schema_version;
        public string layout_name;
        public string units;
        public string unity_conversion;
        public BoundsDto capture_volume;
        public Vec3Dto representative_point_m;
        public MirrorDto[] mirrors;
        public CameraDto[] cameras;
        public RayDto[] rays;
    }

    public sealed class Stage0Viewer : MonoBehaviour
    {
        private const string SceneFileName = "stage0-scene-v2.json";
        private Material _lineMaterial;
        private Material _solidMaterial;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Bootstrap()
        {
            if (FindFirstObjectByType<Stage0Viewer>() != null)
            {
                return;
            }

            GameObject root = new GameObject("CatPose Stage 0 Viewer");
            root.AddComponent<Stage0Viewer>();
        }

        private void Start()
        {
            string path = Path.Combine(Application.streamingAssetsPath, SceneFileName);
            if (!File.Exists(path))
            {
                Debug.LogError($"Stage 0 scene file not found: {path}");
                return;
            }

            Stage0SceneDto scene = JsonUtility.FromJson<Stage0SceneDto>(File.ReadAllText(path));
            if (scene == null || scene.schema_version != "0.2.0")
            {
                Debug.LogError("Unsupported or invalid Stage 0 scene schema.");
                return;
            }

            CreateMaterials();
            EnsureViewCamera();
            EnsureLighting();
            BuildScene(scene);
        }

        private void CreateMaterials()
        {
            Shader lineShader = Shader.Find("Sprites/Default");
            Shader solidShader = Shader.Find("Standard");
            if (lineShader == null || solidShader == null)
            {
                throw new InvalidOperationException("Required built-in shaders are unavailable.");
            }

            _lineMaterial = new Material(lineShader);
            _solidMaterial = new Material(solidShader);
        }

        private static Vector3 ToUnity(Vec3Dto source)
        {
            if (source == null)
            {
                throw new ArgumentNullException(nameof(source));
            }

            // Source: +x right, +y through portal, +z up.
            // Unity:  +x right, +y up,             +z forward.
            return new Vector3(source.x, source.z, source.y);
        }

        private void BuildScene(Stage0SceneDto scene)
        {
            GameObject generated = new GameObject($"Generated {scene.layout_name}");
            generated.transform.SetParent(transform, false);

            CreateCoordinateAxes(generated.transform);
            CreateCaptureVolume(scene.capture_volume, generated.transform);
            CreatePoint("Representative Point", ToUnity(scene.representative_point_m), 0.035f, generated.transform);

            foreach (MirrorDto mirror in scene.mirrors ?? Array.Empty<MirrorDto>())
            {
                CreateMirror(mirror, generated.transform);
            }

            foreach (CameraDto camera in scene.cameras ?? Array.Empty<CameraDto>())
            {
                CreateCameraMarker(camera, generated.transform);
            }

            foreach (RayDto ray in scene.rays ?? Array.Empty<RayDto>())
            {
                CreateRay(ray, generated.transform);
            }
        }

        private void CreateMirror(MirrorDto mirror, Transform parent)
        {
            Vector3 normal = ToUnity(mirror.plane_normal).normalized;
            Vector3 up = ToUnity(mirror.vertical_axis).normalized;

            GameObject body = GameObject.CreatePrimitive(PrimitiveType.Cube);
            body.name = $"Mirror {mirror.name}";
            body.transform.SetParent(parent, false);
            body.transform.position = ToUnity(mirror.plane_point_m);
            body.transform.rotation = Quaternion.LookRotation(normal, up);
            body.transform.localScale = new Vector3(mirror.size_m.x, mirror.size_m.y, 0.008f);
            body.GetComponent<Renderer>().material = new Material(_solidMaterial)
            {
                color = new Color(0.35f, 0.65f, 0.85f, 0.55f)
            };

            Collider collider = body.GetComponent<Collider>();
            if (collider != null)
            {
                Destroy(collider);
            }

            CreateLine(
                $"Normal {mirror.name}",
                new[] { body.transform.position, body.transform.position + normal * 0.25f },
                0.006f,
                new Color(0.2f, 0.8f, 1.0f),
                parent
            );
        }

        private void CreateCameraMarker(CameraDto camera, Transform parent)
        {
            Vector3 position = ToUnity(camera.position_m);
            Vector3 lookAt = ToUnity(camera.look_at_m);

            GameObject marker = GameObject.CreatePrimitive(PrimitiveType.Cube);
            marker.name = $"{camera.kind} camera: {camera.name}";
            marker.transform.SetParent(parent, false);
            marker.transform.position = position;
            marker.transform.localScale = camera.kind == "physical"
                ? new Vector3(0.12f, 0.08f, 0.16f)
                : new Vector3(0.09f, 0.06f, 0.12f);
            marker.transform.rotation = Quaternion.LookRotation((lookAt - position).normalized, Vector3.up);
            marker.GetComponent<Renderer>().material = new Material(_solidMaterial)
            {
                color = camera.kind == "physical"
                    ? new Color(0.95f, 0.65f, 0.15f)
                    : new Color(0.75f, 0.3f, 0.9f)
            };

            Collider collider = marker.GetComponent<Collider>();
            if (collider != null)
            {
                Destroy(collider);
            }

            CreateLine(
                $"Look direction {camera.name}",
                new[] { position, lookAt },
                0.004f,
                camera.kind == "physical" ? Color.yellow : Color.magenta,
                parent
            );
        }

        private void CreateRay(RayDto ray, Transform parent)
        {
            if (ray.points_m == null || ray.points_m.Length < 2)
            {
                return;
            }

            Vector3[] points = new Vector3[ray.points_m.Length];
            for (int index = 0; index < ray.points_m.Length; index++)
            {
                points[index] = ToUnity(ray.points_m[index]);
            }

            CreateLine(
                ray.name,
                points,
                0.008f,
                ray.kind == "direct" ? Color.green : Color.cyan,
                parent
            );
        }

        private void CreateCaptureVolume(BoundsDto bounds, Transform parent)
        {
            Vector3 minimum = ToUnity(bounds.min_m);
            Vector3 maximum = ToUnity(bounds.max_m);
            Vector3 centre = (minimum + maximum) * 0.5f;
            Vector3 extent = (maximum - minimum) * 0.5f;

            Vector3[] corners =
            {
                centre + new Vector3(-extent.x, -extent.y, -extent.z),
                centre + new Vector3( extent.x, -extent.y, -extent.z),
                centre + new Vector3( extent.x, -extent.y,  extent.z),
                centre + new Vector3(-extent.x, -extent.y,  extent.z),
                centre + new Vector3(-extent.x,  extent.y, -extent.z),
                centre + new Vector3( extent.x,  extent.y, -extent.z),
                centre + new Vector3( extent.x,  extent.y,  extent.z),
                centre + new Vector3(-extent.x,  extent.y,  extent.z)
            };

            int[,] edges =
            {
                {0, 1}, {1, 2}, {2, 3}, {3, 0},
                {4, 5}, {5, 6}, {6, 7}, {7, 4},
                {0, 4}, {1, 5}, {2, 6}, {3, 7}
            };

            for (int index = 0; index < edges.GetLength(0); index++)
            {
                CreateLine(
                    $"Capture volume edge {index}",
                    new[] { corners[edges[index, 0]], corners[edges[index, 1]] },
                    0.004f,
                    Color.white,
                    parent
                );
            }
        }

        private void CreateCoordinateAxes(Transform parent)
        {
            CreateLine("Axis +X", new[] { Vector3.zero, Vector3.right * 0.4f }, 0.01f, Color.red, parent);
            CreateLine("Axis +Y", new[] { Vector3.zero, Vector3.up * 0.4f }, 0.01f, Color.green, parent);
            CreateLine("Axis +Z", new[] { Vector3.zero, Vector3.forward * 0.4f }, 0.01f, Color.blue, parent);
        }

        private GameObject CreatePoint(string name, Vector3 position, float diameter, Transform parent)
        {
            GameObject point = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            point.name = name;
            point.transform.SetParent(parent, false);
            point.transform.position = position;
            point.transform.localScale = Vector3.one * diameter;
            point.GetComponent<Renderer>().material = new Material(_solidMaterial) { color = Color.white };
            Collider collider = point.GetComponent<Collider>();
            if (collider != null)
            {
                Destroy(collider);
            }
            return point;
        }

        private void CreateLine(
            string name,
            Vector3[] points,
            float width,
            Color color,
            Transform parent)
        {
            GameObject lineObject = new GameObject(name);
            lineObject.transform.SetParent(parent, false);
            LineRenderer line = lineObject.AddComponent<LineRenderer>();
            line.useWorldSpace = true;
            line.positionCount = points.Length;
            line.SetPositions(points);
            line.startWidth = width;
            line.endWidth = width;
            line.material = new Material(_lineMaterial) { color = color };
        }

        private static void EnsureViewCamera()
        {
            if (FindFirstObjectByType<Camera>() != null)
            {
                return;
            }

            GameObject cameraObject = new GameObject("Viewer Camera");
            Camera camera = cameraObject.AddComponent<Camera>();
            cameraObject.tag = "MainCamera";
            cameraObject.transform.position = new Vector3(0.0f, 1.45f, -3.25f);
            cameraObject.transform.rotation = Quaternion.LookRotation(
                new Vector3(0.0f, 0.45f, 0.15f) - cameraObject.transform.position,
                Vector3.up
            );
            camera.nearClipPlane = 0.01f;
            camera.farClipPlane = 100.0f;
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(0.035f, 0.04f, 0.055f);
        }

        private static void EnsureLighting()
        {
            if (FindFirstObjectByType<Light>() != null)
            {
                return;
            }

            GameObject lightObject = new GameObject("Viewer Light");
            Light light = lightObject.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.2f;
            lightObject.transform.rotation = Quaternion.Euler(45.0f, -30.0f, 0.0f);
        }
    }
}

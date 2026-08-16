using System;
using System.IO;
using UnityEngine;

namespace CatPose.Stage0
{
    [Serializable] public sealed class Vec2Dto { public float x; public float y; }
    [Serializable] public sealed class Vec3Dto { public float x; public float y; public float z; }
    [Serializable] public sealed class BoundsDto { public Vec3Dto min_m; public Vec3Dto max_m; }
    [Serializable] public sealed class MirrorDto
    {
        public string name;
        public Vec3Dto plane_point_m;
        public Vec3Dto plane_normal;
        public Vec3Dto vertical_axis;
        public Vec2Dto size_m;
    }
    [Serializable] public sealed class CameraDto
    {
        public string name;
        public string kind;
        public Vec3Dto position_m;
        public Vec3Dto look_at_m;
    }
    [Serializable] public sealed class RayDto
    {
        public string name;
        public string kind;
        public Vec3Dto[] points_m;
    }
    [Serializable] public sealed class Stage0SceneDto
    {
        public string schema_version;
        public string layout_name;
        public BoundsDto capture_volume;
        public Vec3Dto representative_point_m;
        public MirrorDto[] mirrors;
        public CameraDto[] cameras;
        public RayDto[] rays;
    }

    public sealed class Stage0Viewer : MonoBehaviour
    {
        private Material _lineMaterial;
        private Material _solidMaterial;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Bootstrap()
        {
            if (FindFirstObjectByType<Stage0Viewer>() != null) return;
            new GameObject("CatPose Stage 0 Viewer").AddComponent<Stage0Viewer>();
        }

        private void Start()
        {
            string path = Path.Combine(Application.streamingAssetsPath, "stage0-scene-v2.json");
            if (!File.Exists(path))
            {
                Debug.LogError($"Stage 0 scene file not found: {path}");
                return;
            }

            Stage0SceneDto scene = JsonUtility.FromJson<Stage0SceneDto>(File.ReadAllText(path));
            if (scene == null || scene.schema_version != "0.2.0")
            {
                Debug.LogError("Unsupported Stage 0 scene schema.");
                return;
            }

            Shader lineShader = Shader.Find("Sprites/Default");
            Shader solidShader = Shader.Find("Standard");
            if (lineShader == null || solidShader == null)
                throw new InvalidOperationException("Required built-in shaders are unavailable.");
            _lineMaterial = new Material(lineShader);
            _solidMaterial = new Material(solidShader);

            EnsureViewCamera();
            EnsureLighting();
            Build(scene);
        }

        private static Vector3 ToUnity(Vec3Dto source) => new(source.x, source.z, source.y);

        private void Build(Stage0SceneDto scene)
        {
            Transform root = new GameObject($"Generated {scene.layout_name}").transform;
            root.SetParent(transform, false);
            CreateAxes(root);
            CreateCaptureVolume(scene.capture_volume, root);
            CreatePoint("Representative Point", ToUnity(scene.representative_point_m), 0.035f, Color.white, root);

            foreach (MirrorDto mirror in scene.mirrors ?? Array.Empty<MirrorDto>())
                CreateMirror(mirror, root);
            foreach (CameraDto camera in scene.cameras ?? Array.Empty<CameraDto>())
                CreateCameraMarker(camera, root);
            foreach (RayDto ray in scene.rays ?? Array.Empty<RayDto>())
                CreateRay(ray, root);
        }

        private void CreateMirror(MirrorDto mirror, Transform parent)
        {
            Vector3 normal = ToUnity(mirror.plane_normal).normalized;
            Vector3 up = ToUnity(mirror.vertical_axis).normalized;
            GameObject body = Primitive(
                $"Mirror {mirror.name}",
                PrimitiveType.Cube,
                ToUnity(mirror.plane_point_m),
                new Vector3(mirror.size_m.x, mirror.size_m.y, 0.008f),
                new Color(0.35f, 0.65f, 0.85f, 0.55f),
                parent
            );
            body.transform.rotation = Quaternion.LookRotation(normal, up);
            CreateLine($"Normal {mirror.name}", new[] { body.transform.position, body.transform.position + normal * 0.25f }, 0.006f, Color.cyan, parent);
        }

        private void CreateCameraMarker(CameraDto camera, Transform parent)
        {
            Vector3 position = ToUnity(camera.position_m);
            Vector3 lookAt = ToUnity(camera.look_at_m);
            bool physical = camera.kind == "physical";
            GameObject marker = Primitive(
                $"{camera.kind} camera: {camera.name}",
                PrimitiveType.Cube,
                position,
                physical ? new Vector3(0.12f, 0.08f, 0.16f) : new Vector3(0.09f, 0.06f, 0.12f),
                physical ? new Color(0.95f, 0.65f, 0.15f) : new Color(0.75f, 0.3f, 0.9f),
                parent
            );
            marker.transform.rotation = Quaternion.LookRotation((lookAt - position).normalized, Vector3.up);
            CreateLine($"Look {camera.name}", new[] { position, lookAt }, 0.004f, physical ? Color.yellow : Color.magenta, parent);
        }

        private void CreateRay(RayDto ray, Transform parent)
        {
            if (ray.points_m == null || ray.points_m.Length < 2) return;
            Vector3[] points = Array.ConvertAll(ray.points_m, ToUnity);
            CreateLine(ray.name, points, 0.008f, ray.kind == "direct" ? Color.green : Color.cyan, parent);
        }

        private void CreateCaptureVolume(BoundsDto bounds, Transform parent)
        {
            Vector3 min = ToUnity(bounds.min_m);
            Vector3 max = ToUnity(bounds.max_m);
            Vector3 centre = (min + max) * 0.5f;
            Vector3 extent = (max - min) * 0.5f;
            Vector3[] c =
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
            int[,] edges = { {0,1},{1,2},{2,3},{3,0},{4,5},{5,6},{6,7},{7,4},{0,4},{1,5},{2,6},{3,7} };
            for (int index = 0; index < edges.GetLength(0); index++)
                CreateLine($"Capture edge {index}", new[] { c[edges[index, 0]], c[edges[index, 1]] }, 0.004f, Color.white, parent);
        }

        private void CreateAxes(Transform parent)
        {
            CreateLine("Axis +X", new[] { Vector3.zero, Vector3.right * 0.4f }, 0.01f, Color.red, parent);
            CreateLine("Axis +Y", new[] { Vector3.zero, Vector3.up * 0.4f }, 0.01f, Color.green, parent);
            CreateLine("Axis +Z", new[] { Vector3.zero, Vector3.forward * 0.4f }, 0.01f, Color.blue, parent);
        }

        private GameObject Primitive(string name, PrimitiveType type, Vector3 position, Vector3 scale, Color color, Transform parent)
        {
            GameObject item = GameObject.CreatePrimitive(type);
            item.name = name;
            item.transform.SetParent(parent, false);
            item.transform.position = position;
            item.transform.localScale = scale;
            item.GetComponent<Renderer>().material = new Material(_solidMaterial) { color = color };
            Collider collider = item.GetComponent<Collider>();
            if (collider != null) Destroy(collider);
            return item;
        }

        private GameObject CreatePoint(string name, Vector3 position, float diameter, Color color, Transform parent) =>
            Primitive(name, PrimitiveType.Sphere, position, Vector3.one * diameter, color, parent);

        private void CreateLine(string name, Vector3[] points, float width, Color color, Transform parent)
        {
            GameObject item = new(name);
            item.transform.SetParent(parent, false);
            LineRenderer line = item.AddComponent<LineRenderer>();
            line.useWorldSpace = true;
            line.positionCount = points.Length;
            line.SetPositions(points);
            line.startWidth = width;
            line.endWidth = width;
            line.material = new Material(_lineMaterial) { color = color };
        }

        private static void EnsureViewCamera()
        {
            if (FindFirstObjectByType<Camera>() != null) return;
            GameObject item = new("Viewer Camera");
            Camera camera = item.AddComponent<Camera>();
            item.tag = "MainCamera";
            item.transform.position = new Vector3(0f, 1.45f, -3.25f);
            item.transform.rotation = Quaternion.LookRotation(new Vector3(0f, 0.45f, 0.15f) - item.transform.position, Vector3.up);
            camera.nearClipPlane = 0.01f;
            camera.farClipPlane = 100f;
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(0.035f, 0.04f, 0.055f);
        }

        private static void EnsureLighting()
        {
            if (FindFirstObjectByType<Light>() != null) return;
            GameObject item = new("Viewer Light");
            Light light = item.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.2f;
            item.transform.rotation = Quaternion.Euler(45f, -30f, 0f);
        }
    }
}

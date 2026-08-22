using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace CatPose.Stage0.EditorTools
{
    public sealed class Stage0GeometryWindow : EditorWindow
    {
        private const string ConfigAssetPath =
            "Assets/StreamingAssets/CatPose/stage0-layouts.json";

        private static readonly Color PhysicalCameraColor = new(0.20f, 0.85f, 1.00f, 1f);
        private static readonly Color CaptureVolumeColor = new(0.25f, 1.00f, 0.45f, 1f);
        private static readonly Color MirrorColor = new(1.00f, 0.78f, 0.20f, 1f);
        private static readonly Color VirtualCameraColor = new(1.00f, 0.35f, 0.80f, 1f);
        private static readonly Color ValidRayColor = new(0.35f, 0.90f, 1.00f, 0.28f);
        private static readonly Color InvalidRayColor = new(1.00f, 0.25f, 0.25f, 0.32f);

        private Stage0Config _config;
        private string _loadError = string.Empty;
        private int _selectedLayoutIndex;
        private bool _showSamplePoints = true;
        private bool _showDirectRays;
        private bool _showReflectedRays = true;
        private bool _showInvalidRays;
        private int _rayStride = 5;
        private Vector2 _scroll;

        [MenuItem("Tools/CatPose/Stage 0 Geometry Viewer")]
        public static void Open()
        {
            Stage0GeometryWindow window = GetWindow<Stage0GeometryWindow>();
            window.titleContent = new GUIContent("CatPose Stage 0");
            window.minSize = new Vector2(430f, 620f);
            window.Show();
        }

        private void OnEnable()
        {
            SceneView.duringSceneGui += DrawScene;
            LoadConfiguration();
        }

        private void OnDisable()
        {
            SceneView.duringSceneGui -= DrawScene;
        }

        private void OnGUI()
        {
            using (new EditorGUILayout.HorizontalScope(EditorStyles.toolbar))
            {
                GUILayout.Label(ConfigAssetPath, EditorStyles.miniLabel);
                GUILayout.FlexibleSpace();
                if (GUILayout.Button("Reload", EditorStyles.toolbarButton))
                {
                    LoadConfiguration();
                }
            }

            if (!string.IsNullOrEmpty(_loadError))
            {
                EditorGUILayout.HelpBox(_loadError, MessageType.Error);
                return;
            }

            if (_config == null || _config.layouts == null || _config.layouts.Length == 0)
            {
                EditorGUILayout.HelpBox("No Stage 0 layouts were loaded.", MessageType.Warning);
                return;
            }

            _scroll = EditorGUILayout.BeginScrollView(_scroll);
            string[] layoutNames = _config.layouts
                .Select(layout => layout?.id ?? "<null>")
                .ToArray();
            int nextIndex = EditorGUILayout.Popup(
                "Layout",
                _selectedLayoutIndex,
                layoutNames);
            if (nextIndex != _selectedLayoutIndex)
            {
                _selectedLayoutIndex = nextIndex;
                SceneView.RepaintAll();
            }

            LayoutConfig layout = SelectedLayout;
            EditorGUILayout.HelpBox(layout.description, MessageType.Info);

            EditorGUILayout.LabelField("Scene overlays", EditorStyles.boldLabel);
            _showSamplePoints = EditorGUILayout.Toggle("Sample points", _showSamplePoints);
            _showDirectRays = EditorGUILayout.Toggle("Direct rays", _showDirectRays);
            _showReflectedRays = EditorGUILayout.Toggle("Reflected rays", _showReflectedRays);
            _showInvalidRays = EditorGUILayout.Toggle("Invalid rays", _showInvalidRays);
            _rayStride = EditorGUILayout.IntSlider("Ray stride", _rayStride, 1, 25);

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Coordinate contract", EditorStyles.boldLabel);
            EditorGUILayout.LabelField("Repository", "x=right, y=forward, z=up");
            EditorGUILayout.LabelField("Unity", "x=right, y=up, z=forward");
            EditorGUILayout.LabelField("Mapping", "(x, y, z) → (x, z, y)");
            EditorGUILayout.HelpBox(
                "The axis swap changes handedness intentionally. Reflected image parity is retained and displayed; it is not silently corrected.",
                MessageType.None);

            EditorGUILayout.Space();
            DrawMetrics(layout);

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Physical sensor occupancy", EditorStyles.boldLabel);
            DrawSensorRois(layout);

            EditorGUILayout.Space();
            DrawMirrorValidation(layout);
            EditorGUILayout.EndScrollView();
        }

        private LayoutConfig SelectedLayout
        {
            get
            {
                _selectedLayoutIndex = Mathf.Clamp(
                    _selectedLayoutIndex,
                    0,
                    _config.layouts.Length - 1);
                return _config.layouts[_selectedLayoutIndex];
            }
        }

        private void LoadConfiguration()
        {
            try
            {
                string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
                string fullPath = Path.Combine(
                    projectRoot,
                    ConfigAssetPath.Replace('/', Path.DirectorySeparatorChar));
                if (!File.Exists(fullPath))
                {
                    throw new FileNotFoundException(
                        "Generate the Unity config with `python -m stage0.export_unity_config`.",
                        fullPath);
                }

                string json = File.ReadAllText(fullPath);
                _config = JsonUtility.FromJson<Stage0Config>(json);
                if (_config == null)
                {
                    throw new InvalidDataException("JsonUtility returned a null Stage0Config.");
                }

                _selectedLayoutIndex = Mathf.Clamp(
                    _selectedLayoutIndex,
                    0,
                    Math.Max(0, (_config.layouts?.Length ?? 1) - 1));
                _loadError = string.Empty;
                SceneView.RepaintAll();
                Repaint();
            }
            catch (Exception exception)
            {
                _config = null;
                _loadError = exception.Message;
                Debug.LogException(exception);
            }
        }

        private void DrawMetrics(LayoutConfig layout)
        {
            EditorGUILayout.LabelField("Conditioning summary", EditorStyles.boldLabel);
            EditorGUILayout.LabelField(
                "Common three-view coverage",
                $"{layout.combinedCoverageFraction:P1}");
            EditorGUILayout.LabelField(
                "Nominal p95 radial SD",
                $"{layout.combinedP95RadialStandardDeviationMm:F3} mm");
            EditorGUILayout.LabelField(
                "Nominal p95 anisotropy",
                layout.combinedP95Anisotropy.ToString("F3"));
            EditorGUILayout.HelpBox(
                "These are ideal-plane simulation outputs, not measured calibration accuracy.",
                MessageType.Warning);
        }

        private void DrawMirrorValidation(LayoutConfig layout)
        {
            EditorGUILayout.LabelField("Reference consistency", EditorStyles.boldLabel);
            foreach (MirrorConfig mirror in layout.mirrors ?? Array.Empty<MirrorConfig>())
            {
                float errorMetres = Stage0Geometry.VirtualCameraErrorMetres(
                    _config.camera,
                    mirror);
                MessageType messageType = errorMetres <= 1e-6f
                    ? MessageType.None
                    : MessageType.Error;
                EditorGUILayout.HelpBox(
                    $"{mirror.name}: Python↔C# virtual-camera delta = {errorMetres * 1000f:F6} mm; parity = {mirror.reflectionParity}",
                    messageType);
            }
        }

        private void DrawSensorRois(LayoutConfig layout)
        {
            Vector2Int resolution = _config.camera.resolutionPx.ToVector2Int(
                nameof(_config.camera.resolutionPx));
            Rect available = GUILayoutUtility.GetRect(100f, 250f, GUILayout.ExpandWidth(true));
            float scale = Mathf.Min(
                available.width / resolution.x,
                available.height / resolution.y);
            Vector2 sensorSize = new(resolution.x * scale, resolution.y * scale);
            Rect sensor = new(
                available.x + (available.width - sensorSize.x) * 0.5f,
                available.y + (available.height - sensorSize.y) * 0.5f,
                sensorSize.x,
                sensorSize.y);

            EditorGUI.DrawRect(sensor, new Color(0.08f, 0.08f, 0.08f, 1f));
            GUI.Box(sensor, GUIContent.none);

            DrawRoi(
                sensor,
                resolution,
                layout.directView,
                new Color(0.20f, 0.85f, 1.00f, 0.32f));

            Color[] mirrorPalette =
            {
                new(1.00f, 0.78f, 0.20f, 0.32f),
                new(1.00f, 0.35f, 0.80f, 0.32f),
                new(0.35f, 1.00f, 0.55f, 0.32f),
            };
            MirrorConfig[] mirrors = layout.mirrors ?? Array.Empty<MirrorConfig>();
            for (int index = 0; index < mirrors.Length; index++)
            {
                DrawRoi(
                    sensor,
                    resolution,
                    mirrors[index],
                    mirrorPalette[index % mirrorPalette.Length]);
            }
        }

        private static void DrawRoi(
            Rect sensor,
            Vector2Int resolution,
            ViewSummary view,
            Color color)
        {
            Vector2 minimum = view.roiMinPx.ToVector2(nameof(view.roiMinPx));
            Vector2 maximum = view.roiMaxPx.ToVector2(nameof(view.roiMaxPx));
            Rect roi = new(
                sensor.x + sensor.width * minimum.x / resolution.x,
                sensor.y + sensor.height * minimum.y / resolution.y,
                sensor.width * (maximum.x - minimum.x) / resolution.x,
                sensor.height * (maximum.y - minimum.y) / resolution.y);
            EditorGUI.DrawRect(roi, color);
            GUI.Box(
                roi,
                $"{view.name}\n{view.reflectionParity}\n{view.coverageFraction:P1}",
                EditorStyles.helpBox);
        }

        private void DrawScene(SceneView sceneView)
        {
            if (_config == null || _config.layouts == null || _config.layouts.Length == 0)
            {
                return;
            }

            LayoutConfig layout = SelectedLayout;
            CameraConfig camera = _config.camera;
            Vector3 physicalCameraRepository = camera.centreM.ToVector3(nameof(camera.centreM));
            Vector3 physicalCamera = Stage0Geometry.RepositoryToUnity(
                physicalCameraRepository);
            Vector3 lookAt = Stage0Geometry.RepositoryToUnity(
                camera.lookAtM.ToVector3(nameof(camera.lookAtM)));

            DrawCoordinateAxes();
            DrawCaptureVolume();
            DrawCamera(physicalCamera, lookAt, "physical camera", PhysicalCameraColor);

            List<Vector3> samples = Stage0Geometry
                .SampleCaptureVolume(_config.captureVolume)
                .ToList();
            DrawSamples(samples);

            MirrorConfig[] mirrors = layout.mirrors ?? Array.Empty<MirrorConfig>();
            foreach (MirrorConfig mirror in mirrors)
            {
                DrawMirror(mirror, physicalCameraRepository, samples);
            }
        }

        private static void DrawCoordinateAxes()
        {
            Vector3 origin = Vector3.zero;
            Handles.color = Color.red;
            Handles.DrawLine(origin, Vector3.right * 0.35f, 3f);
            Handles.Label(Vector3.right * 0.37f, "+x right");
            Handles.color = Color.green;
            Handles.DrawLine(origin, Vector3.up * 0.35f, 3f);
            Handles.Label(Vector3.up * 0.37f, "+y up (repo +z)");
            Handles.color = Color.blue;
            Handles.DrawLine(origin, Vector3.forward * 0.35f, 3f);
            Handles.Label(Vector3.forward * 0.37f, "+z forward (repo +y)");
        }

        private void DrawCaptureVolume()
        {
            Bounds bounds = Stage0Geometry.CaptureBoundsInUnity(_config.captureVolume);
            Handles.color = CaptureVolumeColor;
            Handles.DrawWireCube(bounds.center, bounds.size);
            Handles.Label(bounds.max, "capture volume");
        }

        private static void DrawCamera(
            Vector3 centre,
            Vector3 lookAt,
            string label,
            Color color)
        {
            Handles.color = color;
            float size = HandleUtility.GetHandleSize(centre) * 0.06f;
            Handles.SphereHandleCap(0, centre, Quaternion.identity, size, EventType.Repaint);
            Handles.DrawLine(centre, lookAt, 2f);
            Handles.Label(centre + Vector3.up * size, label);
        }

        private void DrawSamples(IReadOnlyList<Vector3> samples)
        {
            if (!_showSamplePoints)
            {
                return;
            }

            Handles.color = new Color(0.25f, 1.00f, 0.45f, 0.72f);
            foreach (Vector3 repositorySample in samples)
            {
                Vector3 sample = Stage0Geometry.RepositoryToUnity(repositorySample);
                float size = HandleUtility.GetHandleSize(sample) * 0.012f;
                Handles.DotHandleCap(0, sample, Quaternion.identity, size, EventType.Repaint);
            }
        }

        private void DrawMirror(
            MirrorConfig mirror,
            Vector3 physicalCameraRepository,
            IReadOnlyList<Vector3> samples)
        {
            Vector3[] repositoryCorners = Stage0Geometry.MirrorCorners(mirror);
            Vector3[] corners = repositoryCorners
                .Select(Stage0Geometry.RepositoryToUnity)
                .ToArray();
            Vector3[] closed = { corners[0], corners[1], corners[2], corners[3], corners[0] };

            Handles.color = MirrorColor;
            Handles.DrawAAPolyLine(3f, closed);
            Vector3 mirrorCentreRepository = mirror.planePointM.ToVector3(
                nameof(mirror.planePointM));
            Vector3 mirrorCentre = Stage0Geometry.RepositoryToUnity(mirrorCentreRepository);
            Vector3 normal = Stage0Geometry.RepositoryToUnity(
                mirror.planeNormal.ToVector3(nameof(mirror.planeNormal))).normalized;
            Handles.DrawLine(mirrorCentre, mirrorCentre + normal * 0.2f, 2f);
            Handles.Label(
                mirrorCentre + normal * 0.22f,
                $"{mirror.name}\nfinite mirror\nparity: {mirror.reflectionParity}");

            Vector3 virtualCameraRepository = Stage0Geometry.VirtualCameraCentre(
                _config.camera,
                mirror);
            Vector3 virtualCamera = Stage0Geometry.RepositoryToUnity(
                virtualCameraRepository);
            DrawCamera(
                virtualCamera,
                mirrorCentre,
                $"virtual: {mirror.name}",
                VirtualCameraColor);

            for (int index = 0; index < samples.Count; index += Math.Max(1, _rayStride))
            {
                Vector3 sampleRepository = samples[index];
                Vector3 sample = Stage0Geometry.RepositoryToUnity(sampleRepository);

                if (_showDirectRays)
                {
                    Handles.color = new Color(
                        PhysicalCameraColor.r,
                        PhysicalCameraColor.g,
                        PhysicalCameraColor.b,
                        0.18f);
                    Handles.DrawLine(
                        Stage0Geometry.RepositoryToUnity(physicalCameraRepository),
                        sample);
                }

                if (!_showReflectedRays && !_showInvalidRays)
                {
                    continue;
                }

                bool intersectsPlane = Stage0Geometry.TryReflectionPoint(
                    sampleRepository,
                    physicalCameraRepository,
                    mirror,
                    out Vector3 reflectionRepository,
                    out _);
                bool insideMirror = intersectsPlane
                    && Stage0Geometry.IsInsideFiniteMirror(reflectionRepository, mirror);

                if (insideMirror && _showReflectedRays)
                {
                    Vector3 reflection = Stage0Geometry.RepositoryToUnity(
                        reflectionRepository);
                    Handles.color = ValidRayColor;
                    Handles.DrawLine(
                        Stage0Geometry.RepositoryToUnity(physicalCameraRepository),
                        reflection);
                    Handles.DrawLine(reflection, sample);
                }
                else if (!insideMirror && _showInvalidRays)
                {
                    Handles.color = InvalidRayColor;
                    Handles.DrawDottedLine(sample, virtualCamera, 4f);
                }
            }
        }
    }
}

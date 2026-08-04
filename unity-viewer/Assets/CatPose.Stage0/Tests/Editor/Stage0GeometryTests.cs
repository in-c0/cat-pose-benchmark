using System;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;

namespace CatPose.Stage0.Tests
{
    public sealed class Stage0GeometryTests
    {
        private const string ConfigAssetPath =
            "Assets/StreamingAssets/CatPose/stage0-layouts.json";

        [Test]
        public void RepositoryToUnity_MapsAxesAndBackExactly()
        {
            Vector3 repository = new(1f, 2f, 3f);
            Vector3 unity = Stage0Geometry.RepositoryToUnity(repository);

            Assert.That(unity, Is.EqualTo(new Vector3(1f, 3f, 2f)));
            Assert.That(
                Stage0Geometry.UnityToRepository(unity),
                Is.EqualTo(repository));
        }

        [Test]
        public void ReflectPoint_AcrossYzPlane_FlipsOnlyX()
        {
            Vector3 reflected = Stage0Geometry.ReflectPoint(
                new Vector3(1f, 2f, 3f),
                Vector3.zero,
                Vector3.right);

            Assert.That(reflected.x, Is.EqualTo(-1f).Within(1e-6f));
            Assert.That(reflected.y, Is.EqualTo(2f).Within(1e-6f));
            Assert.That(reflected.z, Is.EqualTo(3f).Within(1e-6f));
        }

        [Test]
        public void GeneratedConfig_LoadsBothCandidateLayouts()
        {
            Stage0Config config = LoadConfig();

            Assert.That(config.schemaVersion, Is.EqualTo("0.1.0"));
            Assert.That(config.units, Is.EqualTo("metres"));
            Assert.That(config.layouts, Has.Length.EqualTo(2));
            Assert.That(config.FindLayout("A_symmetric_lateral"), Is.Not.Null);
            Assert.That(config.FindLayout("B_lateral_pitched"), Is.Not.Null);
        }

        [Test]
        public void VirtualCameraCentres_MatchPythonReference()
        {
            Stage0Config config = LoadConfig();

            foreach (LayoutConfig layout in config.layouts)
            {
                foreach (MirrorConfig mirror in layout.mirrors)
                {
                    float errorMetres = Stage0Geometry.VirtualCameraErrorMetres(
                        config.camera,
                        mirror);
                    Assert.That(
                        errorMetres,
                        Is.LessThanOrEqualTo(1e-6f),
                        $"{layout.id}/{mirror.name} diverged from the Python reference.");
                }
            }
        }

        [Test]
        public void CentreSample_ProducesFiniteMirrorReflectionInBothLayouts()
        {
            Stage0Config config = LoadConfig();
            Vector3 camera = config.camera.centreM.ToVector3(nameof(config.camera.centreM));
            Vector3 sample = new(0f, 0.3f, 0.35f);

            foreach (LayoutConfig layout in config.layouts)
            {
                foreach (MirrorConfig mirror in layout.mirrors)
                {
                    bool intersects = Stage0Geometry.TryReflectionPoint(
                        sample,
                        camera,
                        mirror,
                        out Vector3 reflection,
                        out float interpolation);
                    Assert.That(intersects, Is.True, $"{layout.id}/{mirror.name}");
                    Assert.That(interpolation, Is.InRange(0f, 1f));
                    Assert.That(
                        Stage0Geometry.IsInsideFiniteMirror(reflection, mirror),
                        Is.True,
                        $"{layout.id}/{mirror.name}");
                }
            }
        }

        private static Stage0Config LoadConfig()
        {
            TextAsset asset = AssetDatabase.LoadAssetAtPath<TextAsset>(ConfigAssetPath);
            Assert.That(
                asset,
                Is.Not.Null,
                $"Missing generated config at {ConfigAssetPath}");
            Stage0Config config = JsonUtility.FromJson<Stage0Config>(asset.text);
            Assert.That(config, Is.Not.Null);
            return config;
        }
    }
}

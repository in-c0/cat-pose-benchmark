using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace CatPose.StageS0
{
    /// <summary>
    /// Removes the recurring manual exporter step.
    ///
    /// - In the local editor, generates and validates the fixture once per editor session
    ///   after scripts finish compiling.
    /// - In any local or cloud player build, regenerates and validates it as a hard
    ///   pre-build gate.
    ///
    /// The generated fixture is also copied into StreamingAssets so it is retained in
    /// the build output produced by Unity Build Automation.
    /// </summary>
    public static class StageS0Automation
    {
        private const string SessionKey = "CatPose.StageS0.AutomationCompleted";
        private const string FixtureFileName = "stage-s0-unity-export.json";

        [Serializable]
        private sealed class DeterminismData
        {
            public long fixed_timestep_ns;
            public int frame_count;
        }

        [Serializable]
        private sealed class FrameData
        {
            public int frame_index;
            public long timestamp_ns;
            public Vector3 subject_root_world_m;
            public Vector3 subject_velocity_world_mps;
        }

        [Serializable]
        private sealed class SequenceEnvelope
        {
            public string schema_version;
            public string sequence_id;
            public string evidence_tier;
            public string quality;
            public DeterminismData determinism;
            public FrameData[] frames;
        }

        [InitializeOnLoadMethod]
        private static void QueueAutomaticEditorExport()
        {
            if (Application.isBatchMode || SessionState.GetBool(SessionKey, false))
            {
                return;
            }

            SessionState.SetBool(SessionKey, true);
            EditorApplication.delayCall += RunAfterCompilation;
        }

        private static void RunAfterCompilation()
        {
            if (EditorApplication.isCompiling || EditorApplication.isUpdating)
            {
                EditorApplication.delayCall += RunAfterCompilation;
                return;
            }

            try
            {
                GenerateAndValidate(copyToStreamingAssets: false);
                Debug.Log("CatPose Stage S0 fixture generated and validated automatically.");
            }
            catch (Exception exception)
            {
                Debug.LogException(exception);
            }
        }

        public static string GenerateAndValidate(bool copyToStreamingAssets)
        {
            string repositoryRoot = Path.GetFullPath(Path.Combine(Application.dataPath, "..", ".."));
            string fixtureDirectory = Path.Combine(repositoryRoot, "synthetic", "fixtures");
            string fixturePath = Path.Combine(fixtureDirectory, FixtureFileName);
            string secondPassPath = fixturePath + ".determinism-check";

            Directory.CreateDirectory(fixtureDirectory);

            try
            {
                StageS0SyntheticExporter.Export(fixturePath);
                StageS0SyntheticExporter.Export(secondPassPath);

                string first = File.ReadAllText(fixturePath);
                string second = File.ReadAllText(secondPassPath);
                if (!string.Equals(first, second, StringComparison.Ordinal))
                {
                    throw new InvalidOperationException(
                        "Stage S0 exporter is not byte-for-byte deterministic across two runs.");
                }

                ValidateEnvelope(first);

                if (copyToStreamingAssets)
                {
                    string streamingDirectory = Path.Combine(
                        Application.dataPath,
                        "StreamingAssets",
                        "CatPose");
                    Directory.CreateDirectory(streamingDirectory);
                    string streamingPath = Path.Combine(streamingDirectory, FixtureFileName);
                    File.Copy(fixturePath, streamingPath, true);
                    AssetDatabase.ImportAsset(
                        "Assets/StreamingAssets/CatPose/" + FixtureFileName,
                        ImportAssetOptions.ForceSynchronousImport);
                }

                return fixturePath;
            }
            finally
            {
                if (File.Exists(secondPassPath))
                {
                    File.Delete(secondPassPath);
                }
            }
        }

        private static void ValidateEnvelope(string json)
        {
            SequenceEnvelope sequence = JsonUtility.FromJson<SequenceEnvelope>(json);
            if (sequence == null)
            {
                throw new InvalidOperationException("Stage S0 fixture could not be parsed.");
            }

            if (sequence.schema_version != "0.1.0")
            {
                throw new InvalidOperationException("Unexpected Stage S0 schema version.");
            }

            if (sequence.evidence_tier != "S" || sequence.quality != "gold")
            {
                throw new InvalidOperationException("Stage S0 evidence metadata is invalid.");
            }

            if (sequence.determinism == null || sequence.determinism.fixed_timestep_ns <= 0)
            {
                throw new InvalidOperationException("Stage S0 fixed timestep is invalid.");
            }

            if (sequence.frames == null || sequence.frames.Length < 2)
            {
                throw new InvalidOperationException("Stage S0 fixture requires at least two frames.");
            }

            if (sequence.frames.Length != sequence.determinism.frame_count)
            {
                throw new InvalidOperationException(
                    "Stage S0 frame_count does not match the exported frame array.");
            }

            double timestepSeconds = sequence.determinism.fixed_timestep_ns / 1_000_000_000.0;
            for (int index = 0; index < sequence.frames.Length; index++)
            {
                FrameData frame = sequence.frames[index];
                if (frame.frame_index != index)
                {
                    throw new InvalidOperationException(
                        "Stage S0 frame indices are not contiguous from zero.");
                }

                long expectedTimestamp = index * sequence.determinism.fixed_timestep_ns;
                if (frame.timestamp_ns != expectedTimestamp)
                {
                    throw new InvalidOperationException(
                        "Stage S0 timestamps do not match the declared fixed timestep.");
                }

                EnsureFinite(frame.subject_root_world_m, "subject_root_world_m");
                EnsureFinite(frame.subject_velocity_world_mps, "subject_velocity_world_mps");

                if (index < sequence.frames.Length - 1)
                {
                    Vector3 next = sequence.frames[index + 1].subject_root_world_m;
                    Vector3 finiteDifference = (next - frame.subject_root_world_m) / (float)timestepSeconds;
                    if ((finiteDifference - frame.subject_velocity_world_mps).sqrMagnitude > 1e-8f)
                    {
                        throw new InvalidOperationException(
                            "Stage S0 velocity does not match the finite difference.");
                    }
                }
            }
        }

        private static void EnsureFinite(Vector3 value, string fieldName)
        {
            if (!IsFinite(value.x) || !IsFinite(value.y) || !IsFinite(value.z))
            {
                throw new InvalidOperationException(fieldName + " contains a non-finite value.");
            }
        }

        private static bool IsFinite(float value)
        {
            return !float.IsNaN(value) && !float.IsInfinity(value);
        }
    }

    public sealed class StageS0BuildGate : IPreprocessBuildWithReport
    {
        public int callbackOrder => -10_000;

        public void OnPreprocessBuild(BuildReport report)
        {
            try
            {
                string path = StageS0Automation.GenerateAndValidate(copyToStreamingAssets: true);
                Debug.Log("CatPose Stage S0 pre-build gate passed: " + path);
            }
            catch (Exception exception)
            {
                throw new BuildFailedException(
                    "CatPose Stage S0 generation or validation failed before build: "
                    + exception.Message);
            }
        }
    }
}

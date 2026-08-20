class A1PCMRecorderProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.recording = false;
    this.started = false;
    this.targetFrames = 0;
    this.capturedFrames = 0;
    this.chunks = [];
    this.port.onmessage = (event) => {
      const message = event.data || {};
      if (message.type === "start") {
        const target = Number(message.targetFrames);
        if (!Number.isInteger(target) || target <= 0) {
          this.port.postMessage({ type: "error", message: "targetFrames must be a positive integer" });
          return;
        }
        if (this.recording) {
          this.port.postMessage({ type: "error", message: "capture is already active" });
          return;
        }
        this.recording = true;
        this.started = false;
        this.targetFrames = target;
        this.capturedFrames = 0;
        this.chunks = [];
      }
    };
  }

  process(inputs) {
    if (!this.recording) return true;
    const input = inputs[0];
    const channel = input && input[0];
    if (!channel || channel.length === 0) return true;

    if (!this.started) {
      this.started = true;
      this.port.postMessage({
        type: "capture-started",
        startFrame: currentFrame,
        sampleRate,
      });
    }

    const remaining = this.targetFrames - this.capturedFrames;
    const take = Math.min(remaining, channel.length);
    if (take > 0) {
      const chunk = new Float32Array(take);
      chunk.set(channel.subarray(0, take));
      this.chunks.push(chunk);
      this.capturedFrames += take;
    }

    if (this.capturedFrames >= this.targetFrames) {
      const merged = new Float32Array(this.capturedFrames);
      let offset = 0;
      for (const chunk of this.chunks) {
        merged.set(chunk, offset);
        offset += chunk.length;
      }
      this.recording = false;
      this.chunks = [];
      this.port.postMessage(
        {
          type: "capture-complete",
          samples: merged.buffer,
          sampleRate,
          frames: merged.length,
        },
        [merged.buffer],
      );
    }
    return true;
  }
}

registerProcessor("a1-pcm-recorder", A1PCMRecorderProcessor);

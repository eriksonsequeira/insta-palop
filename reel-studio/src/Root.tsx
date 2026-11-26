import React from "react";
import { Composition } from "remotion";
import { Reel, ReelProps } from "./Reel";

const defaults: ReelProps = {
  fps: 30,
  duration: 10,
  audio: null,
  music: null,
  accent: "#A78BFA",
  label: "Inteligência Artificial",
  handle: "@erikson_sequeira",
  sentences: [],
};

export const Root: React.FC = () => (
  <Composition
    id="Reel"
    component={Reel}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={300}
    defaultProps={defaults}
    calculateMetadata={({ props }) => ({
      durationInFrames: Math.ceil(props.duration * props.fps),
      fps: props.fps,
    })}
  />
);

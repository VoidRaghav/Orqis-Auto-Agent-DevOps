"use client";

import { useRef, useState, useCallback } from "react";
import Spline from "@splinetool/react-spline";
import type { Application } from "@splinetool/runtime";

const SCENE_URL =
  "https://prod.spline.design/S9Whw1OCbcu7j48MTY29kKaU/scene.splinecode";

interface Props {
  /** Called once the scene is loaded */
  onLoad?: () => void;
}

export default function SplineScene({ onLoad }: Props) {
  const splineRef = useRef<Application | null>(null);
  const [loaded, setLoaded] = useState(false);

  const handleLoad = useCallback(
    (app: Application) => {
      splineRef.current = app;
      setLoaded(true);
      onLoad?.();
    },
    [onLoad]
  );

  return (
    <>
      {/* Fade-in once loaded so there's no flash */}
      <div
        style={{
          width: "100%",
          height: "100%",
          opacity: loaded ? 1 : 0,
          transition: "opacity 0.8s ease",
          // Spline renders its own canvas — make sure it fills the wrapper
          lineHeight: 0,
        }}
      >
        <Spline
          scene={SCENE_URL}
          onLoad={handleLoad}
          style={{ width: "100%", height: "100%" }}
        />
      </div>

      {/* Skeleton pulse while scene loads */}
      {!loaded && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              width: 80,
              height: 80,
              borderRadius: "50%",
              border: "1px solid rgba(0,255,136,0.2)",
              animation: "pulse-slow 1.8s ease-in-out infinite",
            }}
          />
        </div>
      )}
    </>
  );
}

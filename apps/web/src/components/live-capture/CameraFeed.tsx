import { useEffect, type RefObject } from "react";

import { friendlyCameraError } from "../../pages/liveCaptureUi";

interface CameraFeedProps {
  videoRef: RefObject<HTMLVideoElement>;
  deviceId?: string | null;
  mirrored?: boolean;
  className?: string;
  onError?: (message: string) => void;
  onStreamReady?: () => void;
}

export function CameraFeed({
  videoRef,
  deviceId,
  mirrored = false,
  className,
  onError,
  onStreamReady,
}: CameraFeedProps): JSX.Element {
  useEffect(() => {
    let stream: MediaStream | null = null;
    let cancelled = false;

    async function startCamera(): Promise<void> {
      try {
        const constraints: MediaStreamConstraints = {
          video: deviceId
            ? { deviceId: { exact: deviceId } }
            : { facingMode: { ideal: "environment" } },
          audio: false,
        };
        stream = await navigator.mediaDevices.getUserMedia(constraints);
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => undefined);
        }
        onStreamReady?.();
      } catch (error) {
        onError?.(friendlyCameraError(error));
      }
    }

    void startCamera();

    return () => {
      cancelled = true;
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, [deviceId, onError, onStreamReady, videoRef]);

  return (
    <div className={className}>
      <video
        ref={videoRef}
        className={mirrored ? "h-full w-full rounded-3xl object-cover [transform:scaleX(-1)]" : "h-full w-full rounded-3xl object-cover"}
        autoPlay
        muted
        playsInline
      />
    </div>
  );
}

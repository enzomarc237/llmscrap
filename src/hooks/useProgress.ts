import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

export interface Progress {
  downloaded: number;
  total: number;
  failed: number;
  current: string;
  speed_files_per_sec: number;
  percent: number;
}

/** Poll .progress.json from `outputDir` every `intervalMs` while `active` is true. */
export function useProgress(outputDir: string | null, active: boolean, intervalMs = 600) {
  const [progress, setProgress] = useState<Progress | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!active || !outputDir) {
      setProgress(null);
      return;
    }

    const poll = async () => {
      try {
        const raw: string = await invoke("read_progress", { outputDir });
        setProgress(JSON.parse(raw));
      } catch {
        // file may not exist yet — ignore
      }
    };

    poll();
    timerRef.current = setInterval(poll, intervalMs);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [active, outputDir, intervalMs]);

  return progress;
}

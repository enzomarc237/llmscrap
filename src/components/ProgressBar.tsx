import { cn } from "@/lib/utils";
import type { Progress } from "@/hooks/useProgress";

interface ProgressBarProps {
  progress: Progress;
  className?: string;
}

const fmtSec = (value?: number | null) => {
  if (value == null || Number.isNaN(value)) return "—";
  const sec = Math.max(0, Math.round(value));
  const min = Math.floor(sec / 60);
  const rem = sec % 60;
  return `${min}:${rem.toString().padStart(2, "0")}`;
};

export function ProgressBar({ progress, className }: ProgressBarProps) {
  const { downloaded, total, failed, current, current_title, percent, speed_files_per_sec, elapsed_sec, eta_sec } = progress;

  return (
    <div className={cn("space-y-2", className)}>
      <div className="h-2 w-full rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
        <div
          className="h-full rounded-full bg-blue-500 transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>

      <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
        <span>
          {downloaded} / {total} files
          {failed > 0 && <span className="ml-2 text-red-500">{failed} failed</span>}
        </span>
        <span>{percent}% · {speed_files_per_sec.toFixed(1)} files/s</span>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs text-gray-500 dark:text-gray-400">
        <span>Elapsed: {fmtSec(elapsed_sec)}</span>
        <span>ETA: {fmtSec(eta_sec)}</span>
      </div>

      {(current_title || current) && (
        <p className="text-xs text-gray-400 dark:text-gray-500 truncate" title={current || current_title}>
          {current_title || current}
        </p>
      )}
    </div>
  );
}

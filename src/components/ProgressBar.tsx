import { cn } from "@/lib/utils";
import type { Progress } from "@/hooks/useProgress";

interface ProgressBarProps {
  progress: Progress;
  className?: string;
}

export function ProgressBar({ progress, className }: ProgressBarProps) {
  const { downloaded, total, failed, current, percent, speed_files_per_sec } = progress;

  return (
    <div className={cn("space-y-2", className)}>
      {/* Bar */}
      <div className="h-2 w-full rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
        <div
          className="h-full rounded-full bg-blue-500 transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>

      {/* Stats row */}
      <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
        <span>
          {downloaded} / {total} files
          {failed > 0 && (
            <span className="ml-2 text-red-500">{failed} failed</span>
          )}
        </span>
        <span>{percent}% · {speed_files_per_sec.toFixed(1)} files/s</span>
      </div>

      {/* Current file */}
      {current && (
        <p className="text-xs text-gray-400 dark:text-gray-500 truncate" title={current}>
          {current}
        </p>
      )}
    </div>
  );
}

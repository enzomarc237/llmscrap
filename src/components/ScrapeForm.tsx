import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { FolderOpen, Play, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ProgressBar } from "@/components/ProgressBar";
import { useProgress } from "@/hooks/useProgress";
import { pickFolder } from "@/lib/dialog";

interface ScrapeOptions {
  url: string;
  output_dir: string;
  workers: number;
  timeout: number;
  formats: string[];
}

interface ScrapeResult {
  success: boolean;
  message: string;
  artifacts: Record<string, string>;
}

interface ScrapeFormProps {
  onComplete: (result: ScrapeResult, outputDir: string) => void;
}

export function ScrapeForm({ onComplete }: ScrapeFormProps) {
  const [url, setUrl] = useState("");
  const [outputDir, setOutputDir] = useState("");
  const [workers, setWorkers] = useState(4);
  const [timeout, setTimeout_] = useState(20);
  const [formats, setFormats] = useState<string[]>(["json", "sqlite"]);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const progress = useProgress(isRunning ? outputDir : null, isRunning);

  const toggleFormat = (fmt: string) => {
    setFormats((prev) =>
      prev.includes(fmt) ? prev.filter((f) => f !== fmt) : [...prev, fmt]
    );
  };

  const handlePickFolder = async () => {
    const folder = await pickFolder();
    if (folder) setOutputDir(folder);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setError(null);
    setIsRunning(true);

    const opts: ScrapeOptions = {
      url: url.trim(),
      output_dir: outputDir.trim() || "downloads",
      workers,
      timeout,
      formats,
    };

    try {
      const result: ScrapeResult = await invoke("scrape_index", { opts });
      onComplete(result, opts.output_dir);
    } catch (err: unknown) {
      setError(typeof err === "string" ? err : "An unexpected error occurred.");
    } finally {
      setIsRunning(false);
    }
  };

  const isDone = progress?.downloaded === progress?.total && (progress?.total ?? 0) > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Scrape Index</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* URL */}
          <div className="space-y-1">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Index URL
            </label>
            <Input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://docs.example.com/llms.txt"
              disabled={isRunning}
              required
            />
            <p className="text-xs text-gray-400">Any URL containing .md links</p>
          </div>

          {/* Output directory */}
          <div className="space-y-1">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Output Directory
            </label>
            <div className="flex gap-2">
              <Input
                value={outputDir}
                onChange={(e) => setOutputDir(e.target.value)}
                placeholder="downloads"
                disabled={isRunning}
                className="flex-1"
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={handlePickFolder}
                disabled={isRunning}
                title="Browse folder"
              >
                <FolderOpen className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* Advanced row */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-500 dark:text-gray-400">
                Workers
              </label>
              <Input
                type="number"
                min={1}
                max={16}
                value={workers}
                onChange={(e) => setWorkers(Number(e.target.value))}
                disabled={isRunning}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-500 dark:text-gray-400">
                Timeout (s)
              </label>
              <Input
                type="number"
                min={5}
                max={120}
                value={timeout}
                onChange={(e) => setTimeout_(Number(e.target.value))}
                disabled={isRunning}
              />
            </div>
          </div>

          {/* Formats */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400">
              Output Formats
            </label>
            <div className="flex gap-2">
              {["json", "sqlite"].map((fmt) => (
                <button
                  key={fmt}
                  type="button"
                  onClick={() => toggleFormat(fmt)}
                  disabled={isRunning}
                  className={`px-3 py-1 rounded-md text-xs font-medium border transition-colors ${
                    formats.includes(fmt)
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-300 dark:border-gray-600"
                  }`}
                >
                  {fmt}
                </button>
              ))}
            </div>
          </div>

          {/* Progress */}
          {isRunning && progress && (
            <ProgressBar progress={progress} />
          )}

          {/* Error */}
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-md p-2">
              {error}
            </p>
          )}

          {/* Submit */}
          <Button
            type="submit"
            disabled={isRunning || !url.trim()}
            className="w-full"
          >
            {isRunning ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {isDone ? "Saving..." : "Downloading..."}
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Start Scrape
              </>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

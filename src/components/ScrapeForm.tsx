import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { FolderOpen, Play, Loader2, ListChecks, XCircle, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ProgressBar } from "@/components/ProgressBar";
import { useProgress } from "@/hooks/useProgress";
import { pickFolder } from "@/lib/dialog";

interface PreviewLink {
  title: string;
  url: string;
  section?: string;
}

interface ScrapeOptions {
  url: string;
  output_dir: string;
  workers: number;
  timeout: number;
  formats: string[];
  selected_links: PreviewLink[];
  allow_external: boolean;
  recursive_depth: number;
  request_delay: number;
  user_agent: string;
  polite: boolean;
}

interface ScrapeResult {
  success: boolean;
  message: string;
  artifacts: Record<string, string>;
}

interface Preset {
  outputDir: string;
  workers: number;
  timeout: number;
  formats: string[];
  allowExternal: boolean;
  recursiveDepth: number;
  requestDelay: number;
  userAgent: string;
  polite: boolean;
}

interface RecentRun {
  url: string;
  outputDir: string;
  success: boolean;
  timestamp: string;
}

interface ScrapeFormProps {
  onComplete: (result: ScrapeResult, outputDir: string, url: string) => void;
}

const PRESET_KEY = "llmscrap-preset-v1";
const RECENT_KEY = "llmscrap-recent-runs-v1";

const defaultPreset: Preset = {
  outputDir: "",
  workers: 4,
  timeout: 20,
  formats: ["json", "sqlite", "bundle", "zip", "llm"],
  allowExternal: false,
  recursiveDepth: 0,
  requestDelay: 0,
  userAgent: "llmscrap/0.2",
  polite: true,
};

export function ScrapeForm({ onComplete }: ScrapeFormProps) {
  const [url, setUrl] = useState("");
  const [outputDir, setOutputDir] = useState(defaultPreset.outputDir);
  const [workers, setWorkers] = useState(defaultPreset.workers);
  const [timeout, setTimeout_] = useState(defaultPreset.timeout);
  const [formats, setFormats] = useState<string[]>(defaultPreset.formats);
  const [allowExternal, setAllowExternal] = useState(defaultPreset.allowExternal);
  const [recursiveDepth, setRecursiveDepth] = useState(defaultPreset.recursiveDepth);
  const [requestDelay, setRequestDelay] = useState(defaultPreset.requestDelay);
  const [userAgent, setUserAgent] = useState(defaultPreset.userAgent);
  const [polite, setPolite] = useState(defaultPreset.polite);

  const [isRunning, setIsRunning] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [previewLinks, setPreviewLinks] = useState<PreviewLink[]>([]);
  const [selectedUrls, setSelectedUrls] = useState<Set<string>>(new Set());
  const [recentRuns, setRecentRuns] = useState<RecentRun[]>([]);

  const progress = useProgress(isRunning ? outputDir : null, isRunning);

  useEffect(() => {
    try {
      const rawPreset = localStorage.getItem(PRESET_KEY);
      if (rawPreset) {
        const preset = { ...defaultPreset, ...JSON.parse(rawPreset) } as Preset;
        setOutputDir(preset.outputDir);
        setWorkers(preset.workers);
        setTimeout_(preset.timeout);
        setFormats(preset.formats);
        setAllowExternal(preset.allowExternal);
        setRecursiveDepth(preset.recursiveDepth);
        setRequestDelay(preset.requestDelay);
        setUserAgent(preset.userAgent);
        setPolite(preset.polite);
      }

      const rawRecent = localStorage.getItem(RECENT_KEY);
      if (rawRecent) {
        setRecentRuns(JSON.parse(rawRecent));
      }
    } catch {
      // ignore parse issues
    }
  }, []);

  const selectedLinks = useMemo(
    () => previewLinks.filter((link) => selectedUrls.has(link.url)),
    [previewLinks, selectedUrls]
  );

  const toggleFormat = (fmt: string) => {
    setFormats((prev) =>
      prev.includes(fmt) ? prev.filter((f) => f !== fmt) : [...prev, fmt]
    );
  };

  const handlePickFolder = async () => {
    const folder = await pickFolder();
    if (folder) setOutputDir(folder);
  };

  const getOptions = (): ScrapeOptions => ({
    url: url.trim(),
    output_dir: outputDir.trim() || "downloads",
    workers,
    timeout,
    formats,
    selected_links: selectedLinks,
    allow_external: allowExternal,
    recursive_depth: recursiveDepth,
    request_delay: requestDelay,
    user_agent: userAgent.trim() || "llmscrap/0.2",
    polite,
  });

  const handlePreview = async () => {
    if (!url.trim()) return;
    setError(null);
    setIsPreviewing(true);
    try {
      const opts = getOptions();
      const preview = await invoke<{ links: PreviewLink[]; errors: string[] }>("preview_index", {
        opts,
      });
      setPreviewLinks(preview.links ?? []);
      setSelectedUrls(new Set((preview.links ?? []).map((link) => link.url)));
      if ((preview.errors?.length ?? 0) > 0) {
        setError(preview.errors.join("\n"));
      }
    } catch (err: unknown) {
      setError(typeof err === "string" ? err : "Failed to preview links.");
    } finally {
      setIsPreviewing(false);
    }
  };

  const handleCancel = async () => {
    if (!outputDir.trim()) return;
    await invoke("cancel_scrape", { outputDir: outputDir.trim() || "downloads" });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    setError(null);
    setIsRunning(true);

    const opts: ScrapeOptions = getOptions();

    try {
      const result: ScrapeResult = await invoke("scrape_index", { opts });
      onComplete(result, opts.output_dir, opts.url);
    } catch (err: unknown) {
      setError(typeof err === "string" ? err : "An unexpected error occurred.");
    } finally {
      setIsRunning(false);
    }
  };

  const savePreset = () => {
    const preset: Preset = {
      outputDir,
      workers,
      timeout,
      formats,
      allowExternal,
      recursiveDepth,
      requestDelay,
      userAgent,
      polite,
    };
    localStorage.setItem(PRESET_KEY, JSON.stringify(preset));
  };

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const uri = e.dataTransfer.getData("text/uri-list") || e.dataTransfer.getData("text/plain");
    if (uri?.trim()) {
      setUrl(uri.trim().split(/\s+/)[0] ?? "");
      return;
    }

    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    const text = await file.text();
    const firstUrl = text.match(/https?:\/\/\S+/)?.[0];
    if (firstUrl) setUrl(firstUrl);
  };

  const isDone = progress?.downloaded === progress?.total && (progress?.total ?? 0) > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Scrape Index</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4" onDrop={handleDrop} onDragOver={(e) => e.preventDefault()}>
          <div className="space-y-1 rounded border border-dashed border-gray-300 dark:border-gray-700 p-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Index URL</label>
            <Input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://docs.example.com/llms.txt (or drag/drop URL/file)"
              disabled={isRunning || isPreviewing}
              required
            />
            <p className="text-xs text-gray-400">Drag and drop a URL or file here.</p>
          </div>

          {recentRuns.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Recent runs</p>
              <div className="flex flex-wrap gap-2">
                {recentRuns.slice(0, 4).map((run) => (
                  <button
                    key={`${run.timestamp}-${run.url}`}
                    type="button"
                    className="rounded border px-2 py-1 text-xs"
                    onClick={() => {
                      setUrl(run.url);
                      setOutputDir(run.outputDir);
                    }}
                  >
                    {new URL(run.url).hostname}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-1">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Output Directory</label>
            <div className="flex gap-2">
              <Input
                value={outputDir}
                onChange={(e) => setOutputDir(e.target.value)}
                placeholder="downloads"
                disabled={isRunning}
                className="flex-1"
              />
              <Button type="button" variant="outline" size="icon" onClick={handlePickFolder} disabled={isRunning} title="Browse folder">
                <FolderOpen className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Workers</label>
              <Input type="number" min={1} max={16} value={workers} onChange={(e) => setWorkers(Number(e.target.value))} disabled={isRunning} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Timeout (s)</label>
              <Input type="number" min={5} max={120} value={timeout} onChange={(e) => setTimeout_(Number(e.target.value))} disabled={isRunning} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Recursive Depth</label>
              <Input type="number" min={0} max={3} value={recursiveDepth} onChange={(e) => setRecursiveDepth(Number(e.target.value))} disabled={isRunning} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Request Delay (s)</label>
              <Input type="number" min={0} max={5} step={0.1} value={requestDelay} onChange={(e) => setRequestDelay(Number(e.target.value))} disabled={isRunning} />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400">User Agent</label>
            <Input value={userAgent} onChange={(e) => setUserAgent(e.target.value)} disabled={isRunning} />
          </div>

          <div className="flex flex-wrap gap-2 text-xs">
            <label className="inline-flex items-center gap-2 rounded border px-2 py-1">
              <input type="checkbox" checked={allowExternal} onChange={(e) => setAllowExternal(e.target.checked)} disabled={isRunning} />
              Allow external domains
            </label>
            <label className="inline-flex items-center gap-2 rounded border px-2 py-1">
              <input type="checkbox" checked={polite} onChange={(e) => setPolite(e.target.checked)} disabled={isRunning} />
              Polite mode
            </label>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Output Formats</label>
            <div className="flex flex-wrap gap-2">
              {["json", "sqlite", "bundle", "zip", "html", "llm"].map((fmt) => (
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

          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={handlePreview} disabled={isRunning || isPreviewing || !url.trim()} className="flex-1">
              <ListChecks className="h-4 w-4" />
              {isPreviewing ? "Previewing..." : "Preview links"}
            </Button>
            <Button type="button" variant="outline" onClick={savePreset} disabled={isRunning} className="flex-1">
              <Save className="h-4 w-4" />
              Save preset
            </Button>
          </div>

          {previewLinks.length > 0 && (
            <div className="space-y-2 rounded border p-2 max-h-56 overflow-auto">
              <div className="flex items-center justify-between text-xs">
                <span>{selectedLinks.length} / {previewLinks.length} selected</span>
                <div className="flex gap-2">
                  <button type="button" className="underline" onClick={() => setSelectedUrls(new Set(previewLinks.map((l) => l.url)))}>All</button>
                  <button type="button" className="underline" onClick={() => setSelectedUrls(new Set())}>None</button>
                </div>
              </div>
              {previewLinks.map((link) => (
                <label key={link.url} className="flex items-start gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={selectedUrls.has(link.url)}
                    onChange={(e) => {
                      const next = new Set(selectedUrls);
                      if (e.target.checked) next.add(link.url);
                      else next.delete(link.url);
                      setSelectedUrls(next);
                    }}
                  />
                  <span className="truncate" title={link.url}>{link.title || link.url}</span>
                </label>
              ))}
            </div>
          )}

          {isRunning && progress && <ProgressBar progress={progress} />}

          {error && (
            <p className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-md p-2 whitespace-pre-wrap">
              {error}
            </p>
          )}

          <div className="flex gap-2">
            <Button type="submit" disabled={isRunning || !url.trim() || (previewLinks.length > 0 && selectedLinks.length === 0)} className="flex-1">
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
            {isRunning && (
              <Button type="button" variant="destructive" onClick={handleCancel}>
                <XCircle className="h-4 w-4" />
                Stop
              </Button>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

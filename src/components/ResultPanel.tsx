import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { FolderOpen, CheckCircle2, XCircle, FileText, Database, RotateCcw, Archive, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

interface ScrapeResult {
  success: boolean;
  message: string;
  artifacts: Record<string, string>;
}

interface ResultPanelProps {
  result: ScrapeResult;
  outputDir: string;
  indexUrl: string;
  onReset: () => void;
  onComplete: (result: ScrapeResult, outputDir: string, url: string) => void;
}

interface ManifestEntry {
  url: string;
  local_path: string;
  title: string;
  section: string;
  success: boolean;
  size_bytes?: number;
  error?: string;
}

interface ManifestFile {
  total: number;
  downloaded: number;
  failed: number;
  entries: ManifestEntry[];
}

const ARTIFACT_ICONS: Record<string, React.ReactNode> = {
  manifest: <FileText className="h-4 w-4" />,
  sqlite: <Database className="h-4 w-4" />,
  bundle: <FileText className="h-4 w-4" />,
  zip: <Archive className="h-4 w-4" />,
};

const defaultFormats = ["json", "sqlite", "bundle", "zip", "llm"];

export function ResultPanel({ result, outputDir, indexUrl, onReset, onComplete }: ResultPanelProps) {
  const [manifest, setManifest] = useState<ManifestFile | null>(null);
  const [search, setSearch] = useState("");
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [selectedContent, setSelectedContent] = useState<string>("");
  const [retrying, setRetrying] = useState(false);

  const manifestPath = result.artifacts.manifest;
  const sqlitePath = result.artifacts.sqlite;

  useEffect(() => {
    const loadManifest = async () => {
      if (!manifestPath) return;
      try {
        const text = await invoke<string>("read_text_file", { path: manifestPath });
        setManifest(JSON.parse(text));
      } catch {
        // ignore
      }
    };
    void loadManifest();
  }, [manifestPath]);

  useEffect(() => {
    const loadFile = async () => {
      if (!selectedPath) {
        setSelectedContent("");
        return;
      }
      try {
        const text = await invoke<string>("read_text_file", { path: selectedPath });
        setSelectedContent(text);
      } catch {
        setSelectedContent("Failed to open file.");
      }
    };
    void loadFile();
  }, [selectedPath]);

  const filteredEntries = useMemo(() => {
    if (!manifest?.entries) return [];
    const q = search.trim().toLowerCase();
    if (!q) return manifest.entries;
    return manifest.entries.filter((entry) =>
      `${entry.title} ${entry.url} ${entry.section}`.toLowerCase().includes(q)
    );
  }, [manifest, search]);

  const summary = useMemo(() => {
    if (!manifest) return null;
    const totalSize = manifest.entries.reduce((acc, item) => acc + (item.size_bytes ?? 0), 0);
    const sections = manifest.entries.reduce<Record<string, number>>((acc, item) => {
      const key = item.section || "(none)";
      acc[key] = (acc[key] ?? 0) + 1;
      return acc;
    }, {});
    const topSections = Object.entries(sections)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3);

    return { totalSize, topSections };
  }, [manifest]);

  const handleReveal = async () => {
    await invoke("reveal_folder", { path: outputDir });
  };

  const handleOpen = async (path: string) => {
    await invoke("open_path", { path });
  };

  const handleRetryFailed = async () => {
    if (!manifestPath) return;
    setRetrying(true);
    try {
      const opts = {
        url: indexUrl,
        output_dir: outputDir,
        workers: 4,
        timeout: 20,
        formats: defaultFormats,
        selected_links: [],
        allow_external: false,
        recursive_depth: 0,
        request_delay: 0,
        user_agent: "llmscrap/0.2",
        polite: true,
      };
      const retryResult = await invoke<ScrapeResult>("retry_failed", { opts, manifestPath });
      onComplete(retryResult, outputDir, indexUrl);
    } finally {
      setRetrying(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            {result.success ? <CheckCircle2 className="h-5 w-5 text-green-500" /> : <XCircle className="h-5 w-5 text-red-500" />}
            {result.success ? "Scrape Complete" : "Scrape Failed"}
          </CardTitle>
          <Badge variant={result.success ? "success" : "error"}>{result.success ? "success" : "error"}</Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div>
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Output Directory</p>
          <p className="text-sm font-mono text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 rounded px-2 py-1 break-all">{outputDir}</p>
        </div>

        {summary && (
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded border p-2">
              <p>Total downloaded size</p>
              <p className="font-semibold">{(summary.totalSize / 1024).toFixed(1)} KB</p>
            </div>
            <div className="rounded border p-2">
              <p>Top sections</p>
              <p className="font-semibold">{summary.topSections.map((item) => `${item[0]} (${item[1]})`).join(", ") || "—"}</p>
            </div>
          </div>
        )}

        {Object.keys(result.artifacts).length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Generated Files</p>
            <div className="space-y-1">
              {Object.entries(result.artifacts).map(([fmt, path]) => (
                <div key={fmt} className="flex items-center justify-between gap-2 text-sm text-gray-600 dark:text-gray-400">
                  <div className="flex items-center gap-2 min-w-0">
                    {ARTIFACT_ICONS[fmt] ?? <FileText className="h-4 w-4" />}
                    <span className="font-mono text-xs truncate" title={path}>{path}</span>
                  </div>
                  <Button type="button" size="sm" variant="outline" onClick={() => handleOpen(path)}>Open</Button>
                </div>
              ))}
            </div>
          </div>
        )}

        {manifest && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Search className="h-4 w-4" />
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search downloaded docs" />
            </div>
            <div className="max-h-40 overflow-auto space-y-1 rounded border p-2">
              {filteredEntries.slice(0, 20).map((entry) => (
                <button
                  key={`${entry.url}-${entry.local_path}`}
                  type="button"
                  onClick={() => setSelectedPath(`${outputDir}/${entry.local_path}`)}
                  className="block w-full text-left text-xs truncate hover:underline"
                  title={entry.url}
                >
                  {entry.title || entry.url}
                </button>
              ))}
            </div>
            {selectedContent && (
              <pre className="max-h-48 overflow-auto rounded border bg-gray-50 dark:bg-gray-900 p-2 text-xs whitespace-pre-wrap">{selectedContent}</pre>
            )}
          </div>
        )}

        {!result.success && result.message && (
          <p className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded p-2 whitespace-pre-wrap">{result.message}</p>
        )}

        <div className="flex flex-wrap gap-2 pt-2">
          <Button variant="outline" onClick={handleReveal}>
            <FolderOpen className="h-4 w-4" />
            Open Folder
          </Button>
          {manifestPath && (
            <Button variant="outline" onClick={handleRetryFailed} disabled={retrying}>
              <RotateCcw className="h-4 w-4" />
              {retrying ? "Retrying..." : "Retry Failed"}
            </Button>
          )}
          {manifestPath && <Button variant="outline" onClick={() => handleOpen(manifestPath)}>Open manifest.json</Button>}
          {sqlitePath && <Button variant="outline" onClick={() => handleOpen(sqlitePath)}>Open index.db</Button>}
          <Button onClick={onReset}>New Scrape</Button>
        </div>
      </CardContent>
    </Card>
  );
}

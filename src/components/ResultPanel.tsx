import { invoke } from "@tauri-apps/api/core";
import { FolderOpen, CheckCircle2, XCircle, FileText, Database } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface ScrapeResult {
  success: boolean;
  message: string;
  artifacts: Record<string, string>;
}

interface ResultPanelProps {
  result: ScrapeResult;
  outputDir: string;
  onReset: () => void;
}

const ARTIFACT_ICONS: Record<string, React.ReactNode> = {
  manifest: <FileText className="h-4 w-4" />,
  sqlite: <Database className="h-4 w-4" />,
};

export function ResultPanel({ result, outputDir, onReset }: ResultPanelProps) {
  const handleReveal = async () => {
    await invoke("reveal_folder", { path: outputDir });
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            {result.success ? (
              <CheckCircle2 className="h-5 w-5 text-green-500" />
            ) : (
              <XCircle className="h-5 w-5 text-red-500" />
            )}
            {result.success ? "Scrape Complete" : "Scrape Failed"}
          </CardTitle>
          <Badge variant={result.success ? "success" : "error"}>
            {result.success ? "success" : "error"}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Output dir */}
        <div>
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
            Output Directory
          </p>
          <p className="text-sm font-mono text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 rounded px-2 py-1 break-all">
            {outputDir}
          </p>
        </div>

        {/* Artifacts */}
        {Object.keys(result.artifacts).length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
              Generated Files
            </p>
            <div className="space-y-1">
              {Object.entries(result.artifacts).map(([fmt, path]) => (
                <div
                  key={fmt}
                  className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400"
                >
                  {ARTIFACT_ICONS[fmt] ?? <FileText className="h-4 w-4" />}
                  <span className="font-mono text-xs truncate">{path}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Error message */}
        {!result.success && result.message && (
          <p className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded p-2 whitespace-pre-wrap">
            {result.message}
          </p>
        )}

        {/* Actions */}
        <div className="flex gap-2 pt-2">
          <Button variant="outline" onClick={handleReveal} className="flex-1">
            <FolderOpen className="h-4 w-4" />
            Open Folder
          </Button>
          <Button onClick={onReset} className="flex-1">
            New Scrape
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

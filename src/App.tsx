import { useEffect, useState } from "react";
import { ScrapeForm } from "@/components/ScrapeForm";
import { ResultPanel } from "@/components/ResultPanel";
import { Download, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ScrapeResult {
  success: boolean;
  message: string;
  artifacts: Record<string, string>;
}

interface RecentRun {
  url: string;
  outputDir: string;
  success: boolean;
  timestamp: string;
}

const RECENT_KEY = "llmscrap-recent-runs-v1";
const THEME_KEY = "llmscrap-theme-v1";

function App() {
  const [result, setResult] = useState<ScrapeResult | null>(null);
  const [outputDir, setOutputDir] = useState<string>("");
  const [indexUrl, setIndexUrl] = useState<string>("");
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(THEME_KEY);
    const isDark = stored === "dark";
    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
  }, []);

  const handleComplete = (res: ScrapeResult, dir: string, url: string) => {
    setResult(res);
    setOutputDir(dir);
    setIndexUrl(url);

    const next: RecentRun = {
      url,
      outputDir: dir,
      success: res.success,
      timestamp: new Date().toISOString(),
    };

    const existing = JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]") as RecentRun[];
    const merged = [next, ...existing.filter((item) => !(item.url === url && item.outputDir === dir))].slice(0, 10);
    localStorage.setItem(RECENT_KEY, JSON.stringify(merged));
  };

  const handleReset = () => {
    setResult(null);
    setOutputDir("");
    setIndexUrl("");
  };

  const toggleTheme = () => {
    const nextDark = !dark;
    setDark(nextDark);
    document.documentElement.classList.toggle("dark", nextDark);
    localStorage.setItem(THEME_KEY, nextDark ? "dark" : "light");
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
      <header className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-600">
              <Download className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">llmscrap</h1>
              <p className="text-xs text-gray-500 dark:text-gray-400">Download Markdown docs from any index URL</p>
            </div>
          </div>
          <Button variant="outline" size="icon" onClick={toggleTheme} title="Toggle theme">
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        {result ? (
          <ResultPanel result={result} outputDir={outputDir} indexUrl={indexUrl} onReset={handleReset} onComplete={handleComplete} />
        ) : (
          <ScrapeForm onComplete={handleComplete} />
        )}
      </main>
    </div>
  );
}

export default App;

import { useState } from "react";
import { ScrapeForm } from "@/components/ScrapeForm";
import { ResultPanel } from "@/components/ResultPanel";
import { Download } from "lucide-react";

interface ScrapeResult {
  success: boolean;
  message: string;
  artifacts: Record<string, string>;
}

function App() {
  const [result, setResult] = useState<ScrapeResult | null>(null);
  const [outputDir, setOutputDir] = useState<string>("");

  const handleComplete = (res: ScrapeResult, dir: string) => {
    setResult(res);
    setOutputDir(dir);
  };

  const handleReset = () => {
    setResult(null);
    setOutputDir("");
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 px-6 py-4">
        <div className="max-w-2xl mx-auto flex items-center gap-3">
          <div className="p-2 rounded-lg bg-blue-600">
            <Download className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight">llmscrap</h1>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Download Markdown docs from any index URL
            </p>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-2xl mx-auto px-6 py-8">
        {result ? (
          <ResultPanel result={result} outputDir={outputDir} onReset={handleReset} />
        ) : (
          <ScrapeForm onComplete={handleComplete} />
        )}
      </main>
    </div>
  );
}

export default App;


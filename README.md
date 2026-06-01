# llmscrap desktop app

Tauri desktop UI for the `llmscrap` Python scraper.

## Development

```powershell
npm install
npm run tauri dev
```

## Build (self-contained scraper sidecar)

`tauri build` now generates and bundles a Windows sidecar executable for the scraper (`llmscrap-cli`), so end users do not need Python installed.

```powershell
npx tauri build --no-bundle
```

You can also build the sidecar independently:

```powershell
npm run build:sidecar
```

import { open } from "@tauri-apps/plugin-dialog";

/** Open native folder picker and return the selected path. */
export async function pickFolder(): Promise<string | null> {
  const selected = await open({ directory: true, multiple: false });
  if (Array.isArray(selected)) return selected[0] ?? null;
  return selected;
}

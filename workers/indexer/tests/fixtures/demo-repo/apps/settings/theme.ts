// Theme settings: light / dark / OLED night mode.
export type Theme = "light" | "dark" | "oled";

export function resolveTheme(pref: string): Theme {
  if (pref === "oled" || pref === "night") return "oled";
  if (pref === "dark") return "dark";
  return "light";
}

export function darkModeEnabled(theme: Theme): boolean {
  return theme === "dark" || theme === "oled";
}

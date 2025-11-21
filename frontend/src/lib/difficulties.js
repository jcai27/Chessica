export const DIFFICULTY_PRESETS = [
  { key: "beginner", name: "Beginner", depth: 1, rating: 1320 },
  { key: "intermediate", name: "Intermediate", depth: 2, rating: 1600 },
  { key: "advanced", name: "Advanced", depth: 3, rating: 2000 },
  { key: "expert", name: "Expert", depth: 4, rating: 2300 },
  { key: "grandmaster", name: "Grandmaster", depth: 5, rating: 2600 },
];

export function describePreset(key) {
  const preset = DIFFICULTY_PRESETS.find((p) => p.key === key);
  if (!preset) return "Custom difficulty";
  return `${preset.name} (~${preset.rating} Elo, depth ${preset.depth})`;
}

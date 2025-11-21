export function formatEval(cp) {
  if (typeof cp !== "number" || Number.isNaN(cp)) return "N/A";
  const score = (cp / 100).toFixed(2);
  return cp >= 0 ? `+${score}` : score;
}

export function describeEval(cp) {
  if (typeof cp !== "number" || Number.isNaN(cp)) return "No evaluation yet";
  const abs = Math.abs(cp);
  if (abs < 35) return "Balanced tension";
  if (abs < 150) return cp > 0 ? "White edge" : "Black edge";
  if (abs < 300) return cp > 0 ? "White pressing" : "Black pressing";
  return cp > 0 ? "White winning" : "Black winning";
}

export function formatMs(ms) {
  const clamped = Math.max(0, ms || 0);
  if (clamped < 60000) {
    const seconds = Math.floor(clamped / 1000);
    const tenths = Math.floor((clamped % 1000) / 100);
    return `0:${seconds.toString().padStart(2, "0")}.${tenths}`;
  }
  const totalSeconds = Math.floor(clamped / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

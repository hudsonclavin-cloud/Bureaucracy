export const BRANCH_COLORS = {
  constitution: "#FFD400",
  legislative: "#0057FF",
  executive: "#FF3B30",
  judicial: "#48A7FF",
  independent: "#14D864",
  regulatory: "#FFF266",
  position: "#FFFFFF",
};

export const UI_ACCENTS = {
  background: "#04111F",
  backgroundAlt: "#0A1A30",
  panel: "rgba(6, 20, 38, 0.86)",
  panelStrong: "rgba(4, 16, 31, 0.94)",
  panelSoft: "rgba(12, 28, 52, 0.78)",
  border: "rgba(248, 251, 255, 0.18)",
  borderStrong: "rgba(248, 251, 255, 0.32)",
  text: "#F8FBFF",
  textSoft: "#D7E6FF",
  textMuted: "#8FB3E8",
  accent: "#FFD400",
  accentSoft: "#FFF266",
  info: "#48A7FF",
  success: "#14D864",
  danger: "#FF3B30",
};

export const VERIFICATION_BADGES = {
  candidate: {
    label: "CANDIDATE",
    bg: "rgba(0, 87, 255, 0.18)",
    border: BRANCH_COLORS.legislative,
    color: "#DCE8FF",
  },
  inherited: {
    label: "INHERITED",
    bg: "rgba(255, 212, 0, 0.18)",
    border: BRANCH_COLORS.constitution,
    color: "#FFF4BD",
  },
  verified: {
    label: "VERIFIED",
    bg: "rgba(20, 216, 100, 0.18)",
    border: BRANCH_COLORS.independent,
    color: "#DFFFEA",
  },
  partial: {
    label: "PARTIAL",
    bg: "rgba(255, 242, 102, 0.18)",
    border: BRANCH_COLORS.regulatory,
    color: "#FFFBD3",
  },
  unverified: {
    label: "UNVERIFIED",
    bg: "rgba(255, 255, 255, 0.14)",
    border: BRANCH_COLORS.position,
    color: BRANCH_COLORS.position,
  },
};

export const RELATIONSHIP_COLOR = "#48A7FF";

const LEGACY_COLOR_ALIASES = {
  "#c8a84a": BRANCH_COLORS.constitution,
  "#e8c86a": BRANCH_COLORS.constitution,
  "#d9b55e": BRANCH_COLORS.regulatory,
  "#c8884a": BRANCH_COLORS.regulatory,
  "#8a4ac8": BRANCH_COLORS.legislative,
  "#9b8bbd": BRANCH_COLORS.legislative,
  "#c84a4a": BRANCH_COLORS.executive,
  "#4a8ac8": BRANCH_COLORS.judicial,
  "#78a8ff": RELATIONSHIP_COLOR,
  "#8fc2ff": RELATIONSHIP_COLOR,
  "#4ac88a": BRANCH_COLORS.independent,
  "#6fcf97": BRANCH_COLORS.independent,
  "#666666": BRANCH_COLORS.position,
  "#888888": BRANCH_COLORS.position,
  "#8e7d62": BRANCH_COLORS.position,
};

export function normalizeHexColor(value) {
  const text = String(value || "").trim().toLowerCase();
  if (!text) {
    return "";
  }
  if (/^#[0-9a-f]{6}$/.test(text)) {
    return text;
  }
  if (/^#[0-9a-f]{3}$/.test(text)) {
    return `#${text[1]}${text[1]}${text[2]}${text[2]}${text[3]}${text[3]}`;
  }
  return "";
}

export function canonicalizeThemeColor(value, fallback = BRANCH_COLORS.position) {
  const normalized = normalizeHexColor(value);
  if (!normalized) {
    return fallback;
  }
  return LEGACY_COLOR_ALIASES[normalized] || normalized.toUpperCase();
}

export function hexToRgba(hex, alpha) {
  const normalized = canonicalizeThemeColor(hex);
  const red = parseInt(normalized.slice(1, 3), 16);
  const green = parseInt(normalized.slice(3, 5), 16);
  const blue = parseInt(normalized.slice(5, 7), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

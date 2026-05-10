export interface CharacterMeta {
  name: string;
  displayName: string;
  emoji: string;
  color: string;
  hex: string;
  manager: boolean;
  parent?: string;
}

export const CHARACTERS: Record<string, CharacterMeta> = {
  "king": {
    name: "king",
    displayName: "임금",
    emoji: "🤴",
    color: "yellow",
    hex: "#C9A227",
    manager: false,
  },
  "planner-dojeon": {
    name: "planner-dojeon",
    displayName: "정도전",
    emoji: "📐",
    color: "blue",
    hex: "#2C5F8D",
    manager: true,
  },
  "implementer-yeongsil": {
    name: "implementer-yeongsil",
    displayName: "장영실",
    emoji: "🔧",
    color: "orange",
    hex: "#B8651E",
    manager: true,
  },
  "reviewer-sunsin": {
    name: "reviewer-sunsin",
    displayName: "이순신",
    emoji: "⚓",
    color: "red",
    hex: "#1A2B47",
    manager: true,
  },
  "ideator-yagyong": {
    name: "ideator-yagyong",
    displayName: "정약용",
    emoji: "💡",
    color: "green",
    hex: "#7BA05B",
    manager: true,
  },
  "planning-hojo": {
    name: "planning-hojo",
    displayName: "호조낭청",
    emoji: "📋",
    color: "cyan",
    hex: "#06B6D4",
    manager: false,
    parent: "planner-dojeon",
  },
  "uiux-hwawon": {
    name: "uiux-hwawon",
    displayName: "도화서 화원",
    emoji: "📜",
    color: "purple",
    hex: "#7C3AED",
    manager: false,
    parent: "planner-dojeon",
  },
  "docs-sagwan": {
    name: "docs-sagwan",
    displayName: "사관",
    emoji: "🖋️",
    color: "blue",
    hex: "#3B82F6",
    manager: false,
    parent: "planner-dojeon",
  },
  "frontend-dancheong": {
    name: "frontend-dancheong",
    displayName: "단청도제",
    emoji: "🎨",
    color: "yellow",
    hex: "#D97706",
    manager: false,
    parent: "implementer-yeongsil",
  },
  "backend-gigwan": {
    name: "backend-gigwan",
    displayName: "기관도제",
    emoji: "⚙️",
    color: "orange",
    hex: "#C2660A",
    manager: false,
    parent: "implementer-yeongsil",
  },
  "infra-tomok": {
    name: "infra-tomok",
    displayName: "토목도제",
    emoji: "🏗️",
    color: "pink",
    hex: "#DB2777",
    manager: false,
    parent: "implementer-yeongsil",
  },
  "integration-tongsin": {
    name: "integration-tongsin",
    displayName: "통신도제",
    emoji: "📡",
    color: "cyan",
    hex: "#0891B2",
    manager: false,
    parent: "implementer-yeongsil",
  },
  "security-chukhu": {
    name: "security-chukhu",
    displayName: "척후",
    emoji: "🔍",
    color: "red",
    hex: "#DC2626",
    manager: false,
    parent: "reviewer-sunsin",
  },
  "perf-uiwon": {
    name: "perf-uiwon",
    displayName: "의원",
    emoji: "💊",
    color: "pink",
    hex: "#EC4899",
    manager: false,
    parent: "reviewer-sunsin",
  },
  "test-gungwan": {
    name: "test-gungwan",
    displayName: "군관",
    emoji: "🧪",
    color: "red",
    hex: "#B91C1C",
    manager: false,
    parent: "reviewer-sunsin",
  },
  "research-jeja": {
    name: "research-jeja",
    displayName: "제자",
    emoji: "🎓",
    color: "green",
    hex: "#16A34A",
    manager: false,
    parent: "ideator-yagyong",
  },
  "visual-hwagong": {
    name: "visual-hwagong",
    displayName: "화공",
    emoji: "🎨",
    color: "green",
    hex: "#15803D",
    manager: false,
    parent: "ideator-yagyong",
  },
};

export const MANAGERS: CharacterMeta[] = [
  CHARACTERS["planner-dojeon"],
  CHARACTERS["implementer-yeongsil"],
  CHARACTERS["reviewer-sunsin"],
  CHARACTERS["ideator-yagyong"],
];

export const DOJES: CharacterMeta[] = Object.values(CHARACTERS).filter(
  (c) => !c.manager && c.name !== "king"
);

export function getDojesByManager(managerName: string): CharacterMeta[] {
  return DOJES.filter((c) => c.parent === managerName);
}

export const CHARACTER_KEYS = Object.keys(CHARACTERS); // 16개

export function getCharacterIndex(agentName: string): number {
  return CHARACTER_KEYS.indexOf(agentName);
}

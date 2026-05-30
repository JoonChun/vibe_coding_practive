import DojeCharacter from "./DojeCharacter";

interface Props {
  activeDojes: Set<string>;
  dojeBubbles: Record<string, string>;
}

const DOJE_FLOOR_LAYOUT = [
  { name: "planning-hojo",       left: "6%",  top: "92%" },
  { name: "uiux-hwawon",         left: "15%", top: "92%" },
  { name: "docs-sagwan",         left: "24%", top: "92%" },
  { name: "research-jeja",       left: "33%", top: "92%" },
  { name: "visual-hwagong",      left: "42%", top: "92%" },
  { name: "security-chukhu",     left: "58%", top: "92%" },
  { name: "perf-uiwon",          left: "64%", top: "92%" },
  { name: "test-gungwan",        left: "70%", top: "92%" },
  { name: "frontend-dancheong",  left: "76%", top: "92%" },
  { name: "backend-gigwan",      left: "82%", top: "92%" },
  { name: "infra-tomok",         left: "88%", top: "92%" },
  { name: "integration-tongsin", left: "94%", top: "92%" },
] as const;

export default function DojeFloorRow({ activeDojes, dojeBubbles }: Props) {
  return (
    <>
      {DOJE_FLOOR_LAYOUT.map((d) => (
        <div
          key={d.name}
          className="absolute"
          style={{
            left: d.left,
            top: d.top,
            transform: "translate(-50%, -100%)",
            zIndex: 5,
          }}
        >
          <DojeCharacter
            agentName={d.name}
            isActive={activeDojes.has(d.name)}
            message={dojeBubbles[d.name]}
          />
        </div>
      ))}
    </>
  );
}

export default function IlwolObongdo() {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        zIndex: 0,
        pointerEvents: "none",
      }}
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 1000 600"
        preserveAspectRatio="xMidYMid slice"
        width="100%"
        height="100%"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* ── 레이어2: 좌 기둥 몸체 (x=0~50, y=0~600) ── */}
        <rect x="0" y="0" width="50" height="600" fill="#A52A2A" />
        {/* 좌 기둥 단청 띠 4개 */}
        <rect x="0" y="8"  width="50" height="8"  fill="#2C5F8D" />
        <rect x="0" y="16" width="50" height="6"  fill="#C9A84C" />
        <rect x="0" y="22" width="50" height="5"  fill="#2D2926" />
        <rect x="0" y="27" width="50" height="6"  fill="#2C5F8D" />
        {/* 좌 기둥 받침 — v5: y=430~452 */}
        <rect x="0" y="430" width="50" height="22" fill="#5C3A21" />

        {/* ── 레이어2: 우 기둥 몸체 (x=950~1000, y=0~600) ── */}
        <rect x="950" y="0"   width="50" height="600" fill="#A52A2A" />
        {/* 우 기둥 단청 띠 4개 */}
        <rect x="950" y="8"   width="50" height="8"  fill="#2C5F8D" />
        <rect x="950" y="16"  width="50" height="6"  fill="#C9A84C" />
        <rect x="950" y="22"  width="50" height="5"  fill="#2D2926" />
        <rect x="950" y="27"  width="50" height="6"  fill="#2C5F8D" />
        {/* 우 기둥 받침 — v5: y=430~452 */}
        <rect x="950" y="430" width="50" height="22" fill="#5C3A21" />

        {/* ── Step 1: 후벽 단색 #4A2C2A (x=50~950, y=0~450) — 하늘 그라디언트 제거 ── */}
        <rect x="50" y="0" width="900" height="450" fill="#4A2C2A" />

        {/* ── Step 2: 일월오봉도 사각 병풍 (x=400~600, y=140~260) ── */}
        {/* 병풍 외곽 프레임 */}
        <rect x="400" y="140" width="200" height="120"
              fill="none" stroke="#3D2615" strokeWidth="3" />
        {/* 병풍 내부 한지 */}
        <rect x="403" y="143" width="194" height="114" fill="#F4ECD8" />

        {/* 달 */}
        <circle cx="430" cy="175" r="12" fill="#F4ECD8" stroke="#A89878" strokeWidth="1" />
        {/* 해 후광 */}
        <circle cx="570" cy="175" r="18" fill="rgba(231,76,60,0.20)" />
        {/* 해 본체 */}
        <circle cx="570" cy="175" r="12" fill="#E74C3C" />

        {/* 봉1 (좌끝) */}
        <polygon points="405,257  420,220  435,257"  fill="#4A6741" />
        {/* 봉2 (좌중) */}
        <polygon points="430,257  450,205  470,257"  fill="#4A6741" />
        {/* 봉3 (중앙·청람 강조) */}
        <polygon points="465,257  500,195  535,257"  fill="#3B6B8A" />
        {/* 봉4 (우중) */}
        <polygon points="530,257  550,205  570,257"  fill="#4A6741" />
        {/* 봉5 (우끝) */}
        <polygon points="565,257  580,220  595,257"  fill="#4A6741" />
        {/* 봉 하단 채움 */}
        <rect x="403" y="253" width="194" height="4" fill="#4A6741" />

        {/* ── 레이어4: 옥좌 등받이 — y=200~250 ── */}
        {/* 황금 관 장식 (등받이 상단): x=460~540 폭80 */}
        <rect x="460" y="200" width="80"  height="10"  fill="#C9A84C" />
        {/* 등받이 본체: x=468~532 폭64 */}
        <rect x="468" y="205" width="64"  height="40"  fill="#A52A2A" />
        {/* 옥좌 좌석: x=460~540 폭80 */}
        <rect x="460" y="238" width="80"  height="12"  fill="#8B5C1E" />
        {/* 좌석 하단 음영 */}
        <rect x="460" y="249" width="80"  height="3"   fill="#5C3A21" />

        {/* ── 레이어4: 옥좌 단상 — y=240~280 ── */}
        {/* 황금 테두리 상단 */}
        <rect x="420" y="240" width="160" height="2"   fill="#C9A84C" />
        {/* 황금 테두리 좌 */}
        <rect x="418" y="240" width="2"   height="40"  fill="#C9A84C" />
        {/* 황금 테두리 우 */}
        <rect x="580" y="240" width="2"   height="40"  fill="#C9A84C" />
        {/* 단상 상판 */}
        <rect x="420" y="252" width="160" height="20"  fill="#2D2926" />
        {/* 단상 측면 그림자 */}
        <rect x="420" y="272" width="160" height="10"  fill="#1A1410" />

        {/* ── 레이어5: 빨간 계단 5단 — y=282~342 ── */}
        {/* 계단5 (가장 위): x=430~570 폭140 */}
        <rect x="430" y="282" width="140" height="12"  fill="#8B0000" />
        {/* 계단4: x=418~582 폭164 */}
        <rect x="418" y="294" width="164" height="12"  fill="#7A0000" />
        {/* 계단3: x=406~594 폭188 */}
        <rect x="406" y="306" width="188" height="12"  fill="#8B0000" />
        {/* 계단2: x=394~606 폭212 */}
        <rect x="394" y="318" width="212" height="12"  fill="#7A0000" />
        {/* 계단1 (가장 아래): x=370~630 폭260 */}
        <rect x="370" y="330" width="260" height="12"  fill="#8B0000" />
        {/* 계단 하단 경계선 */}
        <rect x="370" y="342" width="260" height="2"   fill="#1A1410" />

        {/* ── 레이어6: 빨간 카펫 사다리꼴 — v5: 하단 y=452 ── */}
        {/* 위 폭 80 (x=460~540 y=344), 아래 폭 330 (x=335~665 y=452) */}
        <polygon
          points="460,344  540,344  665,452  335,452"
          fill="#8B0000"
          stroke="#6B0000"
          strokeWidth="2"
        />
        {/* 카펫 하단 경계선 */}
        <rect x="335" y="450" width="330" height="2" fill="#1A1410" />

        {/* ── Step 3: 마룻바닥 25% (y=450~600) ── */}
        {/* 마루 경계선 — y=450~452 */}
        <rect x="0" y="450" width="1000" height="2" fill="#1A1410" />
        {/* 마룻바닥 기본 — y=452~600 */}
        <rect x="0" y="452" width="1000" height="148" fill="#5C3A21" />
        {/* 마룻결 가로선 4개 */}
        <line x1="0" y1="475" x2="1000" y2="475" stroke="#3D2615" strokeWidth="2" />
        <line x1="0" y1="520" x2="1000" y2="520" stroke="#3D2615" strokeWidth="2" />
        <line x1="0" y1="560" x2="1000" y2="560" stroke="#3D2615" strokeWidth="2" />
        <line x1="0" y1="590" x2="1000" y2="590" stroke="#3D2615" strokeWidth="2" />
      </svg>
    </div>
  );
}

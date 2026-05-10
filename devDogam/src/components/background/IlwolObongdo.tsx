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
        <defs>
          {/* 일월오봉도 하늘 그라디언트 */}
          <linearGradient id="sky-bg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor="#1A2B47" />
            <stop offset="60%"  stopColor="#3B5E8C" />
            <stop offset="100%" stopColor="#2D5A27" />
          </linearGradient>
        </defs>

        {/* ── 레이어1: 단청 천장 + 처마 (y=0~53) ── */}
        <rect x="0"   y="0" width="200" height="50" fill="#2C5F8D" />
        <rect x="200" y="0" width="200" height="50" fill="#D94F2B" />
        <rect x="400" y="0" width="200" height="50" fill="#C9A84C" />
        <rect x="600" y="0" width="200" height="50" fill="#E8DCC8" />
        <rect x="800" y="0" width="200" height="50" fill="#2D2926" />
        {/* 처마 마감선 */}
        <rect x="0" y="50" width="1000" height="3" fill="#1A1410" />

        {/* ── 레이어2: 좌 기둥 몸체 (x=0~70, y=0~600) ── */}
        <rect x="0" y="0" width="70" height="600" fill="#A52A2A" />
        {/* 좌 기둥 단청 띠 4개 */}
        <rect x="0" y="58" width="70" height="8"  fill="#2C5F8D" />
        <rect x="0" y="66" width="70" height="6"  fill="#C9A84C" />
        <rect x="0" y="72" width="70" height="5"  fill="#2D2926" />
        <rect x="0" y="77" width="70" height="6"  fill="#2C5F8D" />
        {/* 좌 기둥 받침 */}
        <rect x="0" y="480" width="70" height="20" fill="#5C3A21" />

        {/* ── 레이어2: 우 기둥 몸체 (x=930~1000, y=0~600) ── */}
        <rect x="930" y="0"   width="70" height="600" fill="#A52A2A" />
        {/* 우 기둥 단청 띠 4개 */}
        <rect x="930" y="58"  width="70" height="8"  fill="#2C5F8D" />
        <rect x="930" y="66"  width="70" height="6"  fill="#C9A84C" />
        <rect x="930" y="72"  width="70" height="5"  fill="#2D2926" />
        <rect x="930" y="77"  width="70" height="6"  fill="#2C5F8D" />
        {/* 우 기둥 받침 */}
        <rect x="930" y="480" width="70" height="20" fill="#5C3A21" />

        {/* ── 레이어3: 일월오봉도 후벽 (x=70~930, y=53~370) ── */}
        <rect x="70" y="53" width="860" height="317" fill="url(#sky-bg)" />

        {/* 달 (좌 상단) cx=200 cy=130 r=50 */}
        <circle cx="200" cy="130" r="50" fill="#F5E6A3" />
        {/* 달 크레이터 */}
        <circle cx="218" cy="116" r="11" fill="#E0D0B0" />

        {/* 해 후광 (우 상단) cx=800 cy=130 r=70 */}
        <circle cx="800" cy="130" r="70" fill="#E87C2A" opacity="0.25" />
        {/* 해 본체 cx=800 cy=130 r=50 */}
        <circle cx="800" cy="130" r="50" fill="#E87C2A" />

        {/* 5봉 실루엣 (y 기준선=370으로 조정) */}
        {/* 봉1 (좌끝) */}
        <polygon points="50,370  130,255  210,370"  fill="#1A2B1A" />
        {/* 봉2 (좌중) */}
        <polygon points="195,370 295,220  395,370"  fill="#1A2B1A" />
        {/* 봉3 (중앙): 청람 강조 */}
        <polygon points="380,370 500,180  620,370"  fill="#2C5F8D" />
        {/* 봉4 (우중) */}
        <polygon points="605,370 705,220  805,370"  fill="#1A2B1A" />
        {/* 봉5 (우끝) */}
        <polygon points="790,370 870,255  950,370"  fill="#1A2B1A" />
        {/* 봉 하단 채움 — 후벽 하단 경계 */}
        <rect x="70" y="368" width="860" height="5" fill="#1A2B1A" />

        {/* ── 레이어4: 옥좌 등받이 ── */}
        {/* 황금 관 장식 (등받이 상단) */}
        <rect x="445" y="255" width="110" height="10"  fill="#C9A84C" />
        {/* 등받이 본체 */}
        <rect x="455" y="260" width="90"  height="55"  fill="#A52A2A" />
        {/* 옥좌 좌석 */}
        <rect x="445" y="305" width="110" height="15"  fill="#8B5C1E" />
        {/* 좌석 하단 음영 */}
        <rect x="445" y="319" width="110" height="3"   fill="#5C3A21" />

        {/* ── 레이어4: 옥좌 단상 ── */}
        {/* 황금 테두리 상단 */}
        <rect x="390" y="308" width="220" height="2"   fill="#C9A84C" />
        {/* 황금 테두리 좌 */}
        <rect x="388" y="308" width="2"   height="54"  fill="#C9A84C" />
        {/* 황금 테두리 우 */}
        <rect x="610" y="308" width="2"   height="54"  fill="#C9A84C" />
        {/* 단상 상판 */}
        <rect x="390" y="322" width="220" height="35"  fill="#2D2926" />
        {/* 단상 측면 그림자 */}
        <rect x="390" y="357" width="220" height="15"  fill="#1A1410" />

        {/* ── 레이어5: 빨간 계단 5단 (위→아래, 아래로 갈수록 넓어짐) ── */}
        {/* 계단5 (가장 위, 단상 바로 앞): x=410~590 */}
        <rect x="410" y="372" width="180" height="12"  fill="#8B0000" />
        {/* 계단4: x=396~604 */}
        <rect x="396" y="384" width="208" height="12"  fill="#7A0000" />
        {/* 계단3: x=380~620 */}
        <rect x="380" y="396" width="240" height="12"  fill="#8B0000" />
        {/* 계단2: x=364~636 */}
        <rect x="364" y="408" width="272" height="12"  fill="#7A0000" />
        {/* 계단1 (가장 아래, 가장 넓음): x=348~652 */}
        <rect x="348" y="420" width="304" height="12"  fill="#8B0000" />
        {/* 계단 하단 경계선 */}
        <rect x="348" y="432" width="304" height="2"   fill="#1A1410" />

        {/* ── 레이어6: 빨간 카펫 사다리꼴 (계단 발치 → 마루 경계) ── */}
        {/* 위 폭 100 (x=450~550 y=434), 아래 폭 330 (x=335~665 y=502) */}
        <polygon
          points="450,434  550,434  665,502  335,502"
          fill="#8B0000"
          stroke="#6B0000"
          strokeWidth="2"
        />
        {/* 카펫 하단 경계선 */}
        <rect x="335" y="500" width="330" height="2" fill="#1A1410" />

        {/* ── 레이어7: 마루 경계선 + 마룻바닥 (y=500~600) ── */}
        {/* 마루 경계선 */}
        <rect x="0" y="500" width="1000" height="2" fill="#1A1410" />
        {/* 마룻바닥 기본 */}
        <rect x="0" y="502" width="1000" height="98" fill="#5C3A21" />
        {/* 마룻결 가로선 3개 */}
        <line x1="0" y1="525" x2="1000" y2="525" stroke="#3D2615" strokeWidth="2" />
        <line x1="0" y1="555" x2="1000" y2="555" stroke="#3D2615" strokeWidth="2" />
        <line x1="0" y1="580" x2="1000" y2="580" stroke="#3D2615" strokeWidth="2" />
      </svg>
    </div>
  );
}

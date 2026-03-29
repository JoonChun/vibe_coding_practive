export interface UnitCategory {
  name: string;
  units: UnitDef[];
}

export interface UnitDef {
  id: string;
  label: string;
  toBase: (value: number) => number;
  fromBase: (value: number) => number;
}

function linear(factor: number): Pick<UnitDef, "toBase" | "fromBase"> {
  return {
    toBase: (v) => v * factor,
    fromBase: (v) => v / factor,
  };
}

export const UNIT_CATEGORIES: UnitCategory[] = [
  {
    name: "길이",
    units: [
      { id: "mm", label: "밀리미터 (mm)", ...linear(0.001) },
      { id: "cm", label: "센티미터 (cm)", ...linear(0.01) },
      { id: "m", label: "미터 (m)", ...linear(1) },
      { id: "km", label: "킬로미터 (km)", ...linear(1000) },
      { id: "in", label: "인치 (in)", ...linear(0.0254) },
      { id: "ft", label: "피트 (ft)", ...linear(0.3048) },
      { id: "mi", label: "마일 (mi)", ...linear(1609.344) },
    ],
  },
  {
    name: "무게",
    units: [
      { id: "mg", label: "밀리그램 (mg)", ...linear(0.001) },
      { id: "g", label: "그램 (g)", ...linear(1) },
      { id: "kg", label: "킬로그램 (kg)", ...linear(1000) },
      { id: "lb", label: "파운드 (lb)", ...linear(453.592) },
      { id: "oz", label: "온스 (oz)", ...linear(28.3495) },
      { id: "근", label: "근", ...linear(600) },
    ],
  },
  {
    name: "온도",
    units: [
      {
        id: "celsius",
        label: "섭씨 (°C)",
        toBase: (v) => v,
        fromBase: (v) => v,
      },
      {
        id: "fahrenheit",
        label: "화씨 (°F)",
        toBase: (v) => (v - 32) * (5 / 9),
        fromBase: (v) => v * (9 / 5) + 32,
      },
      {
        id: "kelvin",
        label: "켈빈 (K)",
        toBase: (v) => v - 273.15,
        fromBase: (v) => v + 273.15,
      },
    ],
  },
  {
    name: "넓이",
    units: [
      { id: "sqm", label: "제곱미터 (m²)", ...linear(1) },
      { id: "sqkm", label: "제곱킬로미터 (km²)", ...linear(1_000_000) },
      { id: "pyeong", label: "평 (坪)", ...linear(3.3058) },
      { id: "sqft", label: "제곱피트 (ft²)", ...linear(0.092903) },
      { id: "acre", label: "에이커", ...linear(4046.86) },
      { id: "ha", label: "헥타르 (ha)", ...linear(10_000) },
    ],
  },
  {
    name: "부피",
    units: [
      { id: "ml", label: "밀리리터 (mL)", ...linear(0.001) },
      { id: "l", label: "리터 (L)", ...linear(1) },
      { id: "gal", label: "갤런 (gal)", ...linear(3.78541) },
      { id: "cup", label: "컵", ...linear(0.236588) },
      { id: "tbsp", label: "큰술 (tbsp)", ...linear(0.014787) },
      { id: "tsp", label: "작은술 (tsp)", ...linear(0.004929) },
    ],
  },
  {
    name: "속도",
    units: [
      { id: "mps", label: "m/s", ...linear(1) },
      { id: "kmh", label: "km/h", ...linear(1 / 3.6) },
      { id: "mph", label: "mph", ...linear(0.44704) },
      { id: "knot", label: "노트 (knot)", ...linear(0.514444) },
    ],
  },
  {
    name: "데이터",
    units: [
      { id: "b", label: "바이트 (B)", ...linear(1) },
      { id: "kb", label: "킬로바이트 (KB)", ...linear(1024) },
      { id: "mb", label: "메가바이트 (MB)", ...linear(1024 ** 2) },
      { id: "gb", label: "기가바이트 (GB)", ...linear(1024 ** 3) },
      { id: "tb", label: "테라바이트 (TB)", ...linear(1024 ** 4) },
    ],
  },
];

export function convertUnit(
  value: number,
  fromUnitId: string,
  toUnitId: string,
  categoryName: string
): number {
  const category = UNIT_CATEGORIES.find((c) => c.name === categoryName);
  if (!category) return 0;

  const fromUnit = category.units.find((u) => u.id === fromUnitId);
  const toUnit = category.units.find((u) => u.id === toUnitId);
  if (!fromUnit || !toUnit) return 0;

  const base = fromUnit.toBase(value);
  return toUnit.fromBase(base);
}

export interface BmiInput {
  heightCm: number;
  weightKg: number;
}

export type BmiCategory =
  | "underweight"
  | "normal"
  | "overweight"
  | "obese1"
  | "obese2"
  | "obese3";

export interface BmiResult {
  bmi: number;
  category: BmiCategory;
  categoryLabel: string;
  standardWeight: number;
  normalMin: number;
  normalMax: number;
}

function round1(v: number): number {
  return Math.round(v * 10) / 10;
}

export function calculateBmi(input: BmiInput): BmiResult {
  const { heightCm, weightKg } = input;

  if (heightCm <= 0) throw new Error("키는 0보다 커야 합니다.");
  if (weightKg <= 0) throw new Error("체중은 0보다 커야 합니다.");

  const heightM = heightCm / 100;
  const bmi = round1(weightKg / (heightM * heightM));

  let category: BmiCategory;
  let categoryLabel: string;

  if (bmi < 18.5) {
    category = "underweight";
    categoryLabel = "저체중";
  } else if (bmi < 23) {
    category = "normal";
    categoryLabel = "정상";
  } else if (bmi < 25) {
    category = "overweight";
    categoryLabel = "과체중";
  } else if (bmi < 30) {
    category = "obese1";
    categoryLabel = "비만 1단계";
  } else if (bmi < 35) {
    category = "obese2";
    categoryLabel = "비만 2단계";
  } else {
    category = "obese3";
    categoryLabel = "고도비만";
  }

  const standardWeight = round1(22 * heightM * heightM);
  const normalMin = round1(18.5 * heightM * heightM);
  const normalMax = round1(22.9 * heightM * heightM);

  return { bmi, category, categoryLabel, standardWeight, normalMin, normalMax };
}

import type { AnalysisResult } from '@/types';
import { COLORS } from '@/constants';

interface ComparisonViewProps {
  products: AnalysisResult[];
}

export function ComparisonView({ products }: ComparisonViewProps) {
  if (products.length < 2) return null;

  return (
    <div className="bg-surface rounded-3xl p-6 shadow-whisper">
      <h2 className="font-headline text-[15px] font-bold text-on-surface mb-5">벤치마킹 비교</h2>

      <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${products.length}, 1fr)` }}>
        {products.map((product) => (
          <ProductColumn key={product.id} product={product} />
        ))}
      </div>

      {/* 차별화 포인트 */}
      {products.length >= 2 && (
        <DifferentiationSection products={products} />
      )}
    </div>
  );
}

function ProductColumn({ product }: { product: AnalysisResult }) {
  const { positivePercent, negativePercent } = product.sentiment;

  return (
    <div className="flex flex-col gap-3 p-4 bg-surface-container-low rounded-2xl">
      <h3 className="font-headline text-[14px] font-bold text-on-surface truncate">
        {product.productName}
      </h3>
      <span className="text-[11px] text-secondary">
        {product.platform === 'coupang' ? '쿠팡' : '네이버'}
      </span>

      {/* 감성 바 */}
      <div>
        <div className="flex justify-between text-[11px] text-secondary mb-1">
          <span>긍정 {positivePercent}%</span>
          <span>부정 {negativePercent}%</span>
        </div>
        <div className="h-2 rounded-full bg-surface-container-high overflow-hidden">
          <div
            className="h-full rounded-full"
            style={{
              width: `${positivePercent}%`,
              background: `linear-gradient(to right, ${COLORS.PRIMARY}, ${COLORS.POSITIVE})`,
            }}
          />
        </div>
      </div>

      {/* 상위 키워드 */}
      <div>
        <p className="text-[11px] text-secondary mb-1.5">주요 키워드</p>
        <div className="flex flex-wrap gap-1">
          {product.keywords.slice(0, 5).map((kw) => (
            <span
              key={kw.word}
              className="px-2 py-0.5 bg-surface-container text-[11px] rounded-full text-secondary"
            >
              {kw.word} ({kw.count})
            </span>
          ))}
        </div>
      </div>

      {/* AI 요약 */}
      <div className="text-[12px] text-on-surface leading-relaxed">
        {product.summary.overall}
      </div>
    </div>
  );
}

function DifferentiationSection({ products }: { products: AnalysisResult[] }) {
  const [p1, p2] = products;

  // 각 상품의 긍정 키워드 추출
  const p1PositiveKeywords = new Set(
    p1.keywords.filter((k) => k.sentiment === 'positive').map((k) => k.word),
  );
  const p2PositiveKeywords = new Set(
    p2.keywords.filter((k) => k.sentiment === 'positive').map((k) => k.word),
  );

  const uniqueTo1 = [...p1PositiveKeywords].filter((k) => !p2PositiveKeywords.has(k));
  const uniqueTo2 = [...p2PositiveKeywords].filter((k) => !p1PositiveKeywords.has(k));

  if (uniqueTo1.length === 0 && uniqueTo2.length === 0) return null;

  return (
    <div className="mt-5 p-4 bg-primary/5 rounded-[12px]">
      <p className="text-[13px] font-semibold text-primary mb-3">차별화 포인트</p>
      <div className="grid grid-cols-2 gap-4">
        {uniqueTo1.length > 0 && (
          <div>
            <p className="text-[12px] text-secondary mb-1.5">
              {p1.productName.slice(0, 20)}만의 강점
            </p>
            <div className="flex flex-wrap gap-1">
              {uniqueTo1.slice(0, 5).map((kw) => (
                <span key={kw} className="px-2 py-0.5 bg-primary/10 text-primary text-[11px] rounded-full">
                  {kw}
                </span>
              ))}
            </div>
          </div>
        )}
        {uniqueTo2.length > 0 && (
          <div>
            <p className="text-[12px] text-secondary mb-1.5">
              {p2.productName.slice(0, 20)}만의 강점
            </p>
            <div className="flex flex-wrap gap-1">
              {uniqueTo2.slice(0, 5).map((kw) => (
                <span key={kw} className="px-2 py-0.5 bg-positive/10 text-positive text-[11px] rounded-full">
                  {kw}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

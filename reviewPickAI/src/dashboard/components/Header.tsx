import { RefObject } from 'react';
import { Download, FileText, Image, ExternalLink } from 'lucide-react';
import type { AnalysisResult } from '@/types';
import { useExport } from '../hooks/useExport';

interface HeaderProps {
  data: AnalysisResult;
  svgRef: RefObject<SVGSVGElement>;
}

export function Header({ data, svgRef }: HeaderProps) {
  const { exportCSV, exportPDF, exportMindmapPNG } = useExport(data);

  const platformLabel = data.platform === 'coupang' ? '쿠팡' : '네이버 쇼핑';
  const avgRating =
    data.reviews.length > 0
      ? (data.reviews.reduce((s, r) => s + r.rating, 0) / data.reviews.length).toFixed(1)
      : '-';

  return (
    <header className="sticky top-0 z-20 bg-surface/80 backdrop-blur-xl border-b border-outline-variant/10 shadow-whisper-sm">
      <div className="max-w-screen-2xl mx-auto px-8 py-4">
        <div className="flex items-center justify-between gap-6">
          {/* Brand + 상품 정보 */}
          <div className="flex items-center gap-5 min-w-0">
            <span className="font-headline font-bold text-[18px] text-gradient-brand flex-shrink-0 leading-none">
              ReviewPick AI
            </span>

            <div className="h-4 w-px bg-outline-variant/50 flex-shrink-0" />

            <div className="min-w-0">
              <h1 className="font-headline font-bold text-[16px] text-on-surface truncate max-w-[460px] leading-tight">
                {data.productName}
              </h1>
              <div className="flex items-center gap-3 mt-0.5 text-[12px] text-secondary">
                <span className="px-2 py-0.5 bg-primary/10 text-primary rounded-full font-semibold">
                  {platformLabel}
                </span>
                <span>리뷰 {data.totalReviews.toLocaleString()}개</span>
                <span className="text-yellow-500">★</span>
                <span>{avgRating}</span>
                <span className="text-outline-variant">·</span>
                <span>{new Date(data.scrapedAt).toLocaleDateString('ko-KR')}</span>
              </div>
            </div>

            <a
              href={data.productUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-shrink-0 text-secondary hover:text-primary transition-colors"
              title="상품 페이지 열기"
            >
              <ExternalLink size={14} />
            </a>
          </div>

          {/* 내보내기 버튼 그룹 */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <div className="flex bg-surface-container-low p-1 rounded-[14px] gap-0.5">
              <button
                onClick={exportCSV}
                className="px-3.5 py-2 hover:bg-surface rounded-[10px] transition-colors flex items-center gap-1.5 text-[12px] font-medium text-secondary"
              >
                <Download size={13} />
                CSV
              </button>
              <button
                onClick={exportPDF}
                className="px-3.5 py-2 hover:bg-surface rounded-[10px] transition-colors flex items-center gap-1.5 text-[12px] font-medium text-secondary"
              >
                <FileText size={13} />
                PDF
              </button>
              <button
                onClick={() => exportMindmapPNG(svgRef)}
                className="px-3.5 py-2 bg-gradient-primary text-white rounded-[10px] flex items-center gap-1.5 text-[12px] font-semibold hover:opacity-90 transition-opacity"
              >
                <Image size={13} />
                마인드맵 PNG
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

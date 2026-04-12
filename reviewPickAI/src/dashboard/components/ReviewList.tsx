import { useMemo } from 'react';
import { Star } from 'lucide-react';
import type { TaggedReview, SentimentLabel } from '@/types';

interface ReviewListProps {
  reviews: TaggedReview[];
  highlightKeyword?: string;
  filterIndices?: number[];
}

const SENTIMENT_STYLE: Record<SentimentLabel, { label: string; className: string }> = {
  positive: { label: '긍정', className: 'bg-primary/10 text-primary' },
  negative: { label: '부정', className: 'bg-negative/10 text-negative' },
  neutral: { label: '중립', className: 'bg-surface-container-high text-secondary' },
};

export function ReviewList({ reviews, highlightKeyword, filterIndices }: ReviewListProps) {
  const displayReviews = useMemo(() => {
    if (!filterIndices) return reviews;
    return filterIndices.map((i) => reviews[i]).filter(Boolean);
  }, [reviews, filterIndices]);

  return (
    <div className="flex flex-col">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-8 py-5 border-b border-outline-variant/10">
        <h2 className="font-headline font-semibold text-[16px] text-on-surface">리뷰 목록</h2>
        <span className="text-[12px] text-secondary font-medium">
          {displayReviews.length.toLocaleString()}개{filterIndices && ' (필터됨)'}
        </span>
      </div>

      {/* 리뷰 카드 목록 */}
      <div className="overflow-y-auto p-6 space-y-3" style={{ maxHeight: 520 }}>
        {displayReviews.length === 0 ? (
          <div className="py-16 text-center text-secondary text-[14px]">
            해당 조건의 리뷰가 없습니다.
          </div>
        ) : (
          displayReviews.map((review) => (
            <ReviewItem key={review.id} review={review} highlightKeyword={highlightKeyword} />
          ))
        )}
      </div>
    </div>
  );
}

function ReviewItem({
  review,
  highlightKeyword,
}: {
  review: TaggedReview;
  highlightKeyword?: string;
}) {
  const style = SENTIMENT_STYLE[review.sentiment];
  const initials = review.author.slice(0, 2).toUpperCase();

  return (
    <div className="p-5 rounded-2xl bg-surface-container-low hover:bg-surface-container transition-colors border border-transparent hover:border-outline-variant/20">
      <div className="flex items-start gap-3.5">
        {/* 아바타 */}
        <div className="w-8 h-8 rounded-full bg-surface-container-high flex items-center justify-center text-[11px] font-bold text-secondary flex-shrink-0 mt-0.5">
          {initials}
        </div>

        <div className="flex-1 min-w-0">
          {/* 메타 행 */}
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2.5">
              <span className="font-semibold text-[13px] text-on-surface">{review.author}</span>
              <StarRating rating={review.rating} />
              <span className="text-[11px] text-on-surface-variant">{review.date}</span>
            </div>
            <span
              className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold flex-shrink-0 ${style.className}`}
            >
              {style.label}
            </span>
          </div>

          {/* 리뷰 본문 */}
          <p className="text-[13px] text-on-surface-variant leading-relaxed">
            {highlightKeyword
              ? highlightText(review.text, highlightKeyword)
              : review.text}
          </p>

          {/* 키워드 태그 */}
          {review.keywords.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {review.keywords.map((kw) => (
                <span
                  key={kw}
                  className="px-2.5 py-0.5 bg-surface-container-highest text-secondary text-[11px] rounded-full"
                >
                  #{kw}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StarRating({ rating }: { rating: number }) {
  return (
    <div className="flex items-center gap-0.5">
      {Array.from({ length: 5 }).map((_, i) => (
        <Star
          key={i}
          size={10}
          className={i < Math.round(rating) ? 'text-yellow-400 fill-yellow-400' : 'text-surface-container-highest'}
        />
      ))}
    </div>
  );
}

function highlightText(text: string, keyword: string): React.ReactNode {
  if (!keyword) return text;
  const parts = text.split(new RegExp(`(${escapeRegex(keyword)})`, 'gi'));
  return parts.map((part, i) =>
    part.toLowerCase() === keyword.toLowerCase() ? (
      <mark key={i} className="bg-primary/20 text-primary rounded px-0.5">
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

function escapeRegex(str: string) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

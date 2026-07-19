import { useEffect, useRef, type ReactNode } from "react";

interface BottomSheetProps {
  onClose: () => void;
  /** role="dialog" aria-labelledby 대상 — 콘텐츠(children) 안에 같은 id를 가진 헤딩이 있어야 한다. */
  titleId: string;
  /** 열리는 즉시 어디에 포커스를 줄지 소유자가 결정(§12 "첫 포커스는 날짜 입력"). 없으면 패널 자체에 포커스. */
  onRequestInitialFocus?: () => void;
  children: ReactNode;
}

const FOCUSABLE_SELECTOR =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

/**
 * 범용 바텀시트 프리미티브(docs/wireframes/phase3-timemachine.md §8) — 백드롭·드래그 핸들(장식)·
 * 닫기 버튼·포커스 트랩만 소유하고, 헤더 텍스트(타이틀/뒤로가기)는 콘텐츠(children)가 자체적으로
 * 그린다 — Phase 3 외 다른 기능에서도 재사용 가능하도록 콘텐츠 종류를 가정하지 않는다.
 * 마운트=열림, 언마운트=닫힘으로 취급한다(호출부가 `{open && <BottomSheet>...}`로 조건부 렌더).
 */
export function BottomSheet({ onClose, titleId, onRequestInitialFocus, children }: BottomSheetProps) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const previousActiveRef = useRef<Element | null>(null);
  // 유령 클릭 방어: 차트 탭(pointerup)으로 시트가 열린 직후, 같은 제스처의 click 이벤트가
  // 새로 마운트된 백드롭 위에 떨어져 시트가 즉시 닫히는 것을 막는다(열림 직후 350ms 무시).
  const openedAtRef = useRef<number>(performance.now());

  // 열릴 때: 트리거 포커스 기억 + 배경 스크롤 잠금 + 초기 포커스. 닫힐 때(언마운트): 원복.
  useEffect(() => {
    previousActiveRef.current = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    if (onRequestInitialFocus) {
      onRequestInitialFocus();
    } else {
      panelRef.current?.focus();
    }

    return () => {
      document.body.style.overflow = previousOverflow;
      const prev = previousActiveRef.current;
      if (prev instanceof HTMLElement) {
        prev.focus();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Escape 닫기 + Tab 포커스 트랩(§12 "Escape 키·백드롭 클릭·닫기 버튼 모두 동일하게 닫음").
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const panel = panelRef.current;
      if (!panel) return;
      const focusables = panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="bottom-sheet">
      <div
        className="bottom-sheet__backdrop"
        onClick={() => {
          if (performance.now() - openedAtRef.current < 350) return; // 유령 클릭 무시
          onClose();
        }}
        aria-hidden="true"
      />
      <div
        ref={panelRef}
        className="bottom-sheet__panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <div className="bottom-sheet__handle" aria-hidden="true" />
        <button
          type="button"
          className="detail-header__back bottom-sheet__close"
          onClick={onClose}
          aria-label="닫기"
        >
          <span aria-hidden="true">✕</span>
        </button>
        <div className="bottom-sheet__content">{children}</div>
      </div>
    </div>
  );
}

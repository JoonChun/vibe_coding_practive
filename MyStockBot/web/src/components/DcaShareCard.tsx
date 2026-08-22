import { useEffect, useMemo, useRef, useState } from "react";
import type { DcaResponse } from "../types";
import { CARD_H, CARD_W, buildShareModel, drawShareCard } from "../utils/dcaShare";

/** navigator.share 로 파일을 보낼 수 있는 환경인가(모바일 원탭 공유). */
function canShareFiles(): boolean {
  const n = navigator as Navigator & {
    canShare?: (data: { files?: File[] }) => boolean;
  };
  if (typeof n.share !== "function" || typeof n.canShare !== "function") return false;
  try {
    // 빈 File 로 물어본다 — 실제 이미지가 준비되기 전에 버튼 문구를 정해야 하므로.
    return n.canShare({ files: [new File([""], "probe.png", { type: "image/png" })] });
  } catch {
    return false;
  }
}

function toBlob(canvas: HTMLCanvasElement): Promise<Blob | null> {
  return new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
}

/**
 * 적립식 결과 공유 카드 — 세로(9:16) 미리보기 + 원탭 저장/공유.
 *
 * 미리보기로 보이는 캔버스를 **그대로** PNG 로 내보낸다(§utils/dcaShare 주석 참고).
 * 화면용 렌더러와 이미지용 렌더러를 따로 두면 면책·가정 문구가 한쪽에서만 빠지는
 * 사고가 나기 때문이다.
 */
export function DcaShareCard({ data, name }: { data: DcaResponse; name: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [fits, setFits] = useState(true);
  const shareable = useMemo(canShareFiles, []);

  const model = useMemo(() => buildShareModel(data, name), [data, name]);

  useEffect(() => {
    let alive = true;
    // 웹폰트가 도착하기 전에 그리면 폴백 폰트로 픽셀이 굳고, 그게 저장된다.
    // fonts.ready 는 폰트가 막힌 네트워크에서도 (폴백 확정 후) resolve 된다.
    const draw = () => {
      if (!alive || !canvasRef.current) return;
      const r = drawShareCard(canvasRef.current, model);
      setFits(r.fits);
      if (!r.fits) {
        // 가정·한계가 CTA 를 침범했다 = 작은 글씨가 잘려 나갔다. 조용히 넘기면
        // 면책 없는 카드가 SNS 로 나간다.
        console.warn(
          `[dca-share] 가정·한계가 카드에 다 들어가지 않았습니다 ` +
            `(${r.contentBottom} > ${r.limit}). 문구가 잘렸을 수 있습니다.`
        );
      }
    };
    draw(); // 즉시 한 번 — 폰트가 이미 준비됐으면 이게 최종이다.
    void document.fonts?.ready.then(draw).catch(() => {});
    return () => {
      alive = false;
    };
  }, [model]);

  async function save() {
    const canvas = canvasRef.current;
    if (!canvas) return;
    setBusy(true);
    setStatus(null);
    try {
      const blob = await toBlob(canvas);
      if (!blob) throw new Error("이미지 변환에 실패했습니다.");
      const kb = Math.max(1, Math.round(blob.size / 1024));

      if (shareable) {
        const file = new File([blob], model.fileName, { type: "image/png" });
        const n = navigator as Navigator & {
          share: (d: { files: File[]; title?: string }) => Promise<void>;
        };
        try {
          await n.share({ files: [file], title: `${model.title} 적립식 결과` });
          setStatus(`공유 시트를 열었습니다 · ${CARD_W}×${CARD_H} PNG (${kb}KB)`);
          return;
        } catch (e) {
          // 사용자가 공유 시트를 닫은 것(AbortError)은 실패가 아니다 — 조용히 끝낸다.
          if (e instanceof DOMException && e.name === "AbortError") {
            setStatus("공유를 취소했습니다.");
            return;
          }
          // 그 외(권한·미지원)는 저장으로 내려간다.
        }
      }

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = model.fileName;
      // ★ 문서에 붙여야 `download` 속성이 먹는다. 떼어놓은 앵커를 click() 하면
      //   다운로드는 되지만 파일명이 무시되고 확장자 없는 "download" 로 떨어진다
      //   (실측으로 확인 — 스모크의 파일명 검사가 이걸 잡았다).
      a.style.display = "none";
      document.body.appendChild(a);
      a.click();
      a.remove();
      // revoke 를 즉시 하면 브라우저가 저장을 시작하기 전에 URL 이 사라질 수 있다.
      window.setTimeout(() => URL.revokeObjectURL(url), 10000);
      setStatus(`이미지를 저장했습니다 · ${CARD_W}×${CARD_H} PNG (${kb}KB)`);
    } catch (e) {
      setStatus(e instanceof Error ? `실패: ${e.message}` : "이미지 만들기에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="dca-share">
      <canvas
        ref={canvasRef}
        className="dca-share__canvas"
        width={CARD_W}
        height={CARD_H}
        role="img"
        aria-label={model.altText}
        data-fit={fits ? "ok" : "overflow"}
      />
      <div className="dca-share__actions">
        <button
          type="button"
          className="dca-share__save"
          onClick={() => void save()}
          disabled={busy}
        >
          {busy ? "만드는 중…" : shareable ? "이미지 공유" : "이미지 저장"}
        </button>
      </div>
      {status ? (
        <p className="dca-share__status" data-testid="dca-share-status" role="status">
          {status}
        </p>
      ) : null}
    </div>
  );
}

import { useCallback, RefObject } from 'react';
import type { AnalysisResult } from '@/types';

export function useExport(data: AnalysisResult | null) {
  const exportCSV = useCallback(() => {
    if (!data) return;

    const rows = [
      ['ID', '플랫폼', '감성', '별점', '작성자', '날짜', '키워드', '리뷰 내용'],
      ...data.reviews.map((r) => [
        r.id,
        r.platform,
        r.sentiment,
        String(r.rating),
        r.author,
        r.date,
        r.keywords.join(';'),
        `"${r.text.replace(/"/g, '""')}"`,
      ]),
    ];

    // BOM + UTF-8 (한글 엑셀 호환)
    const csv = '\uFEFF' + rows.map((row) => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `reviewpick_${data.productName}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [data]);

  const exportPDF = useCallback(async () => {
    if (!data) return;

    const { jsPDF } = await import('jspdf');
    const { default: html2canvas } = await import('html2canvas');

    const dashboard = document.getElementById('dashboard-root');
    if (!dashboard) return;

    const canvas = await html2canvas(dashboard, {
      scale: 1.5,
      useCORS: true,
      allowTaint: true,
      // 배경색 명시 → 투명 영역이 검게 깨지는 현상 방지
      backgroundColor: '#F8F9FB',
      logging: false,
      imageTimeout: 0,
      // 현재 스크롤 위치 보정 → 스크롤된 상태에서도 최상단부터 캡처
      scrollX: 0,
      scrollY: -window.scrollY,
      // 전체 콘텐츠 크기로 캡처 (잘림 방지)
      windowWidth: dashboard.scrollWidth,
      windowHeight: dashboard.scrollHeight,
      onclone: (_doc: Document, el: HTMLElement) => {
        // backdrop-filter: blur()는 html2canvas 미지원 → 단색 배경으로 대체
        const removeBlur = (node: HTMLElement) => {
          node.style.backdropFilter = 'none';
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (node.style as any)['-webkit-backdrop-filter'] = 'none';
        };
        const header = el.querySelector('header');
        if (header instanceof HTMLElement) {
          removeBlur(header);
          header.style.backgroundColor = 'rgba(255, 255, 255, 0.97)';
        }
        // 마인드맵 배경 블러 컨테이너도 동일하게 처리
        el.querySelectorAll('[class*="backdrop-blur"]').forEach((node) => {
          if (node instanceof HTMLElement) removeBlur(node);
        });
      },
    });

    const imgData = canvas.toDataURL('image/png');
    const pdf = new jsPDF('l', 'mm', 'a4');
    const pdfW = pdf.internal.pageSize.getWidth();
    const pdfH = pdf.internal.pageSize.getHeight();
    // 전체 이미지를 PDF 너비에 맞춰 환산한 높이
    const imgH = (canvas.height * pdfW) / canvas.width;

    // 여러 페이지에 걸쳐 이미지를 분할 출력
    let yOffset = 0;
    let remaining = imgH;

    while (remaining > 0) {
      if (yOffset > 0) pdf.addPage();
      // y 좌표를 음수로 옮겨 해당 페이지 구간이 보이도록 함
      pdf.addImage(imgData, 'PNG', 0, -yOffset, pdfW, imgH);
      yOffset += pdfH;
      remaining -= pdfH;
    }

    const safeName = data.productName.replace(/[/\\:*?"<>|]/g, '_').slice(0, 40);
    pdf.save(`reviewpick_${safeName}_${new Date().toISOString().slice(0, 10)}.pdf`);
  }, [data]);

  const exportMindmapPNG = useCallback(
    (svgRef: RefObject<SVGSVGElement>) => {
      if (!data || !svgRef.current) return;

      const svg = svgRef.current;
      const serializer = new XMLSerializer();
      const svgStr = serializer.serializeToString(svg);
      const svgBlob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(svgBlob);

      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = svg.clientWidth * 2;
        canvas.height = svg.clientHeight * 2;
        const ctx = canvas.getContext('2d')!;
        ctx.fillStyle = '#FFFFFF';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.scale(2, 2);
        ctx.drawImage(img, 0, 0);
        URL.revokeObjectURL(url);

        const a = document.createElement('a');
        a.download = `reviewpick_mindmap_${new Date().toISOString().slice(0, 10)}.png`;
        a.href = canvas.toDataURL('image/png');
        a.click();
      };
      img.src = url;
    },
    [data],
  );

  return { exportCSV, exportPDF, exportMindmapPNG };
}

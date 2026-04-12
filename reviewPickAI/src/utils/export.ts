import type { AnalysisResult } from '@/types';

/**
 * 분석 결과를 PDF로 내보내기
 * (html2canvas + jsPDF 사용)
 */
export async function exportPDF(data: AnalysisResult): Promise<void> {
  const { jsPDF } = await import('jspdf');
  const { default: html2canvas } = await import('html2canvas');

  const dashboard = document.getElementById('dashboard-root');
  if (!dashboard) throw new Error('dashboard-root 요소를 찾을 수 없습니다.');

  const canvas = await html2canvas(dashboard, {
    scale: 1.5,
    useCORS: true,
    logging: false,
  });

  const imgData = canvas.toDataURL('image/png');
  const pdf = new jsPDF('l', 'mm', 'a4');
  const pdfWidth = pdf.internal.pageSize.getWidth();
  const pdfHeight = (canvas.height * pdfWidth) / canvas.width;

  // 여러 페이지 처리
  const pageHeight = pdf.internal.pageSize.getHeight();
  let heightLeft = pdfHeight;
  let position = 0;

  pdf.addImage(imgData, 'PNG', 0, position, pdfWidth, pdfHeight);
  heightLeft -= pageHeight;

  while (heightLeft > 0) {
    position = heightLeft - pdfHeight;
    pdf.addPage();
    pdf.addImage(imgData, 'PNG', 0, position, pdfWidth, pdfHeight);
    heightLeft -= pageHeight;
  }

  const filename = `reviewpick_${sanitizeFilename(data.productName)}_${todayStr()}.pdf`;
  pdf.save(filename);
}

/**
 * 원본 리뷰를 CSV로 내보내기 (한글 엑셀 호환 BOM UTF-8)
 */
export function exportCSV(data: AnalysisResult): void {
  const headers = ['ID', '플랫폼', '감성', '별점', '작성자', '날짜', '키워드', '리뷰내용'];

  const rows = data.reviews.map((r) => [
    r.id,
    r.platform === 'coupang' ? '쿠팡' : '네이버',
    r.sentiment === 'positive' ? '긍정' : r.sentiment === 'negative' ? '부정' : '중립',
    String(r.rating),
    r.author,
    r.date,
    r.keywords.join(';'),
    `"${r.text.replace(/"/g, '""')}"`,
  ]);

  const csvContent = [headers, ...rows].map((row) => row.join(',')).join('\n');
  const bom = '\uFEFF'; // BOM for Korean Excel
  const blob = new Blob([bom + csvContent], { type: 'text/csv;charset=utf-8;' });

  downloadBlob(
    blob,
    `reviewpick_${sanitizeFilename(data.productName)}_${todayStr()}.csv`,
  );
}

/**
 * 마인드맵 SVG를 PNG로 내보내기
 */
export function exportMindmapPNG(svg: SVGSVGElement, productName: string): void {
  const serializer = new XMLSerializer();
  const svgStr = serializer.serializeToString(svg);
  const svgBlob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(svgBlob);

  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement('canvas');
    const scale = 2; // 고해상도
    canvas.width = (svg.clientWidth || 800) * scale;
    canvas.height = (svg.clientHeight || 500) * scale;

    const ctx = canvas.getContext('2d')!;
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.scale(scale, scale);
    ctx.drawImage(img, 0, 0);

    URL.revokeObjectURL(url);

    const a = document.createElement('a');
    a.download = `reviewpick_mindmap_${sanitizeFilename(productName)}_${todayStr()}.png`;
    a.href = canvas.toDataURL('image/png');
    a.click();
  };
  img.src = url;
}

// ─── 헬퍼 ────────────────────────────────────────────────────────────────

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function sanitizeFilename(name: string): string {
  return name.replace(/[/\\:*?"<>|]/g, '_').slice(0, 40);
}

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

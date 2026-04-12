import { useEffect, useRef, forwardRef, useImperativeHandle } from 'react';
import * as d3 from 'd3';
import type { MindmapNode, SentimentLabel } from '@/types';
import { COLORS } from '@/constants';

interface MindmapProps {
  root: MindmapNode;
  onNodeClick: (node: MindmapNode) => void;
  activeNodeId?: string;
}

const SENTIMENT_COLOR: Record<SentimentLabel, string> = {
  positive: COLORS.PRIMARY,
  negative: COLORS.NEGATIVE,
  neutral: '#5A6270',   // 충분히 어두운 중립색
};

/** 라디알 좌표 → 데카르트 X (회전 없이 수평 텍스트를 위해 필요) */
const toX = (d: d3.HierarchyPointNode<MindmapNode>) =>
  d.y * Math.cos(d.x - Math.PI / 2);

/** 라디알 좌표 → 데카르트 Y */
const toY = (d: d3.HierarchyPointNode<MindmapNode>) =>
  d.y * Math.sin(d.x - Math.PI / 2);

export const Mindmap = forwardRef<SVGSVGElement, MindmapProps>(
  ({ root, onNodeClick, activeNodeId }, ref) => {
    const svgRef = useRef<SVGSVGElement>(null);
    useImperativeHandle(ref, () => svgRef.current!);

    useEffect(() => {
      if (!svgRef.current) return;

      const svg = d3.select(svgRef.current);
      svg.selectAll('*').remove();

      const width = svgRef.current.clientWidth || 800;
      const height = svgRef.current.clientHeight || 500;

      const g = svg
        .append('g')
        .attr('transform', `translate(${width / 2},${height / 2})`);

      // 줌/패닝
      // wheelDelta를 정규화해 마우스 모델/해상도에 무관하게 일정한 줌 속도 보장
      // D3 기본값(픽셀 모드 0.002)의 절반 → 부드럽고 예측 가능한 줌
      const zoom = d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.4, 3])
        .wheelDelta((event) =>
          -event.deltaY *
          (event.deltaMode === 1 ? 0.025 : event.deltaMode ? 0.5 : 0.001),
        )
        .on('zoom', (event) => g.attr('transform', event.transform.toString()));
      svg.call(zoom);

      // 방사형 트리 레이아웃
      const hierarchy = d3.hierarchy<MindmapNode>(root);
      const treeLayout = d3
        .tree<MindmapNode>()
        .size([2 * Math.PI, Math.min(width, height) / 2 - 80])
        .separation((a, b) => (a.parent === b.parent ? 1.2 : 2.5) / a.depth);

      const treeData = treeLayout(hierarchy);

      // ── 링크 ──────────────────────────────────────────────────────────────
      g.append('g')
        .attr('fill', 'none')
        .attr('stroke', '#C3C5D9')
        .attr('stroke-width', 1.5)
        .attr('stroke-opacity', 0.55)
        .selectAll('path')
        .data(treeData.links())
        .join('path')
        .attr(
          'd',
          d3
            .linkRadial<
              d3.HierarchyPointLink<MindmapNode>,
              d3.HierarchyPointNode<MindmapNode>
            >()
            .angle((d) => d.x)
            .radius((d) => d.y),
        );

      // ── 노드 그룹 ─────────────────────────────────────────────────────────
      // 데카르트 좌표로 배치 → 그룹 자체는 회전 없음 → 텍스트가 항상 수평
      const node = g
        .append('g')
        .selectAll('g')
        .data(treeData.descendants())
        .join('g')
        .attr('transform', (d) => `translate(${toX(d)},${toY(d)})`)
        .style('cursor', 'pointer')
        .on('click', (_event, d) => onNodeClick(d.data));

      // ── 원 배경 ───────────────────────────────────────────────────────────
      const RADIUS: Record<number, number> = { 0: 32, 1: 22, 2: 14 };
      node
        .append('circle')
        .attr('r', (d) => RADIUS[d.depth] ?? 14)
        .attr('fill', (d) => {
          if (d.depth === 0) return COLORS.PRIMARY;
          if (d.data.id === activeNodeId) return SENTIMENT_COLOR[d.data.sentiment];
          return '#fff';
        })
        .attr('stroke', (d) =>
          d.depth === 0 ? 'none' : SENTIMENT_COLOR[d.data.sentiment],
        )
        .attr('stroke-width', 2.5)
        .attr('filter', 'drop-shadow(0 2px 8px rgba(0,0,0,0.10))');

      // ── 루트 라벨 (원 안, 흰색, 수평) ────────────────────────────────────
      node
        .filter((d) => d.depth === 0)
        .append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '0.35em')
        .text((d) =>
          d.data.label.length > 9 ? d.data.label.slice(0, 9) + '…' : d.data.label,
        )
        .attr('font-size', '11px')
        .attr('font-weight', '700')
        .attr('fill', '#fff')
        .style('pointer-events', 'none');

      // ── 1레벨 원 안: count 뱃지 ───────────────────────────────────────────
      node
        .filter((d) => d.depth === 1)
        .append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '0.35em')
        .text((d) => d.data.count)
        .attr('font-size', '10px')
        .attr('font-weight', '700')
        .attr('fill', (d) =>
          d.data.id === activeNodeId ? '#fff' : SENTIMENT_COLOR[d.data.sentiment],
        )
        .style('pointer-events', 'none');

      // ── 비루트 라벨 (원 바깥, 수평, halo로 가독성 확보) ──────────────────
      // paint-order: stroke 를 사용해 흰색 테두리를 텍스트 뒤에 그림 →
      // dot-grid 배경이나 링크선 위에서도 명확하게 보임
      node
        .filter((d) => d.depth > 0)
        .append('text')
        .attr('dy', '0.35em')
        .attr('x', (d) => {
          const r = RADIUS[d.depth] ?? 14;
          return toX(d) >= 0 ? r + 5 : -(r + 5);
        })
        .attr('text-anchor', (d) => (toX(d) >= 0 ? 'start' : 'end'))
        .text((d) => d.data.label)
        .attr('font-size', (d) => (d.depth === 1 ? '12px' : '11px'))
        .attr('font-weight', (d) => (d.depth === 1 ? '600' : '400'))
        // 항상 어두운 색 → 배경 색상과 무관하게 대비 확보
        .attr('fill', (d) =>
          d.data.id === activeNodeId
            ? SENTIMENT_COLOR[d.data.sentiment]
            : '#191C1E',
        )
        // 흰색 halo: 배경(점 격자, 링크선)과 섞이지 않도록
        .attr('stroke', 'rgba(248,249,251,0.92)')
        .attr('stroke-width', '5')
        .attr('paint-order', 'stroke')
        .attr('stroke-linejoin', 'round')
        .style('pointer-events', 'none');

    }, [root, activeNodeId, onNodeClick]);

    return (
      <svg
        ref={svgRef}
        className="w-full h-full"
        style={{ minHeight: 480 }}
      />
    );
  },
);

Mindmap.displayName = 'Mindmap';

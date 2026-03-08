import { Position } from './schema';

// 2D 벡터 헬퍼
const dotProduct = (v1: Position, v2: Position) => v1.x * v2.x + v1.y * v2.y;
const normalize = (v: Position): Position => {
    const mag = Math.hypot(v.x, v.y);
    return { x: v.x / mag, y: v.y / mag };
};

// 분리축 정리(Separating Axis Theorem, SAT)를 이용한 볼록 다각형 충돌 검사
// poly1, poly2는 각각 렌더링된 점들의 배열 (월드 좌표계 기준)
export const checkPolygonIntersection = (poly1: Position[], poly2: Position[]): boolean => {
    const getAxes = (poly: Position[]) => {
        const axes: Position[] = [];
        for (let i = 0; i < poly.length; i++) {
            const p1 = poly[i];
            const p2 = poly[(i + 1) % poly.length];
            // edge vector
            const edge = { x: p2.x - p1.x, y: p2.y - p1.y };
            // normal vector (perpendicular to edge)
            axes.push(normalize({ x: -edge.y, y: edge.x }));
        }
        return axes;
    };

    const project = (poly: Position[], axis: Position) => {
        let min = dotProduct(poly[0], axis);
        let max = min;
        for (let i = 1; i < poly.length; i++) {
            const p = dotProduct(poly[i], axis);
            if (p < min) min = p;
            if (p > max) max = p;
        }
        return { min, max };
    };

    const overlap = (proj1: { min: number, max: number }, proj2: { min: number, max: number }) => {
        return Math.max(0, Math.min(proj1.max, proj2.max) - Math.max(proj1.min, proj2.min));
    };

    const axes1 = getAxes(poly1);
    const axes2 = getAxes(poly2);
    const axes = [...axes1, ...axes2];

    for (const axis of axes) {
        const proj1 = project(poly1, axis);
        const proj2 = project(poly2, axis);

        if (overlap(proj1, proj2) <= 0) {
            // 투영된 선분이 겹치지 않는 축이 존재하면, 두 다각형은 충돌하지 않는다.
            return false;
        }
    }

    // 모든 축에 대해 투영 선분이 겹치면 충돌 발생
    return true;
};

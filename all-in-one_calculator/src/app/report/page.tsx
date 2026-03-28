"use client";

import { useState, useEffect, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Trash2, GripVertical, ChevronDown, ChevronUp, Sparkles, ArrowLeftRight } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCalculatorStore } from "@/stores/calculator-store";
import { generateComparison, ComparisonField } from "@/lib/report-engine";
import { formatCurrency, cn } from "@/lib/utils";
import type { CalculationResult, CalculatorType } from "@/types/calculator";
import { REPORT_CATEGORIES, ReportCategory } from "@/lib/categories";
import { motion, AnimatePresence } from "framer-motion";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

const typeLabels: Record<CalculatorType, string> = {
  compound: "복리/적금",
  loan: "대출 상환",
  salary: "연봉 실수령액",
  unit: "단위 변환",
  dday: "디데이",
};

// --- Sortable Item Component ---
function SortableRow({ 
  field, 
  itemCount, 
  winnerIndex 
}: { 
  field: ComparisonField; 
  itemCount: number;
  winnerIndex: number | null;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: field.field });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 10 : 1,
    boxShadow: isDragging ? "0 10px 15px -3px rgb(0 0 0 / 0.1)" : "none",
  };

  return (
    <TableRow 
      ref={setNodeRef} 
      style={style}
      className={cn(isDragging && "bg-accent/50 opacity-80")}
    >
      <TableCell className="w-10">
        <button {...attributes} {...listeners} className="cursor-grab active:cursor-grabbing p-1 hover:bg-accent rounded">
          <GripVertical className="h-4 w-4 text-muted-foreground/50" />
        </button>
      </TableCell>
      <TableCell className="font-medium whitespace-nowrap min-w-[120px]">{field.label}</TableCell>
      {field.values.map((value, i) => (
        <TableCell
          key={i}
          className={cn(
            "text-right font-mono",
            field.winnerIndex === i && "text-primary font-bold"
          )}
        >
          {typeof value === "number" ? formatCurrency(value) : value}
        </TableCell>
      ))}
    </TableRow>
  );
}

// --- Category Section Component ---
function CategorySection({ 
  category, 
  fields, 
  itemCount,
  onReorder
}: { 
  category: typeof REPORT_CATEGORIES[ReportCategory]; 
  fields: ComparisonField[];
  itemCount: number;
  onReorder: (activeId: string, overId: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(true);
  const Icon = category.icon;

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      onReorder(active.id as string, over.id as string);
    }
  };

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  return (
    <div className="border border-border/50 rounded-xl overflow-hidden bg-card/30 backdrop-blur-md shadow-sm transition-all hover:shadow-md">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 hover:bg-accent/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={cn("p-2 rounded-lg bg-card border border-border/50", category.color)}>
            <Icon className="h-5 w-5" />
          </div>
          <span className="font-bold text-sm tracking-tight">{category.label}</span>
          <Badge variant="secondary" className="text-[10px] h-4 px-1.5 opacity-70">
            {fields.length}
          </Badge>
        </div>
        {isOpen ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-1 pb-1">
              <DndContext 
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={handleDragEnd}
              >
                <Table>
                  <SortableContext 
                    items={fields.map(f => f.field)}
                    strategy={verticalListSortingStrategy}
                  >
                    <TableBody>
                      {fields.map((field) => (
                        <SortableRow 
                          key={field.field} 
                          field={field} 
                          itemCount={itemCount}
                          winnerIndex={field.winnerIndex}
                        />
                      ))}
                    </TableBody>
                  </SortableContext>
                </Table>
              </DndContext>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function ReportPage() {
  const [mounted, setMounted] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const results = useCalculatorStore((s) => s.results);
  const removeResult = useCalculatorStore((s) => s.removeResult);

  // For DND management
  const [customFieldOrder, setCustomFieldOrder] = useState<Record<ReportCategory, string[]>>({
    growth: [],
    cost: [],
    net: [],
    general: []
  });

  useEffect(() => setMounted(true), []);

  const allResults = useMemo(
    () => Object.values(results).sort((a, b) => b.timestamp - a.timestamp),
    [results]
  );

  const resultsByType = useMemo(() => {
    const grouped: Partial<Record<CalculatorType, CalculationResult[]>> = {};
    for (const r of allResults) {
      if (!grouped[r.type]) grouped[r.type] = [];
      grouped[r.type]!.push(r);
    }
    return grouped;
  }, [allResults]);

  const selectedItems = useMemo(
    () => selected.map((id) => results[id]).filter(Boolean) as CalculationResult[],
    [selected, results]
  );

  const rawComparison = useMemo(
    () => (selectedItems.length >= 2 ? generateComparison(selectedItems) : null),
    [selectedItems]
  );

  // Apply custom ordering to comparison fields
  const comparison = useMemo(() => {
    if (!rawComparison) return null;
    return {
      ...rawComparison,
      categories: rawComparison.categories.map(cat => {
        const customOrder = customFieldOrder[cat.id];
        if (customOrder.length > 0) {
          const sortedFields = [...cat.fields].sort((a, b) => {
            const indexA = customOrder.indexOf(a.field);
            const indexB = customOrder.indexOf(b.field);
            if (indexA === -1 || indexB === -1) return 0;
            return indexA - indexB;
          });
          return { ...cat, fields: sortedFields };
        }
        return cat;
      })
    };
  }, [rawComparison, customFieldOrder]);

  const handleReorder = (catId: ReportCategory, activeId: string, overId: string) => {
    const cat = rawComparison?.categories.find(c => c.id === catId);
    if (!cat) return;
    
    setCustomFieldOrder(prev => {
      const currentOrder = prev[catId].length > 0 
        ? prev[catId] 
        : cat.fields.map(f => f.field);
      
      const oldIndex = currentOrder.indexOf(activeId);
      const newIndex = currentOrder.indexOf(overId);
      
      return {
        ...prev,
        [catId]: arrayMove(currentOrder, oldIndex, newIndex)
      };
    });
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id].slice(-3)
    );
  };

  if (!mounted) return null;

  return (
    <div className="space-y-10 pb-20 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="h-5 w-5 text-primary animate-pulse" />
            <span className="text-xs font-bold uppercase tracking-widest text-primary/80">Premium Analysis</span>
          </div>
          <h2 className="text-4xl font-extrabold tracking-tight bg-gradient-to-br from-foreground to-foreground/50 bg-clip-text text-transparent">
            비교 리포트
          </h2>
          <p className="mt-2 text-muted-foreground max-w-md">
            다양한 재무 시나리오를 카테고리별로 정밀하게 분석하고 최적의 선택을 찾아보세요.
          </p>
        </div>
      </div>

      {/* 결과 선택 섹션 (Glassy Horizontal Scroll) */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
            대상 시나리오 선택
            <Badge variant="outline" className="text-[10px] font-mono">{selected.length}/3</Badge>
          </h3>
        </div>

        {allResults.length === 0 ? (
          <Card className="border-dashed border-2 bg-transparent">
            <CardContent className="py-12 text-center text-muted-foreground">
              <p>저장된 계산 결과가 없습니다.</p>
              <p className="text-xs mt-1">계산기에서 결과의 '저장' 버튼을 눌러주세요.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-8">
            {(Object.keys(typeLabels) as CalculatorType[])
              .filter((type) => resultsByType[type]?.length)
              .map((type) => (
                <div key={type} className="space-y-3">
                  <p className="text-xs font-bold text-muted-foreground/60 px-1">{typeLabels[type]}</p>
                  <div className="flex overflow-x-auto gap-4 pb-4 snap-x snap-mandatory scrollbar-hide -mx-4 px-4">
                    {resultsByType[type]!.map((r) => (
                      <motion.div
                        key={r.id}
                        whileHover={{ y: -4 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => toggleSelect(r.id)}
                        className={cn(
                          "relative min-w-[220px] max-w-[220px] shrink-0 snap-center cursor-pointer transition-all duration-300 rounded-2xl border-2 p-4 flex flex-col justify-between overflow-hidden",
                          selected.includes(r.id)
                            ? "border-primary bg-primary/10 shadow-lg shadow-primary/5"
                            : "border-border/50 bg-card/50 hover:border-border hover:bg-accent/20"
                        )}
                      >
                        {selected.includes(r.id) && (
                          <div className="absolute top-0 right-0 p-2">
                            <Badge className="rounded-full h-5 w-5 p-0 flex items-center justify-center text-[10px]">
                              {String.fromCharCode(65 + selected.indexOf(r.id))}
                            </Badge>
                          </div>
                        )}
                        <div>
                          <p className="text-sm font-bold line-clamp-2 leading-tight">{r.label}</p>
                        </div>
                        <div className="mt-4 flex items-center justify-between">
                          <span className="text-[10px] text-muted-foreground font-mono">
                            {new Date(r.timestamp).toLocaleDateString()}
                          </span>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 text-muted-foreground hover:text-destructive rounded-full"
                            onClick={(e) => {
                              e.stopPropagation();
                              removeResult(r.id);
                              setSelected((prev) => prev.filter((id) => id !== r.id));
                            }}
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </div>
              ))}
          </div>
        )}
      </section>

      {/* 비교 리포트 섹션 */}
      <AnimatePresence>
        {comparison && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="space-y-6"
          >
            {/* 인사이트 카드 (Animated Gradient Border) */}
            <div className="relative group p-[2px] rounded-2xl overflow-hidden bg-gradient-to-r from-primary/50 via-primary/20 to-primary/50">
              <div className="bg-card dark:bg-slate-950 rounded-[14px] p-6 relative flex flex-col md:flex-row md:items-center gap-6">
                 <div className="flex-1">
                   <h4 className="text-lg font-bold mb-2 flex items-center gap-2">
                     <Sparkles className="h-4 w-4 text-primary" />
                     Smart Insights
                   </h4>
                   <p className="text-foreground/80 leading-relaxed italic">
                     "{comparison.insight}"
                   </p>
                 </div>
                 <div className="flex gap-2">
                   {comparison.items.map((item, i) => (
                     <div key={item.id} className="flex flex-col items-center">
                        <Badge variant="outline" className="mb-1 text-[10px]">시나리오 {String.fromCharCode(65 + i)}</Badge>
                        <div className="text-[10px] text-muted-foreground max-w-[80px] truncate text-center" title={item.label}>{item.label}</div>
                     </div>
                   ))}
                 </div>
              </div>
            </div>

            {/* 비교 테이블 헤더 */}
            <div className="grid grid-cols-[auto_1fr] md:grid-cols-[200px_1fr] gap-4 px-4 sticky top-0 z-20 bg-background/80 backdrop-blur-sm py-4 border-b border-border/50">
               <div className="text-xs font-bold text-muted-foreground uppercase tracking-widest pt-2">지표 항목</div>
               <div className="flex justify-between md:justify-end gap-8 overflow-x-auto scollbar-hide px-2">
                 {comparison.items.map((_, i) => (
                   <div key={i} className="min-w-[100px] text-right">
                     <span className="text-xs font-black text-primary/40 mr-2">{String.fromCharCode(65 + i)}</span>
                     <span className="text-xs font-bold uppercase tracking-tighter">Scenario</span>
                   </div>
                 ))}
               </div>
            </div>

            {/* 카테고리별 섹션 */}
            <div className="space-y-4">
              {comparison.categories.map((cat) => (
                <CategorySection
                  key={cat.id}
                  category={REPORT_CATEGORIES[cat.id]}
                  fields={cat.fields}
                  itemCount={comparison.items.length}
                  onReorder={(activeId, overId) => handleReorder(cat.id, activeId, overId)}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      
      {!comparison && selected.length < 2 && (
        <div className="text-center py-20 bg-accent/20 rounded-3xl border-2 border-dashed border-border/50">
           <div className="flex justify-center mb-4">
             <div className="p-4 rounded-full bg-background shadow-inner">
               <ArrowLeftRight className="h-8 w-8 text-muted-foreground/50" />
             </div>
           </div>
           <p className="text-muted-foreground">비교할 시나리오를 2개 이상 선택해 주세요.</p>
           <p className="text-xs text-muted-foreground/60 mt-1">서로 다른 설정을 가진 시나리오를 비교하면 더 정확한 인사이트를 얻을 수 있습니다.</p>
        </div>
      )}
    </div>
  );
}

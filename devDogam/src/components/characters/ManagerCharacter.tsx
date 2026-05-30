import React, { useEffect, useRef } from "react";
import { motion, useAnimate } from "framer-motion";
import { CHARACTERS } from "@/lib/characters";
import {
  CARPET_STEP_X_PX,
  CARPET_CENTER_X_PX,
  CARPET_Y_PX,
  BOW_DURATION_MS,
  STEP_TO_CARPET_MS,
  CARPET_TO_STAIRS_MS,
  BOW_DOWN_MS,
  BOW_UP_MS,
} from "@/lib/carpetPath";
import CharacterAvatar from "./CharacterAvatar";
import ChatBubble from "@/components/chat/ChatBubble";

interface Props {
  agentName: string;
  isActive?: boolean;
  side?: "left" | "right";
  message?: string;
  style?: React.CSSProperties;
  /**
   * 값이 바뀔 때마다 절 1회 발동.
   * BOW_DURATION_MS(2100ms) 후 idle 자동 복귀.
   */
  bowTrigger?: string;
}

/**
 * 매니저별 카펫 이동 동선 keyframe 객체 배열.
 * useAnimate의 sequence 형식: [target, keyframe, options][] 대신
 * 단일 animate() 호출로 모든 속성을 times 배열로 처리.
 *
 * §7 keyframe 순서: step1(300) + step2(500) + step3(400) + step4(200) + step5(700) = 2100ms
 */
function buildBowKeyframes(side?: "left" | "right") {
  const stepX = side === "right"
    ? `-${CARPET_STEP_X_PX}px`
    : `${CARPET_STEP_X_PX}px`;
  const carpetX = side === "right"
    ? `-${CARPET_CENTER_X_PX}px`
    : `${CARPET_CENTER_X_PX}px`;
  const carpetY = `${CARPET_Y_PX}px`;

  const t0 = 0;
  const t1 = STEP_TO_CARPET_MS / BOW_DURATION_MS;
  const t2 = (STEP_TO_CARPET_MS + CARPET_TO_STAIRS_MS) / BOW_DURATION_MS;
  const t3 = (STEP_TO_CARPET_MS + CARPET_TO_STAIRS_MS + BOW_DOWN_MS) / BOW_DURATION_MS;
  const t4 = (STEP_TO_CARPET_MS + CARPET_TO_STAIRS_MS + BOW_DOWN_MS + BOW_UP_MS) / BOW_DURATION_MS;
  const t5 = 1;

  return {
    x: [0, stepX, carpetX, carpetX, carpetX, 0] as string[],
    y: [0, "0px", carpetY, carpetY, carpetY, "0px"] as string[],
    scaleY: [1, 1, 1, 0.92, 1, 1] as number[],
    rotate: [0, 0, 0, 5, 0, 0] as number[],
    transition: {
      duration: BOW_DURATION_MS / 1000,
      times: [t0, t1, t2, t3, t4, t5] as number[],
      ease: "easeInOut" as const,
    },
  };
}

export default function ManagerCharacter({
  agentName,
  isActive = false,
  side,
  message,
  style,
  bowTrigger,
}: Props) {
  // useAnimate: scope는 motion.div에 붙음. animate()로 1회 절 keyframe 발동.
  const [scope, animate] = useAnimate();

  // 이전 bowTrigger 값 추적 — mount 시 불필요한 절 방지
  const prevTriggerRef = useRef<string | undefined>(undefined);
  // 현재 절 진행 중 여부 — 이전 절이 끝나기 전 새 trigger 온 경우 대기
  const isBowingRef = useRef(false);
  const pendingTriggerRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    // mount 최초 실행 방지: prevTriggerRef가 undefined인 상태에서 bowTrigger가 있으면 기록만 하고 절 X
    if (prevTriggerRef.current === undefined) {
      prevTriggerRef.current = bowTrigger;
      return;
    }
    // 값 변화 없으면 무시
    if (bowTrigger === prevTriggerRef.current || !bowTrigger) return;

    prevTriggerRef.current = bowTrigger;

    async function doBow() {
      if (isBowingRef.current) {
        // 이전 절 진행 중 — 나중 trigger를 pending으로 기록
        pendingTriggerRef.current = bowTrigger;
        return;
      }
      isBowingRef.current = true;
      const keyframes = buildBowKeyframes(side);
      const { transition, ...animProps } = keyframes;
      await animate(scope.current, animProps, transition);
      // idle 복귀
      animate(scope.current, { x: 0, y: "0px", scaleY: 1, rotate: 0 }, { duration: 0 });
      isBowingRef.current = false;

      // pending trigger가 있으면 연속 절
      if (pendingTriggerRef.current) {
        pendingTriggerRef.current = undefined;
        doBow();
      }
    }

    doBow();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bowTrigger]);

  // hooks 호출 완료 후 early return
  const character = CHARACTERS[agentName];
  if (!character || !character.manager) return null;

  return (
    <motion.div
      ref={scope}
      className="relative flex flex-col items-center"
      style={{ zIndex: 10, paddingBottom: "0", ...style }}
    >
      {/* 말풍선 — 머리 위 absolute */}
      {message && (
        <div
          style={{
            position: "absolute",
            bottom: "calc(100% + 8px)",
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 30,
            maxWidth: "140px",
          }}
        >
          <ChatBubble
            agentName={agentName}
            message={message}
            side="center"
          />
        </div>
      )}

      {/* 아바타 + ring */}
      <div
        className="rounded-full"
        style={{
          boxShadow: isActive ? `0 0 0 4px ${character.hex}` : "none",
          transition: "box-shadow 5s ease-out",
        }}
        aria-label={`${character.displayName} ${isActive ? "활성" : "대기"}`}
      >
        <CharacterAvatar agentName={agentName} size="manager" />
      </div>

      {/* 이름 라벨 */}
      <span
        className="text-sm mt-1 whitespace-nowrap"
        style={{ color: "#F4ECD8", fontFamily: "var(--font-serif)" }}
      >
        {character.emoji} {character.displayName}
      </span>
    </motion.div>
  );
}

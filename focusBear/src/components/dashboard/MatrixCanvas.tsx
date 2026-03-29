import { useEffect, useRef } from 'react'

const CHARS = 'アイウエオカキクケコサシスセソ01アBCDEF'

export function MatrixCanvas({ active }: { active: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rafRef = useRef<number>(0)

  useEffect(() => {
    const canvas = canvasRef.current!
    const ctx = canvas.getContext('2d')!
    if (!active) {
      cancelAnimationFrame(rafRef.current)
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      return
    }

    const W = canvas.width
    const H = canvas.height
    const fontSize = 12
    const cols = Math.floor(W / fontSize)
    const drops = Array(cols).fill(1)

    function draw() {
      ctx.fillStyle = 'rgba(15, 23, 42, 0.08)'
      ctx.fillRect(0, 0, W, H)
      ctx.fillStyle = '#00FF41'
      ctx.font = `${fontSize}px "JetBrains Mono", monospace`

      drops.forEach((y, i) => {
        const char = CHARS[Math.floor(Math.random() * CHARS.length)]
        ctx.fillText(char, i * fontSize, y * fontSize)
        if (y * fontSize > H && Math.random() > 0.975) drops[i] = 0
        drops[i]++
      })
      rafRef.current = requestAnimationFrame(draw)
    }

    draw()
    return () => cancelAnimationFrame(rafRef.current)
  }, [active])

  return (
    <canvas
      ref={canvasRef}
      width={220}
      height={150}
      className="rounded-lg border border-green-500/20"
      style={{ background: '#0F172A' }}
    />
  )
}

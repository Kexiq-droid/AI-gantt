import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createNoise3D } from 'simplex-noise'
import { cn } from '../../lib/utils'

/** Teal waves — light theme */
export const BIOPLAN_WAVE_COLORS = [
  '#0f766e',
  '#14b8a6',
  '#2dd4bf',
  '#5eead4',
  '#134e4a',
]

/** Brighter teals on dark bg */
export const BIOPLAN_WAVE_COLORS_DARK = [
  '#2dd4bf',
  '#5eead4',
  '#14b8a6',
  '#99f6e4',
  '#0d9488',
]

type Props = {
  children?: ReactNode
  className?: string
  containerClassName?: string
  colors?: string[]
  waveWidth?: number
  backgroundFill?: string
  blur?: number
  speed?: 'slow' | 'fast'
  waveOpacity?: number
}

export function WavyBackground({
  children,
  className,
  containerClassName,
  colors = BIOPLAN_WAVE_COLORS,
  waveWidth = 50,
  backgroundFill = '#f6f3ee',
  blur = 10,
  speed = 'fast',
  waveOpacity = 0.45,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const noiseRef = useRef(createNoise3D())
  const [isSafari, setIsSafari] = useState(false)

  useEffect(() => {
    setIsSafari(
      typeof navigator !== 'undefined' &&
        navigator.userAgent.includes('Safari') &&
        !navigator.userAgent.includes('Chrome'),
    )
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const noise = noiseRef.current
    let w = 0
    let h = 0
    let nt = 0
    let animationId = 0

    const getSpeed = () => (speed === 'fast' ? 0.002 : 0.001)

    const resize = () => {
      const parent = canvas.parentElement
      w = canvas.width = parent?.clientWidth || window.innerWidth
      h = canvas.height = parent?.clientHeight || window.innerHeight
      ctx.filter = `blur(${blur}px)`
    }

    const drawWave = (n: number) => {
      nt += getSpeed()
      for (let i = 0; i < n; i++) {
        ctx.beginPath()
        ctx.lineWidth = waveWidth
        ctx.strokeStyle = colors[i % colors.length]
        for (let x = 0; x < w; x += 5) {
          const y = noise(x / 800, 0.3 * i, nt) * 100
          ctx.lineTo(x, y + h * 0.5)
        }
        ctx.stroke()
        ctx.closePath()
      }
    }

    const render = () => {
      ctx.fillStyle = backgroundFill
      ctx.globalAlpha = waveOpacity
      ctx.fillRect(0, 0, w, h)
      drawWave(5)
      animationId = requestAnimationFrame(render)
    }

    resize()
    render()
    window.addEventListener('resize', resize)

    return () => {
      cancelAnimationFrame(animationId)
      window.removeEventListener('resize', resize)
    }
  }, [backgroundFill, blur, colors, speed, waveOpacity, waveWidth])

  return (
    <div
      className={cn(
        'relative flex h-full min-h-full flex-col items-center justify-center overflow-hidden',
        containerClassName,
      )}
    >
      <canvas
        className="absolute inset-0 z-0 h-full w-full"
        ref={canvasRef}
        style={isSafari ? { filter: `blur(${blur}px)` } : undefined}
        aria-hidden
      />
      <div className={cn('relative z-10', className)}>{children}</div>
    </div>
  )
}

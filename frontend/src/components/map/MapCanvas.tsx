import { useRef, useEffect } from 'react'
import type { OccupancyGrid } from '../../types'

// ─── Rendering constants ──────────────────────────────────────────────────────

/** Pixels per occupancy-grid cell. Canvas size = grid.width/height × CELL_PX. */
const CELL_PX = 4

/** Grid cell colours */
const COLOR_UNKNOWN  = { r: 22,  g: 32,  b: 48  } // dark navy — unexplored
const COLOR_FREE     = { r: 200, g: 213, b: 228 } // light blue-gray — navigable
const COLOR_OCCUPIED = { r: 26,  g: 38,  b: 58  } // dark — walls

// ─── Coordinate helpers ───────────────────────────────────────────────────────

/**
 * Convert a world-frame coordinate (meters) to a canvas pixel position.
 *
 * ROS map convention: Y increases upward.
 * Canvas convention:  Y increases downward.
 * The Y-axis is therefore flipped.
 */
function worldToCanvas(
  wx: number, wy: number,
  grid: OccupancyGrid,
  canvasH: number,
): [cx: number, cy: number] {
  const cx = (wx - grid.origin.x) / grid.resolution * CELL_PX
  const cy = canvasH - (wy - grid.origin.y) / grid.resolution * CELL_PX
  return [cx, cy]
}

// ─── Component ────────────────────────────────────────────────────────────────

interface Props {
  grid: OccupancyGrid
  robot: { x: number; y: number; heading: number } // heading: radians, ROS convention
  goal:  { x: number; y: number } | null
  path:  { x: number; y: number }[]
  traveledPath?: { x: number; y: number }[]
  isGoalReached?: boolean
}

export function MapCanvas({ grid, robot, goal, path, traveledPath, isGoalReached }: Props) {
  const canvasRef    = useRef<HTMLCanvasElement>(null)
  /** Cached ImageData for the static grid — recomputed only when grid reference changes. */
  const gridImgRef   = useRef<ImageData | null>(null)
  const lastGridRef  = useRef<OccupancyGrid | null>(null)

  const CANVAS_W = grid.width  * CELL_PX
  const CANVAS_H = grid.height * CELL_PX

  // ── Precompute grid ImageData (only when grid object changes) ──
  useEffect(() => {
    if (lastGridRef.current === grid && gridImgRef.current !== null) return

    const imgData = new ImageData(CANVAS_W, CANVAS_H)
    const buf = imgData.data

    for (let gy = 0; gy < grid.height; gy++) {
      const gyFlipped = grid.height - 1 - gy  // flip Y for canvas
      const cellVal   = grid.data              // Int8Array

      for (let gx = 0; gx < grid.width; gx++) {
        const v = cellVal[gy * grid.width + gx]
        const { r, g, b } = v === 0 ? COLOR_FREE : v > 0 ? COLOR_OCCUPIED : COLOR_UNKNOWN

        // Fill CELL_PX × CELL_PX pixels
        for (let py = 0; py < CELL_PX; py++) {
          for (let px = 0; px < CELL_PX; px++) {
            const idx = ((gyFlipped * CELL_PX + py) * CANVAS_W + gx * CELL_PX + px) * 4
            buf[idx]     = r
            buf[idx + 1] = g
            buf[idx + 2] = b
            buf[idx + 3] = 255
          }
        }
      }
    }

    gridImgRef.current  = imgData
    lastGridRef.current = grid
  }, [grid, CANVAS_W, CANVAS_H])

  // ── Render frame (robot + goal + path overlay on cached grid) ──
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx || !gridImgRef.current) return

    // 1. Blit cached grid
    ctx.putImageData(gridImgRef.current, 0, 0)

    const H = canvas.height

    // 2. Planned path — dashed faint cyan line
    if (path.length > 1) {
      ctx.save()
      ctx.beginPath()
      ctx.strokeStyle = '#38bdf8'
      ctx.lineWidth   = 1.5
      ctx.setLineDash([4, 4])
      ctx.globalAlpha = 0.45

      const [sx, sy] = worldToCanvas(path[0].x, path[0].y, grid, H)
      ctx.moveTo(sx, sy)
      for (let i = 1; i < path.length; i++) {
        const [px, py] = worldToCanvas(path[i].x, path[i].y, grid, H)
        ctx.lineTo(px, py)
      }
      ctx.stroke()
      ctx.restore()
    }

    // 3. Traveled trajectory path — solid cyan line with glow
    if (traveledPath && traveledPath.length > 1) {
      ctx.save()
      ctx.beginPath()
      ctx.strokeStyle = '#06b6d4'
      ctx.lineWidth   = 2.5
      ctx.globalAlpha = 0.9

      const [sx, sy] = worldToCanvas(traveledPath[0].x, traveledPath[0].y, grid, H)
      ctx.moveTo(sx, sy)
      for (let i = 1; i < traveledPath.length; i++) {
        const [px, py] = worldToCanvas(traveledPath[i].x, traveledPath[i].y, grid, H)
        ctx.lineTo(px, py)
      }
      ctx.stroke()
      ctx.restore()
    }

    // 4. Goal marker — yellow diamond + label
    if (goal) {
      const [gx, gy] = worldToCanvas(goal.x, goal.y, grid, H)
      const s = 7  // half-size of diamond

      ctx.save()
      ctx.globalAlpha = 0.95

      // Filled diamond
      ctx.beginPath()
      ctx.moveTo(gx,     gy - s)
      ctx.lineTo(gx + s, gy    )
      ctx.lineTo(gx,     gy + s)
      ctx.lineTo(gx - s, gy    )
      ctx.closePath()
      ctx.fillStyle   = isGoalReached ? '#4ade80' : '#facc15'
      ctx.fill()
      ctx.strokeStyle = '#0b1120'
      ctx.lineWidth   = 1
      ctx.stroke()

      // Outer ring
      ctx.beginPath()
      ctx.arc(gx, gy, s * 2, 0, Math.PI * 2)
      ctx.strokeStyle = isGoalReached ? '#4ade80' : '#facc15'
      ctx.lineWidth   = 1
      ctx.globalAlpha = isGoalReached ? 0.8 : 0.4
      ctx.stroke()

      // Label
      ctx.globalAlpha = 0.9
      ctx.fillStyle   = isGoalReached ? '#4ade80' : '#facc15'
      ctx.font        = 'bold 9px monospace'
      ctx.fillText(isGoalReached ? 'REACHED' : 'GOAL', gx + s * 2 + 3, gy + 3)

      ctx.restore()
    }

    // 4. Robot marker — cyan circle + heading arrow
    {
      const [rx, ry] = worldToCanvas(robot.x, robot.y, grid, H)
      const radius   = 7

      // Heading in canvas coordinates:
      //   ROS heading 0 = +X (right on canvas)
      //   ROS heading π/2 = +Y (up in ROS = down on canvas → negate)
      const canvasAngle = -robot.heading

      ctx.save()

      // Outer glow ring
      ctx.beginPath()
      ctx.arc(rx, ry, radius * 2.2, 0, Math.PI * 2)
      ctx.strokeStyle = '#06b6d4'
      ctx.lineWidth   = 1
      ctx.globalAlpha = 0.2
      ctx.stroke()

      ctx.globalAlpha = 1

      // Heading arrow
      const arrowLen = radius * 2.5
      ctx.beginPath()
      ctx.moveTo(rx, ry)
      ctx.lineTo(
        rx + Math.cos(canvasAngle) * arrowLen,
        ry + Math.sin(canvasAngle) * arrowLen,
      )
      ctx.strokeStyle = '#22d3ee'
      ctx.lineWidth   = 2.5
      ctx.lineCap     = 'round'
      ctx.stroke()

      // Body fill
      ctx.beginPath()
      ctx.arc(rx, ry, radius, 0, Math.PI * 2)
      ctx.fillStyle = '#06b6d4'
      ctx.fill()

      // Outline
      ctx.strokeStyle = '#0b1120'
      ctx.lineWidth   = 1.5
      ctx.stroke()

      // Centre dot
      ctx.beginPath()
      ctx.arc(rx, ry, 2.5, 0, Math.PI * 2)
      ctx.fillStyle = '#fff'
      ctx.fill()

      ctx.restore()
    }
  }, [grid, robot, goal, path, traveledPath, isGoalReached])

  return (
    <canvas
      ref={canvasRef}
      width={CANVAS_W}
      height={CANVAS_H}
      style={{
        maxWidth:        '100%',
        maxHeight:       '100%',
        imageRendering:  'pixelated',
      }}
    />
  )
}

// Studio backdrop like Tesla's in-car UI: a gradient wall behind the robot and a glossy floor
// that mirrors it, fading out into the background with distance. Two palettes: dark (charcoal,
// the default) and light (pale grey); setTheme() repaints in place.

import * as THREE from 'three'
import { Reflector } from 'three/addons/objects/Reflector.js'

export type Theme = 'dark' | 'light'

type Palette = { wallTop: string; horizon: string; floor: string }
const PALETTES: Record<Theme, Palette> = {
  dark: { wallTop: '#4a4b4e', horizon: '#2a2b2d', floor: '#0e0f10' }, // fog matches the horizon
  light: { wallTop: '#f4f5f6', horizon: '#dcdee1', floor: '#b9bcc0' },
}
const FLOOR_RADIUS = 10 // metres

export class Backdrop {
  readonly group = new THREE.Group()
  readonly background: THREE.CanvasTexture
  readonly fog: THREE.Fog
  private reflector: Reflector
  private fade: THREE.CanvasTexture

  constructor(theme: Theme = 'dark') {
    this.background = canvasTexture(2, 256)
    this.fade = canvasTexture(512, 512)
    this.fog = new THREE.Fog(PALETTES[theme].horizon, 6, 16) // starts past the robot's resting distance

    // A mirror at floor level, then a disc just above it: see-through in the middle
    // (the reflection shows, dimmed) and solid further out.
    this.reflector = new Reflector(new THREE.CircleGeometry(FLOOR_RADIUS, 64), {
      textureWidth: 1024,
      textureHeight: 1024,
      color: 0x888888,
    })
    this.reflector.rotation.x = -Math.PI / 2
    const dimmer = new THREE.Mesh(
      new THREE.CircleGeometry(FLOOR_RADIUS, 64),
      new THREE.MeshBasicMaterial({ map: this.fade, transparent: true, toneMapped: false }),
    )
    dimmer.rotation.x = -Math.PI / 2
    dimmer.position.y = 0.001
    this.group.add(this.reflector, dimmer)

    this.setTheme(theme)
  }

  setTheme(theme: Theme) {
    const p = PALETTES[theme]
    // Screen-space wall: lighter at the top, darkest at the bottom.
    paint(this.background, (ctx, w, h) => {
      const g = ctx.createLinearGradient(0, 0, 0, h)
      g.addColorStop(0, p.wallTop)
      g.addColorStop(0.5, p.horizon)
      g.addColorStop(1, p.floor)
      ctx.fillStyle = g
      ctx.fillRect(0, 0, w, h)
    })
    const [r, g, b] = new THREE.Color(p.floor).toArray().map((c) => Math.round(c * 255))
    paint(this.fade, (ctx, w, h) => {
      const grad = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2)
      grad.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.55)`)
      grad.addColorStop(0.2, `rgba(${r}, ${g}, ${b}, 0.9)`)
      grad.addColorStop(0.35, `rgba(${r}, ${g}, ${b}, 1)`)
      ctx.fillStyle = grad
      ctx.fillRect(0, 0, w, h)
    })
    this.fog.color.set(p.horizon)
  }

  dispose() {
    this.reflector.dispose() // its render target; scene.traverse frees the meshes
    this.background.dispose()
    this.fade.dispose()
  }
}

function canvasTexture(width: number, height: number): THREE.CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  return texture
}

function paint(texture: THREE.CanvasTexture, draw: (ctx: CanvasRenderingContext2D, w: number, h: number) => void) {
  const canvas = texture.image as HTMLCanvasElement
  const ctx = canvas.getContext('2d')!
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  draw(ctx, canvas.width, canvas.height)
  texture.needsUpdate = true
}

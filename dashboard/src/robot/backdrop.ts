// Studio backdrop like Tesla's in-car UI: a charcoal gradient behind the robot and a dark
// glossy floor that mirrors it, fading out into the background with distance.

import * as THREE from 'three'
import { Reflector } from 'three/addons/objects/Reflector.js'

const WALL_TOP = '#4a4b4e'
const HORIZON = '#2a2b2d' // fog matches this so the far floor melts into the wall
const FLOOR = '#0e0f10'
const FLOOR_RADIUS = 10 // metres

function canvasTexture(width: number, height: number, paint: (ctx: CanvasRenderingContext2D) => void) {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  paint(canvas.getContext('2d')!)
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  return texture
}

export class Backdrop {
  readonly group = new THREE.Group()
  readonly background: THREE.Texture
  readonly fog = new THREE.Fog(HORIZON, 6, 16) // starts past the robot's resting distance
  private reflector: Reflector
  private fade: THREE.Texture

  constructor() {
    // Screen-space wall: lighter at the top, near black at the bottom.
    this.background = canvasTexture(2, 256, (ctx) => {
      const g = ctx.createLinearGradient(0, 0, 0, 256)
      g.addColorStop(0, WALL_TOP)
      g.addColorStop(0.5, HORIZON)
      g.addColorStop(1, FLOOR)
      ctx.fillStyle = g
      ctx.fillRect(0, 0, 2, 256)
    })

    // A mirror at floor level, then a dark disc just above it: see-through in the middle
    // (the reflection shows, dimmed) and solid further out.
    this.reflector = new Reflector(new THREE.CircleGeometry(FLOOR_RADIUS, 64), {
      textureWidth: 1024,
      textureHeight: 1024,
      color: 0x888888,
    })
    this.reflector.rotation.x = -Math.PI / 2

    this.fade = canvasTexture(512, 512, (ctx) => {
      const g = ctx.createRadialGradient(256, 256, 0, 256, 256, 256)
      g.addColorStop(0, 'rgba(14, 15, 16, 0.55)')
      g.addColorStop(0.2, 'rgba(14, 15, 16, 0.9)')
      g.addColorStop(0.35, 'rgba(14, 15, 16, 1)')
      ctx.fillStyle = g
      ctx.fillRect(0, 0, 512, 512)
    })
    const dimmer = new THREE.Mesh(
      new THREE.CircleGeometry(FLOOR_RADIUS, 64),
      new THREE.MeshBasicMaterial({ map: this.fade, transparent: true, toneMapped: false }),
    )
    dimmer.rotation.x = -Math.PI / 2
    dimmer.position.y = 0.001

    this.group.add(this.reflector, dimmer)
  }

  dispose() {
    this.reflector.dispose() // its render target; scene.traverse frees the meshes
    this.background.dispose()
    this.fade.dispose()
  }
}

// The 3D view: a three.js scene holding the H2 model loaded from its URDF.
// Plain class, not React: it owns the renderer, camera and animation loop.

import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'
import { CSS2DRenderer, type CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js'
import URDFLoader, { type URDFRobot, type URDFVisual } from 'urdf-loader'
import type { Joint } from '../bridge/protocol'
import { Backdrop } from './backdrop'
import { blackenEyes } from './head'
import { SAMPLE_MARKERS, createMarker } from './markers'

const URDF_URL = '/renders/h2_description/H2.urdf'

// The URDF only has flat greys ("white" 0.7 shell, "dark" 0.4 joints); swap in materials matched
// to a photo of the real H2: satin silver shell, matte black actuators, hands and feet.
const SHELL = new THREE.MeshStandardMaterial({ color: 0xb0b3b7, roughness: 0.32, metalness: 0.75 })
const JOINT = new THREE.MeshStandardMaterial({ color: 0x1c1d20, roughness: 0.6, metalness: 0.2 })
const BLACK_LINKS = new Set(['waist_yaw_link', 'waist_roll_link']) // "white" in the URDF, black on the robot

// Two framings, one per metrics-panel state. Panel open: the robot faces the camera, slid left
// into the free 40% of the screen. Panel closed: a 45° side view from the robot's left, close
// enough that the knees sit just below the frame. The camera flies in to the first framing once
// the model has loaded, and glides between them when the panel toggles.
const START_DISTANCE = 10
const INTRO_MS = 2200
const REFRAME_MS = 700

// direction: from the target out to the camera (three.js axes: +X robot's front, -Z robot's left).
// shiftX: how far the picture slides left, as a fraction of the view's width.
type Framing = { targetY: number; distance: number; shiftX: number; direction: THREE.Vector3 }
const FRAMING: Record<'panelOpen' | 'panelClosed', Framing> = {
  panelOpen: {
    targetY: 0.85,
    distance: 2.9,
    shiftX: 0.3,
    direction: new THREE.Vector3(1, 0.1, -0.12).normalize(), // ~7° to the robot's left
  },
  // Frame spans ~0.65 m (just above the knees, 0.57 m) to ~1.9 m (head top 1.82 m).
  panelClosed: {
    targetY: 1.27,
    distance: 1.75,
    shiftX: 0,
    direction: new THREE.Vector3(1, 0.1, -1).normalize(), // 45° to the robot's left
  },
}

type CameraMove = {
  fromTarget: THREE.Vector3
  toTarget: THREE.Vector3
  fromDistance: number
  toDistance: number
  fromShift: number
  toShift: number
  fromDirection: THREE.Vector3
  toDirection: THREE.Vector3
  start: number
  ms: number
}

export type SceneStatus = { state: 'loading' } | { state: 'ready' } | { state: 'error'; message: string }

/** Bridge joint name -> URDF joint name: "L_hip_roll" -> "left_hip_roll_joint", "waist_yaw" -> "waist_yaw_joint". */
export function urdfJointName(bridgeName: string): string {
  return bridgeName.replace(/^L_/, 'left_').replace(/^R_/, 'right_') + '_joint'
}

export class RobotScene {
  robot: URDFRobot | null = null

  private renderer: THREE.WebGLRenderer
  private labelRenderer = new CSS2DRenderer() // HTML markers drawn over the canvas
  private markers: CSS2DObject[] = []
  private projected = new THREE.Vector3()
  private scene = new THREE.Scene()
  private backdrop = new Backdrop()
  private camera = new THREE.PerspectiveCamera(40, 1, 0.05, 50)
  private controls: OrbitControls
  private resizeObserver: ResizeObserver
  private frame = 0
  private framing = FRAMING.panelClosed
  private move: CameraMove | null = null
  private shiftX = 0
  private direction = new THREE.Vector3() // scratch for camera moves
  private disposed = false
  private container: HTMLElement
  private pose: Joint[] | null = null // newest pose, applied once the model has loaded
  private unknownJoints = new Set<string>() // bridge names with no URDF joint, warned about once

  constructor(container: HTMLElement, onStatus: (status: SceneStatus) => void) {
    this.container = container
    this.renderer = new THREE.WebGLRenderer({ antialias: true })
    this.renderer.setPixelRatio(window.devicePixelRatio)
    container.appendChild(this.renderer.domElement)
    this.labelRenderer.domElement.className = 'marker-layer'
    container.appendChild(this.labelRenderer.domElement)

    this.renderer.toneMapping = THREE.ACESFilmicToneMapping
    this.scene.background = this.backdrop.background
    this.scene.fog = this.backdrop.fog
    this.scene.add(this.backdrop.group)
    // Soft studio reflections so the materials read as plastic and metal, not flat grey.
    const pmrem = new THREE.PMREMGenerator(this.renderer)
    this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture
    pmrem.dispose()
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x8e8e8e, 0.6))
    const sun = new THREE.DirectionalLight(0xffffff, 1.5)
    sun.position.set(3, 5, 2)
    this.scene.add(sun)

    this.controls = new OrbitControls(this.camera, this.renderer.domElement)
    this.placeForIntro()

    this.resizeObserver = new ResizeObserver(() => this.resize())
    this.resizeObserver.observe(container)
    this.resize()

    this.loadRobot(onStatus)
    this.animate()
  }

  private loadRobot(onStatus: (status: SceneStatus) => void) {
    onStatus({ state: 'loading' })
    const loader = new URDFLoader()
    let robot: URDFRobot | null = null
    let pendingMeshes = 0
    let failed = false

    // Count meshes ourselves: LoadingManager.onLoad can fire before they arrive
    // (three.js shares in-flight downloads between loaders without telling the
    // second manager, which happens when StrictMode mounts the view twice).
    const finishIfLoaded = () => {
      if (this.disposed || failed || !robot || pendingMeshes > 0) return
      this.applyMaterials(robot)
      blackenEyes(robot, SHELL)
      robot.rotation.x = -Math.PI / 2 // URDF is Z-up, three.js is Y-up
      this.scene.add(robot)
      robot.updateMatrixWorld(true)
      robot.position.y -= new THREE.Box3().setFromObject(robot).min.y // feet on the floor
      this.robot = robot
      if (this.pose) this.setPose(this.pose) // data arrived before the meshes
      this.flyTo(this.framing, INTRO_MS)
      this.addMarkers(robot)
      onStatus({ state: 'ready' })
    }

    loader.loadMeshCb = (path, manager, material, done) => {
      pendingMeshes++
      loader.defaultMeshLoader(path, manager, material, (mesh, err) => {
        done(mesh, err)
        pendingMeshes--
        if (err) {
          failed = true
          onStatus({ state: 'error', message: `couldn't load ${path}` })
        }
        finishIfLoaded()
      })
    }

    loader.load(
      URDF_URL,
      (loaded) => {
        robot = loaded // every mesh load has been started by now
        finishIfLoaded()
      },
      undefined,
      (err) => onStatus({ state: 'error', message: `couldn't load ${URDF_URL}: ${String(err)}` }),
    )
  }

  private applyMaterials(robot: URDFRobot) {
    for (const [name, link] of Object.entries(robot.links)) {
      // Only this link's own visuals: its child links are handled by their own loop turn.
      for (const visual of link.children.filter((c) => (c as URDFVisual).isURDFVisual)) {
        visual.traverse((obj) => {
          if (!(obj instanceof THREE.Mesh)) return
          const old = obj.material as THREE.MeshPhongMaterial
          obj.material = old.color.r < 0.5 || BLACK_LINKS.has(name) ? JOINT : SHELL
          old.dispose()
        })
      }
    }
  }

  private addMarkers(robot: URDFRobot) {
    for (const spec of SAMPLE_MARKERS) {
      const link = robot.links[spec.link]
      if (!link) continue // link renamed in the URDF: skip rather than fail the view
      const marker = createMarker(spec)
      link.add(marker)
      this.markers.push(marker)
    }
  }

  // Point each card away from the robot: left of the orbit target on screen -> card on the left.
  private updateMarkerSides() {
    const centerX = this.projected.copy(this.controls.target).project(this.camera).x
    for (const marker of this.markers) {
      const x = marker.getWorldPosition(this.projected).project(this.camera).x
      marker.element.dataset.side = x < centerX ? 'left' : 'right'
    }
  }

  /**
   * Pose the model from the bridge's joints, matched by name (never by slot). A joint whose q is
   * null (no data, or NaN on the robot) keeps its last angle. Before the model has loaded, the pose
   * is kept and applied when it's ready.
   */
  setPose(joints: Joint[]) {
    this.pose = joints
    const robot = this.robot
    if (!robot) return
    for (const joint of joints) {
      if (joint.q === null) continue
      const name = urdfJointName(joint.name)
      if (!robot.joints[name]) {
        if (!this.unknownJoints.has(name)) console.warn(`no URDF joint ${name} for bridge joint ${joint.name}`)
        this.unknownJoints.add(name)
        continue
      }
      robot.setJointValue(name, joint.q)
    }
  }

  /** Reframe the robot for the metrics panel, and hide the markers while it's open. */
  setPanelOpen(open: boolean) {
    this.framing = open ? FRAMING.panelOpen : FRAMING.panelClosed
    this.labelRenderer.domElement.classList.toggle('hidden', open)
    if (this.robot) this.flyTo(this.framing, REFRAME_MS)
    else this.placeForIntro() // not loaded yet: start the fly-in on this framing's line
  }

  private placeForIntro() {
    this.controls.target.set(0, this.framing.targetY, 0)
    this.camera.position.copy(this.controls.target).addScaledVector(this.framing.direction, START_DISTANCE)
    this.controls.enabled = false // until the intro finishes
    this.controls.update()
  }

  private flyTo(framing: Framing, ms: number) {
    const offset = this.camera.position.clone().sub(this.controls.target)
    const fromDistance = offset.length()
    this.move = {
      fromTarget: this.controls.target.clone(),
      toTarget: new THREE.Vector3(0, framing.targetY, 0),
      fromDistance,
      toDistance: framing.distance,
      fromShift: this.shiftX,
      toShift: framing.shiftX,
      fromDirection: offset.normalize(),
      toDirection: framing.direction,
      start: performance.now(),
      ms,
    }
    this.controls.enabled = false // no dragging against the animation
  }

  private updateMove() {
    const move = this.move
    if (!move) return
    const t = Math.min(1, (performance.now() - move.start) / move.ms)
    const eased = 1 - (1 - t) ** 3 // fast start, gentle stop
    this.controls.target.lerpVectors(move.fromTarget, move.toTarget, eased)
    const distance = move.fromDistance + (move.toDistance - move.fromDistance) * eased
    const direction = this.direction.lerpVectors(move.fromDirection, move.toDirection, eased).normalize()
    this.camera.position.copy(this.controls.target).addScaledVector(direction, distance)
    this.shiftX = move.fromShift + (move.toShift - move.fromShift) * eased
    this.applyShift()
    if (t === 1) {
      this.move = null
      this.controls.enabled = true
    }
  }

  private resize() {
    const { clientWidth: w, clientHeight: h } = this.container
    if (w === 0 || h === 0) return
    this.renderer.setSize(w, h)
    this.labelRenderer.setSize(w, h)
    this.camera.aspect = w / h
    this.applyShift() // also updates the projection
  }

  /** Slide the rendered picture left without moving the camera, so orbiting still circles the robot. */
  private applyShift() {
    const { clientWidth: w, clientHeight: h } = this.container
    if (this.shiftX === 0 || w === 0 || h === 0) this.camera.clearViewOffset()
    else this.camera.setViewOffset(w, h, this.shiftX * w, 0, w, h)
  }

  private animate = () => {
    if (this.disposed) return
    this.frame = requestAnimationFrame(this.animate)
    this.updateMove()
    this.controls.update()
    this.renderer.render(this.scene, this.camera)
    this.updateMarkerSides()
    this.labelRenderer.render(this.scene, this.camera)
  }

  /** Stop the loop and free GPU memory. Safe to call twice. */
  dispose() {
    if (this.disposed) return
    this.disposed = true
    cancelAnimationFrame(this.frame)
    this.resizeObserver.disconnect()
    this.controls.dispose()
    this.scene.traverse((obj) => {
      if (obj instanceof THREE.Mesh) {
        obj.geometry.dispose()
        const materials = Array.isArray(obj.material) ? obj.material : [obj.material]
        materials.forEach((m) => m.dispose())
      }
    })
    this.scene.environment?.dispose()
    this.backdrop.dispose()
    this.renderer.dispose()
    this.renderer.domElement.remove()
    this.labelRenderer.domElement.remove()
  }
}

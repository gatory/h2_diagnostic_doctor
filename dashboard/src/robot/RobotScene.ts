// The 3D view: a three.js scene holding the H2 model loaded from its URDF.
// Plain class, not React: it owns the renderer, camera and animation loop.

import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'
import { CSS2DRenderer, type CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js'
import URDFLoader, { type URDFRobot, type URDFVisual } from 'urdf-loader'
import { SAMPLE_MARKERS, createMarker } from './markers'

const URDF_URL = '/renders/h2_description/H2.urdf'

// The URDF only has flat greys ("white" 0.7 shell, "dark" 0.4 joints); swap in materials matched
// to a photo of the real H2: satin silver shell, matte black actuators, hands and feet.
const SHELL = new THREE.MeshStandardMaterial({ color: 0xb0b3b7, roughness: 0.32, metalness: 0.75 })
const JOINT = new THREE.MeshStandardMaterial({ color: 0x1c1d20, roughness: 0.6, metalness: 0.2 })
const BLACK_LINKS = new Set(['waist_yaw_link', 'waist_roll_link']) // "white" in the URDF, black on the robot

export type SceneStatus = { state: 'loading' } | { state: 'ready' } | { state: 'error'; message: string }

export class RobotScene {
  robot: URDFRobot | null = null

  private renderer: THREE.WebGLRenderer
  private labelRenderer = new CSS2DRenderer() // HTML markers drawn over the canvas
  private markers: CSS2DObject[] = []
  private projected = new THREE.Vector3()
  private scene = new THREE.Scene()
  private camera = new THREE.PerspectiveCamera(40, 1, 0.05, 50)
  private controls: OrbitControls
  private resizeObserver: ResizeObserver
  private frame = 0
  private disposed = false
  private container: HTMLElement

  constructor(container: HTMLElement, onStatus: (status: SceneStatus) => void) {
    this.container = container
    this.renderer = new THREE.WebGLRenderer({ antialias: true })
    this.renderer.setPixelRatio(window.devicePixelRatio)
    container.appendChild(this.renderer.domElement)
    this.labelRenderer.domElement.className = 'marker-layer'
    container.appendChild(this.labelRenderer.domElement)

    this.renderer.toneMapping = THREE.ACESFilmicToneMapping
    this.scene.background = new THREE.Color(0xf4f4f4) // surface-soft
    // Soft studio reflections so the materials read as plastic and metal, not flat grey.
    const pmrem = new THREE.PMREMGenerator(this.renderer)
    this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture
    pmrem.dispose()
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x8e8e8e, 0.6))
    const sun = new THREE.DirectionalLight(0xffffff, 1.5)
    sun.position.set(3, 5, 2)
    this.scene.add(sun)
    this.scene.add(new THREE.GridHelper(4, 20, 0xd0d1d2, 0xeeeeee)) // 20 cm squares, floor at y = 0

    // Three.js is Y-up; we look at the robot's front (URDF +X) from slightly to its left.
    this.camera.position.set(2.6, 1.3, 1.2)
    this.controls = new OrbitControls(this.camera, this.renderer.domElement)
    this.controls.target.set(0, 0.9, 0)
    this.controls.update()

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
      robot.rotation.x = -Math.PI / 2 // URDF is Z-up, three.js is Y-up
      this.scene.add(robot)
      robot.updateMatrixWorld(true)
      robot.position.y -= new THREE.Box3().setFromObject(robot).min.y // feet on the floor
      this.robot = robot
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

  private resize() {
    const { clientWidth: w, clientHeight: h } = this.container
    if (w === 0 || h === 0) return
    this.renderer.setSize(w, h)
    this.labelRenderer.setSize(w, h)
    this.camera.aspect = w / h
    this.camera.updateProjectionMatrix()
  }

  private animate = () => {
    if (this.disposed) return
    this.frame = requestAnimationFrame(this.animate)
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
    this.renderer.dispose()
    this.renderer.domElement.remove()
    this.labelRenderer.domElement.remove()
  }
}

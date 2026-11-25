// The 3D view: a three.js scene holding the H2 model loaded from its URDF.
// Plain class, not React: it owns the renderer, camera and animation loop.

import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import URDFLoader, { type URDFRobot } from 'urdf-loader'

const URDF_URL = '/renders/h2_description/H2.urdf'

export type SceneStatus = { state: 'loading' } | { state: 'ready' } | { state: 'error'; message: string }

export class RobotScene {
  robot: URDFRobot | null = null

  private renderer: THREE.WebGLRenderer
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

    this.scene.background = new THREE.Color(0x15171a)
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 2.0))
    const sun = new THREE.DirectionalLight(0xffffff, 2.0)
    sun.position.set(3, 5, 2)
    this.scene.add(sun)
    this.scene.add(new THREE.GridHelper(4, 20, 0x555555, 0x2a2a2a)) // 20 cm squares, floor at y = 0

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
      robot.rotation.x = -Math.PI / 2 // URDF is Z-up, three.js is Y-up
      this.scene.add(robot)
      robot.updateMatrixWorld(true)
      robot.position.y -= new THREE.Box3().setFromObject(robot).min.y // feet on the floor
      this.robot = robot
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

  private resize() {
    const { clientWidth: w, clientHeight: h } = this.container
    if (w === 0 || h === 0) return
    this.renderer.setSize(w, h)
    this.camera.aspect = w / h
    this.camera.updateProjectionMatrix()
  }

  private animate = () => {
    if (this.disposed) return
    this.frame = requestAnimationFrame(this.animate)
    this.controls.update()
    this.renderer.render(this.scene, this.camera)
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
    this.renderer.dispose()
    this.renderer.domElement.remove()
  }
}

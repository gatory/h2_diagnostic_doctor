// Black eyes on the URDF head mesh, to match the real H2's dark lenses. The STL is one piece,
// so the iris triangles are picked by position: within EYE_RADIUS of an eye centre seen from
// the front, on the face side (head_yaw_link frame, URDF axes: +X forward, +Y left, +Z up).

import * as THREE from 'three'
import type { URDFRobot, URDFVisual } from 'urdf-loader'

const HEAD_LINK = 'head_yaw_link'
const EYES = [new THREE.Vector2(-0.031, 0.01), new THREE.Vector2(0.031, 0.01)] // (y, z), metres
const EYE_RADIUS = 0.007
const FACE_MIN_X = 0.05 // skips the back of the head, which shares the same (y, z)
const LENS = new THREE.MeshStandardMaterial({ color: 0x0b0c0e, roughness: 0.15, metalness: 0.3 })

function isEyeTriangle(pos: THREE.BufferAttribute, tri: number): boolean {
  const yz = new THREE.Vector2()
  for (let k = 0; k < 3; k++) {
    const i = tri * 3 + k
    if (pos.getX(i) < FACE_MIN_X) return false
    yz.set(pos.getY(i), pos.getZ(i))
    if (!EYES.some((eye) => eye.distanceTo(yz) < EYE_RADIUS)) return false
  }
  return true
}

/** Reorder the head's triangles (rest first, eyes last) and give the eyes their own material. */
export function blackenEyes(robot: URDFRobot, shell: THREE.Material) {
  const link = robot.links[HEAD_LINK]
  const visual = link?.children.find((c) => (c as URDFVisual).isURDFVisual)
  const mesh = visual?.children.find((c): c is THREE.Mesh => c instanceof THREE.Mesh)
  if (!mesh) return

  const geometry = mesh.geometry
  const pos = geometry.getAttribute('position') as THREE.BufferAttribute
  const triangles = pos.count / 3 // STLLoader geometry is non-indexed: 3 vertices per triangle
  const order = [...Array(triangles).keys()]
  const eye = order.map((t) => isEyeTriangle(pos, t))
  order.sort((a, b) => Number(eye[a]) - Number(eye[b]))

  for (const name of Object.keys(geometry.attributes)) {
    const attr = geometry.getAttribute(name) as THREE.BufferAttribute
    const src = attr.array
    const per = attr.itemSize * 3
    const dst = new (src.constructor as Float32ArrayConstructor)(src.length)
    order.forEach((t, newT) => dst.set(src.subarray(t * per, (t + 1) * per), newT * per))
    geometry.setAttribute(name, new THREE.BufferAttribute(dst, attr.itemSize))
  }

  const eyeVertices = eye.filter(Boolean).length * 3
  geometry.clearGroups()
  geometry.addGroup(0, pos.count - eyeVertices, 0)
  geometry.addGroup(pos.count - eyeVertices, eyeVertices, 1)
  mesh.material = [shell, LENS]
}

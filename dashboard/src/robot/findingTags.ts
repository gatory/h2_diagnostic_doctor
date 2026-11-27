// Tags pinned to the robot for checkup's findings: a dot on the joint, a leader line and a
// card ("Warning · L_knee", then checkup's own message). Only shows what checkup decided.
// Styled with Tailwind classes; only the left/right placement is plain CSS (index.css).

import type * as THREE from 'three'
import { CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js'
import type { URDFRobot } from 'urdf-loader'
import type { Finding } from '../bridge/protocol'
import { STATUS_EDGE, STATUS_FILL } from '../ui/styles'
import { urdfJointName } from './jointNames'

/** At most this many tags on the body (worst first); the banner's list has the rest. */
export const MAX_TAGS = 3

const STATUS_WORD: Record<string, string> = { warn: 'Warning', fail: 'Fail' }

/**
 * Where on the model a finding belongs, or null if it has no place on the body (battery, topics).
 * Subjects come from checkup's rules: body joints by bridge name ("L_knee"), hand motors
 * ("left:index_knuckle_bend"), hands ("left hand"), IMU agreement ("IMU roll": the waist/torso).
 */
export function findingAnchor(subject: string, robot: URDFRobot): THREE.Object3D | null {
  const joint = robot.joints[urdfJointName(subject)]
  if (joint) return joint
  const hand = /^(left|right)[: ]/.exec(subject)
  if (hand) return robot.links[`${hand[1]}_hand_link`] ?? null
  if (subject.startsWith('IMU ')) return robot.links['torso_link'] ?? null
  return null
}

/** Which side of the robot a subject is on, to pick the camera's side when focusing it. */
export function subjectSide(subject: string): 'left' | 'right' | 'centre' {
  if (/^(L_|left)/.test(subject)) return 'left'
  if (/^(R_|right)/.test(subject)) return 'right'
  return 'centre'
}

/** A tag for one finding; `onClick(subject)` when its card is clicked. */
export function createTag(finding: Finding, onClick: (subject: string) => void): CSS2DObject {
  // The card: frosted, a status-coloured bar on its left edge, clickable (the tag layer ignores the mouse).
  const card = div(
    `marker-card pointer-events-auto absolute top-0 max-w-[260px] -translate-y-1/2 cursor-pointer rounded-xs
     border-l-[3px] bg-frost px-3 py-2 backdrop-blur-md ${STATUS_EDGE[finding.status]}`,
  )
  card.append(
    div('text-muted', `${STATUS_WORD[finding.status] ?? finding.status} · ${finding.subject}`),
    div('marker-detail text-ink', finding.message),
  )
  card.addEventListener('click', () => onClick(finding.subject))
  card.title = 'Zoom to this joint (Esc to go back)'
  // A zero-size point on the joint: a dot on it, and a 56px line out to the card (side: index.css).
  const el = div('marker size-0')
  el.dataset.side = 'right' // RobotScene flips it so the card points away from the robot
  el.append(
    div(`absolute -top-1 -left-1 size-2 rounded-full ${STATUS_FILL[finding.status]}`),
    div(`marker-line absolute top-0 h-px w-14 ${STATUS_FILL[finding.status]}`),
    card,
  )
  return new CSS2DObject(el)
}

function div(className: string, text = ''): HTMLDivElement {
  const el = document.createElement('div')
  el.className = className
  el.textContent = text
  return el
}

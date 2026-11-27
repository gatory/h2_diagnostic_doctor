// Metric callouts pinned to robot links. Values are sample data until recordings are wired in.

import { CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js'

export type MarkerSpec = {
  link: string // URDF link the marker's dot sits on
  title: string
  value: string
  detail: string
}

export const SAMPLE_MARKERS: MarkerSpec[] = [
  { link: 'head_pitch_link', title: 'Telemetry', value: '6 / 6 topics', detail: 'lowstate 500 Hz' },
  { link: 'torso_link', title: 'Battery', value: '82 %', detail: '52.1 V · −3.4 A' },
  { link: 'imu_in_pelvis', title: 'IMU', value: 'Level', detail: 'roll 0.4° · pitch −1.2°' },
  { link: 'left_hand_link', title: 'Hands', value: '2 / 2 online', detail: 'dex5' },
  { link: 'left_knee_link', title: 'Motor temp', value: '41 °C max', detail: 'left knee' },
]

function div(className: string, text = ''): HTMLDivElement {
  const el = document.createElement('div')
  el.className = className
  el.textContent = text
  return el
}

/** Zero-size element at the link's origin: a dot, a leader line and a card. */
export function createMarker(spec: MarkerSpec): CSS2DObject {
  const card = div('marker-card')
  card.append(div('marker-title', spec.title), div('marker-value', spec.value), div('marker-detail', spec.detail))
  const el = div('marker')
  el.dataset.side = 'right' // RobotScene flips it so the card points away from the robot
  el.append(div('marker-dot'), div('marker-line'), card)
  return new CSS2DObject(el)
}

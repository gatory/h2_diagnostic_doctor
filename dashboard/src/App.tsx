import { RobotView } from './robot/RobotView'

export default function App() {
  return (
    <div className="app">
      <nav className="top-nav">
        <span className="wordmark">H2 DOCTOR</span>
        <span className="nav-status">Sample data</span>
      </nav>
      <main className="stage">
        <RobotView />
        <div className="hero">
          <h1>H2</h1>
          <p>Unitree H2 · no recording loaded</p>
        </div>
      </main>
    </div>
  )
}

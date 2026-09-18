// FishTankView.swift — SceneKit glass morph tank + agent spheres
// Authors: Ahmad Ali Parr, Jessica L. Williams (SNAPKITTYWEST)
// Apple platforms: macOS 14+ / iOS 17+

import SwiftUI
import SceneKit
import simd

public struct FishTankView: View {
    @ObservedObject var engine: SwarmEngine
    @ObservedObject var state: SwarmState
    @State private var scene = SCNScene()
    @State private var agentNodes: [String: SCNNode] = [:]
    @State private var messageNodes: [SCNNode] = []

    public init(engine: SwarmEngine) {
        self.engine = engine
        self.state = engine.state
    }

    public var body: some View {
        ZStack {
            // SceneKit glass tank
            SceneView(
                scene: scene,
                options: [.allowsCameraControl, .autoenablesDefaultLighting]
            )
            .background(Color(red: 0.02, green: 0.03, blue: 0.07))
            .onAppear { setupScene() }
            .onChange(of: state.agents.map { $0.position }) { _ in updateAgentPositions() }
            .onChange(of: state.glass.waveIntensity) { intensity in
                if intensity > 0.8 { triggerGlassWave() }
            }

            // Overlay — corpus filter sidebar + agent inspector
            HStack(spacing: 0) {
                CorpusTreeSidebar(state: state)
                    .frame(width: 220)
                Spacer()
                if let selected = state.selectedAgent {
                    AgentInspector(agent: selected)
                        .frame(width: 280)
                }
            }

            // Bottom timeline
            VStack {
                Spacer()
                EventTimeline(events: state.events)
                    .frame(height: 80)
            }
        }
        .task { await engine.loadCorpora() }
        .onAppear { engine.start() }
        .onDisappear { engine.stop() }
    }

    // MARK: - Scene Setup

    private func setupScene() {
        scene.background.contents = NSColor(red: 0.02, green: 0.03, blue: 0.07, alpha: 1)

        // Camera
        let cameraNode = SCNNode()
        cameraNode.camera = SCNCamera()
        cameraNode.position = SCNVector3(0, 0, 4)
        scene.rootNode.addChildNode(cameraNode)

        // Glass box
        let box = SCNBox(width: 2, height: 2, length: 2, chamferRadius: 0.08)
        let glassMat = SCNMaterial()
        glassMat.diffuse.contents = NSColor(white: 1, alpha: 0.04)
        glassMat.emission.contents = NSColor(red: 0.4, green: 0.6, blue: 1.0, alpha: 0.08)
        glassMat.metalness.contents = 0.1
        glassMat.roughness.contents = 0.05
        glassMat.transparency = 0.85
        glassMat.isDoubleSided = true
        box.materials = [glassMat]
        let boxNode = SCNNode(geometry: box)
        boxNode.name = "glass_box"
        scene.rootNode.addChildNode(boxNode)

        // Volumetric particles inside box
        addParticles()

        // Agent spheres
        for agent in state.agents {
            let sphere = SCNSphere(radius: 0.035)
            let mat = SCNMaterial()
            mat.diffuse.contents = NSColor(
                red: CGFloat(agent.color.x),
                green: CGFloat(agent.color.y),
                blue: CGFloat(agent.color.z),
                alpha: 1.0
            )
            mat.emission.contents = NSColor(
                red: CGFloat(agent.color.x * 0.5),
                green: CGFloat(agent.color.y * 0.5),
                blue: CGFloat(agent.color.z * 0.5),
                alpha: 1.0
            )
            sphere.materials = [mat]
            let node = SCNNode(geometry: sphere)
            node.position = SCNVector3(agent.position.x, agent.position.y, agent.position.z)
            node.name = agent.agentId
            scene.rootNode.addChildNode(node)
            agentNodes[agent.agentId] = node
        }
    }

    private func addParticles() {
        let system = SCNParticleSystem()
        system.particleColor = NSColor(red: 0.5, green: 0.7, blue: 1.0, alpha: 0.3)
        system.particleSize = 0.005
        system.birthRate = 80
        system.particleLifeSpan = 3.0
        system.emitterShape = SCNBox(width: 1.8, height: 1.8, length: 1.8, chamferRadius: 0)
        system.spreadingAngle = 180
        system.particleVelocity = 0.05
        system.particleVelocityVariation = 0.03
        let particleNode = SCNNode()
        particleNode.addParticleSystem(system)
        scene.rootNode.addChildNode(particleNode)
    }

    // MARK: - Updates

    private func updateAgentPositions() {
        for agent in state.agents {
            guard let node = agentNodes[agent.agentId] else { continue }
            let pos = agent.position
            SCNTransaction.begin()
            SCNTransaction.animationDuration = 0.016
            node.position = SCNVector3(pos.x, pos.y, pos.z)

            // Color reflects state
            let stateColor = agent.state.color
            if let mat = node.geometry?.firstMaterial {
                mat.diffuse.contents = NSColor(
                    red: CGFloat(stateColor.x),
                    green: CGFloat(stateColor.y),
                    blue: CGFloat(stateColor.z),
                    alpha: 1.0
                )
                // Progress ring via emission intensity
                mat.emission.contents = NSColor(
                    red: CGFloat(stateColor.x * agent.progress),
                    green: CGFloat(stateColor.y * agent.progress),
                    blue: CGFloat(stateColor.z * agent.progress),
                    alpha: 1.0
                )
            }
            SCNTransaction.commit()
        }
    }

    private func triggerGlassWave() {
        guard let boxNode = scene.rootNode.childNode(withName: "glass_box", recursively: false) else { return }
        let pulse = CAKeyframeAnimation(keyPath: "scale")
        pulse.values = [
            NSValue(scnVector3: SCNVector3(1, 1, 1)),
            NSValue(scnVector3: SCNVector3(1.015, 1.015, 1.015)),
            NSValue(scnVector3: SCNVector3(1, 1, 1)),
        ]
        pulse.keyTimes = [0, 0.3, 1.0]
        pulse.duration = 0.4
        boxNode.addAnimation(pulse, forKey: "wave")
    }
}

// MARK: - Corpus Tree Sidebar

struct CorpusTreeSidebar: View {
    @ObservedObject var state: SwarmState

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("TRAINING CORPUS")
                .font(.system(size: 10, weight: .bold, design: .monospaced))
                .foregroundColor(.white.opacity(0.5))
                .padding(.horizontal, 12)
                .padding(.vertical, 8)

            ScrollView {
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(CorpusSource.allCases, id: \.self) { source in
                        CorpusRow(source: source, state: state)
                    }
                }
                .padding(.horizontal, 8)
            }
        }
        .background(.ultraThinMaterial)
        .overlay(Rectangle().frame(width: 1).foregroundColor(.white.opacity(0.08)), alignment: .trailing)
    }
}

struct CorpusRow: View {
    let source: CorpusSource
    @ObservedObject var state: SwarmState
    @State private var expanded = true

    var corpus: TrainingCorpus? { state.corpora[source] }
    var isSelected: Bool { state.selectedCorpus == source }
    var agentCount: Int { state.agents.filter { $0.corpusSource == source }.count }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Button {
                state.filterByCorpus(isSelected ? nil : source)
                expanded.toggle()
            } label: {
                HStack(spacing: 6) {
                    Circle()
                        .fill(Color(red: Double(source.color.x),
                                   green: Double(source.color.y),
                                   blue: Double(source.color.z)))
                        .frame(width: 6, height: 6)
                    Text(source.displayName)
                        .font(.system(size: 11, weight: .medium, design: .monospaced))
                        .foregroundColor(isSelected ? .white : .white.opacity(0.7))
                    Spacer()
                    Text("\(agentCount)")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundColor(.white.opacity(0.4))
                }
                .padding(.vertical, 5)
                .padding(.horizontal, 6)
                .background(isSelected ? Color.white.opacity(0.08) : Color.clear)
                .cornerRadius(6)
            }
            .buttonStyle(.plain)

            if expanded, let corpus {
                ForEach(corpus.root.children, id: \.nodeId) { child in
                    NodeRow(node: child, state: state, indent: 1)
                }
            }
        }
    }
}

struct NodeRow: View {
    let node: TrainingNode
    @ObservedObject var state: SwarmState
    let indent: Int

    var body: some View {
        Button {
            state.selectedNode = node
        } label: {
            HStack(spacing: 4) {
                Rectangle()
                    .fill(Color.white.opacity(0.06))
                    .frame(width: 1)
                    .padding(.leading, CGFloat(indent * 10))
                Text(node.name)
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundColor(.white.opacity(0.5))
                    .lineLimit(1)
                Spacer()
                if node.totalExamples > 0 {
                    Text("\(node.totalExamples)")
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundColor(.cyan.opacity(0.5))
                }
            }
            .padding(.vertical, 3)
            .padding(.horizontal, 6)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Agent Inspector

struct AgentInspector: View {
    @ObservedObject var agent: Agent

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(agent.agentId)
                .font(.system(size: 13, weight: .bold, design: .monospaced))
                .foregroundColor(.white)
            Text(agent.state.rawValue)
                .font(.system(size: 10, design: .monospaced))
                .foregroundColor(Color(red: Double(agent.state.color.x),
                                      green: Double(agent.state.color.y),
                                      blue: Double(agent.state.color.z)))
            Divider().background(Color.white.opacity(0.1))
            Text(agent.corpusSource.displayName)
                .font(.system(size: 10, design: .monospaced))
                .foregroundColor(.cyan.opacity(0.7))
            if let node = agent.currentNode {
                Text(node.name)
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundColor(.white.opacity(0.6))
                    .lineLimit(2)
            }
            ProgressView(value: agent.progress)
                .tint(Color(red: Double(agent.state.color.x),
                            green: Double(agent.state.color.y),
                            blue: Double(agent.state.color.z)))
            Divider().background(Color.white.opacity(0.1))
            Text("PIPELINE")
                .font(.system(size: 9, weight: .bold, design: .monospaced))
                .foregroundColor(.white.opacity(0.3))
            ForEach(Array(agent.pipeline.enumerated()), id: \.offset) { i, step in
                HStack(spacing: 6) {
                    Circle()
                        .fill(stepColor(step.status))
                        .frame(width: 5, height: 5)
                    Text(step.label)
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundColor(i == agent.currentStep ? .white : .white.opacity(0.35))
                        .lineLimit(1)
                }
            }
            Spacer()
        }
        .padding(12)
        .background(.ultraThinMaterial)
        .overlay(Rectangle().frame(width: 1).foregroundColor(.white.opacity(0.08)), alignment: .leading)
    }

    private func stepColor(_ status: ExecutionNode.NodeStatus) -> Color {
        switch status {
        case .pending: return .white.opacity(0.2)
        case .running: return .yellow
        case .done:    return .green
        case .failed:  return .red
        }
    }
}

// MARK: - Event Timeline

struct EventTimeline: View {
    let events: [ExecutionEvent]

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 12) {
                ForEach(events.prefix(30)) { event in
                    HStack(spacing: 4) {
                        Circle()
                            .fill(eventColor(event.type))
                            .frame(width: 4, height: 4)
                        Text("\(event.agentId) \(event.detail)")
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundColor(.white.opacity(0.5))
                            .lineLimit(1)
                    }
                }
            }
            .padding(.horizontal, 12)
        }
        .background(.ultraThinMaterial)
        .overlay(Rectangle().frame(height: 1).foregroundColor(.white.opacity(0.06)), alignment: .top)
    }

    private func eventColor(_ type: ExecutionEvent.EventType) -> Color {
        switch type {
        case .stateChange:  return .blue
        case .clusterForm:  return .green
        case .waveEmit:     return .white
        case .message:      return .cyan
        case .corpusSealed: return .purple
        case .trainingStep: return .yellow
        }
    }
}

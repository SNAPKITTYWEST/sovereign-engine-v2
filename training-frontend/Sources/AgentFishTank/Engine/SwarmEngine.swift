// SwarmEngine.swift — 60fps deterministic state machine
// Authors: Ahmad Ali Parr, Jessica L. Williams (SNAPKITTYWEST)
// Based on Nova Parr's original spec, extended for training corpus

import Foundation
import simd
import Combine

public class SwarmEngine: ObservableObject {

    public let state: SwarmState
    private var timer: Timer?
    private var tick: UInt64 = 0
    private let bounds: Float = 1.0

    // Task pool — nodes waiting to be assigned
    private var taskPool: [(TrainingNode, CorpusSource, TaskType)] = []

    public init(state: SwarmState) {
        self.state = state
    }

    // MARK: - Start / Stop

    public func start() {
        timer = Timer.scheduledTimer(withTimeInterval: 1.0 / 60.0, repeats: true) { [weak self] _ in
            self?.tick()
        }
    }

    public func stop() {
        timer?.invalidate()
        timer = nil
    }

    // MARK: - Load corpora and seed task pool

    public func loadCorpora() async {
        let corpora = await CorpusLoader.loadAll()
        await MainActor.run {
            state.corpora = corpora
            seedTaskPool(from: corpora)
            assignInitialTasks()
        }
    }

    private func seedTaskPool(from corpora: [CorpusSource: TrainingCorpus]) {
        taskPool.removeAll()
        for (source, corpus) in corpora {
            let nodes = corpus.allNodes
            // Distribute all 7 task types across nodes
            for node in nodes {
                for taskType in TaskType.allCases {
                    taskPool.append((node, source, taskType))
                }
            }
        }
        taskPool.shuffle()
    }

    private func assignInitialTasks() {
        for agent in state.agents {
            assignNextTask(to: agent)
        }
    }

    private func assignNextTask(to agent: Agent) {
        guard !taskPool.isEmpty else { return }
        let (node, source, task) = taskPool.removeFirst()
        agent.assignTask(task, node: node, corpus: source)
        updateCluster(agent: agent, node: node)
    }

    // MARK: - 60fps tick

    private func tick() {
        self.tick &+= 1

        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            for agent in self.state.agents {
                self.moveAgent(agent)
                self.advancePipeline(agent)
            }
            self.detectClusters()
        }
    }

    // MARK: - Movement — bounce inside [-bounds, bounds]³

    private func moveAgent(_ agent: Agent) {
        agent.position += agent.velocity

        var vel = agent.velocity
        var pos = agent.position

        // Cluster pull — agents on same node drift together
        if let node = agent.currentNode,
           let center = state.clusters[node.nodeId] {
            let pull = (center - pos) * 0.002
            vel += pull
        }

        // Separation from neighbors
        for other in state.agents where other.id != agent.id {
            let diff = pos - other.position
            let dist = length(diff)
            if dist < 0.15 && dist > 0 {
                vel += normalize(diff) * 0.003
            }
        }

        // Bound bounce
        for i in 0..<3 {
            if pos[i] > bounds  { pos[i] = bounds;  vel[i] = -abs(vel[i]) }
            if pos[i] < -bounds { pos[i] = -bounds; vel[i] =  abs(vel[i]) }
        }

        // Speed cap
        let speed = length(vel)
        if speed > 0.015 { vel = normalize(vel) * 0.015 }
        if speed < 0.002 { vel = normalize(vel + SIMD3(0.001, 0.001, 0.001)) * 0.003 }

        agent.velocity = vel
        agent.position = pos
    }

    // MARK: - Pipeline advancement

    private func advancePipeline(_ agent: Agent) {
        guard agent.state != .idle && agent.state != .failed else { return }

        // Each step runs for ~30 ticks (0.5s at 60fps)
        let stepDuration: UInt64 = 30
        let globalTick = tick
        let agentPhase = UInt64(agent.agentId.hashValue & 0xFFFF)
        let localTick = (globalTick + agentPhase) % (stepDuration * UInt64(agent.pipeline.count + 1))

        let newStep = Int(localTick / stepDuration)
        if newStep != agent.currentStep && newStep < agent.pipeline.count {
            agent.currentStep = newStep
            agent.pipeline[newStep].status = .running

            // Mark previous as done
            if newStep > 0 { agent.pipeline[newStep - 1].status = .done }

            // Update state based on step
            agent.state = stateForStep(newStep, total: agent.pipeline.count)
            agent.progress = Float(newStep) / Float(agent.pipeline.count)

            // Log event
            let event = ExecutionEvent(
                agentId: agent.agentId,
                type: .trainingStep,
                detail: "\(agent.pipeline[newStep].label) → \(agent.currentNode?.name ?? "?")",
                corpus: agent.corpusSource
            )
            state.logEvent(event)

            // Glass deform on state changes
            if agent.state == .communicating || agent.state == .verifying {
                state.glass.deform(at: agent.position, intensity: 0.4)
                sendMessage(from: agent)
            }

        } else if newStep >= agent.pipeline.count {
            completeAgent(agent)
        }
    }

    private func stateForStep(_ step: Int, total: Int) -> AgentState {
        let ratio = Float(step) / Float(max(total - 1, 1))
        switch ratio {
        case 0..<0.2:  return .traversing
        case 0.2..<0.4: return .parsing
        case 0.4..<0.6: return .extracting
        case 0.6..<0.8: return .transforming
        case 0.8..<0.9: return .verifying
        default:        return .communicating
        }
    }

    private func completeAgent(_ agent: Agent) {
        agent.state = .complete
        agent.progress = 1.0
        for i in agent.pipeline.indices { agent.pipeline[i].status = .done }

        // Shockwave
        state.glass.emitWave(from: agent.position)

        let event = ExecutionEvent(
            agentId: agent.agentId,
            type: .waveEmit,
            detail: "COMPLETE: \(agent.taskType.rawValue) on \(agent.currentNode?.name ?? "?")",
            corpus: agent.corpusSource
        )
        state.logEvent(event)

        // Log corpus seal
        let seal = ExecutionEvent(
            agentId: agent.agentId,
            type: .corpusSealed,
            detail: "Training example sealed → \(agent.corpusSource.rawValue)",
            corpus: agent.corpusSource
        )
        state.logEvent(seal)

        // Reassign after brief pause
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
            guard let self else { return }
            agent.state = .idle
            self.assignNextTask(to: agent)
        }
    }

    // MARK: - Messaging

    private func sendMessage(from agent: Agent) {
        // Pick a random other agent as target
        let others = state.agents.filter { $0.id != agent.id }
        guard let target = others.randomElement() else { return }

        let msg = AgentMessage(
            from: agent.agentId,
            to: target.agentId,
            payload: agent.pipeline[min(agent.currentStep, agent.pipeline.count - 1)].label,
            corpusRef: agent.currentNode?.path ?? "",
            trainingClass: .extraction,
            latency: Double.random(in: 0.01...0.1)
        )
        state.messages.insert(msg, at: 0)
        if state.messages.count > 100 { state.messages.removeLast() }
    }

    // MARK: - Cluster detection

    private func detectClusters() {
        var nodeGroups: [String: [SIMD3<Float>]] = [:]
        for agent in state.agents {
            if let node = agent.currentNode {
                nodeGroups[node.nodeId, default: []].append(agent.position)
            }
        }
        for (nodeId, positions) in nodeGroups where positions.count >= 3 {
            let center = positions.reduce(.zero, +) / Float(positions.count)
            if state.clusters[nodeId] == nil {
                let event = ExecutionEvent(
                    agentId: "SWARM",
                    type: .clusterForm,
                    detail: "Cluster formed: \(nodeId) (\(positions.count) agents)",
                    corpus: state.agents.first?.corpusSource ?? .commonMetadataRepository
                )
                state.logEvent(event)
            }
            state.clusters[nodeId] = center
        }
        // Remove dissolved clusters
        for nodeId in state.clusters.keys {
            if nodeGroups[nodeId].map({ $0.count }) ?? 0 < 2 {
                state.clusters.removeValue(forKey: nodeId)
            }
        }
    }

    private func updateCluster(agent: Agent, node: TrainingNode) {
        // Cluster center will be computed in detectClusters()
    }
}

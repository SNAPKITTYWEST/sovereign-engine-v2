// SwarmState.swift — observable swarm + glass environment state
// Authors: Ahmad Ali Parr, Jessica L. Williams (SNAPKITTYWEST)

import Foundation
import Combine
import simd

// MARK: - Agent Message

public struct AgentMessage: Identifiable {
    public let id: UUID
    public let fromId: String
    public let toId: String
    public let payload: String
    public let corpusRef: String         // e.g. "CMR/services/search-service"
    public let trainingClass: TrainingClass
    public let latency: TimeInterval
    public let timestamp: Date

    public init(from: String, to: String, payload: String, corpusRef: String,
                trainingClass: TrainingClass, latency: TimeInterval = 0.0) {
        self.id = UUID()
        self.fromId = from
        self.toId = to
        self.payload = payload
        self.corpusRef = corpusRef
        self.trainingClass = trainingClass
        self.latency = latency
        self.timestamp = Date()
    }
}

// MARK: - Execution Event (bottom timeline)

public struct ExecutionEvent: Identifiable {
    public let id: UUID
    public let agentId: String
    public let type: EventType
    public let detail: String
    public let corpusSource: CorpusSource
    public let timestamp: Date

    public enum EventType: String {
        case stateChange    = "STATE"
        case clusterForm    = "CLUSTER"
        case waveEmit       = "WAVE"
        case message        = "MSG"
        case corpusSealed   = "SEAL"
        case trainingStep   = "TRAIN"
    }

    public init(agentId: String, type: EventType, detail: String, corpus: CorpusSource) {
        self.id = UUID()
        self.agentId = agentId
        self.type = type
        self.detail = detail
        self.corpusSource = corpus
        self.timestamp = Date()
    }
}

// MARK: - Glass Environment

public class GlassEnvironment: ObservableObject {
    @Published public var morphFactor: Float    = 0.0    // 0–1 deformation scale (λ)
    @Published public var waveIntensity: Float  = 0.0    // shockwave on COMPLETE
    @Published public var refractiveIndex: Float = 1.45  // glass IOR
    @Published public var impactPoint: SIMD3<Float> = .zero

    private var decayTimer: Timer?

    public func deform(at point: SIMD3<Float>, intensity: Float = 1.0) {
        impactPoint = point
        morphFactor = min(1.0, morphFactor + intensity * 0.3)
        waveIntensity = intensity
        scheduleDecay()
    }

    public func emitWave(from point: SIMD3<Float>) {
        impactPoint = point
        waveIntensity = 1.0
        scheduleDecay()
    }

    private func scheduleDecay() {
        decayTimer?.invalidate()
        decayTimer = Timer.scheduledTimer(withTimeInterval: 0.016, repeats: true) { [weak self] _ in
            guard let self else { return }
            DispatchQueue.main.async {
                self.morphFactor    = max(0, self.morphFactor - 0.02)
                self.waveIntensity  = max(0, self.waveIntensity - 0.04)
                if self.morphFactor == 0 && self.waveIntensity == 0 {
                    self.decayTimer?.invalidate()
                }
            }
        }
    }
}

// MARK: - Swarm State

public class SwarmState: ObservableObject {
    @Published public var agents: [Agent]
    @Published public var messages: [AgentMessage]
    @Published public var events: [ExecutionEvent]
    @Published public var selectedAgent: Agent?
    @Published public var selectedCorpus: CorpusSource?
    @Published public var selectedNode: TrainingNode?
    public let glass: GlassEnvironment

    // Training corpora loaded from GitHub forks
    public var corpora: [CorpusSource: TrainingCorpus] = [:]

    // Cluster positions — agents executing same corpus node cluster together
    public var clusters: [String: SIMD3<Float>] = [:]

    public init(agentCount: Int = 36) {
        self.agents = (0..<agentCount).map { i in
            let corpus = CorpusSource.allCases[i % CorpusSource.allCases.count]
            return Agent(index: i, corpusSource: corpus)
        }
        self.messages = []
        self.events = []
        self.glass = GlassEnvironment()
    }

    public func selectAgent(_ agent: Agent) {
        selectedAgent = agent
        selectedCorpus = agent.corpusSource
        selectedNode = agent.currentNode
    }

    public func filterByCorpus(_ source: CorpusSource?) {
        selectedCorpus = source
    }

    public func logEvent(_ event: ExecutionEvent) {
        events.insert(event, at: 0)
        if events.count > 200 { events.removeLast() }
    }
}

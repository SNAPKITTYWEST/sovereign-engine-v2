// Agent.swift — sovereign training agent model
// Extends Nova's original spec with training corpus fields
// Authors: Ahmad Ali Parr, Jessica L. Williams (SNAPKITTYWEST)

import Foundation
import simd

// MARK: - Agent State

public enum AgentState: String, CaseIterable {
    case idle           = "IDLE"
    case traversing     = "TRAVERSING"
    case parsing        = "PARSING"
    case extracting     = "EXTRACTING"
    case transforming   = "TRANSFORMING"
    case verifying      = "VERIFYING"
    case communicating  = "COMMUNICATING"
    case complete       = "COMPLETE"
    case failed         = "FAILED"

    public var color: SIMD3<Float> {
        switch self {
        case .idle:          return SIMD3(0.5, 0.5, 0.5)
        case .traversing:    return SIMD3(0.2, 0.4, 1.0)
        case .parsing:       return SIMD3(0.0, 0.9, 0.9)
        case .extracting:    return SIMD3(1.0, 0.9, 0.0)
        case .transforming:  return SIMD3(0.6, 0.2, 0.9)
        case .verifying:     return SIMD3(1.0, 0.5, 0.0)
        case .communicating: return SIMD3(0.0, 1.0, 0.4)
        case .complete:      return SIMD3(1.0, 1.0, 1.0)
        case .failed:        return SIMD3(1.0, 0.1, 0.1)
        }
    }

    public var emitsWave: Bool { self == .complete }
    public var pulsates: Bool  { self == .communicating }
}

// MARK: - Task Type

public enum TaskType: String, CaseIterable {
    case traverseTree     = "TRAVERSE_TREE"
    case extractMetadata  = "EXTRACT_METADATA"
    case buildRelGraph    = "BUILD_REL_GRAPH"
    case reconstructArch  = "RECONSTRUCT_ARCH"
    case generateTraining = "GENERATE_TRAINING"
    case validateOutput   = "VALIDATE_OUTPUT"
    case sendToAgent      = "SEND_TO_AGENT"
}

// MARK: - Execution Node (pipeline step)

public struct ExecutionNode: Identifiable {
    public let id: UUID
    public let label: String
    public var input: String
    public var output: String
    public var status: NodeStatus
    public let timestamp: Date

    public enum NodeStatus { case pending, running, done, failed }

    public init(label: String, input: String = "", output: String = "") {
        self.id = UUID()
        self.label = label
        self.input = input
        self.output = output
        self.status = .pending
        self.timestamp = Date()
    }

    public static func defaultPipeline(for taskType: TaskType, corpus: CorpusSource) -> [ExecutionNode] {
        switch taskType {
        case .traverseTree:
            return [
                ExecutionNode(label: "Load \(corpus.displayName) tree"),
                ExecutionNode(label: "Traverse node hierarchy"),
                ExecutionNode(label: "Index child nodes"),
                ExecutionNode(label: "Send to extractor"),
            ]
        case .extractMetadata:
            return [
                ExecutionNode(label: "Read evidence file"),
                ExecutionNode(label: "Parse structure"),
                ExecutionNode(label: "Extract facts"),
                ExecutionNode(label: "Tag confidence level"),
                ExecutionNode(label: "Append to corpus"),
            ]
        case .buildRelGraph:
            return [
                ExecutionNode(label: "Load component list"),
                ExecutionNode(label: "Detect imports/deps"),
                ExecutionNode(label: "Classify relationship type"),
                ExecutionNode(label: "Build edge → \(corpus.rawValue)"),
            ]
        case .reconstructArch:
            return [
                ExecutionNode(label: "Gather all edges"),
                ExecutionNode(label: "Cluster by subsystem"),
                ExecutionNode(label: "Derive data flow"),
                ExecutionNode(label: "Validate against evidence"),
            ]
        case .generateTraining:
            return [
                ExecutionNode(label: "Select training class"),
                ExecutionNode(label: "Form question from node"),
                ExecutionNode(label: "Derive answer from evidence"),
                ExecutionNode(label: "Serialize to corpus"),
            ]
        case .validateOutput:
            return [
                ExecutionNode(label: "Load reconstructed spec"),
                ExecutionNode(label: "Compare to observable behavior"),
                ExecutionNode(label: "Classify: MATCH/PARTIAL/MISMATCH"),
                ExecutionNode(label: "Emit WORM seal"),
            ]
        case .sendToAgent:
            return [
                ExecutionNode(label: "Pack payload"),
                ExecutionNode(label: "Route to target"),
                ExecutionNode(label: "Await ACK"),
            ]
        }
    }
}

// MARK: - Agent

public class Agent: Identifiable, ObservableObject {
    public let id: UUID
    public let agentId: String          // "Agent-07"
    public var position: SIMD3<Float>
    public var velocity: SIMD3<Float>
    public var color: SIMD3<Float>

    @Published public var state: AgentState
    @Published public var taskType: TaskType
    @Published public var progress: Float            // 0.0 – 1.0
    @Published public var currentNode: TrainingNode?
    @Published public var corpusSource: CorpusSource
    @Published public var pipeline: [ExecutionNode]
    @Published public var currentStep: Int
    @Published public var inputTrace: [String]
    @Published public var outputTrace: [String]
    @Published public var connections: [String]      // connected agent IDs
    @Published public var reasoning: String

    public init(index: Int, corpusSource: CorpusSource = .commonMetadataRepository) {
        self.id = UUID()
        self.agentId = String(format: "Agent-%02d", index)
        self.position = SIMD3(
            Float.random(in: -0.8...0.8),
            Float.random(in: -0.8...0.8),
            Float.random(in: -0.8...0.8)
        )
        self.velocity = SIMD3(
            Float.random(in: -0.01...0.01),
            Float.random(in: -0.01...0.01),
            Float.random(in: -0.01...0.01)
        )
        // Unique hue per agent
        let hue = Float(index) / 36.0
        self.color = SIMD3(
            abs(sin(hue * .pi * 2)),
            abs(sin(hue * .pi * 2 + 2.094)),
            abs(sin(hue * .pi * 2 + 4.189))
        )
        self.state = .idle
        self.taskType = .traverseTree
        self.progress = 0
        self.corpusSource = corpusSource
        self.pipeline = ExecutionNode.defaultPipeline(for: .traverseTree, corpus: corpusSource)
        self.currentStep = 0
        self.inputTrace = []
        self.outputTrace = []
        self.connections = []
        self.reasoning = ""
    }

    public func assignTask(_ task: TaskType, node: TrainingNode, corpus: CorpusSource) {
        taskType = task
        currentNode = node
        corpusSource = corpus
        pipeline = ExecutionNode.defaultPipeline(for: task, corpus: corpus)
        currentStep = 0
        progress = 0
        state = .traversing
        reasoning = "Assigned \(task.rawValue) on \(node.name) [\(corpus.rawValue)]"
    }
}

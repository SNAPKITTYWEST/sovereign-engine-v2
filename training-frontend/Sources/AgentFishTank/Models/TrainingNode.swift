// TrainingNode.swift — mirrors BibleNode but for sovereign training corpus
// Authors: Ahmad Ali Parr, Jessica L. Williams (SNAPKITTYWEST)
// Sovereign Source License v1.0

import Foundation
import simd

// MARK: - Corpus Source

public enum CorpusSource: String, Codable, CaseIterable {
    case commonMetadataRepository = "CMR"
    case openMetadata             = "OM"
    case autoware                 = "AW"
    case bible                    = "BIBLE"

    public var displayName: String {
        switch self {
        case .commonMetadataRepository: return "NASA CMR"
        case .openMetadata:             return "OpenMetadata"
        case .autoware:                 return "Autoware"
        case .bible:                    return "Bible"
        }
    }

    public var color: SIMD3<Float> {
        switch self {
        case .commonMetadataRepository: return SIMD3(0.2, 0.6, 1.0)   // NASA blue
        case .openMetadata:             return SIMD3(0.4, 0.9, 0.5)   // data green
        case .autoware:                 return SIMD3(1.0, 0.6, 0.1)   // drive orange
        case .bible:                    return SIMD3(0.8, 0.7, 1.0)   // violet
        }
    }
}

// MARK: - Training Class

public enum TrainingClass: String, Codable, CaseIterable {
    case discovery      = "DISCOVERY"
    case extraction     = "EXTRACTION"
    case classification = "CLASSIFICATION"
    case relationship   = "RELATIONSHIP"
    case architecture   = "ARCHITECTURE"
    case behavior       = "BEHAVIOR"
    case reconstruction = "RECONSTRUCTION"

    public var pipelineLabel: String {
        switch self {
        case .discovery:      return "Observe repo structure"
        case .extraction:     return "Extract metadata facts"
        case .classification: return "Classify component type"
        case .relationship:   return "Map dependency edges"
        case .architecture:   return "Reconstruct architecture"
        case .behavior:       return "Trace execution path"
        case .reconstruction: return "Rebuild from spec"
        }
    }
}

// MARK: - Training Example

public struct TrainingExample: Identifiable, Codable {
    public let id: UUID
    public let trainingClass: TrainingClass
    public let question: String
    public let answer: String
    public let evidence: String
    public let source: CorpusSource
    public let nodePath: String          // e.g. "CMR/services/search-service"

    public init(trainingClass: TrainingClass, question: String, answer: String,
                evidence: String, source: CorpusSource, nodePath: String) {
        self.id = UUID()
        self.trainingClass = trainingClass
        self.question = question
        self.answer = answer
        self.evidence = evidence
        self.source = source
        self.nodePath = nodePath
    }
}

// MARK: - Training Node (mirrors BibleNode hierarchy)

public class TrainingNode: Identifiable, ObservableObject {
    public let id: UUID
    public let nodeId: String
    public let nodeType: String          // repository | subsystem | component | schema | api | test
    public let name: String
    public let path: String
    public let source: CorpusSource
    public var children: [TrainingNode]
    public var examples: [TrainingExample]
    public var confidence: String        // OBSERVED | DERIVED | INFERRED | HYPOTHESIZED

    public init(nodeId: String, nodeType: String, name: String, path: String,
                source: CorpusSource, children: [TrainingNode] = [],
                examples: [TrainingExample] = [], confidence: String = "OBSERVED") {
        self.id = UUID()
        self.nodeId = nodeId
        self.nodeType = nodeType
        self.name = name
        self.path = path
        self.source = source
        self.children = children
        self.examples = examples
        self.confidence = confidence
    }

    public var totalExamples: Int {
        examples.count + children.reduce(0) { $0 + $1.totalExamples }
    }

    public func allExamples() -> [TrainingExample] {
        examples + children.flatMap { $0.allExamples() }
    }

    public func find(nodeId: String) -> TrainingNode? {
        if self.nodeId == nodeId { return self }
        for child in children {
            if let found = child.find(nodeId: nodeId) { return found }
        }
        return nil
    }
}

// MARK: - Relationship Edge

public struct RelationshipEdge: Identifiable, Codable {
    public let id: UUID
    public let from: String
    public let to: String
    public let relationship: String
    public let evidence: String
    public let confidence: String
    public let source: CorpusSource

    public init(from: String, to: String, relationship: String,
                evidence: String, confidence: String, source: CorpusSource) {
        self.id = UUID()
        self.from = from
        self.to = to
        self.relationship = relationship
        self.evidence = evidence
        self.confidence = confidence
        self.source = source
    }
}

// MARK: - Full Training Corpus

public struct TrainingCorpus {
    public let source: CorpusSource
    public let root: TrainingNode
    public let edges: [RelationshipEdge]
    public let summary: CorpusSummary

    public var allNodes: [TrainingNode] {
        func flatten(_ node: TrainingNode) -> [TrainingNode] {
            [node] + node.children.flatMap { flatten($0) }
        }
        return flatten(root)
    }
}

public struct CorpusSummary: Codable {
    public let domain: String
    public let architectureType: String
    public let primaryLanguage: String
    public let majorComponents: [String]
    public let dataStores: [String]
    public let externalInterfaces: [String]
    public let evidenceFilesRead: [String]
}

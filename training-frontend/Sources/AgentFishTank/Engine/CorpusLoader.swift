// CorpusLoader.swift — loads TRAINING_CORPUS.json from GitHub forks
// Authors: Ahmad Ali Parr, Jessica L. Williams (SNAPKITTYWEST)

import Foundation

// MARK: - Raw JSON structures (mirrors the workflow output schema)

private struct RawCorpusJSON: Decodable {
    let repo: String
    let summary: RawSummary
    let metadata_tree: RawNode
    let relationship_graph: [RawEdge]
    let training_corpus: RawTrainingCorpus
}

private struct RawSummary: Decodable {
    let domain: String
    let architecture_type: String
    let primary_language: String
    let major_components: [String]
    let data_stores: [String]
    let external_interfaces: [String]
    let evidence_files_read: [String]
}

private struct RawNode: Decodable {
    let node_id: String
    let node_type: String
    let name: String
    let children: [RawNode]?
}

private struct RawEdge: Decodable {
    let from: String
    let to: String
    let relationship: String
    let evidence: String
    let confidence: String
}

private struct RawTrainingCorpus: Decodable {
    let DISCOVERY:      [RawExample]
    let EXTRACTION:     [RawExample]
    let CLASSIFICATION: [RawExample]
    let RELATIONSHIP:   [RawExample]
    let ARCHITECTURE:   [RawExample]
    let BEHAVIOR:       [RawExample]
    let RECONSTRUCTION: [RawExample]
}

private struct RawExample: Decodable {
    let question: String
    let answer: String
    let evidence: String
}

// MARK: - Loader

public class CorpusLoader {

    private static let baseURL = "https://raw.githubusercontent.com/SNAPKITTYWEST"
    private static let trainingPath = "/main/TRAINING"

    private static let repoMap: [CorpusSource: String] = [
        .commonMetadataRepository: "Common-Metadata-Repository",
        .openMetadata:             "OpenMetadata",
        .autoware:                 "autoware",
    ]

    public static func loadAll() async -> [CorpusSource: TrainingCorpus] {
        var result: [CorpusSource: TrainingCorpus] = [:]
        await withTaskGroup(of: (CorpusSource, TrainingCorpus?)?.self) { group in
            for (source, repo) in repoMap {
                group.addTask { await load(source: source, repo: repo) }
            }
            for await pair in group {
                if let (source, corpus) = pair, let corpus {
                    result[source] = corpus
                }
            }
        }
        return result
    }

    private static func load(source: CorpusSource, repo: String) async -> (CorpusSource, TrainingCorpus?)? {
        let urlStr = "\(baseURL)/\(repo)\(trainingPath)/TRAINING_CORPUS.json"
        guard let url = URL(string: urlStr) else { return nil }
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let raw = try JSONDecoder().decode(RawCorpusJSON.self, from: data)
            let corpus = map(raw: raw, source: source)
            return (source, corpus)
        } catch {
            print("[CorpusLoader] Failed \(source.rawValue): \(error.localizedDescription)")
            return (source, nil)
        }
    }

    // MARK: - Mapping

    private static func map(raw: RawCorpusJSON, source: CorpusSource) -> TrainingCorpus {
        let root = mapNode(raw: raw.metadata_tree, source: source,
                           corpus: raw.training_corpus, path: source.rawValue)
        let edges = raw.relationship_graph.map { e in
            RelationshipEdge(from: e.from, to: e.to, relationship: e.relationship,
                             evidence: e.evidence, confidence: e.confidence, source: source)
        }
        let summary = CorpusSummary(
            domain: raw.summary.domain,
            architectureType: raw.summary.architecture_type,
            primaryLanguage: raw.summary.primary_language,
            majorComponents: raw.summary.major_components,
            dataStores: raw.summary.data_stores,
            externalInterfaces: raw.summary.external_interfaces,
            evidenceFilesRead: raw.summary.evidence_files_read
        )
        return TrainingCorpus(source: source, root: root, edges: edges, summary: summary)
    }

    private static func mapNode(raw: RawNode, source: CorpusSource,
                                corpus: RawTrainingCorpus, path: String) -> TrainingNode {
        let nodePath = "\(path)/\(raw.node_id)"
        let children = (raw.children ?? []).map { child in
            mapNode(raw: child, source: source, corpus: corpus, path: nodePath)
        }
        // Attach training examples to leaf nodes by matching node_id in evidence
        let examples = examplesFor(nodeId: raw.node_id, source: source, corpus: corpus, path: nodePath)
        return TrainingNode(
            nodeId: raw.node_id,
            nodeType: raw.node_type,
            name: raw.name,
            path: nodePath,
            source: source,
            children: children,
            examples: examples
        )
    }

    private static func examplesFor(nodeId: String, source: CorpusSource,
                                    corpus: RawTrainingCorpus, path: String) -> [TrainingExample] {
        let all: [(TrainingClass, [RawExample])] = [
            (.discovery,      corpus.DISCOVERY),
            (.extraction,     corpus.EXTRACTION),
            (.classification, corpus.CLASSIFICATION),
            (.relationship,   corpus.RELATIONSHIP),
            (.architecture,   corpus.ARCHITECTURE),
            (.behavior,       corpus.BEHAVIOR),
            (.reconstruction, corpus.RECONSTRUCTION),
        ]
        var result: [TrainingExample] = []
        for (cls, raws) in all {
            for raw in raws where raw.evidence.lowercased().contains(nodeId.lowercased()) {
                result.append(TrainingExample(
                    trainingClass: cls,
                    question: raw.question,
                    answer: raw.answer,
                    evidence: raw.evidence,
                    source: source,
                    nodePath: path
                ))
            }
        }
        return result
    }
}

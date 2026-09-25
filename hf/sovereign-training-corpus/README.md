# Sovereign training corpus schema

This directory contains a [JSON Schema](schema/training_corpus.schema.json) for repository-grounded training examples. It does not currently contain the `data/*.jsonl` files named by the previous dataset card. A published Hugging Face dataset is not verified by this local documentation.

Authors: Ahmad Ali Parr, Jessica L. Williams (SNAPKITTYWEST).

## Document structure

| Required field | Purpose |
|---|---|
| `repo` | Repository identifier |
| `summary` | Domain, architecture type, language, and major components |
| `metadata_tree` | Root node with node ID, type, name, and optional children |
| `relationship_graph` | Edges with source, destination, relationship, evidence, and confidence |
| `training_corpus` | Arrays for all seven training classes |

The seven classes are DISCOVERY, EXTRACTION, CLASSIFICATION, RELATIONSHIP, ARCHITECTURE, BEHAVIOR, and RECONSTRUCTION. Each example requires `question`, `answer`, and `evidence`. Relationship confidence is one of OBSERVED, DERIVED, INFERRED, or HYPOTHESIZED.

## Local example: validate a minimal document

Run from this directory with `jsonschema` installed:

```python
import json
from pathlib import Path
from jsonschema import Draft7Validator

classes = [
    "DISCOVERY", "EXTRACTION", "CLASSIFICATION", "RELATIONSHIP",
    "ARCHITECTURE", "BEHAVIOR", "RECONSTRUCTION",
]
document = {
    "repo": "example/repository",
    "summary": {
        "domain": "example", "architecture_type": "library",
        "primary_language": "Python", "major_components": [],
    },
    "metadata_tree": {
        "node_id": "root", "node_type": "repository", "name": "example",
    },
    "relationship_graph": [],
    "training_corpus": {name: [] for name in classes},
}
schema = json.loads(Path("schema/training_corpus.schema.json").read_text())
Draft7Validator.check_schema(schema)
Draft7Validator(schema).validate(document)
print("schema-valid document")
```

Schema validation checks structure. It does not establish that an answer is true, an evidence path exists, the corpus has sufficient coverage, or source material is licensed for the intended use.

## Frontend integration

[CorpusLoader.swift](../../training/Sources/AgentFishTank/Engine/CorpusLoader.swift) loads corpus data for the Swift frontend. Inspect its source mapping and models before adding a source. The frontend's scheduling and visualization are not evidence that it automatically writes a complete training dataset back to GitHub.

Record the source revision, extraction method, evidence paths, and validation results alongside generated examples. Keep hypotheses visibly distinguished from observed facts.

## License

Consult [LICENSE.tri](../../LICENSE.tri) and the source material's own terms. No dataset publication or new licensing assignment is performed by this guide.

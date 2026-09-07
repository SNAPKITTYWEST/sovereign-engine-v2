// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "AgentFishTank",
    platforms: [.macOS(.v14), .iOS(.v17)],
    products: [
        .library(name: "AgentFishTank", targets: ["AgentFishTank"]),
    ],
    dependencies: [],
    targets: [
        .target(
            name: "AgentFishTank",
            dependencies: [],
            path: "Sources/AgentFishTank"
        ),
        .testTarget(
            name: "AgentFishTankTests",
            dependencies: ["AgentFishTank"]
        ),
    ]
)

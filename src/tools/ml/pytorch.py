"""
PyTorch Tools
Part of SOVEREIGN PYTHON LLM ENGINE

Enables agents to use PyTorch for tensor operations and model inference.
"""

from typing import Any
import json


async def tensor_operation(params: dict[str, Any]) -> dict[str, Any]:
    """
    Execute PyTorch tensor operation.

    Args:
        params: {
            "operation": str,  # "add", "matmul", "softmax", etc
            "tensor_a": list,  # Input tensor data
            "tensor_b": list | None,  # Second tensor (optional)
            "dim": int | None  # Dimension for operations
        }

    Returns:
        dict with "result" (tensor as list) and "shape"
    """
    try:
        import torch
    except ImportError:
        return {"error": "PyTorch not installed. Run: pip install torch"}

    operation = params.get("operation")
    tensor_a_data = params.get("tensor_a")
    tensor_b_data = params.get("tensor_b")
    dim = params.get("dim")

    if not operation or not tensor_a_data:
        return {"error": "operation and tensor_a required"}

    try:
        # Convert to tensors
        tensor_a = torch.tensor(tensor_a_data)
        tensor_b = torch.tensor(tensor_b_data) if tensor_b_data else None

        # Execute operation
        if operation == "add":
            result = tensor_a + tensor_b if tensor_b is not None else tensor_a
        elif operation == "matmul":
            if tensor_b is None:
                return {"error": "tensor_b required for matmul"}
            result = torch.matmul(tensor_a, tensor_b)
        elif operation == "softmax":
            result = torch.softmax(tensor_a, dim=dim if dim is not None else -1)
        elif operation == "relu":
            result = torch.relu(tensor_a)
        elif operation == "mean":
            result = torch.mean(tensor_a, dim=dim)
        elif operation == "sum":
            result = torch.sum(tensor_a, dim=dim)
        elif operation == "transpose":
            result = torch.transpose(tensor_a, dim0=0, dim1=1)
        else:
            return {"error": f"Unknown operation: {operation}"}

        return {
            "result": result.tolist(),
            "shape": list(result.shape),
            "dtype": str(result.dtype)
        }

    except Exception as e:
        return {"error": f"PyTorch operation failed: {str(e)}"}


async def load_model(params: dict[str, Any]) -> dict[str, Any]:
    """
    Load PyTorch model from file.

    Args:
        params: {
            "model_path": str,  # Path to model file (.pt, .pth)
            "device": str | None  # "cpu" or "cuda"
        }

    Returns:
        dict with "model_id" and "device"
    """
    try:
        import torch
    except ImportError:
        return {"error": "PyTorch not installed"}

    model_path = params.get("model_path")
    device = params.get("device", "cpu")

    if not model_path:
        return {"error": "model_path required"}

    try:
        # Check if CUDA available
        if device == "cuda" and not torch.cuda.is_available():
            device = "cpu"
            print("CUDA not available, using CPU")

        # Load model
        model = torch.load(model_path, map_location=device)

        # Store model in global cache (simple implementation)
        # In production, use proper model registry
        model_id = f"model_{id(model)}"

        return {
            "model_id": model_id,
            "device": device,
            "success": True
        }

    except Exception as e:
        return {"error": f"Failed to load model: {str(e)}"}


async def model_inference(params: dict[str, Any]) -> dict[str, Any]:
    """
    Run inference on loaded PyTorch model.

    Args:
        params: {
            "model_id": str,  # Model ID from load_model
            "input": list,  # Input tensor data
            "batch_size": int | None
        }

    Returns:
        dict with "output" (predictions) and "shape"
    """
    try:
        import torch
    except ImportError:
        return {"error": "PyTorch not installed"}

    # NOTE: This is a simplified implementation
    # In production, would use proper model registry
    return {
        "error": "Model inference requires model registry (TODO)",
        "note": "Use tensor_operation for basic PyTorch ops"
    }


async def check_cuda(params: dict[str, Any]) -> dict[str, Any]:
    """
    Check CUDA availability and device info.

    Returns:
        dict with CUDA status and device info
    """
    try:
        import torch
    except ImportError:
        return {"error": "PyTorch not installed"}

    cuda_available = torch.cuda.is_available()

    result = {
        "cuda_available": cuda_available,
        "cuda_device_count": torch.cuda.device_count() if cuda_available else 0,
        "pytorch_version": torch.__version__
    }

    if cuda_available:
        result["cuda_version"] = torch.version.cuda
        result["cudnn_version"] = torch.backends.cudnn.version()
        result["devices"] = [
            {
                "index": i,
                "name": torch.cuda.get_device_name(i),
                "memory_total": torch.cuda.get_device_properties(i).total_memory,
                "capability": torch.cuda.get_device_capability(i)
            }
            for i in range(torch.cuda.device_count())
        ]

    return result

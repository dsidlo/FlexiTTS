"""GPU memory monitoring and management."""
from __future__ import annotations

import logging
from typing import Optional, Dict
from dataclasses import dataclass

logger = logging.getLogger('tts_models.gpu')


@dataclass
class GPUMemoryInfo:
    """GPU memory statistics."""
    device_id: int
    total_mb: float
    used_mb: float
    free_mb: float
    cached_mb: Optional[float] = None


def get_gpu_memory_info(device_id: int = 0) -> Optional[GPUMemoryInfo]:
    """Get GPU memory info for device.
    
    Returns None if CUDA unavailable or error.
    """
    try:
        import torch
        if not torch.cuda.is_available():
            return None
        
        props = torch.cuda.get_device_properties(device_id)
        total = props.total_memory / (1024**2)  # Convert to MB
        
        torch.cuda.synchronize(device_id)
        allocated = torch.cuda.memory_allocated(device_id) / (1024**2)
        reserved = torch.cuda.memory_reserved(device_id) / (1024**2)
        
        return GPUMemoryInfo(
            device_id=device_id,
            total_mb=total,
            used_mb=allocated,
            free_mb=total - allocated,
            cached_mb=reserved
        )
    except Exception as e:
        logger.warning(f"Failed to get GPU memory info: {e}")
        return None


def check_gpu_available_memory(
    required_mb: int = 4000,
    device_id: int = 0
) -> tuple[bool, Optional[GPUMemoryInfo]]:
    """Check if GPU has sufficient available memory.
    
    Args:
        required_mb: Required free memory in MB
        device_id: CUDA device ID
    
    Returns:
        (has_enough_memory, memory_info)
    """
    info = get_gpu_memory_info(device_id)
    if info is None:
        logger.warning("CUDA not available, cannot check GPU memory")
        return True, None  # Allow fallback to CPU
    
    has_enough = info.free_mb >= required_mb
    
    if not has_enough:
        logger.error(
            f"GPU {device_id}: Insufficient memory. "
            f"Required: {required_mb}MB, Available: {info.free_mb:.0f}MB"
        )
    else:
        logger.info(
            f"GPU {device_id}: Memory check passed. "
            f"Free: {info.free_mb:.0f}MB (required {required_mb}MB)"
        )
    
    return has_enough, info

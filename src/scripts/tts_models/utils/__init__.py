"""TTS Models utilities."""
from .gpu_utils import get_gpu_memory_info, check_gpu_available_memory, GPUMemoryInfo

__all__ = ['get_gpu_memory_info', 'check_gpu_available_memory', 'GPUMemoryInfo']

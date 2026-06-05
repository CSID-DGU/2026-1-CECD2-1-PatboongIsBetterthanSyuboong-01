"""
Segmentation preprocessing utilities leveraging the CheXmask HybridGNet models.

This package hosts helper modules that wrap the original CheXmask code so that
we can generate lung/heart masks and apply ROI-based masking before any model
training or evaluation steps.
"""

from .hybridgnet_segmenter import HybridGNetSegmenter  # noqa: F401


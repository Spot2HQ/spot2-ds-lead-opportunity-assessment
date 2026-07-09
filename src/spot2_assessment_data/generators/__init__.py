"""Synthetic data generators — one module per table.

All public generators (leads, spots, spot_attributes, inquiries,
market_context, availability_snapshot) are re-exported here.

``generate_outcomes`` is intentionally NOT exported — it produces
the hidden evaluation table and must not be visible to candidates.
"""

from spot2_assessment_data.generators._availability import generate_availability_snapshot
from spot2_assessment_data.generators._inquiries import generate_inquiries
from spot2_assessment_data.generators._leads import generate_leads
from spot2_assessment_data.generators._market_context import generate_market_context
from spot2_assessment_data.generators._spot_attributes import generate_spot_attributes
from spot2_assessment_data.generators._spots import generate_spots

__all__ = [
    "generate_availability_snapshot",
    "generate_inquiries",
    "generate_leads",
    "generate_market_context",
    "generate_spot_attributes",
    "generate_spots",
]

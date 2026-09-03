"""tripadvisor-intel: Agentic TripAdvisor data acquisition and reasoning engine."""

from .models import (
    PlaceSummary,
    PlaceDetail,
    Subrating,
    PriceRange,
    ReviewItem,
    ReviewAuthor,
    ReviewDistribution,
    DossierReport,
    RedFlagItem,
    PersonaFitScore,
)
from .client import TripAdvisorClient
from .doctor import run_doctor
from .reasoning.engine import generate_dossier

__version__ = "1.0.0"

__all__ = [
    "TripAdvisorClient",
    "PlaceSummary",
    "PlaceDetail",
    "Subrating",
    "PriceRange",
    "ReviewItem",
    "ReviewAuthor",
    "ReviewDistribution",
    "DossierReport",
    "RedFlagItem",
    "PersonaFitScore",
    "generate_dossier",
    "run_doctor",
]

"""Complaint and demographic models for the deep research pipeline."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AgeGroup(str, Enum):
    """9 medical age bands for demographic stratification."""

    NEONATAL = "neonatal"  # 0-28 days
    INFANT = "infant"  # 1-12 months
    TODDLER_PRESCHOOL = "toddler_preschool"  # 1-5 years
    SCHOOL_AGE = "school_age"  # 6-11 years
    ADOLESCENT = "adolescent"  # 12-17 years
    YOUNG_ADULT = "young_adult"  # 18-39 years
    MIDDLE_AGE = "middle_age"  # 40-64 years
    OLDER_ADULT = "older_adult"  # 65-79 years
    GERIATRIC = "geriatric"  # 80+ years


class TraumaAgeGroup(str, Enum):
    """4 consolidated trauma age groups."""

    PRE_MOBILE_PEDIATRIC = "pre_mobile_pediatric"  # Neonatal, Infant, Toddler <3y
    ACTIVE_PEDIATRIC = "active_pediatric"  # Toddler 3-5y, School Age, Adolescent
    WORKING_ADULT = "working_adult"  # Young Adult, Middle Age
    FRAGILE_ADULT = "fragile_adult"  # Older Adult, Geriatric


class Sex(str, Enum):
    """Biological sex for demographic stratification."""

    MALE = "male"
    FEMALE = "female"


class SpecialPopulation(str, Enum):
    """Special populations requiring modified clinical approaches."""

    PREGNANCY = "pregnancy"
    POSTPARTUM = "postpartum"
    IMMUNOCOMPROMISED = "immunocompromised"
    CHRONIC_DISEASE = "chronic_disease"  # DM, CKD, cirrhosis, CHF, COPD
    SUBSTANCE_USE = "substance_use"
    PSYCHIATRIC_COMORBIDITY = "psychiatric_comorbidity"
    SOCIAL_DETERMINANTS = "social_determinants"  # Homeless, communication barriers
    PALLIATIVE_CARE = "palliative_care"


class ComplaintType(str, Enum):
    """Type of medical complaint - determines pipeline routing."""

    MEDICAL = "medical"
    TRAUMA = "trauma"


class ComplaintInput(BaseModel):
    """Input model for a medical complaint to research."""

    complaint: str = Field(..., description="The medical complaint name (e.g., 'chest pain')")
    category: Optional[str] = Field(None, description="Clinical category (e.g., 'cardiovascular')")
    subcategory: Optional[str] = Field(None, description="Clinical subcategory (e.g., 'cardiac')")
    complaint_type: ComplaintType = Field(
        default=ComplaintType.MEDICAL,
        description="Type of complaint - medical or trauma"
    )

    @property
    def normalized_name(self) -> str:
        """Return normalized complaint name for file/directory naming."""
        return self.complaint.lower().replace(" ", "_").replace("-", "_")

    def to_display_name(self) -> str:
        """Return human-readable complaint name."""
        return self.complaint.title()


class DemographicCombination(BaseModel):
    """Represents a specific demographic combination for template generation."""

    age_group: AgeGroup
    sex: Sex
    special_population: Optional[SpecialPopulation] = None

    @property
    def identifier(self) -> str:
        """Return unique identifier for this demographic combination."""
        base = f"{self.age_group.value}_{self.sex.value}"
        if self.special_population:
            base += f"_{self.special_population.value}"
        return base

    @property
    def display_name(self) -> str:
        """Return human-readable name for this demographic."""
        age_display = {
            AgeGroup.NEONATAL: "Neonatal (0-28 days)",
            AgeGroup.INFANT: "Infant (1-12 months)",
            AgeGroup.TODDLER_PRESCHOOL: "Toddler/Preschool (1-5 years)",
            AgeGroup.SCHOOL_AGE: "School Age (6-11 years)",
            AgeGroup.ADOLESCENT: "Adolescent (12-17 years)",
            AgeGroup.YOUNG_ADULT: "Young Adult (18-39 years)",
            AgeGroup.MIDDLE_AGE: "Middle Age (40-64 years)",
            AgeGroup.OLDER_ADULT: "Older Adult (65-79 years)",
            AgeGroup.GERIATRIC: "Geriatric (80+ years)",
        }
        sex_display = "Male" if self.sex == Sex.MALE else "Female"
        base = f"{age_display[self.age_group]} - {sex_display}"
        if self.special_population:
            pop_display = self.special_population.value.replace("_", " ").title()
            base += f" ({pop_display})"
        return base


class TraumaDemographicCombination(BaseModel):
    """Represents a trauma demographic combination (4 age groups)."""

    trauma_age_group: TraumaAgeGroup
    sex: Sex

    @property
    def identifier(self) -> str:
        """Return unique identifier for this trauma demographic."""
        return f"{self.trauma_age_group.value}_{self.sex.value}"

    @property
    def display_name(self) -> str:
        """Return human-readable name for this trauma demographic."""
        age_display = {
            TraumaAgeGroup.PRE_MOBILE_PEDIATRIC: "Pre-Mobile Pediatric",
            TraumaAgeGroup.ACTIVE_PEDIATRIC: "Active Pediatric",
            TraumaAgeGroup.WORKING_ADULT: "Working-Age Adult",
            TraumaAgeGroup.FRAGILE_ADULT: "Fragile Adult",
        }
        sex_display = "Male" if self.sex == Sex.MALE else "Female"
        return f"{age_display[self.trauma_age_group]} - {sex_display}"


# Mapping from trauma groups to constituent medical age bands
TRAUMA_TO_MEDICAL_AGE_MAPPING: dict[TraumaAgeGroup, list[AgeGroup]] = {
    TraumaAgeGroup.PRE_MOBILE_PEDIATRIC: [
        AgeGroup.NEONATAL,
        AgeGroup.INFANT,
        AgeGroup.TODDLER_PRESCHOOL,  # <3y portion
    ],
    TraumaAgeGroup.ACTIVE_PEDIATRIC: [
        AgeGroup.TODDLER_PRESCHOOL,  # 3-5y portion
        AgeGroup.SCHOOL_AGE,
        AgeGroup.ADOLESCENT,
    ],
    TraumaAgeGroup.WORKING_ADULT: [
        AgeGroup.YOUNG_ADULT,
        AgeGroup.MIDDLE_AGE,
    ],
    TraumaAgeGroup.FRAGILE_ADULT: [
        AgeGroup.OLDER_ADULT,
        AgeGroup.GERIATRIC,
    ],
}

"""Pydantic models for the structured resume JSON. Every value comes from extraction; missing => None/[]."""
from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

Status = Literal["verified", "needs_review"]
_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FieldTrace(_M):
    value: Any = None
    source_page: Optional[int] = None
    source_text: Optional[str] = None
    method: str = "rule_based"
    rule: Optional[str] = None
    confidence: float = Field(0.0, ge=0, le=1)
    status: Status = "needs_review"


class EntryBase(_M):
    source_page: Optional[int] = None
    source_text: Optional[str] = None
    confidence: float = Field(0.0, ge=0, le=1)
    status: Status = "needs_review"


class DocumentInfo(_M):
    filename: Optional[str] = None
    file_type: Optional[str] = None
    document_type: Optional[str] = None
    total_pages: int = 0
    extraction_method: Optional[str] = None
    ocr_used: bool = False
    processing_time_ms: Optional[int] = None


class PersonalInformation(_M):
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    address: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    website: Optional[str] = None

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        if v and not _EMAIL.match(v):
            raise ValueError("invalid email")
        return v


class SocialProfiles(_M):
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    kaggle: Optional[str] = None
    leetcode: Optional[str] = None
    hackerrank: Optional[str] = None
    other: list[str] = []


class EducationEntry(EntryBase):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    graduation_year: Optional[int] = None
    cgpa: Optional[float] = None
    cgpa_scale: Optional[float] = None
    percentage: Optional[float] = None
    grade: Optional[str] = None
    relevant_coursework: list[str] = []


class ExperienceEntry(EntryBase):
    job_title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    responsibilities: list[str] = []
    achievements: list[str] = []
    technologies: list[str] = []


class Skills(_M):
    programming_languages: list[str] = []
    frameworks: list[str] = []
    libraries: list[str] = []
    databases: list[str] = []
    developer_tools: list[str] = []
    cloud: list[str] = []
    ai_ml: list[str] = []
    data_analytics: list[str] = []
    operating_systems: list[str] = []
    soft_skills: list[str] = []
    other: list[str] = []
    # Technologies mentioned in experience/projects but NOT listed in a skills section (unconfirmed).
    inferred_from_context: list[str] = []


class ProjectEntry(EntryBase):
    name: Optional[str] = None
    description: Optional[str] = None
    bullet_points: list[str] = []
    technologies: list[str] = []
    url: Optional[str] = None
    github_url: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    role: Optional[str] = None
    achievements: list[str] = []


class CertificationEntry(EntryBase):
    name: Optional[str] = None
    issuer: Optional[str] = None
    issue_date: Optional[str] = None
    expiration_date: Optional[str] = None
    credential_id: Optional[str] = None
    credential_url: Optional[str] = None


class AchievementEntry(EntryBase):
    title: Optional[str] = None
    description: Optional[str] = None
    issuer: Optional[str] = None
    date: Optional[str] = None
    category: Optional[str] = None


class PublicationEntry(EntryBase):
    title: Optional[str] = None
    publisher: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None


class LanguageEntry(EntryBase):
    name: Optional[str] = None
    proficiency: Optional[str] = None


class GenericEntry(EntryBase):
    title: Optional[str] = None
    organization: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


class AdditionalInfo(_M):
    section: str
    text: str
    source_page: Optional[int] = None


class UnclassifiedText(_M):
    text: str
    source_page: Optional[int] = None
    reason: Optional[str] = None


class ExtractionMetadata(_M):
    pages_processed: int = 0
    ocr_pages: list[int] = []
    ocr_mean_confidence: Optional[float] = None
    warnings: list[str] = []
    missing_fields: list[str] = []
    needs_review: list[str] = []
    extracted_field_count: int = 0
    section_counts: dict[str, int] = {}
    field_traces: dict[str, FieldTrace] = {}


class ResumeResult(_M):
    document: DocumentInfo = DocumentInfo()
    personal_information: PersonalInformation = PersonalInformation()
    social_profiles: SocialProfiles = SocialProfiles()
    education: list[EducationEntry] = []
    experience: list[ExperienceEntry] = []
    skills: Skills = Skills()
    projects: list[ProjectEntry] = []
    certifications: list[CertificationEntry] = []
    achievements: list[AchievementEntry] = []
    publications: list[PublicationEntry] = []
    languages: list[LanguageEntry] = []
    volunteer_experience: list[GenericEntry] = []
    training: list[GenericEntry] = []
    awards: list[AchievementEntry] = []
    interests: list[str] = []
    additional_information: list[AdditionalInfo] = []
    unclassified_text: list[UnclassifiedText] = []
    extraction_metadata: ExtractionMetadata = ExtractionMetadata()

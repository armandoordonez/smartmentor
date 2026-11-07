"""Perfil y hoja de vida (E2, E2b, E15): del contrato al formulario y de vuelta."""

from clients.base import SmartMentorClient
from clients.models import Language, Profile, ProfileUpdate
from components.resume_form import ResumeValues


def resume_values(profile: Profile) -> ResumeValues:
    return ResumeValues(
        education_level=profile.education_level,
        qualification_title=profile.qualification_title or "",
        job_title=profile.job_title or "",
        experience_band=profile.experience_band,
        tools=tuple(profile.tools),
        languages=tuple((language.code, language.cefr_level) for language in profile.languages),
    )


def save_description(client: SmartMentorClient, profile: Profile, description: str) -> Profile:
    """Guarda la descripción conservando la hoja de vida que ya tuviera (`PUT /me/profile`)."""
    update = _update_from(profile)
    update.description = description.strip()
    return client.update_profile(update)


def save_resume(client: SmartMentorClient, profile: Profile, values: ResumeValues) -> Profile:
    """Guarda la hoja de vida conservando la descripción."""
    update = _update_from(profile)
    _apply_resume(update, values)
    return client.update_profile(update)


def save_profile(
    client: SmartMentorClient, profile: Profile, description: str, values: ResumeValues
) -> Profile:
    """Guarda la descripción y la hoja de vida en una sola operación (E15)."""
    update = _update_from(profile)
    update.description = description.strip()
    _apply_resume(update, values)
    return client.update_profile(update)


def _apply_resume(update: ProfileUpdate, values: ResumeValues) -> None:
    update.education_level = values.education_level
    update.qualification_title = values.qualification_title or None
    update.job_title = values.job_title or None
    update.experience_band = values.experience_band
    update.tools = list(values.tools)
    update.languages = [Language(code=code, cefr_level=level) for code, level in values.languages]


def _update_from(profile: Profile) -> ProfileUpdate:
    return ProfileUpdate(
        description=profile.description,
        education_level=profile.education_level,
        qualification_title=profile.qualification_title,
        job_title=profile.job_title,
        experience_band=profile.experience_band,
        tools=list(profile.tools),
        languages=list(profile.languages),
    )

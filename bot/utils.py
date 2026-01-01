import re
from typing import Set


# Articles/prepositions to skip (lowercase only, unless first word)
SKIP_WORDS = {"a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or", "but"}


def generate_acronym(name: str) -> str:
    """
    Generate acronym from game name.
    
    Examples:
        "Steal a Brainrot" -> "SaB"
        "The Great Escape" -> "TGE"
        "Rise of Kingdoms" -> "RoK"
    """
    words = name.split()
    if not words:
        return ""
    
    acronym_parts = []
    for i, word in enumerate(words):
        # Clean word of non-alphanumeric chars
        clean_word = re.sub(r'[^a-zA-Z0-9]', '', word)
        if not clean_word:
            continue
            
        # First word always included
        if i == 0:
            acronym_parts.append(clean_word[0].upper())
        # Skip articles/prepositions but keep their lowercase letter
        elif word.lower() in SKIP_WORDS:
            acronym_parts.append(clean_word[0].lower())
        else:
            acronym_parts.append(clean_word[0].upper())
    
    return ''.join(acronym_parts)


def resolve_acronym_conflict(base_acronym: str, existing_acronyms: Set[str]) -> str:
    """
    If acronym exists, append incrementing number.
    
    Examples:
        "SaB" with {"SaB"} -> "SaB2"
        "SaB" with {"SaB", "SaB2"} -> "SaB3"
    """
    if base_acronym not in existing_acronyms:
        return base_acronym
    
    counter = 2
    while f"{base_acronym}{counter}" in existing_acronyms:
        counter += 1
    
    return f"{base_acronym}{counter}"


def format_channel_name(emoji: str, acronym: str, channel_name: str) -> str:
    """
    Format channel name with emoji and acronym prefix.
    
    Example: format_channel_name("💻", "SaB", "code-frontend") -> "💻-sab-code-frontend"
    """
    return f"{emoji}-{acronym.lower()}-{channel_name}"


def format_voice_channel_name(emoji: str, acronym: str, channel_name: str) -> str:
    """
    Format voice channel name.
    
    Example: format_voice_channel_name("🎙️", "SaB", "voice") -> "🎙️-sab-voice"
    """
    return f"{emoji}-{acronym.lower()}-{channel_name}"


def format_role_name(acronym: str, role_suffix: str) -> str:
    """
    Format game role name.
    
    Example: format_role_name("SaB", "Coder") -> "SaB-Coder"
    """
    return f"{acronym}-{role_suffix}"

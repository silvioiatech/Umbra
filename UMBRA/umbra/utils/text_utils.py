"""
Text utilities for command processing and suggestion engine.

Provides Levenshtein distance calculation and text normalization
for near-miss command suggestions.
"""



def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate the Levenshtein distance between two strings.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Levenshtein distance (minimum number of edits needed)
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Calculate costs for insertion, deletion, and substitution
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def normalize_command(command: str) -> str:
    """
    Normalize a command string for comparison.

    Args:
        command: Command string to normalize

    Returns:
        Normalized command string
    """
    return command.lower().strip()


def find_similar_commands(
    input_command: str,
    available_commands: list[str],
    max_distance: int = 2,
    min_length: int = 3
) -> list[str]:
    """
    Find commands similar to the input command using Levenshtein distance.

    Args:
        input_command: Command that was not found
        available_commands: List of available command names
        max_distance: Maximum Levenshtein distance to consider (default: 2)
        min_length: Minimum length of command to consider for suggestions (default: 3)

    Returns:
        List of similar commands sorted by distance
    """
    if len(input_command) < min_length:
        return []

    normalized_input = normalize_command(input_command)
    suggestions = []

    for command in available_commands:
        normalized_command = normalize_command(command)

        # Skip if command is too short
        if len(normalized_command) < min_length:
            continue

        distance = levenshtein_distance(normalized_input, normalized_command)

        if distance <= max_distance and distance > 0:  # Don't suggest exact matches
            suggestions.append((command, distance))

    # Sort by distance (closest first) and return command names
    suggestions.sort(key=lambda x: x[1])
    return [command for command, _ in suggestions]


def get_available_commands_from_registry() -> list[str]:
    """
    Get list of available commands from the command registry.

    Returns:
        List of command names and text triggers
    """
    try:
        from ..core.command_registry import get_registry

        registry = get_registry()
        commands = set()

        # Add command names
        for spec in registry.get_all_commands():
            commands.add(spec.name)

            # Add text triggers
            for trigger in spec.text_triggers:
                commands.add(trigger)

        # Add common system commands
        system_commands = [
            "help", "start", "status", "health", "uptime", "metrics",
            "finance", "receipt", "expense", "budget"
        ]
        commands.update(system_commands)

        return list(commands)
    except ImportError:
        # Fallback if command registry is not available
        return [
            "help", "start", "status", "health", "uptime", "metrics",
            "finance", "receipt", "expense", "budget"
        ]


def suggest_command(input_command: str) -> str | None:
    """
    Suggest a similar command for a given input.

    Args:
        input_command: Command that was not recognized

    Returns:
        Suggested command or None if no good suggestion found
    """
    available_commands = get_available_commands_from_registry()
    similar_commands = find_similar_commands(input_command, available_commands)

    if similar_commands:
        return similar_commands[0]  # Return the closest match

    return None


class TextProcessor:
    """
    Text processing utility class that provides text manipulation and analysis methods.

    This class wraps the utility functions in this module to provide a convenient
    object-oriented interface for text processing operations.
    """

    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """Calculate the Levenshtein distance between two strings."""
        return levenshtein_distance(s1, s2)

    @staticmethod
    def normalize_command(command: str) -> str:
        """Normalize a command string for comparison."""
        return normalize_command(command)

    @staticmethod
    def find_similar_commands(
        input_command: str,
        available_commands: list[str],
        max_distance: int = 2,
        min_length: int = 3
    ) -> list[str]:
        """Find commands similar to the input command using Levenshtein distance."""
        return find_similar_commands(input_command, available_commands, max_distance, min_length)

    @staticmethod
    def suggest_command(input_command: str) -> str | None:
        """Suggest a similar command for a given input."""
        return suggest_command(input_command)

    @staticmethod
    def get_available_commands() -> list[str]:
        """Get list of available commands from the command registry."""
        return get_available_commands_from_registry()

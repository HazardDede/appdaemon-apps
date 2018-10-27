import re


def try_parse_int(candidate):
    """
    Convert the given candidate to int. If it fails None is returned.

    Example:

        >>> type(try_parse_int(1))  # int will still be int
        <class 'int'>
        >>> type(try_parse_int("15"))
        <class 'int'>
        >>> print(try_parse_int("a"))
        None

    Args:
        candidate: The candidate to convert.

    Returns:
        Returns the converted candidate if convertible; otherwise None.

    """
    try:
        return int(candidate)
    except (ValueError, TypeError):
        return None


def parse_duration_literal(literal):
    """
    Converts duration literals as '1m', '1h', and so on to an actual duration in seconds.
    Supported are 's' (seconds), 'm' (minutes), 'h' (hours), 'd' (days) and 'w' (weeks).

    Examples:

        >>> parse_duration_literal(60)  # Int will be interpreted as seconds
        60
        >>> parse_duration_literal('10')  # Any int convertible will be interpreted as seconds
        10
        >>> parse_duration_literal('20s')  # Seconds literal
        20
        >>> parse_duration_literal('2m')  # Minutes literal
        120
        >>> parse_duration_literal('1h')  # Hours literal
        3600
        >>> parse_duration_literal('1d')  # Days literal
        86400
        >>> parse_duration_literal('1w')  # Weeks literal
        604800
        >>> parse_duration_literal('invalid')  # Invalid will raise an error
        Traceback (most recent call last):
        ...
        TypeError: Interval 'invalid' is not a valid literal

    Args:
        literal: Literal to parse.

    Returns:
        Returns the converted literal's duration in seconds. If conversion is not possible
        an exception is raised.
    """
    try:
        # if successful we got seconds
        return int(literal)
    except:  # pylint: disable=broad-except
        # We have to check for s, m, h, d, w suffix
        seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
        # Remove all non-alphanumeric letters
        s = re.sub('[^0-9a-zA-Z]+', '', str(literal))
        value_str, unit = s[:-1], s[-1].lower()
        value = try_parse_int(value_str)
        if value is None or unit not in seconds_per_unit:
            raise TypeError("Interval '{}' is not a valid literal".format(literal))
        return value * seconds_per_unit[unit]

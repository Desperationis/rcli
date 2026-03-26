from datetime import datetime


def format_size(size_bytes):
    """Format a byte count into a human-readable string."""
    if size_bytes is None or size_bytes < 0:
        return "unknown"

    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size_bytes)

    for unit in units:
        if value < 1024:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{value:.1f} PB"


def format_date(iso_str):
    """Format an ISO 8601 date string into 'YYYY-MM-DD HH:MM'."""
    if not iso_str or not isinstance(iso_str, str):
        return "unknown"

    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return "unknown"

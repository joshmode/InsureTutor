"""Match the bounded deadline advertised by the application's health contract."""

def request_timeout(health: dict) -> float:
    value = health.get("request_timeout_seconds", 195)
    if type(value) in (int, float) and 1 <= value <= 640:
        return float(value)
    return 195.0

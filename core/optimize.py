import re

SLUGS = {
    "Sodium": "sodium",
    "Embeddium": "embeddium",
    "Rubidium": "rubidium",
    "Vulkan": "vulkanmod",
}

RULES = (
    ("Embeddium", {"forge", "fabric", "neoforge"}, "1.16.5", "1.21.4"),
    ("Rubidium", {"forge", "neoforge"}, "1.16.5", "1.20.1"),
    ("Sodium", {"fabric", "neoforge"}, "1.16.3", "26.3"),
    ("Vulkan", {"fabric"}, "1.18.2", "26.1.2"),
    ("OptiFine", {"forge"}, "1.12.2", "26.2"),
)

def parse(version):
    parts = re.findall(r"\d+", str(version or ""))
    return tuple(int(part) for part in parts) if parts else (0,)

def options(loader, version):
    loader = str(loader or "").strip().lower()
    current = parse(version)

    if current == (0,):
        return []

    return [
        name
        for name, loaders, minimum, maximum in RULES
        if (
            loader in loaders
            and parse(minimum) <= current <= parse(maximum)
        )
    ]
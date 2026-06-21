def matches_magic(entity: dict, magic: int) -> bool:
    entity_magic = entity.get("magic")
    if entity_magic is None:
        return False
    try:
        return int(entity_magic) == int(magic)
    except (TypeError, ValueError):
        return str(entity_magic) == str(magic)

def matches_magic(entity: dict, magic: int) -> bool:
    magic_str = str(magic)
    for key in ("magic", "label"):
        entity_magic = entity.get(key)
        if entity_magic is None:
            continue
        try:
            if int(entity_magic) == int(magic):
                return True
        except (TypeError, ValueError):
            if str(entity_magic) == magic_str:
                return True
    return False

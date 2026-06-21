def filter_by_targets(entities: list[dict], target_ids: list[str]) -> list[dict]:
    if not target_ids:
        return entities

    allowed = {str(item_id) for item_id in target_ids}
    return [
        entity for entity in entities
        if str(entity.get("id", "")) in allowed
    ]

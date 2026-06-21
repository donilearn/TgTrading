# MetaTrader magic is int32
MAX_MAGIC = 2_147_483_647


def magic_from_group_id(chat_id: int) -> int:
    """Derive magic from group ID — last digits that fit in int32."""
    digits = str(abs(chat_id))

    magic = int(digits)
    while magic > MAX_MAGIC:
        digits = digits[1:]
        magic = int(digits)

    return magic if magic > 0 else 1


def group_magic_map(group_ids: list[int]) -> dict[int, int]:
    return {chat_id: magic_from_group_id(chat_id) for chat_id in group_ids}

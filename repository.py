import aiosqlite

DB = "database.db"


async def add_like(from_user: int, to_user: int) -> bool:
    """
    Добавляет лайк.
    Возвращает True, если это взаимный лайк (match).
    """
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO likes (from_user, to_user) VALUES (?, ?)",
            (from_user, to_user)
        )

        cursor = await db.execute(
            "SELECT 1 FROM likes WHERE from_user = ? AND to_user = ?",
            (to_user, from_user)
        )
        match = await cursor.fetchone()
        await db.commit()

    return bool(match)


async def get_next_profile(viewer_id: int):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("""
            SELECT id, name, age, city, goal, photo_id
            FROM profiles
            WHERE id != ?
              AND id NOT IN (
                  SELECT to_user FROM likes WHERE from_user = ?
              )
            ORDER BY RANDOM()
            LIMIT 1
        """, (viewer_id, viewer_id))

        return await cursor.fetchone()


async def get_profile(user_id: int):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "SELECT name, age, city, goal, photo_id FROM profiles WHERE id = ?",
            (user_id,)
        )
        return await cursor.fetchone()

from app.services.ui import clean_ui_text


ACTION_LABELS = {
    "ban": "🚫 Бан", "unban": "✅ Разбан", "mute": "🔇 Мут", "unmute": "🔊 Размут",
    "kick": "🚪 Кик", "warn": "⚠️ Предупреждение", "unwarn": "↩️ Снятие предупреждения",
    "auto_mute": "🤖 Автоматический мут", "delete_message": "🗑 Удаление сообщения",
    "lockdown_on": "🔒 Локдаун включён", "lockdown_off": "🔓 Локдаун выключен",
    "note_add": "📝 Заметка добавлена", "note_delete": "🗑 Заметка удалена",
}


def render_log(group, row) -> str:
    label = clean_ui_text(ACTION_LABELS.get(row.action, f"⚙️ {row.action}"))
    lines = [
        label,
        f"Группа: {clean_ui_text(group.title)}",
        f"Администратор: {row.actor_telegram_id}",
    ]
    if row.target_telegram_id is not None:
        lines.append(f"Пользователь: {row.target_telegram_id}")
    if row.reason:
        lines.append(f"Причина: {clean_ui_text(row.reason)}")
    lines.append(f"Событие: LOG-{row.id}")
    return "\n".join(lines)

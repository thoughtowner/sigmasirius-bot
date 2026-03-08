from ..model.models import Status


def parse_status(status):
    # Accept either Status enum or string
    if isinstance(status, Status):
        value = status
    else:
        try:
            value = Status(status)
        except Exception:
            # fallback: compare raw string
            value = None

    if value == Status.NOT_COMPLETED or (value is None and status == 'not_completed'):
        return '🔴 НЕ ВЫПОЛНЕНА'
    if value == Status.IN_PROCESSING or (value is None and status == 'in_processing'):
        return '🟡 В ОБРАБОТКЕ'
    if value == Status.COMPLETED or (value is None and status == 'completed'):
        return '🟢 ВЫПОЛНЕНА'
    if value == Status.CANCELELLED or (value is None and status == 'cancelled'):
        return '⚠️ ОТМЕНЕНА'

    return str(status)
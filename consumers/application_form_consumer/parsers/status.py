from ..model.models import ApplicationFormStatus


def parse_status(status):
    # Accept either Status enum or string
    if isinstance(status, ApplicationFormStatus):
        value = status
    else:
        try:
            value = ApplicationFormStatus(status)
        except Exception:
            # fallback: compare raw string
            value = None

    if value == ApplicationFormStatus.NOT_COMPLETED or (value is None and status == 'not_completed'):
        return '🔴 НЕ ВЫПОЛНЕНА'
    if value == ApplicationFormStatus.IN_PROCESSING or (value is None and status == 'in_processing'):
        return '🟡 В ОБРАБОТКЕ'
    if value == ApplicationFormStatus.COMPLETED or (value is None and status == 'completed'):
        return '🟢 ВЫПОЛНЕНА'
    if value == ApplicationFormStatus.CANCELELLED or (value is None and status == 'cancelled'):
        return '⚠️ ОТМЕНЕНА'

    return str(status)
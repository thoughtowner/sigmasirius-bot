def parse_status(status):
    if status == 'not_completed':
        status = '🔴 НЕ ВЫПОЛНЕНА'
    elif status == 'in_processing':
        status = '🟡 В ОБРАБОТКЕ'
    elif status == 'completed':
        status = '🟢 ВЫПОЛНЕНА'
    elif status == 'cancelled':
        status = '⚠️ ОТМЕНЕНА'
    return status
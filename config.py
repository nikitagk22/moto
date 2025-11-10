"""Конфигурация для диагностики Harley-Davidson через J2534"""

import os

# Путь к J2534 DLL (настройте под вашу систему)
J2534_DLL_PATH = r"C:\Program Files (x86)\OpenECU\OpenPort 2.0\drivers\openport 2.0\openport.dll"

# Альтернативные пути (будут проверены автоматически)
ALTERNATIVE_DLL_PATHS = [
    r"C:\Program Files\Tactrix\OpenPort 2.0\openport.dll",
    r"C:\Program Files (x86)\Tactrix\OpenPort 2.0\openport.dll",
    r"C:\Program Files (x86)\OpenECU\OpenPort 2.0\drivers\openport 2.0\openport.dll",
    r"openport.dll"  # Если DLL в PATH
]

def find_dll_path():
    """Автоматический поиск DLL в стандартных путях"""
    # Проверка основного пути
    if os.path.exists(J2534_DLL_PATH):
        return J2534_DLL_PATH
    
    # Проверка альтернативных путей
    for path in ALTERNATIVE_DLL_PATHS:
        if os.path.exists(path):
            return path
    
    return None  # DLL не найдена

# CAN параметры для HDLAN (Harley-Davidson Local Area Network)
CAN_PROTOCOL = 'ISO15765'  # ISO 15765-4 (DoCAN)
CAN_BAUDRATE = 500000  # 500 кбит/с
CAN_FLAGS = 0x00000000

# UDS адреса (стандартные для автомобильной диагностики)
UDS_REQUEST_ID = 0x7E0  # Физический адрес запроса к ЭБУ
UDS_RESPONSE_ID = 0x7E8  # Физический адрес ответа от ЭБУ

# Альтернативные адреса для Harley (могут потребоваться)
# UDS_REQUEST_ID = 0x18DA10F1  # Extended ID
# UDS_RESPONSE_ID = 0x18DAF110  # Extended ID

# ISO-TP параметры
ISO_TP_BS = 0x00  # Block Size (0 = непрерывная передача)
ISO_TP_STMIN = 0x00  # Separation Time minimum (0 мс)
ISO_TP_TIMEOUT = 1000  # Тайм-аут ожидания кадра (мс)

# UDS параметры
UDS_SESSION_TIMEOUT = 5000  # Тайм-аут диагностической сессии (мс)
TESTER_PRESENT_INTERVAL = 2.0  # Интервал отправки TesterPresent (сек)

# DIDs для диагностики Harley-Davidson
DIDS = {
    'VIN': 0xF190,  # Vehicle Identification Number (стандартный)
    'ECU_INFO': 0xF191,
    'CALIBRATION_ID': 0xF192,
    'ECU_SERIAL': 0xF18C,
    'DIAGNOSTIC_ID': 0xF186,
    # Одометр - точный DID неизвестен, будем сканировать
    'ODOMETER_CANDIDATES': list(range(0xF191, 0xF1A0))  # Диапазон для поиска
}

# Режимы логирования
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR
LOG_TO_FILE = True
LOG_FILE = 'harley_diagnostics.log'

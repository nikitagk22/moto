"""
Harley-Davidson XG750A Diagnostic Tool

Комплексная система для диагностики Harley-Davidson XG750A
через Tactrix OpenPort 2.0 с использованием J2534 PassThru API.

Основные возможности:
- Чтение VIN (идентификационного номера)
- Сканирование DIDs для поиска одометра (пробега)
- Чтение информации о ЭБУ
- Полная поддержка UDS (ISO 14229)
- Реализация ISO-TP (ISO 15765-2)
- Низкоуровневый доступ через J2534

Использование:
    from harley_diagnostics import HarleyDiagnostics
    
    with HarleyDiagnostics() as diag:
        vin = diag.read_vin()
        print(f"VIN: {vin}")

Автор: Emergent AI
Версия: 1.0.0
Лицензия: MIT
"""

__version__ = '1.0.0'
__author__ = 'Emergent AI'
__license__ = 'MIT'

# Экспорт основных классов для удобного импорта
from harley_diagnostics import HarleyDiagnostics
from j2534_wrapper import J2534Wrapper, J2534Exception
from isotp_handler import ISOTPHandler, ISOTPException
from uds_client import UDSClient, UDSException

__all__ = [
    'HarleyDiagnostics',
    'J2534Wrapper',
    'J2534Exception',
    'ISOTPHandler',
    'ISOTPException',
    'UDSClient',
    'UDSException',
]

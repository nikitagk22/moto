#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Пример использования Harley Diagnostics в Python коде

Этот файл демонстрирует, как использовать модули диагностики
программно в ваших собственных Python скриптах.
"""

import sys
import os

# Добавление текущей директории в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harley_diagnostics import HarleyDiagnostics
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def example_basic_usage():
    """Базовый пример: чтение VIN"""
    print("\n" + "="*60)
    print("ПРИМЕР 1: Базовое использование - чтение VIN")
    print("="*60)
    
    # Создание экземпляра диагностики
    diag = HarleyDiagnostics()
    
    try:
        # Подключение
        if diag.connect():
            # Чтение VIN
            vin = diag.read_vin()
            
            if vin:
                print(f"\n✅ Успешно! VIN: {vin}")
            else:
                print("\n❌ Не удалось прочитать VIN")
        else:
            print("\n❌ Не удалось подключиться к мотоциклу")
    
    finally:
        # Всегда отключаемся
        diag.disconnect()


def example_with_context_manager():
    """Пример с использованием контекстного менеджера"""
    print("\n" + "="*60)
    print("ПРИМЕР 2: Использование with (context manager)")
    print("="*60)
    
    # Использование with - автоматическое подключение и отключение
    with HarleyDiagnostics() as diag:
        # Чтение VIN
        vin = diag.read_vin()
        print(f"VIN: {vin}")
        
        # Чтение информации о ЭБУ
        ecu_info = diag.read_ecu_info()
        print("\nИнформация о ЭБУ:")
        for key, value in ecu_info.items():
            print(f"  {key}: {value}")


def example_scan_odometer():
    """Пример: сканирование для поиска одометра"""
    print("\n" + "="*60)
    print("ПРИМЕР 3: Сканирование DIDs для поиска одометра")
    print("="*60)
    
    with HarleyDiagnostics() as diag:
        # Сканирование диапазона DIDs
        results = diag.scan_for_odometer(start_did=0xF191, end_did=0xF19F)
        
        if results:
            print(f"\n✅ Найдено {len(results)} доступных DIDs:")
            
            for did, data in results.items():
                print(f"\n  DID 0x{did:04X}:")
                print(f"    Raw: {data['raw_data']}")
                print(f"    Возможные значения:")
                for interpretation in data['possible_values']:
                    print(f"      - {interpretation}")


def example_read_specific_odometer():
    """Пример: чтение конкретного DID одометра"""
    print("\n" + "="*60)
    print("ПРИМЕР 4: Чтение конкретного одометра")
    print("="*60)
    
    # Замените на ваш найденный DID
    ODOMETER_DID = 0xF192
    
    with HarleyDiagnostics() as diag:
        result = diag.read_odometer(ODOMETER_DID)
        
        if result:
            print(f"\n✅ Одометр (DID 0x{ODOMETER_DID:04X}):")
            print(f"  Raw: {result['raw_data']}")
            print(f"  Интерпретации:")
            for interpretation in result['interpretations']:
                print(f"    - {interpretation}")


def example_advanced_usage():
    """Продвинутый пример: использование низкоуровневых API"""
    print("\n" + "="*60)
    print("ПРИМЕР 5: Продвинутое использование - прямой доступ к UDS")
    print("="*60)
    
    from j2534_wrapper import J2534Wrapper
    from isotp_handler import ISOTPHandler
    from uds_client import UDSClient
    import config
    
    # Создание экземпляров вручную
    j2534 = J2534Wrapper()
    
    try:
        # Подключение
        j2534.open_device()
        j2534.connect_channel()
        j2534.set_flow_control_filter(
            config.UDS_REQUEST_ID,
            config.UDS_RESPONSE_ID
        )
        j2534.start_reading()
        
        # ISO-TP и UDS
        isotp = ISOTPHandler(
            j2534,
            config.UDS_REQUEST_ID,
            config.UDS_RESPONSE_ID
        )
        uds = UDSClient(isotp)
        
        # Переключение в расширенную сессию
        uds.diagnostic_session_control()
        
        # Запуск TesterPresent
        uds.start_tester_present()
        
        # Чтение VIN напрямую через UDS
        vin_data = uds.read_data_by_identifier(config.DIDS['VIN'])
        if vin_data:
            vin = vin_data.decode('ascii', errors='ignore')
            print(f"\n✅ VIN (прямой UDS запрос): {vin}")
        
        # Остановка TesterPresent
        uds.stop_tester_present()
    
    finally:
        # Отключение
        j2534.disconnect_channel()
        j2534.close_device()


def example_error_handling():
    """Пример: обработка ошибок"""
    print("\n" + "="*60)
    print("ПРИМЕР 6: Обработка ошибок")
    print("="*60)
    
    from j2534_wrapper import J2534Exception
    from uds_client import UDSException
    
    try:
        with HarleyDiagnostics() as diag:
            # Попытка прочитать несуществующий DID
            try:
                data = diag.uds.read_data_by_identifier(0xFFFF)
                print("Данные получены (неожиданно!)")
            except UDSException as e:
                print(f"⚠️ UDS ошибка (ожидаемо): {e}")
            
            # Чтение VIN
            vin = diag.read_vin()
            print(f"✅ VIN: {vin}")
    
    except J2534Exception as e:
        print(f"❌ J2534 ошибка: {e}")
    except Exception as e:
        print(f"❌ Общая ошибка: {e}")


def main():
    """Главная функция - запуск всех примеров"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║  Примеры использования Harley-Davidson Diagnostic Tool  ║")
    print("╚" + "="*58 + "╝")
    
    examples = [
        ("1", "Базовое использование", example_basic_usage),
        ("2", "Context Manager", example_with_context_manager),
        ("3", "Сканирование одометра", example_scan_odometer),
        ("4", "Чтение одометра", example_read_specific_odometer),
        ("5", "Продвинутое использование", example_advanced_usage),
        ("6", "Обработка ошибок", example_error_handling),
    ]
    
    print("\nДоступные примеры:")
    for num, desc, _ in examples:
        print(f"  {num}. {desc}")
    print("  0. Выход")
    
    while True:
        try:
            choice = input("\nВыберите пример (0-6): ").strip()
            
            if choice == "0":
                print("\n👋 До свидания!")
                break
            
            # Поиск и запуск примера
            found = False
            for num, desc, func in examples:
                if choice == num:
                    try:
                        func()
                        found = True
                    except KeyboardInterrupt:
                        print("\n\n⚠️ Прервано пользователем")
                        break
                    except Exception as e:
                        print(f"\n❌ Ошибка при выполнении примера: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    input("\nНажмите Enter для продолжения...")
                    break
            
            if not found:
                print("❌ Неверный выбор. Попробуйте снова.")
        
        except KeyboardInterrupt:
            print("\n\n👋 До свидания!")
            break


if __name__ == '__main__':
    main()

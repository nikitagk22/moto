#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для диагностики Harley-Davidson XG750A через Tactrix OpenPort 2.0

Использование:
    python main.py [--scan] [--read-vin] [--read-odometer DID] [--ecu-info] [--verbose]

Примеры:
    # Чтение VIN
    python main.py --read-vin
    
    # Сканирование DIDs для поиска одометра
    python main.py --scan
    
    # Чтение конкретного DID одометра
    python main.py --read-odometer 0xF192
    
    # Чтение информации о ЭБУ
    python main.py --ecu-info
    
    # Полная диагностика (все данные)
    python main.py --read-vin --scan --ecu-info --verbose
"""

import sys
import logging
import argparse
import os

# Добавление текущей директории в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from harley_diagnostics import HarleyDiagnostics


def setup_logging(verbose: bool = False):
    """Настройка логирования"""
    level = logging.DEBUG if verbose else getattr(logging, config.LOG_LEVEL)
    
    # Формат лога
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    # Добавление логирования в файл
    if config.LOG_TO_FILE:
        handlers.append(logging.FileHandler(config.LOG_FILE, encoding='utf-8'))
    
    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt=date_format,
        handlers=handlers
    )
    
    # Установка уровня для наших модулей
    for module in ['j2534_wrapper', 'isotp_handler', 'uds_client', 'harley_diagnostics']:
        logging.getLogger(module).setLevel(level)


def print_banner():
    """Вывод баннера"""
    banner = """
╭────────────────────────────────────────────────────────────╮
│     Harley-Davidson XG750A Diagnostic Tool                    │
│     Tactrix OpenPort 2.0 + J2534 + UDS/ISO-TP                │
│     © 2025                                                     │
╰────────────────────────────────────────────────────────────╯
    """
    print(banner)


def main():
    """ Главная функция"""
    parser = argparse.ArgumentParser(
        description='Harley-Davidson XG750A Diagnostic Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--read-vin', action='store_true',
                       help='Читать VIN (идентификационный номер)')
    
    parser.add_argument('--scan', action='store_true',
                       help='Сканировать DIDs для поиска одометра')
    
    parser.add_argument('--read-odometer', type=str, metavar='DID',
                       help='Читать одометр по конкретному DID (напр., 0xF192)')
    
    parser.add_argument('--ecu-info', action='store_true',
                       help='Читать информацию о ЭБУ')
    
    parser.add_argument('--scan-range', nargs=2, metavar=('START', 'END'),
                       help='Диапазон сканирования DIDs (напр., 0xF191 0xF1A0)')
    
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Подробный вывод (DEBUG)')
    
    parser.add_argument('--auto-detect', action='store_true',
                       help='Автоматический поиск рабочих CAN ID')
    
    parser.add_argument('--save-params', nargs=2, metavar=('DID', 'SCALE'),
                       help='Сохранить найденные параметры одометра (напр., 0xF192 0.1)')
    
    args = parser.parse_args()
    
    # Настройка логирования
    setup_logging(args.verbose)
    
    # Вывод баннера
    print_banner()
    
    # Если нет аргументов, выводим справку
    if not any([args.read_vin, args.scan, args.read_odometer, args.ecu_info]):
        parser.print_help()
        print("\n⚠️  Не указано ни одной операции. Используйте --help для помощи.")
        sys.exit(1)
    
    try:
        # Создание экземпляра диагностики
        diag = HarleyDiagnostics(auto_detect_can_ids=args.auto_detect)
        
        # Подключение
        if not diag.connect():
            print("\n❌ Не удалось подключиться к мотоциклу")
            print("Проверьте:")
            print("  1. Подключен ли Tactrix OpenPort 2.0 к компьютеру")
            print("  2. Подключен ли адаптер к OBD-II порту мотоцикла")
            print("  3. Включено ли зажигание")
            print(f"  4. Правильно ли указан путь к DLL в config.py: {config.J2534_DLL_PATH}")
            sys.exit(1)
        
        try:
            # Выполнение запрошенных операций
            
            # Чтение VIN
            if args.read_vin:
                vin = diag.read_vin()
                if vin:
                    print(f"\n🎯 VIN: {vin}")
            
            # Чтение информации о ЭБУ
            if args.ecu_info:
                ecu_info = diag.read_ecu_info()
                if ecu_info:
                    print("\n📊 Информация о ЭБУ:")
                    for key, value in ecu_info.items():
                        print(f"  {key}: {value}")
            
            # Сканирование DIDs
            if args.scan:
                if args.scan_range:
                    start = int(args.scan_range[0], 16)
                    end = int(args.scan_range[1], 16)
                else:
                    start = config.DIDS['ODOMETER_CANDIDATES'][0]
                    end = config.DIDS['ODOMETER_CANDIDATES'][-1]
                
                results = diag.scan_for_odometer(start, end)
                
                if results:
                    print(f"\n🔍 Результаты сканирования:")
                    for did, data in results.items():
                        print(f"\n  DID 0x{did:04X}:")
                        print(f"    Raw: {data['raw_data']}")
                        print(f"    Возможные значения:")
                        for interp in data['possible_values']:
                            print(f"      - {interp}")
            
            # Чтение конкретного одометра
            if args.read_odometer:
                did = int(args.read_odometer, 16)
                result = diag.read_odometer(did)
                
                if result:
                    print(f"\n📍 Одометр (DID 0x{did:04X}):")
                    print(f"  Raw: {result['raw_data']}")
                    print(f"  Возможные значения:")
                    for interp in result['interpretations']:
                        print(f"    - {interp}")
            
            # Сохранение найденных параметров
            if args.save_params:
                did = int(args.save_params[0], 16)
                scale = float(args.save_params[1])
                diag.save_discovered_params(did, scale)
            
            print("\n" + "="*60)
            print("✅ Диагностика завершена успешно!")
            print("="*60)
            
        finally:
            # Отключение
            diag.disconnect()
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
        sys.exit(0)
    
    except Exception as e:
        logging.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

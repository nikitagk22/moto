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
import traceback

# Добавление текущей директории в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from harley_diagnostics import HarleyDiagnostics
from error_handler import global_error_handler, ErrorSeverity, ErrorCategory, DiagnosticError
from diagnostic_report import global_diagnostic_reporter


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
    """Главная функция с улучшенной обработкой ошибок"""
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
    
    diag = None
    operation_successful = False
    
    try:
        logger.info("="*60)
        logger.info("ЗАПУСК ДИАГНОСТИЧЕСКОЙ СЕССИИ")
        logger.info("="*60)
        
        # Создание экземпляра диагностики
        diag = HarleyDiagnostics(auto_detect_can_ids=args.auto_detect)
        
        # Подключение с автоматическим retry и диагностикой
        logger.info("Попытка подключения к мотоциклу...")
        if not diag.connect():
            print("\n" + "="*60)
            print("❌ НЕ УДАЛОСЬ ПОДКЛЮЧИТЬСЯ К МОТОЦИКЛУ")
            print("="*60)
            print("\nПроверьте следующее:")
            print("  1. ✓ Tactrix OpenPort 2.0 подключен к USB порту компьютера")
            print("  2. ✓ 6-pin адаптер подключен к диагностическому порту мотоцикла")
            print("  3. ✓ Зажигание включено (двигатель НЕ запущен)")
            print("  4. ✓ Адаптер не используется другой программой")
            print(f"  5. ✓ Путь к DLL корректен: {config.J2534_DLL_PATH}")
            print("\nДополнительные действия:")
            print("  - Запустите: python check_system.py (для проверки системы)")
            print("  - Попробуйте с флагом: --auto-detect (автопоиск CAN ID)")
            print("  - Изучите логи в директории: logs/")
            
            # Генерация отчёта о проблеме
            if config.ENABLE_DIAGNOSTIC_REPORTS:
                print("\n📄 Генерация диагностического отчёта...")
                try:
                    report_path = global_diagnostic_reporter.generate_report(
                        global_error_handler,
                        connection_state={"status": "failed"},
                        operation_context={"operation": "connection", "auto_detect": args.auto_detect}
                    )
                    if report_path:
                        print(f"   Отчёт сохранён: {report_path}")
                except Exception as report_error:
                    logger.error(f"Ошибка генерации отчёта: {report_error}")
            
            print("="*60)
            sys.exit(1)
        
        try:
            # Выполнение запрошенных операций
            operations_performed = []
            
            # Чтение VIN
            if args.read_vin:
                logger.info("Выполнение операции: Чтение VIN")
                try:
                    vin = diag.read_vin()
                    if vin:
                        print(f"\n🎯 VIN: {vin}")
                        operations_performed.append(("read_vin", "success"))
                    else:
                        print("\n⚠️ Не удалось прочитать VIN")
                        operations_performed.append(("read_vin", "failed"))
                except Exception as e:
                    logger.error(f"Ошибка чтения VIN: {e}")
                    operations_performed.append(("read_vin", "error"))
            
            # Чтение информации о ЭБУ
            if args.ecu_info:
                logger.info("Выполнение операции: Чтение информации о ЭБУ")
                try:
                    ecu_info = diag.read_ecu_info()
                    if ecu_info:
                        print("\n📊 Информация о ЭБУ:")
                        for key, value in ecu_info.items():
                            print(f"  {key}: {value}")
                        operations_performed.append(("ecu_info", "success"))
                    else:
                        print("\n⚠️ Информация о ЭБУ недоступна")
                        operations_performed.append(("ecu_info", "failed"))
                except Exception as e:
                    logger.error(f"Ошибка чтения информации о ЭБУ: {e}")
                    operations_performed.append(("ecu_info", "error"))
            
            # Сканирование DIDs
            if args.scan:
                logger.info("Выполнение операции: Сканирование DIDs")
                try:
                    if args.scan_range:
                        try:
                            start = int(args.scan_range[0], 16)
                            end = int(args.scan_range[1], 16)
                        except ValueError as e:
                            print(f"\n❌ Ошибка в диапазоне: {e}")
                            print("   Используйте формат: 0xF191 0xF1A0")
                            start = config.DIDS['ODOMETER_CANDIDATES'][0]
                            end = config.DIDS['ODOMETER_CANDIDATES'][-1]
                    else:
                        start = config.DIDS['ODOMETER_CANDIDATES'][0]
                        end = config.DIDS['ODOMETER_CANDIDATES'][-1]
                    
                    results = diag.scan_for_odometer(start, end)
                    
                    if results:
                        print(f"\n🔍 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ:")
                        print("="*60)
                        for did, data in results.items():
                            print(f"\n  DID 0x{did:04X}:")
                            print(f"    Raw: {data['raw_data']}")
                            print(f"    Возможные значения:")
                            for interp in data['possible_values']:
                                print(f"      - {interp}")
                        print("\n" + "="*60)
                        operations_performed.append(("scan", "success"))
                    else:
                        print("\n⚠️ Не найдено доступных DIDs")
                        operations_performed.append(("scan", "failed"))
                except KeyboardInterrupt:
                    print("\n\n⚠️ Сканирование прервано пользователем")
                    operations_performed.append(("scan", "interrupted"))
                    raise
                except Exception as e:
                    logger.error(f"Ошибка сканирования: {e}")
                    operations_performed.append(("scan", "error"))
            
            # Чтение конкретного одометра
            if args.read_odometer:
                logger.info(f"Выполнение операции: Чтение одометра {args.read_odometer}")
                try:
                    did = int(args.read_odometer, 16)
                    result = diag.read_odometer(did)
                    
                    if result:
                        print(f"\n📍 Одометр (DID 0x{did:04X}):")
                        print(f"  Raw: {result['raw_data']}")
                        print(f"  Возможные значения:")
                        for interp in result['interpretations']:
                            print(f"    - {interp}")
                        operations_performed.append(("read_odometer", "success"))
                    else:
                        print(f"\n⚠️ Не удалось прочитать одометр (DID 0x{did:04X})")
                        operations_performed.append(("read_odometer", "failed"))
                except ValueError as e:
                    print(f"\n❌ Ошибка формата DID: {e}")
                    print("   Используйте формат: 0xF192")
                    operations_performed.append(("read_odometer", "error"))
                except Exception as e:
                    logger.error(f"Ошибка чтения одометра: {e}")
                    operations_performed.append(("read_odometer", "error"))
            
            # Сохранение найденных параметров
            if args.save_params:
                logger.info("Выполнение операции: Сохранение параметров")
                try:
                    did = int(args.save_params[0], 16)
                    scale = float(args.save_params[1])
                    diag.save_discovered_params(did, scale)
                    operations_performed.append(("save_params", "success"))
                except Exception as e:
                    logger.error(f"Ошибка сохранения параметров: {e}")
                    operations_performed.append(("save_params", "error"))
            
            # Вывод итогов
            print("\n" + "="*60)
            print("✅ ДИАГНОСТИКА ЗАВЕРШЕНА")
            print("="*60)
            
            # Статистика операций
            successful_ops = sum(1 for _, status in operations_performed if status == "success")
            failed_ops = sum(1 for _, status in operations_performed if status in ["failed", "error"])
            
            print(f"\nВыполнено операций: {len(operations_performed)}")
            print(f"  ✅ Успешно: {successful_ops}")
            if failed_ops > 0:
                print(f"  ⚠️ С ошибками: {failed_ops}")
            
            # Сводка по ошибкам
            error_summary = global_error_handler.get_error_summary()
            if error_summary['total_errors'] > 0:
                print(f"\nОшибок во время сессии: {error_summary['total_errors']}")
                print(f"  Критических: {error_summary['critical_errors']}")
                print(f"\nЛоги сохранены в: {config.LOG_FILE}")
            
            print("="*60)
            
            operation_successful = True
            
        finally:
            # Отключение с обработкой ошибок
            logger.info("Завершение диагностической сессии...")
            if diag:
                diag.disconnect()
    
    except KeyboardInterrupt:
        print("\n\n" + "="*60)
        print("⚠️  ПРЕРВАНО ПОЛЬЗОВАТЕЛЕМ")
        print("="*60)
        
        global_error_handler.handle_error(
            Exception("User interrupted"),
            severity=ErrorSeverity.INFO,
            category=ErrorCategory.SYSTEM
        )
        
        if diag:
            diag.disconnect()
        
        sys.exit(0)
    
    except DiagnosticError as e:
        print("\n\n" + "="*60)
        print(f"❌ ДИАГНОСТИЧЕСКАЯ ОШИБКА: {e.message}")
        print("="*60)
        
        if e.recovery_hint:
            print(f"\n💡 Рекомендация: {e.recovery_hint}")
        
        logger.critical(f"Диагностическая ошибка: {e.message}", exc_info=True)
        
        # Генерация отчёта при критических ошибках
        if config.ENABLE_DIAGNOSTIC_REPORTS and e.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.FATAL]:
            try:
                print("\n📄 Генерация диагностического отчёта...")
                report_path = global_diagnostic_reporter.generate_report(
                    global_error_handler,
                    operation_context={"error": e.message, "category": e.category.value}
                )
                if report_path:
                    print(f"   Отчёт сохранён: {report_path}")
            except Exception as report_error:
                logger.error(f"Ошибка генерации отчёта: {report_error}")
        
        sys.exit(1)
    
    except Exception as e:
        print("\n\n" + "="*60)
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        print("="*60)
        
        logger.critical(f"Критическая ошибка: {e}", exc_info=True)
        
        global_error_handler.handle_error(
            e,
            severity=ErrorSeverity.FATAL,
            category=ErrorCategory.SYSTEM,
            recovery_hint="Перезапустите программу. Если проблема повторяется, проверьте system и hardware."
        )
        
        # Генерация отчёта при критических ошибках
        if config.ENABLE_DIAGNOSTIC_REPORTS:
            try:
                print("\n📄 Генерация диагностического отчёта...")
                report_path = global_diagnostic_reporter.generate_report(
                    global_error_handler,
                    operation_context={"error": str(e), "traceback": traceback.format_exc()}
                )
                if report_path:
                    print(f"   Отчёт сохранён: {report_path}")
                    print(f"   Отправьте этот отчёт для анализа проблемы")
            except Exception as report_error:
                logger.error(f"Ошибка генерации отчёта: {report_error}")
        
        sys.exit(1)
    
    finally:
        # Финальная очистка
        logger.info("="*60)
        logger.info("ЗАВЕРШЕНИЕ ПРОГРАММЫ")
        logger.info("="*60)


if __name__ == '__main__':
    main()

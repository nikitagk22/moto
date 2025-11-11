#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Генератор диагностических отчётов при сбоях
"""

import logging
import datetime
import platform
import sys
import os
from typing import Optional, Dict, Any, List
import json

logger = logging.getLogger(__name__)


class DiagnosticReport:
    """Генератор детальных диагностических отчётов"""
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_report(self, 
                       error_handler,
                       connection_state: Optional[Dict[str, Any]] = None,
                       operation_context: Optional[Dict[str, Any]] = None) -> str:
        """Генерация полного диагностического отчёта"""
        
        timestamp = datetime.datetime.now()
        report_filename = f"diagnostic_report_{timestamp.strftime('%Y%m%d_%H%M%S')}.txt"
        report_path = os.path.join(self.output_dir, report_filename)
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                self._write_header(f, timestamp)
                self._write_system_info(f)
                self._write_configuration_info(f)
                self._write_connection_state(f, connection_state)
                self._write_error_summary(f, error_handler)
                self._write_operation_context(f, operation_context)
                self._write_recommendations(f, error_handler)
                self._write_footer(f)
            
            logger.info(f"✅ Диагностический отчёт сохранён: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Ошибка создания отчёта: {e}")
            return ""
    
    def _write_header(self, f, timestamp):
        """Заголовок отчёта"""
        f.write("="*80 + "\n")
        f.write("   ДИАГНОСТИЧЕСКИЙ ОТЧЁТ\n")
        f.write("   Harley-Davidson XG750A Diagnostic Tool\n")
        f.write("="*80 + "\n")
        f.write(f"\nДата и время: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("\n")
    
    def _write_system_info(self, f):
        """Информация о системе"""
        f.write("-"*80 + "\n")
        f.write("ИНФОРМАЦИЯ О СИСТЕМЕ\n")
        f.write("-"*80 + "\n")
        
        f.write(f"Операционная система: {platform.system()} {platform.release()}\n")
        f.write(f"Версия: {platform.version()}\n")
        f.write(f"Архитектура: {platform.machine()}\n")
        f.write(f"Python версия: {sys.version.split()[0]}\n")
        f.write(f"Python архитектура: {'32-bit' if sys.maxsize <= 2**32 else '64-bit'}\n")
        f.write(f"Исполняемый файл: {sys.executable}\n")
        f.write("\n")
    
    def _write_configuration_info(self, f):
        """Информация о конфигурации"""
        try:
            import config
            
            f.write("-"*80 + "\n")
            f.write("КОНФИГУРАЦИЯ\n")
            f.write("-"*80 + "\n")
            
            f.write(f"J2534 DLL Path: {config.J2534_DLL_PATH}\n")
            f.write(f"DLL существует: {'Да' if os.path.exists(config.J2534_DLL_PATH) else 'Нет'}\n")
            f.write(f"CAN Protocol: {config.CAN_PROTOCOL}\n")
            f.write(f"CAN Baudrate: {config.CAN_BAUDRATE} бит/с\n")
            f.write(f"UDS Request ID: 0x{config.UDS_REQUEST_ID:03X}\n")
            f.write(f"UDS Response ID: 0x{config.UDS_RESPONSE_ID:03X}\n")
            f.write(f"ISO-TP Timeout: {config.ISO_TP_TIMEOUT} мс\n")
            f.write(f"UDS Session Timeout: {config.UDS_SESSION_TIMEOUT} мс\n")
            f.write("\n")
            
            # Альтернативные CAN ID
            f.write("Альтернативные CAN ID пары:\n")
            for req_id, resp_id in config.ALTERNATIVE_CAN_IDS:
                f.write(f"  Request=0x{req_id:03X}, Response=0x{resp_id:03X}\n")
            f.write("\n")
            
        except Exception as e:
            f.write(f"Ошибка чтения конфигурации: {e}\n\n")
    
    def _write_connection_state(self, f, connection_state: Optional[Dict[str, Any]]):
        """Состояние подключения"""
        f.write("-"*80 + "\n")
        f.write("СОСТОЯНИЕ ПОДКЛЮЧЕНИЯ\n")
        f.write("-"*80 + "\n")
        
        if connection_state:
            for key, value in connection_state.items():
                f.write(f"{key}: {value}\n")
        else:
            f.write("Информация о подключении недоступна\n")
        
        f.write("\n")
    
    def _write_error_summary(self, f, error_handler):
        """Сводка по ошибкам"""
        f.write("-"*80 + "\n")
        f.write("СВОДКА ПО ОШИБКАМ\n")
        f.write("-"*80 + "\n")
        
        summary = error_handler.get_error_summary()
        
        f.write(f"Всего ошибок: {summary['total_errors']}\n")
        f.write(f"Критических ошибок: {summary['critical_errors']}\n\n")
        
        f.write("Ошибки по категориям:\n")
        for category, count in summary['errors_by_category'].items():
            if count > 0:
                f.write(f"  {category.value}: {count}\n")
        f.write("\n")
        
        # Последние ошибки
        if summary['recent_errors']:
            f.write("Последние ошибки:\n")
            for err in summary['recent_errors']:
                f.write(f"  [{err['timestamp']}] {err['severity']} - {err['category']}: {err['message']}\n")
        
        f.write("\n")
    
    def _write_operation_context(self, f, operation_context: Optional[Dict[str, Any]]):
        """Контекст операции"""
        f.write("-"*80 + "\n")
        f.write("КОНТЕКСТ ОПЕРАЦИИ\n")
        f.write("-"*80 + "\n")
        
        if operation_context:
            f.write(json.dumps(operation_context, indent=2, ensure_ascii=False))
        else:
            f.write("Контекст операции недоступен\n")
        
        f.write("\n\n")
    
    def _write_recommendations(self, f, error_handler):
        """Рекомендации по устранению"""
        f.write("-"*80 + "\n")
        f.write("РЕКОМЕНДАЦИИ ПО УСТРАНЕНИЮ ПРОБЛЕМ\n")
        f.write("-"*80 + "\n")
        
        # Анализ ошибок и генерация рекомендаций
        summary = error_handler.get_error_summary()
        
        recommendations = []
        
        # Рекомендации на основе категорий ошибок
        for category, count in summary['errors_by_category'].items():
            if count == 0:
                continue
            
            if category.value == 'hardware':
                recommendations.append(
                    "1. ПРОБЛЕМЫ С ОБОРУДОВАНИЕМ:\n"
                    "   - Проверьте подключение OpenPort 2.0 к USB порту\n"
                    "   - Убедитесь, что драйверы установлены корректно\n"
                    "   - Попробуйте другой USB порт\n"
                    "   - Проверьте, не используется ли адаптер другой программой\n"
                )
            
            elif category.value == 'connection':
                recommendations.append(
                    "2. ПРОБЛЕМЫ С ПОДКЛЮЧЕНИЕМ К МОТОЦИКЛУ:\n"
                    "   - Проверьте 6-pin адаптер H-D → OBD-II подключение\n"
                    "   - Убедитесь, что адаптер подключен к диагностическому порту мотоцикла\n"
                    "   - Включите зажигание (без запуска двигателя)\n"
                    "   - Проверьте правильность распиновки адаптера (CAN H/L на pin 3/4)\n"
                    "   - Попробуйте запустить с флагом --auto-detect для поиска CAN ID\n"
                )
            
            elif category.value == 'protocol':
                recommendations.append(
                    "3. ОШИБКИ ПРОТОКОЛА:\n"
                    "   - Возможно неправильные CAN ID адреса\n"
                    "   - Попробуйте автоматический поиск: python main.py --read-vin --auto-detect\n"
                    "   - Проверьте скорость CAN шины (обычно 500 кбит/с для HDLAN)\n"
                    "   - Убедитесь, что мотоцикл поддерживает протокол UDS\n"
                )
            
            elif category.value == 'timeout':
                recommendations.append(
                    "4. ТАЙМ-АУТЫ:\n"
                    "   - Увеличьте значения timeout в config.py\n"
                    "   - Проверьте качество соединения адаптера\n"
                    "   - Убедитесь, что ЭБУ готов к диагностике (зажигание включено)\n"
                )
            
            elif category.value == 'configuration':
                recommendations.append(
                    "5. ПРОБЛЕМЫ С КОНФИГУРАЦИЕЙ:\n"
                    "   - Проверьте путь к J2534 DLL в config.py\n"
                    "   - Убедитесь, что все параметры в config.py корректны\n"
                    "   - Запустите: python check_system.py для проверки системы\n"
                )
        
        if not recommendations:
            f.write("Нет специфических рекомендаций. Система работает нормально.\n")
        else:
            for rec in recommendations:
                f.write(rec + "\n")
        
        # Общие рекомендации
        f.write("\nОБЩИЕ РЕКОМЕНДАЦИИ:\n")
        f.write("- Изучите логи в директории logs/ для детальной информации\n")
        f.write("- Обратитесь к документации: README.md, QUICKSTART.md\n")
        f.write("- Используйте --verbose флаг для подробного вывода\n")
        f.write("- При повторяющихся проблемах - обратитесь к дилеру Harley-Davidson\n")
        f.write("\n")
    
    def _write_footer(self, f):
        """Футер отчёта"""
        f.write("="*80 + "\n")
        f.write("Конец отчёта\n")
        f.write("="*80 + "\n")


# Глобальный экземпляр
global_diagnostic_reporter = DiagnosticReport()

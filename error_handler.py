#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Централизованная система обработки ошибок с автоматической диагностикой
"""

import logging
import traceback
import datetime
import os
import sys
from typing import Optional, Dict, Any, Callable
from enum import Enum
import json

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Уровни критичности ошибок"""
    INFO = 1        # Информационное сообщение
    WARNING = 2     # Предупреждение, можно продолжать
    RECOVERABLE = 3 # Восстановимая ошибка, требуется retry
    CRITICAL = 4    # Критическая ошибка, требуется вмешательство
    FATAL = 5       # Фатальная ошибка, продолжение невозможно


class ErrorCategory(Enum):
    """Категории ошибок"""
    HARDWARE = "hardware"           # Проблемы с адаптером/железом
    CONNECTION = "connection"       # Проблемы с подключением
    PROTOCOL = "protocol"           # Ошибки протокола
    DATA = "data"                   # Проблемы с данными
    TIMEOUT = "timeout"             # Таймауты
    CONFIGURATION = "configuration" # Проблемы с конфигурацией
    SYSTEM = "system"               # Системные ошибки
    UNKNOWN = "unknown"             # Неизвестные ошибки


class DiagnosticError(Exception):
    """Базовый класс для всех диагностических ошибок"""
    
    def __init__(self, message: str, severity: ErrorSeverity, 
                 category: ErrorCategory, details: Optional[Dict[str, Any]] = None,
                 recovery_hint: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.category = category
        self.details = details or {}
        self.recovery_hint = recovery_hint
        self.timestamp = datetime.datetime.now()
        self.traceback = traceback.format_exc()


class ErrorHandler:
    """Центральный обработчик ошибок с автоматической диагностикой"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        self.error_history = []
        self.critical_errors = []
        
        # Создание директории для логов
        os.makedirs(log_dir, exist_ok=True)
        
        # Счетчики ошибок
        self.error_counts = {
            category: 0 for category in ErrorCategory
        }
        
        logger.info("ErrorHandler инициализирован")
    
    def handle_error(self, error: Exception, 
                    severity: ErrorSeverity = ErrorSeverity.RECOVERABLE,
                    category: ErrorCategory = ErrorCategory.UNKNOWN,
                    context: Optional[Dict[str, Any]] = None,
                    recovery_hint: Optional[str] = None) -> DiagnosticError:
        """Обработка ошибки с классификацией и логированием"""
        
        # Создание диагностической ошибки
        if isinstance(error, DiagnosticError):
            diag_error = error
        else:
            diag_error = DiagnosticError(
                message=str(error),
                severity=severity,
                category=category,
                details=context or {},
                recovery_hint=recovery_hint
            )
        
        # Добавление в историю
        self.error_history.append(diag_error)
        self.error_counts[category] += 1
        
        # Логирование
        log_msg = f"[{diag_error.category.value.upper()}] {diag_error.message}"
        
        if severity == ErrorSeverity.FATAL or severity == ErrorSeverity.CRITICAL:
            self.critical_errors.append(diag_error)
            logger.critical(log_msg)
            self._save_critical_error_log(diag_error)
        elif severity == ErrorSeverity.RECOVERABLE:
            logger.error(log_msg)
        elif severity == ErrorSeverity.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
        
        # Вывод подсказки по восстановлению
        if diag_error.recovery_hint:
            logger.info(f"💡 Подсказка: {diag_error.recovery_hint}")
        
        return diag_error
    
    def _save_critical_error_log(self, error: DiagnosticError):
        """Автоматическое сохранение лога критической ошибки"""
        try:
            timestamp = error.timestamp.strftime("%Y%m%d_%H%M%S")
            filename = f"critical_error_{timestamp}.log"
            filepath = os.path.join(self.log_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write(f"КРИТИЧЕСКАЯ ОШИБКА - {error.timestamp}\n")
                f.write("="*80 + "\n\n")
                
                f.write(f"Категория: {error.category.value.upper()}\n")
                f.write(f"Серьёзность: {error.severity.name}\n")
                f.write(f"Сообщение: {error.message}\n\n")
                
                if error.recovery_hint:
                    f.write(f"Подсказка по восстановлению:\n{error.recovery_hint}\n\n")
                
                if error.details:
                    f.write("Детали:\n")
                    f.write(json.dumps(error.details, indent=2, ensure_ascii=False))
                    f.write("\n\n")
                
                f.write("Traceback:\n")
                f.write(error.traceback)
                f.write("\n")
            
            logger.info(f"Лог критической ошибки сохранён: {filepath}")
            
        except Exception as e:
            logger.error(f"Не удалось сохранить лог критической ошибки: {e}")
    
    def retry_with_recovery(self, func: Callable, max_attempts: int = 3,
                           initial_delay: float = 1.0, 
                           backoff_factor: float = 2.0,
                           error_category: ErrorCategory = ErrorCategory.UNKNOWN,
                           recovery_callback: Optional[Callable] = None) -> Any:
        """Выполнение функции с автоматическим retry и exponential backoff"""
        import time
        
        last_error = None
        delay = initial_delay
        
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Попытка {attempt}/{max_attempts}: {func.__name__}")
                result = func()
                
                if attempt > 1:
                    logger.info(f"✅ Успешно после {attempt} попыток")
                
                return result
                
            except Exception as e:
                last_error = e
                
                severity = ErrorSeverity.RECOVERABLE if attempt < max_attempts else ErrorSeverity.CRITICAL
                
                diag_error = self.handle_error(
                    e, 
                    severity=severity,
                    category=error_category,
                    context={"attempt": attempt, "max_attempts": max_attempts}
                )
                
                if attempt < max_attempts:
                    logger.warning(f"⏳ Повтор через {delay:.1f} секунд...")
                    time.sleep(delay)
                    delay *= backoff_factor
                    
                    # Вызов callback для восстановления если есть
                    if recovery_callback:
                        try:
                            logger.info("Вызов recovery callback...")
                            recovery_callback()
                        except Exception as recovery_error:
                            logger.error(f"Ошибка в recovery callback: {recovery_error}")
        
        # Все попытки исчерпаны
        raise DiagnosticError(
            f"Не удалось выполнить {func.__name__} после {max_attempts} попыток",
            severity=ErrorSeverity.CRITICAL,
            category=error_category,
            details={"last_error": str(last_error)}
        )
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Получение сводки по ошибкам"""
        return {
            "total_errors": len(self.error_history),
            "critical_errors": len(self.critical_errors),
            "errors_by_category": self.error_counts,
            "recent_errors": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "severity": e.severity.name,
                    "category": e.category.value,
                    "message": e.message
                }
                for e in self.error_history[-10:]  # Последние 10
            ]
        }
    
    def clear_history(self):
        """Очистка истории ошибок"""
        self.error_history.clear()
        self.critical_errors.clear()
        self.error_counts = {category: 0 for category in ErrorCategory}
        logger.info("История ошибок очищена")


# Глобальный экземпляр для использования во всех модулях
global_error_handler = ErrorHandler()

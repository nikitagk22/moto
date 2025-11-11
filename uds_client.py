"""UDS (Unified Diagnostic Services) клиент для диагностики ЭБУ"""
import logging
import threading
import time
from typing import Optional, Dict, Any

import config
from isotp_handler import ISOTPHandler
from error_handler import global_error_handler, ErrorSeverity, ErrorCategory, DiagnosticError

logger = logging.getLogger(__name__)

# UDS Service IDs (SIDs)
DIAGNOSTIC_SESSION_CONTROL = 0x10
ECU_RESET = 0x11
READ_DATA_BY_IDENTIFIER = 0x22
READ_MEMORY_BY_ADDRESS = 0x23
SECURITY_ACCESS = 0x27
WRITE_DATA_BY_IDENTIFIER = 0x2E
TESTER_PRESENT = 0x3E
CONTROL_DTC_SETTING = 0x85

# Diagnostic Session Types
DEFAULT_SESSION = 0x01
PROGRAMMING_SESSION = 0x02
EXTENDED_DIAGNOSTIC_SESSION = 0x03
SAFETY_SYSTEM_DIAGNOSTIC_SESSION = 0x04

# UDS положительный ответ: SID + 0x40
POSITIVE_RESPONSE_OFFSET = 0x40

# UDS отрицательный ответ
NEGATIVE_RESPONSE = 0x7F

# Negative Response Codes (NRC)
NRC_DESCRIPTIONS = {
    0x10: "General reject",
    0x11: "Service not supported",
    0x12: "Sub-function not supported",
    0x13: "Incorrect message length or invalid format",
    0x22: "Conditions not correct",
    0x31: "Request out of range",
    0x33: "Security access denied",
    0x35: "Invalid key",
    0x36: "Exceeded number of attempts",
    0x37: "Required time delay not expired",
    0x78: "Request correctly received but response is pending"
}


class UDSException(Exception):
    """Исключение для ошибок UDS"""
    pass


class UDSClient:
    """Клиент UDS для диагностики ЭБУ"""
    
    def __init__(self, isotp_handler: ISOTPHandler):
        self.isotp = isotp_handler
        self.current_session = DEFAULT_SESSION
        self._tester_present_thread = None
        self._stop_tester_present = threading.Event()
        
        logger.info("UDS клиент инициализирован")
    
    def send_request(self, service_id: int, data: bytes = b'', timeout: Optional[int] = None) -> Optional[bytes]:
        """Отправка UDS запроса и получение ответа с обработкой ошибок"""
        try:
            request = bytes([service_id]) + data
            logger.debug(f"UDS Request: {request.hex().upper()}")
            
            # Валидация запроса
            if len(request) > 4095:  # Максимальный размер UDS сообщения
                raise ValueError(f"UDS запрос слишком большой: {len(request)} байт")
            
            # Отправка через ISO-TP с retry
            send_attempts = 0
            max_send_attempts = 2
            
            while send_attempts < max_send_attempts:
                if self.isotp.send(request):
                    break
                send_attempts += 1
                if send_attempts < max_send_attempts:
                    logger.warning(f"⚠️ Повтор отправки UDS запроса (попытка {send_attempts + 1})")
                    time.sleep(0.1)
            else:
                error = Exception("Не удалось отправить UDS запрос")
                global_error_handler.handle_error(
                    error,
                    severity=ErrorSeverity.RECOVERABLE,
                    category=ErrorCategory.PROTOCOL,
                    context={"service_id": f"0x{service_id:02X}"},
                    recovery_hint="Проверьте соединение с ЭБУ"
                )
                return None
            
            # Прием ответа
            if timeout is None:
                timeout = config.ISO_TP_TIMEOUT
            
            response = self.isotp.receive(timeout=timeout)
            
            if response is None:
                error = Exception(f"Timeout ожидания UDS ответа (SID 0x{service_id:02X})")
                global_error_handler.handle_error(
                    error,
                    severity=ErrorSeverity.RECOVERABLE,
                    category=ErrorCategory.TIMEOUT,
                    context={"service_id": f"0x{service_id:02X}", "timeout": timeout},
                    recovery_hint="Увеличьте timeout или проверьте связь с ЭБУ"
                )
                return None
            
            logger.debug(f"UDS Response: {response.hex().upper()}")
            
            # Проверка ответа
            if len(response) < 1:
                logger.error("Пустой ответ UDS")
                return None
            
            response_sid = response[0]
            
            # Положительный ответ
            if response_sid == service_id + POSITIVE_RESPONSE_OFFSET:
                logger.info(f"✅ UDS положительный ответ на сервис 0x{service_id:02X}")
                return response[1:]  # Возвращаем данные без SID
            
            # Отрицательный ответ
            elif response_sid == NEGATIVE_RESPONSE:
                if len(response) >= 3:
                    requested_sid = response[1]
                    nrc = response[2]
                    nrc_desc = NRC_DESCRIPTIONS.get(nrc, f"Unknown NRC: 0x{nrc:02X}")
                    logger.error(f"❌ UDS отрицательный ответ: SID=0x{requested_sid:02X}, NRC=0x{nrc:02X} ({nrc_desc})")
                    
                    # Определение серьёзности на основе NRC
                    severity = ErrorSeverity.WARNING if nrc == 0x78 else ErrorSeverity.RECOVERABLE
                    
                    error = UDSException(f"Negative response: {nrc_desc} (0x{nrc:02X})")
                    global_error_handler.handle_error(
                        error,
                        severity=severity,
                        category=ErrorCategory.PROTOCOL,
                        context={"nrc": f"0x{nrc:02X}", "service_id": f"0x{service_id:02X}"}
                    )
                    raise error
                else:
                    logger.error("Некорректный отрицательный ответ UDS")
                    return None
            
            else:
                logger.warning(f"⚠️ Неожиданный SID ответа: 0x{response_sid:02X}")
                return response
                
        except UDSException:
            raise  # Пробрасываем UDSException дальше
        except Exception as e:
            global_error_handler.handle_error(
                e,
                severity=ErrorSeverity.RECOVERABLE,
                category=ErrorCategory.PROTOCOL,
                context={"service_id": f"0x{service_id:02X}"}
            )
            raise
    
    def diagnostic_session_control(self, session_type: int = EXTENDED_DIAGNOSTIC_SESSION) -> bool:
        """Управление диагностической сессией (0x10)"""
        logger.info(f"Переключение в сессию: 0x{session_type:02X}")
        
        try:
            response = self.send_request(DIAGNOSTIC_SESSION_CONTROL, bytes([session_type]))
            if response is not None:
                self.current_session = session_type
                logger.info(f"Диагностическая сессия установлена: 0x{session_type:02X}")
                return True
            return False
        except UDSException as e:
            logger.error(f"Ошибка переключения сессии: {e}")
            return False
    
    def tester_present(self, suppress_response: bool = True) -> bool:
        """Отправка TesterPresent (0x3E) для поддержания сессии"""
        sub_function = 0x00 if not suppress_response else 0x80
        
        try:
            response = self.send_request(TESTER_PRESENT, bytes([sub_function]), timeout=500)
            if response is not None or suppress_response:
                logger.debug("TesterPresent отправлен")
                return True
            return False
        except UDSException:
            logger.warning("Ошибка TesterPresent")
            return False
    
    def read_data_by_identifier(self, did: int) -> Optional[bytes]:
        """Чтение данных по идентификатору (0x22) с retry механизмом"""
        
        # Валидация DID
        if did < 0 or did > 0xFFFF:
            error = ValueError(f"Недопустимый DID: 0x{did:04X}")
            global_error_handler.handle_error(
                error,
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.DATA,
                recovery_hint="DID должен быть в диапазоне 0x0000-0xFFFF"
            )
            return None
        
        did_bytes = bytes([did >> 8, did & 0xFF])
        logger.info(f"🔍 Чтение DID: 0x{did:04X}")
        
        try:
            # Retry механизм для чтения DID
            def _read_attempt():
                response = self.send_request(READ_DATA_BY_IDENTIFIER, did_bytes, timeout=2000)
                
                if response is None:
                    raise Exception(f"Нет ответа от ЭБУ для DID 0x{did:04X}")
                
                if len(response) < 2:
                    raise Exception(f"Некорректная длина ответа: {len(response)} байт")
                
                # Проверка DID в ответе
                response_did = (response[0] << 8) | response[1]
                if response_did != did:
                    raise Exception(f"Несоответствие DID: ожидался 0x{did:04X}, получен 0x{response_did:04X}")
                
                data = response[2:]
                
                # Валидация данных
                if len(data) == 0:
                    logger.warning(f"⚠️ DID 0x{did:04X} вернул пустые данные")
                
                logger.info(f"✅ DID 0x{did:04X}: {data.hex().upper()} ({len(data)} байт)")
                return data
            
            # Попытка с retry (только для временных ошибок)
            try:
                return _read_attempt()
            except UDSException:
                # UDS ошибки (например NRC) не требуют retry
                return None
            except Exception as e:
                # Для других ошибок пытаемся retry
                logger.warning(f"⚠️ Ошибка чтения DID 0x{did:04X}, попытка повтора...")
                time.sleep(0.5)
                try:
                    return _read_attempt()
                except Exception:
                    global_error_handler.handle_error(
                        e,
                        severity=ErrorSeverity.WARNING,
                        category=ErrorCategory.DATA,
                        context={"did": f"0x{did:04X}"},
                        recovery_hint=f"DID 0x{did:04X} может быть недоступен для этого ЭБУ"
                    )
                    return None
                    
        except UDSException as e:
            logger.error(f"❌ UDS ошибка чтения DID 0x{did:04X}: {e}")
            return None
        except Exception as e:
            global_error_handler.handle_error(
                e,
                severity=ErrorSeverity.RECOVERABLE,
                category=ErrorCategory.DATA,
                context={"did": f"0x{did:04X}"}
            )
            return None
    
    def start_tester_present(self, interval: float = config.TESTER_PRESENT_INTERVAL):
        """Запуск фонового потока TesterPresent"""
        if self._tester_present_thread is not None and self._tester_present_thread.is_alive():
            logger.warning("TesterPresent поток уже запущен")
            return
        
        self._stop_tester_present.clear()
        self._tester_present_thread = threading.Thread(
            target=self._tester_present_loop,
            args=(interval,),
            daemon=True
        )
        self._tester_present_thread.start()
        logger.info(f"TesterPresent поток запущен (интервал {interval} сек)")
    
    def stop_tester_present(self):
        """Остановка потока TesterPresent"""
        if self._tester_present_thread is not None:
            self._stop_tester_present.set()
            self._tester_present_thread.join(timeout=2.0)
            logger.info("TesterPresent поток остановлен")
    
    def _tester_present_loop(self, interval: float):
        """Цикл TesterPresent в фоновом потоке"""
        while not self._stop_tester_present.is_set():
            try:
                self.tester_present(suppress_response=True)
            except Exception as e:
                logger.error(f"Ошибка в TesterPresent потоке: {e}")
            
            time.sleep(interval)

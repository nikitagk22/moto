"""J2534 PassThru API обертка для работы с Tactrix OpenPort 2.0"""
import ctypes
import logging
import threading
import time
from typing import Optional, List, Tuple

from j2534_constants import *
import config
from error_handler import global_error_handler, ErrorSeverity, ErrorCategory, DiagnosticError

logger = logging.getLogger(__name__)


class J2534Exception(Exception):
    """Исключение для ошибок J2534"""
    pass


class J2534Wrapper:
    """Обертка для J2534 PassThru API"""
    
    def __init__(self, dll_path: str = None):
        # Автоматический поиск DLL если путь не указан
        if dll_path is None:
            dll_path = config.find_dll_path()
            if dll_path is None:
                raise J2534Exception(
                    "Не удалось найти J2534 DLL!\n"
                    "Проверьте установку драйверов OpenPort 2.0.\n"
                    "Или укажите путь к DLL в config.py"
                )
            logger.info(f"Автоматически найден DLL: {dll_path}")
        
        # Проверка существования DLL
        import os
        if not os.path.exists(dll_path):
            raise J2534Exception(
                f"DLL файл не найден: {dll_path}\n"
                f"Проверьте установку драйверов OpenPort 2.0"
            )
        
        self.dll_path = dll_path
        self.dll = None
        self.device_id = None
        self.channel_id = None
        self.filter_id = None
        self._read_thread = None
        self._stop_reading = threading.Event()
        self._message_queue = []
        self._queue_lock = threading.Lock()
        
        logger.info(f"Инициализация J2534 с DLL: {dll_path}")
        
    def _load_dll(self):
        """Загрузка J2534 DLL и определение прототипов функций"""
        try:
            # Загрузка DLL (stdcall для Windows)
            self.dll = ctypes.windll.LoadLibrary(self.dll_path)
            logger.info("DLL успешно загружена")
            
            # PassThruOpen
            self.dll.PassThruOpen.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
            self.dll.PassThruOpen.restype = ctypes.c_long
            
            # PassThruClose
            self.dll.PassThruClose.argtypes = [ctypes.c_ulong]
            self.dll.PassThruClose.restype = ctypes.c_long
            
            # PassThruConnect
            self.dll.PassThruConnect.argtypes = [
                ctypes.c_ulong,  # DeviceID
                ctypes.c_ulong,  # ProtocolID
                ctypes.c_ulong,  # Flags
                ctypes.c_ulong,  # Baudrate
                ctypes.POINTER(ctypes.c_ulong)  # pChannelID
            ]
            self.dll.PassThruConnect.restype = ctypes.c_long
            
            # PassThruDisconnect
            self.dll.PassThruDisconnect.argtypes = [ctypes.c_ulong]
            self.dll.PassThruDisconnect.restype = ctypes.c_long
            
            # PassThruReadMsgs
            self.dll.PassThruReadMsgs.argtypes = [
                ctypes.c_ulong,  # ChannelID
                ctypes.POINTER(PASSTHRU_MSG),  # pMsg
                ctypes.POINTER(ctypes.c_ulong),  # pNumMsgs
                ctypes.c_ulong  # Timeout
            ]
            self.dll.PassThruReadMsgs.restype = ctypes.c_long
            
            # PassThruWriteMsgs
            self.dll.PassThruWriteMsgs.argtypes = [
                ctypes.c_ulong,  # ChannelID
                ctypes.POINTER(PASSTHRU_MSG),  # pMsg
                ctypes.POINTER(ctypes.c_ulong),  # pNumMsgs
                ctypes.c_ulong  # Timeout
            ]
            self.dll.PassThruWriteMsgs.restype = ctypes.c_long
            
            # PassThruStartMsgFilter
            self.dll.PassThruStartMsgFilter.argtypes = [
                ctypes.c_ulong,  # ChannelID
                ctypes.c_ulong,  # FilterType
                ctypes.POINTER(PASSTHRU_MSG),  # pMaskMsg
                ctypes.POINTER(PASSTHRU_MSG),  # pPatternMsg
                ctypes.POINTER(PASSTHRU_MSG),  # pFlowControlMsg
                ctypes.POINTER(ctypes.c_ulong)  # pFilterID
            ]
            self.dll.PassThruStartMsgFilter.restype = ctypes.c_long
            
            # PassThruStopMsgFilter
            self.dll.PassThruStopMsgFilter.argtypes = [
                ctypes.c_ulong,  # ChannelID
                ctypes.c_ulong  # FilterID
            ]
            self.dll.PassThruStopMsgFilter.restype = ctypes.c_long
            
            # PassThruIoctl
            self.dll.PassThruIoctl.argtypes = [
                ctypes.c_ulong,  # ChannelID
                ctypes.c_ulong,  # IoctlID
                ctypes.c_void_p,  # pInput
                ctypes.c_void_p  # pOutput
            ]
            self.dll.PassThruIoctl.restype = ctypes.c_long
            
            logger.info("Прототипы функций J2534 определены")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки DLL: {e}")
            raise J2534Exception(f"Не удалось загрузить DLL {self.dll_path}: {e}")
    
    def _check_error(self, result: int, function_name: str):
        """Проверка кода возврата J2534 и генерация исключения при ошибке"""
        if result != STATUS_NOERROR:
            error_msg = J2534_ERRORS.get(result, f"Unknown error code: {result}")
            logger.error(f"{function_name} failed: {error_msg} (0x{result:02X})")
            
            # Определение категории и серьёзности
            if result == ERR_DEVICE_NOT_CONNECTED:
                category = ErrorCategory.HARDWARE
                severity = ErrorSeverity.CRITICAL
                hint = "Проверьте подключение OpenPort 2.0 к USB порту"
            elif result == ERR_TIMEOUT:
                category = ErrorCategory.TIMEOUT
                severity = ErrorSeverity.RECOVERABLE
                hint = "Увеличьте timeout или проверьте соединение"
            elif result == ERR_INVALID_CHANNEL_ID or result == ERR_INVALID_DEVICE_ID:
                category = ErrorCategory.CONFIGURATION
                severity = ErrorSeverity.CRITICAL
                hint = "Переподключите устройство и попробуйте снова"
            else:
                category = ErrorCategory.HARDWARE
                severity = ErrorSeverity.RECOVERABLE
                hint = f"J2534 ошибка: {error_msg}"
            
            # Регистрация ошибки
            global_error_handler.handle_error(
                J2534Exception(f"{function_name}: {error_msg} (0x{result:02X})"),
                severity=severity,
                category=category,
                context={"function": function_name, "error_code": result},
                recovery_hint=hint
            )
            
            raise J2534Exception(f"{function_name}: {error_msg} (0x{result:02X})")
    
    def open_device(self) -> int:
        """Открытие устройства J2534 с retry механизмом"""
        try:
            if self.dll is None:
                self._load_dll()
            
            # Retry механизм для открытия устройства
            def _open_attempt():
                device_id = ctypes.c_ulong(0)
                result = self.dll.PassThruOpen(None, ctypes.byref(device_id))
                self._check_error(result, "PassThruOpen")
                return device_id.value
            
            self.device_id = global_error_handler.retry_with_recovery(
                _open_attempt,
                max_attempts=config.MAX_RETRY_ATTEMPTS,
                initial_delay=config.RETRY_INITIAL_DELAY,
                backoff_factor=config.RETRY_BACKOFF_FACTOR,
                error_category=ErrorCategory.HARDWARE
            )
            
            logger.info(f"✅ Устройство открыто, DeviceID: {self.device_id}")
            return self.device_id
            
        except Exception as e:
            global_error_handler.handle_error(
                e,
                severity=ErrorSeverity.FATAL,
                category=ErrorCategory.HARDWARE,
                recovery_hint="Проверьте подключение OpenPort 2.0 к USB и перезапустите программу"
            )
            raise
    
    def close_device(self):
        """Закрытие устройства J2534"""
        if self.device_id is not None:
            result = self.dll.PassThruClose(self.device_id)
            try:
                self._check_error(result, "PassThruClose")
                logger.info("Устройство закрыто")
            except J2534Exception:
                logger.warning("Ошибка при закрытии устройства")
            finally:
                self.device_id = None
    
    def connect_channel(self, protocol_id: int = ISO15765, 
                       baudrate: int = config.CAN_BAUDRATE,
                       flags: int = config.CAN_FLAGS) -> int:
        """Подключение к CAN каналу"""
        if self.device_id is None:
            raise J2534Exception("Устройство не открыто")
        
        channel_id = ctypes.c_ulong(0)
        result = self.dll.PassThruConnect(
            self.device_id,
            protocol_id,
            flags,
            baudrate,
            ctypes.byref(channel_id)
        )
        self._check_error(result, "PassThruConnect")
        
        self.channel_id = channel_id.value
        logger.info(f"Канал подключен, ChannelID: {self.channel_id}, Baudrate: {baudrate}")
        return self.channel_id
    
    def disconnect_channel(self):
        """Отключение от канала"""
        if self.channel_id is not None:
            # Остановить поток чтения
            self.stop_reading()
            
            result = self.dll.PassThruDisconnect(self.channel_id)
            try:
                self._check_error(result, "PassThruDisconnect")
                logger.info("Канал отключен")
            except J2534Exception:
                logger.warning("Ошибка при отключении канала")
            finally:
                self.channel_id = None
    
    def set_flow_control_filter(self, request_id: int, response_id: int) -> int:
        """Установка фильтра управления потоком для ISO-TP"""
        if self.channel_id is None:
            raise J2534Exception("Канал не подключен")
        
        # Маска (все биты значимы для стандартного 11-бит ID)
        mask = PASSTHRU_MSG()
        mask.ProtocolID = ISO15765
        mask.DataSize = 4
        mask.Data[0] = 0xFF
        mask.Data[1] = 0xFF
        mask.Data[2] = 0xFF
        mask.Data[3] = 0xFF
        
        # Паттерн (ID ответа от ЭБУ)
        pattern = PASSTHRU_MSG()
        pattern.ProtocolID = ISO15765
        pattern.DataSize = 4
        pattern.Data[0] = (response_id >> 24) & 0xFF
        pattern.Data[1] = (response_id >> 16) & 0xFF
        pattern.Data[2] = (response_id >> 8) & 0xFF
        pattern.Data[3] = response_id & 0xFF
        
        # Flow Control (наш запрос к ЭБУ)
        fc = PASSTHRU_MSG()
        fc.ProtocolID = ISO15765
        fc.DataSize = 4
        fc.Data[0] = (request_id >> 24) & 0xFF
        fc.Data[1] = (request_id >> 16) & 0xFF
        fc.Data[2] = (request_id >> 8) & 0xFF
        fc.Data[3] = request_id & 0xFF
        
        filter_id = ctypes.c_ulong(0)
        result = self.dll.PassThruStartMsgFilter(
            self.channel_id,
            FLOW_CONTROL_FILTER,
            ctypes.byref(mask),
            ctypes.byref(pattern),
            ctypes.byref(fc),
            ctypes.byref(filter_id)
        )
        self._check_error(result, "PassThruStartMsgFilter")
        
        self.filter_id = filter_id.value
        logger.info(f"Фильтр установлен, FilterID: {self.filter_id}")
        return self.filter_id
    
    def write_message(self, can_id: int, data: bytes, timeout: int = 100) -> bool:
        """Отправка CAN сообщения"""
        if self.channel_id is None:
            raise J2534Exception("Канал не подключен")
        
        msg = PASSTHRU_MSG()
        msg.ProtocolID = ISO15765
        msg.TxFlags = 0
        msg.DataSize = 4 + len(data)  # 4 байта ID + данные
        
        # CAN ID (11-бит, стандартный)
        msg.Data[0] = (can_id >> 24) & 0xFF
        msg.Data[1] = (can_id >> 16) & 0xFF
        msg.Data[2] = (can_id >> 8) & 0xFF
        msg.Data[3] = can_id & 0xFF
        
        # Данные
        for i, byte in enumerate(data):
            msg.Data[4 + i] = byte
        
        num_msgs = ctypes.c_ulong(1)
        result = self.dll.PassThruWriteMsgs(
            self.channel_id,
            ctypes.byref(msg),
            ctypes.byref(num_msgs),
            timeout
        )
        
        try:
            self._check_error(result, "PassThruWriteMsgs")
            logger.debug(f"Отправлено: ID=0x{can_id:03X}, Data={data.hex().upper()}")
            return True
        except J2534Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            return False
    
    def read_messages(self, timeout: int = 100, max_msgs: int = 10) -> List[Tuple[int, bytes]]:
        """Чтение CAN сообщений"""
        if self.channel_id is None:
            raise J2534Exception("Канал не подключен")
        
        messages = []
        msg_array = (PASSTHRU_MSG * max_msgs)()
        num_msgs = ctypes.c_ulong(max_msgs)
        
        result = self.dll.PassThruReadMsgs(
            self.channel_id,
            ctypes.byref(msg_array),
            ctypes.byref(num_msgs),
            timeout
        )
        
        # ERR_BUFFER_EMPTY не является ошибкой при чтении
        if result != STATUS_NOERROR and result != ERR_BUFFER_EMPTY:
            self._check_error(result, "PassThruReadMsgs")
        
        # Обработка полученных сообщений
        for i in range(num_msgs.value):
            msg = msg_array[i]
            
            # Извлечение CAN ID (первые 4 байта)
            can_id = (msg.Data[0] << 24) | (msg.Data[1] << 16) | (msg.Data[2] << 8) | msg.Data[3]
            
            # Извлечение данных (после ID)
            data_len = msg.DataSize - 4
            data = bytes(msg.Data[4:4+data_len])
            
            messages.append((can_id, data))
            logger.debug(f"Получено: ID=0x{can_id:03X}, Data={data.hex().upper()}")
        
        return messages
    
    def start_reading(self):
        """Запуск фонового потока для непрерывного чтения сообщений"""
        if self._read_thread is not None and self._read_thread.is_alive():
            logger.warning("Поток чтения уже запущен")
            return
        
        self._stop_reading.clear()
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()
        logger.info("Поток чтения запущен")
    
    def stop_reading(self):
        """Остановка потока чтения"""
        if self._read_thread is not None:
            self._stop_reading.set()
            self._read_thread.join(timeout=2.0)
            logger.info("Поток чтения остановлен")
    
    def _read_loop(self):
        """Цикл чтения сообщений в фоновом потоке"""
        while not self._stop_reading.is_set():
            try:
                messages = self.read_messages(timeout=50, max_msgs=10)
                if messages:
                    with self._queue_lock:
                        self._message_queue.extend(messages)
            except Exception as e:
                logger.error(f"Ошибка в потоке чтения: {e}")
                time.sleep(0.1)
    
    def get_queued_messages(self, can_id: Optional[int] = None) -> List[Tuple[int, bytes]]:
        """Получение сообщений из очереди"""
        with self._queue_lock:
            if can_id is None:
                messages = self._message_queue[:]
                self._message_queue.clear()
            else:
                messages = [(mid, data) for mid, data in self._message_queue if mid == can_id]
                self._message_queue = [(mid, data) for mid, data in self._message_queue if mid != can_id]
        return messages
    
    def clear_buffers(self):
        """Очистка буферов TX/RX"""
        if self.channel_id is None:
            return
        
        try:
            # Очистка TX буфера
            self.dll.PassThruIoctl(self.channel_id, CLEAR_TX_BUFFER, None, None)
            # Очистка RX буфера
            self.dll.PassThruIoctl(self.channel_id, CLEAR_RX_BUFFER, None, None)
            logger.debug("Буферы очищены")
        except Exception as e:
            logger.warning(f"Ошибка очистки буферов: {e}")
    
    def __enter__(self):
        """Контекстный менеджер: вход"""
        self.open_device()
        self.connect_channel()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер: выход"""
        self.disconnect_channel()
        self.close_device()

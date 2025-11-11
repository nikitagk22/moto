"""ISO-TP (Транспортный протокол ISO 15765-2) для многокадровых сообщений"""
import logging
import time
from typing import Optional, List, Tuple

import config
from error_handler import global_error_handler, ErrorSeverity, ErrorCategory

logger = logging.getLogger(__name__)

# ISO-TP типы кадров
SINGLE_FRAME = 0x0
FIRST_FRAME = 0x1
CONSECUTIVE_FRAME = 0x2
FLOW_CONTROL = 0x3

# Flow Control флаги
FC_CONTINUE = 0x0  # Продолжать передачу
FC_WAIT = 0x1      # Подождать
FC_OVERFLOW = 0x2  # Переполнение буфера


class ISOTPException(Exception):
    """Исключение для ошибок ISO-TP"""
    pass


class ISOTPHandler:
    """Обработчик ISO-TP протокола"""
    
    def __init__(self, j2534_wrapper, request_id: int, response_id: int):
        self.j2534 = j2534_wrapper
        self.request_id = request_id
        self.response_id = response_id
        self.bs = config.ISO_TP_BS
        self.stmin = config.ISO_TP_STMIN
        self.timeout = config.ISO_TP_TIMEOUT
        
        logger.info(f"ISO-TP инициализирован: Request=0x{request_id:03X}, Response=0x{response_id:03X}")
    
    def send(self, data: bytes) -> bool:
        """Отправка данных с использованием ISO-TP и валидацией"""
        try:
            # Валидация данных
            if not data:
                logger.error("❌ Попытка отправить пустые данные")
                return False
            
            data_len = len(data)
            
            # Проверка максимального размера (4095 байт для ISO-TP)
            if data_len > 4095:
                error = ValueError(f"Данные слишком большие для ISO-TP: {data_len} байт (макс 4095)")
                global_error_handler.handle_error(
                    error,
                    severity=ErrorSeverity.WARNING,
                    category=ErrorCategory.DATA,
                    recovery_hint="Разделите данные на меньшие части"
                )
                return False
            
            if data_len <= 7:
                # Single Frame (до 7 байт данных)
                result = self._send_single_frame(data)
            else:
                # Multi-frame (более 7 байт)
                result = self._send_multi_frame(data)
            
            if not result:
                global_error_handler.handle_error(
                    Exception("Не удалось отправить ISO-TP сообщение"),
                    severity=ErrorSeverity.RECOVERABLE,
                    category=ErrorCategory.PROTOCOL,
                    context={"data_length": data_len}
                )
            
            return result
            
        except Exception as e:
            global_error_handler.handle_error(
                e,
                severity=ErrorSeverity.RECOVERABLE,
                category=ErrorCategory.PROTOCOL,
                context={"data_length": len(data) if data else 0}
            )
            return False
    
    def _send_single_frame(self, data: bytes) -> bool:
        """Отправка Single Frame"""
        frame_data = bytes([SINGLE_FRAME << 4 | len(data)]) + data
        # Дополнение до 8 байт (опционально)
        if len(frame_data) < 8:
            frame_data += bytes([0x00] * (8 - len(frame_data)))
        
        logger.debug(f"ISO-TP Single Frame: {frame_data.hex().upper()}")
        return self.j2534.write_message(self.request_id, frame_data)
    
    def _send_multi_frame(self, data: bytes) -> bool:
        """Отправка многокадрового сообщения (First Frame + Consecutive Frames)"""
        data_len = len(data)
        
        # First Frame (FF)
        ff_len_high = (data_len >> 8) & 0x0F
        ff_len_low = data_len & 0xFF
        ff_data = bytes([FIRST_FRAME << 4 | ff_len_high, ff_len_low]) + data[:6]
        
        logger.debug(f"ISO-TP First Frame: {ff_data.hex().upper()}")
        if not self.j2534.write_message(self.request_id, ff_data):
            return False
        
        # Ожидание Flow Control
        fc = self._wait_for_flow_control()
        if fc is None or fc['status'] != FC_CONTINUE:
            logger.error("Не получен Flow Control или получен отказ")
            return False
        
        # Отправка Consecutive Frames (CF)
        remaining_data = data[6:]
        seq_num = 1
        offset = 0
        
        while offset < len(remaining_data):
            cf_data = bytes([CONSECUTIVE_FRAME << 4 | (seq_num & 0x0F)]) + remaining_data[offset:offset+7]
            # Дополнение до 8 байт
            if len(cf_data) < 8:
                cf_data += bytes([0x00] * (8 - len(cf_data)))
            
            logger.debug(f"ISO-TP Consecutive Frame #{seq_num}: {cf_data.hex().upper()}")
            if not self.j2534.write_message(self.request_id, cf_data):
                return False
            
            seq_num = (seq_num + 1) % 16
            offset += 7
            
            # Задержка между кадрами (STmin)
            if self.stmin > 0:
                time.sleep(self.stmin / 1000.0)
        
        return True
    
    def _wait_for_flow_control(self) -> Optional[dict]:
        """Ожидание кадра Flow Control от ЭБУ"""
        start_time = time.time()
        
        while (time.time() - start_time) < (self.timeout / 1000.0):
            messages = self.j2534.get_queued_messages(self.response_id)
            
            for can_id, data in messages:
                if len(data) < 1:
                    continue
                
                frame_type = (data[0] >> 4) & 0x0F
                if frame_type == FLOW_CONTROL:
                    fc_status = data[0] & 0x0F
                    bs = data[1] if len(data) > 1 else 0
                    stmin = data[2] if len(data) > 2 else 0
                    
                    logger.debug(f"Flow Control: Status={fc_status}, BS={bs}, STmin={stmin}")
                    return {'status': fc_status, 'bs': bs, 'stmin': stmin}
            
            time.sleep(0.01)
        
        logger.error("Timeout ожидания Flow Control")
        return None
    
    def receive(self, timeout: Optional[int] = None) -> Optional[bytes]:
        """Прием ISO-TP сообщения (Single Frame или Multi-frame) с улучшенной обработкой"""
        try:
            if timeout is None:
                timeout = self.timeout
            
            # Валидация timeout
            if timeout <= 0:
                logger.warning(f"⚠️ Недопустимый timeout: {timeout}, используем значение по умолчанию")
                timeout = self.timeout
            
            start_time = time.time()
            received_frames = 0
            
            while (time.time() - start_time) < (timeout / 1000.0):
                messages = self.j2534.get_queued_messages(self.response_id)
                
                for can_id, data in messages:
                    received_frames += 1
                    
                    # Валидация данных кадра
                    if len(data) < 1:
                        logger.debug(\"Пропущен пустой кадр\")\n                        continue\n                    \n                    frame_type = (data[0] >> 4) & 0x0F\n                    \n                    if frame_type == SINGLE_FRAME:\n                        # Single Frame\n                        length = data[0] & 0x0F\n                        \n                        # Валидация длины\n                        if length > 7:\n                            logger.warning(f\"⚠️ Недопустимая длина Single Frame: {length}\")\n                            continue\n                        \n                        if len(data) < (1 + length):\n                            logger.warning(f\"⚠️ Недостаточно данных в Single Frame\")\n                            continue\n                        \n                        payload = data[1:1+length]\n                        logger.debug(f\"✅ ISO-TP Single Frame принят: {payload.hex().upper()}\")\n                        return payload\n                    \n                    elif frame_type == FIRST_FRAME:\n                        # Multi-frame: First Frame\n                        try:\n                            return self._receive_multi_frame(data, timeout)\n                        except Exception as e:\n                            logger.error(f\"❌ Ошибка приёма multi-frame: {e}\")\n                            global_error_handler.handle_error(\n                                e,\n                                severity=ErrorSeverity.RECOVERABLE,\n                                category=ErrorCategory.PROTOCOL,\n                                recovery_hint=\"Проверьте качество соединения CAN шины\"\n                            )\n                            return None\n                \n                time.sleep(0.01)\n            \n            # Timeout\n            logger.warning(f\"⏱️ Timeout ожидания ISO-TP сообщения ({timeout} мс, получено {received_frames} кадров)\")\n            \n            if received_frames == 0:\n                global_error_handler.handle_error(\n                    Exception(\"Не получено ни одного CAN кадра\"),\n                    severity=ErrorSeverity.RECOVERABLE,\n                    category=ErrorCategory.TIMEOUT,\n                    context={\"timeout\": timeout, \"response_id\": f\"0x{self.response_id:03X}\"},\n                    recovery_hint=\"Проверьте CAN ID ответа или используйте --auto-detect\"\n                )\n            \n            return None\n            \n        except Exception as e:\n            global_error_handler.handle_error(\n                e,\n                severity=ErrorSeverity.RECOVERABLE,\n                category=ErrorCategory.PROTOCOL\n            )\n            return None
    
    def _receive_multi_frame(self, first_frame_data: bytes, timeout: int) -> Optional[bytes]:
        """Прием многокадрового сообщения"""
        # Разбор First Frame
        ff_len_high = first_frame_data[0] & 0x0F
        ff_len_low = first_frame_data[1]
        total_length = (ff_len_high << 8) | ff_len_low
        
        logger.debug(f"ISO-TP First Frame: общая длина={total_length} байт")
        
        # Первые 6 байт данных
        payload = bytearray(first_frame_data[2:8])
        
        # Отправка Flow Control
        fc_data = bytes([FLOW_CONTROL << 4 | FC_CONTINUE, self.bs, self.stmin])
        # Дополнение до 8 байт
        fc_data += bytes([0x00] * (8 - len(fc_data)))
        
        logger.debug(f"ISO-TP отправка Flow Control: {fc_data.hex().upper()}")
        if not self.j2534.write_message(self.request_id, fc_data):
            logger.error("Ошибка отправки Flow Control")
            return None
        
        # Прием Consecutive Frames
        expected_seq = 1
        start_time = time.time()
        
        while len(payload) < total_length:
            if (time.time() - start_time) > (timeout / 1000.0):
                logger.error("Timeout при приеме Consecutive Frames")
                return None
            
            messages = self.j2534.get_queued_messages(self.response_id)
            
            for can_id, data in messages:
                if len(data) < 1:
                    continue
                
                frame_type = (data[0] >> 4) & 0x0F
                
                if frame_type == CONSECUTIVE_FRAME:
                    seq_num = data[0] & 0x0F
                    
                    if seq_num != expected_seq:
                        logger.warning(f"Неправильная последовательность CF: ожидалось {expected_seq}, получено {seq_num}")
                    
                    # Добавление данных (максимум 7 байт)
                    remaining = total_length - len(payload)
                    chunk_len = min(7, remaining)
                    payload.extend(data[1:1+chunk_len])
                    
                    expected_seq = (expected_seq + 1) % 16
                    logger.debug(f"ISO-TP Consecutive Frame #{seq_num}: +{chunk_len} байт, всего {len(payload)}/{total_length}")
                    
                    if len(payload) >= total_length:
                        logger.info(f"ISO-TP Multi-frame принят: {total_length} байт")
                        return bytes(payload[:total_length])
            
            time.sleep(0.01)
        
        return bytes(payload[:total_length])

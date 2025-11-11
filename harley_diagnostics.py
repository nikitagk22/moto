"""Harley-Davidson XG750A диагностика через HDLAN/UDS"""
import logging
import time
from typing import Optional, Dict, Any, List

import config
from j2534_wrapper import J2534Wrapper
from isotp_handler import ISOTPHandler
from uds_client import UDSClient, EXTENDED_DIAGNOSTIC_SESSION
from error_handler import global_error_handler, ErrorSeverity, ErrorCategory, DiagnosticError
from diagnostic_report import global_diagnostic_reporter

logger = logging.getLogger(__name__)


class HarleyDiagnostics:
    """Основной класс для диагностики Harley-Davidson"""
    
    def __init__(self, auto_detect_can_ids: bool = False):
        self.j2534 = None
        self.isotp = None
        self.uds = None
        self.connected = False
        self.auto_detect_can_ids = auto_detect_can_ids
        self.working_can_ids = None  # (request_id, response_id)
        
        logger.info("Инициализация Harley Diagnostics")
    
    def connect(self) -> bool:
        """Подключение к мотоциклу"""
        try:
            logger.info("="*60)
            logger.info("Начало подключения к Harley-Davidson XG750A")
            logger.info("="*60)
            
            # Инициализация J2534
            self.j2534 = J2534Wrapper()
            self.j2534.open_device()
            self.j2534.connect_channel()
            
            # Автоматический поиск рабочих CAN ID если включен
            if self.auto_detect_can_ids:
                logger.info("Автоматический поиск рабочих CAN ID...")
                can_ids = self._find_working_can_ids()
                if can_ids:
                    request_id, response_id = can_ids
                    logger.info(f"✅ Найдены рабочие CAN ID: Request=0x{request_id:03X}, Response=0x{response_id:03X}")
                    self.working_can_ids = can_ids
                else:
                    logger.warning("⚠️ Не удалось найти рабочие CAN ID, используем стандартные")
                    request_id = config.UDS_REQUEST_ID
                    response_id = config.UDS_RESPONSE_ID
            else:
                request_id = config.UDS_REQUEST_ID
                response_id = config.UDS_RESPONSE_ID
            
            # Установка фильтра для ISO-TP
            self.j2534.set_flow_control_filter(request_id, response_id)
            
            # Запуск фонового чтения
            self.j2534.start_reading()
            
            # Очистка буферов
            time.sleep(0.2)
            self.j2534.clear_buffers()
            
            # Инициализация ISO-TP и UDS
            self.isotp = ISOTPHandler(self.j2534, request_id, response_id)
            self.uds = UDSClient(self.isotp)
            
            # Переключение в расширенную диагностическую сессию
            logger.info("Переключение в Extended Diagnostic Session...")
            if not self.uds.diagnostic_session_control(EXTENDED_DIAGNOSTIC_SESSION):
                logger.warning("Не удалось переключиться в расширенную сессию, продолжаем в стандартной")
            
            # Запуск TesterPresent
            self.uds.start_tester_present()
            
            self.connected = True
            logger.info("✅ Подключение успешно!")
            
            # Вывод используемых CAN ID
            logger.info(f"Используемые CAN ID: Request=0x{request_id:03X}, Response=0x{response_id:03X}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка подключения: {e}")
            self.disconnect()
            return False
    
    def _find_working_can_ids(self) -> Optional[tuple]:
        """Автоматический поиск рабочих CAN ID"""
        logger.info("Проверка CAN ID пар...")
        
        for request_id, response_id in config.ALTERNATIVE_CAN_IDS:
            logger.info(f"Пробуем: Request=0x{request_id:03X}, Response=0x{response_id:03X}")
            
            try:
                # Временная установка фильтра
                self.j2534.set_flow_control_filter(request_id, response_id)
                time.sleep(0.1)
                
                # Запуск чтения
                if not self.j2534._read_thread or not self.j2534._read_thread.is_alive():
                    self.j2534.start_reading()
                
                time.sleep(0.2)
                self.j2534.clear_buffers()
                
                # Создание временных обработчиков
                temp_isotp = ISOTPHandler(self.j2534, request_id, response_id)
                temp_uds = UDSClient(temp_isotp)
                
                # Попытка прочитать VIN
                vin_data = temp_uds.read_data_by_identifier(config.DIDS['VIN'])
                
                if vin_data and len(vin_data) == 17:
                    logger.info(f"✅ Успех! Найдены рабочие CAN ID")
                    return (request_id, response_id)
                
            except Exception as e:
                logger.debug(f"Не подошло: {e}")
                continue
        
        return None
    
    def disconnect(self):
        """Отключение от мотоцикла"""
        logger.info("Отключение...")
        
        try:
            if self.uds:
                self.uds.stop_tester_present()
            
            if self.j2534:
                self.j2534.disconnect_channel()
                self.j2534.close_device()
            
            self.connected = False
            logger.info("✅ Отключение успешно")
            
        except Exception as e:
            logger.error(f"Ошибка при отключении: {e}")
    
    def read_vin(self) -> Optional[str]:
        """Чтение VIN (идентификационного номера транспортного средства)"""
        if not self.connected:
            logger.error("Не подключено к мотоциклу")
            return None
        
        logger.info("-" * 60)
        logger.info("🔍 Чтение VIN...")
        
        try:
            data = self.uds.read_data_by_identifier(config.DIDS['VIN'])
            
            if data and len(data) == 17:
                vin = data.decode('ascii', errors='ignore')
                # Проверка формата VIN (не должен содержать I, O, Q)
                if all(c not in 'IOQ' for c in vin.upper()):
                    logger.info(f"✅ VIN: {vin}")
                    return vin
                else:
                    logger.warning(f"⚠️ VIN содержит недопустимые символы: {vin}")
                    return vin
            else:
                logger.error(f"❌ Некорректная длина VIN: {len(data) if data else 0} байт")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка чтения VIN: {e}")
            return None
    
    def scan_for_odometer(self, start_did: int = 0xF191, end_did: int = 0xF1A0) -> Optional[Dict[str, Any]]:
        """
        Сканирование DIDs для поиска одометра (пробега)
        Возвращает словарь с найденными DID и их данными
        """
        if not self.connected:
            logger.error("Не подключено к мотоциклу")
            return None
        
        logger.info("-" * 60)
        logger.info(f"🔍 Сканирование DIDs 0x{start_did:04X} - 0x{end_did:04X} для поиска одометра...")
        
        results = {}
        
        for did in range(start_did, end_did + 1):
            try:
                data = self.uds.read_data_by_identifier(did)
                
                if data:
                    # Анализ данных
                    results[did] = {
                        'raw_data': data.hex().upper(),
                        'length': len(data),
                        'possible_values': self._analyze_odometer_data(data)
                    }
                    
                    logger.info(f"✅ DID 0x{did:04X}: {data.hex().upper()} ({len(data)} байт)")
                    
                    # Анализ возможных значений
                    for interpretation in results[did]['possible_values']:
                        logger.info(f"   ➡️ {interpretation}")
                
                # Небольшая задержка между запросами
                time.sleep(0.1)
                
            except Exception as e:
                logger.debug(f"DID 0x{did:04X}: недоступен")
        
        if results:
            logger.info(f"\n✅ Найдено {len(results)} доступных DIDs")
            return results
        else:
            logger.warning("⚠️ Не найдено доступных DIDs в указанном диапазоне")
            return None
    
    def _analyze_odometer_data(self, data: bytes) -> List[str]:
        """Анализ данных для определения возможных значений пробега"""
        interpretations = []
        
        # Проб разных интерпретаций
        
        # 1. 2-байтовое значение (Big Endian)
        if len(data) >= 2:
            value_2b = int.from_bytes(data[:2], byteorder='big')
            interpretations.append(f"2-byte (BE): {value_2b} (может быть {value_2b/10:.1f} km с коэф. 0.1)")
        
        # 2. 3-байтовое значение
        if len(data) >= 3:
            value_3b = int.from_bytes(data[:3], byteorder='big')
            interpretations.append(f"3-byte (BE): {value_3b} km (или {value_3b/10:.1f} km с коэф. 0.1)")
            interpretations.append(f"3-byte (BE): {value_3b * 0.621371:.1f} miles (если в милях)")
        
        # 3. 4-байтовое значение
        if len(data) >= 4:
            value_4b = int.from_bytes(data[:4], byteorder='big')
            interpretations.append(f"4-byte (BE): {value_4b} (может быть {value_4b/10:.1f} km с коэф. 0.1)")
            interpretations.append(f"4-byte (BE): {value_4b/100:.2f} km с коэф. 0.01")
        
        # 4. Попытка декодировать как ASCII (если текстовые данные)
        try:
            ascii_str = data.decode('ascii')
            if ascii_str.isprintable():
                interpretations.append(f"ASCII: '{ascii_str}'")
        except:
            pass
        
        return interpretations
    
    def read_odometer(self, did: int) -> Optional[Dict[str, Any]]:
        """Чтение конкретного DID одометра"""
        if not self.connected:
            logger.error("Не подключено к мотоциклу")
            return None
        
        logger.info("-" * 60)
        logger.info(f"🔍 Чтение одометра (DID 0x{did:04X})...")
        
        try:
            data = self.uds.read_data_by_identifier(did)
            
            if data:
                result = {
                    'did': did,
                    'raw_data': data.hex().upper(),
                    'length': len(data),
                    'interpretations': self._analyze_odometer_data(data)
                }
                
                logger.info(f"✅ Одометр DID 0x{did:04X}:")
                logger.info(f"   Raw: {result['raw_data']}")
                
                for interpretation in result['interpretations']:
                    logger.info(f"   ➡️ {interpretation}")
                
                return result
            else:
                logger.error("❌ Не удалось прочитать одометр")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка чтения одометра: {e}")
            return None
    
    def read_ecu_info(self) -> Dict[str, Any]:
        """Чтение информации о ЭБУ"""
        if not self.connected:
            logger.error("Не подключено к мотоциклу")
            return {}
        
        logger.info("-" * 60)
        logger.info("🔍 Чтение информации о ЭБУ...")
        
        info = {}
        
        # Список стандартных DIDs
        standard_dids = {
            0xF18C: 'ECU Serial Number',
            0xF190: 'VIN',
            0xF191: 'Hardware Number',
            0xF192: 'Software Number',
            0xF194: 'Supplier ID',
            0xF195: 'Date of Manufacture',
            0xF197: 'System Name',
            0xF19E: 'Active Diagnostic Session'
        }
        
        for did, name in standard_dids.items():
            try:
                data = self.uds.read_data_by_identifier(did)
                if data:
                    # Попытка декодировать как ASCII
                    try:
                        decoded = data.decode('ascii', errors='ignore')
                        if decoded.isprintable():
                            info[name] = decoded
                        else:
                            info[name] = data.hex().upper()
                    except:
                        info[name] = data.hex().upper()
                    
                    logger.info(f"✅ {name}: {info[name]}")
                    
                time.sleep(0.1)
            except Exception as e:
                logger.debug(f"{name}: недоступен")
        
        return info
    
    def __enter__(self):
        """Контекстный менеджер: вход"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер: выход"""
        self.disconnect()
    
    def save_discovered_params(self, odometer_did: int, scale_factor: float, unit: str = 'km'):
        """Сохранение найденных параметров в файл"""
        params_file = 'discovered_params.txt'
        
        try:
            with open(params_file, 'w', encoding='utf-8') as f:
                f.write("# Найденные параметры для Harley-Davidson\n")
                f.write("# Скопируйте эти значения в config.py\n\n")
                
                if self.working_can_ids:
                    req_id, resp_id = self.working_can_ids
                    f.write(f"UDS_REQUEST_ID = 0x{req_id:03X}\n")
                    f.write(f"UDS_RESPONSE_ID = 0x{resp_id:03X}\n\n")
                
                f.write(f"ODOMETER_DID = 0x{odometer_did:04X}\n")
                f.write(f"ODOMETER_SCALE_FACTOR = {scale_factor}\n")
                f.write(f"ODOMETER_UNIT = '{unit}'\n")
            
            logger.info(f"✅ Параметры сохранены в {params_file}")
            print(f"\n✅ Найденные параметры сохранены в {params_file}")
            print("📝 Скопируйте их в config.py для дальнейшего использования")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения параметров: {e}")

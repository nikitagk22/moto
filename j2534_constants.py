"""Константы и структуры J2534 API"""
import ctypes

# J2534 Protocol IDs
J1850VPW = 1
J1850PWM = 2
ISO9141 = 3
ISO14230 = 4
CAN = 5
ISO15765 = 6
SCI_A_ENGINE = 7
SCI_A_TRANS = 8
SCI_B_ENGINE = 9
SCI_B_TRANS = 10

# J2534 Return codes
STATUS_NOERROR = 0x00
ERR_NOT_SUPPORTED = 0x01
ERR_INVALID_CHANNEL_ID = 0x02
ERR_INVALID_PROTOCOL_ID = 0x03
ERR_NULL_PARAMETER = 0x04
ERR_INVALID_IOCTL_VALUE = 0x05
ERR_INVALID_FLAGS = 0x06
ERR_FAILED = 0x07
ERR_DEVICE_NOT_CONNECTED = 0x08
ERR_TIMEOUT = 0x09
ERR_INVALID_MSG = 0x0A
ERR_INVALID_TIME_INTERVAL = 0x0B
ERR_EXCEEDED_LIMIT = 0x0C
ERR_INVALID_MSG_ID = 0x0D
ERR_DEVICE_IN_USE = 0x0E
ERR_INVALID_IOCTL_ID = 0x0F
ERR_BUFFER_EMPTY = 0x10
ERR_BUFFER_FULL = 0x11
ERR_BUFFER_OVERFLOW = 0x12
ERR_PIN_INVALID = 0x13
ERR_CHANNEL_IN_USE = 0x14
ERR_MSG_PROTOCOL_ID = 0x15
ERR_INVALID_FILTER_ID = 0x16
ERR_NO_FLOW_CONTROL = 0x17
ERR_NOT_UNIQUE = 0x18
ERR_INVALID_BAUDRATE = 0x19
ERR_INVALID_DEVICE_ID = 0x1A

# J2534 Error messages
J2534_ERRORS = {
    ERR_NOT_SUPPORTED: "Function not supported",
    ERR_INVALID_CHANNEL_ID: "Invalid channel ID",
    ERR_INVALID_PROTOCOL_ID: "Invalid protocol ID",
    ERR_NULL_PARAMETER: "NULL parameter",
    ERR_INVALID_IOCTL_VALUE: "Invalid IOCTL value",
    ERR_INVALID_FLAGS: "Invalid flags",
    ERR_FAILED: "General failure",
    ERR_DEVICE_NOT_CONNECTED: "Device not connected",
    ERR_TIMEOUT: "Timeout",
    ERR_INVALID_MSG: "Invalid message",
    ERR_INVALID_TIME_INTERVAL: "Invalid time interval",
    ERR_EXCEEDED_LIMIT: "Exceeded limit",
    ERR_INVALID_MSG_ID: "Invalid message ID",
    ERR_DEVICE_IN_USE: "Device in use",
    ERR_INVALID_IOCTL_ID: "Invalid IOCTL ID",
    ERR_BUFFER_EMPTY: "Buffer empty",
    ERR_BUFFER_FULL: "Buffer full",
    ERR_BUFFER_OVERFLOW: "Buffer overflow",
    ERR_PIN_INVALID: "Pin invalid",
    ERR_CHANNEL_IN_USE: "Channel in use",
    ERR_MSG_PROTOCOL_ID: "Message protocol ID mismatch",
    ERR_INVALID_FILTER_ID: "Invalid filter ID",
    ERR_NO_FLOW_CONTROL: "No flow control",
    ERR_NOT_UNIQUE: "Not unique",
    ERR_INVALID_BAUDRATE: "Invalid baudrate",
    ERR_INVALID_DEVICE_ID: "Invalid device ID"
}

# J2534 Flags
ISO15765_FRAME_PAD = 0x00000040
CAN_29BIT_ID = 0x00000100

# Filter types
PASS_FILTER = 0x00000001
BLOCK_FILTER = 0x00000002
FLOW_CONTROL_FILTER = 0x00000003

# IOCTL IDs
GET_CONFIG = 0x01
SET_CONFIG = 0x02
READ_VBATT = 0x03
FIVE_BAUD_INIT = 0x04
FAST_INIT = 0x05
CLEAR_TX_BUFFER = 0x07
CLEAR_RX_BUFFER = 0x08
CLEAR_PERIODIC_MSGS = 0x09
CLEAR_MSG_FILTERS = 0x0A
CLEAR_FUNCT_MSG_LOOKUP_TABLE = 0x0B
ADD_TO_FUNCT_MSG_LOOKUP_TABLE = 0x0C
DELETE_FROM_FUNCT_MSG_LOOKUP_TABLE = 0x0D
READ_PROG_VOLTAGE = 0x0E

# Max data size
MAX_DATA_SIZE = 4128


class PASSTHRU_MSG(ctypes.Structure):
    """Структура сообщения J2534"""
    _fields_ = [
        ("ProtocolID", ctypes.c_ulong),
        ("RxStatus", ctypes.c_ulong),
        ("TxFlags", ctypes.c_ulong),
        ("Timestamp", ctypes.c_ulong),
        ("DataSize", ctypes.c_ulong),
        ("ExtraDataIndex", ctypes.c_ulong),
        ("Data", ctypes.c_ubyte * MAX_DATA_SIZE)
    ]


class SCONFIG(ctypes.Structure):
    """Структура конфигурации J2534"""
    _fields_ = [
        ("Parameter", ctypes.c_ulong),
        ("Value", ctypes.c_ulong)
    ]


class SCONFIG_LIST(ctypes.Structure):
    """Список конфигураций J2534"""
    _fields_ = [
        ("NumOfParams", ctypes.c_ulong),
        ("ConfigPtr", ctypes.POINTER(SCONFIG))
    ]


class SBYTE_ARRAY(ctypes.Structure):
    """Массив байтов для J2534"""
    _fields_ = [
        ("NumOfBytes", ctypes.c_ulong),
        ("BytePtr", ctypes.POINTER(ctypes.c_ubyte))
    ]

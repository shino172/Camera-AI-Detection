import ctypes
from ctypes import *

# Define device info struct for Hikvision NVR
class NET_DVR_DEVICEINFO_V30(Structure):
    _fields_ = [
        ("sSerialNumber", c_ubyte * 48),
        ("byAlarmInPortNum", c_ubyte),
        ("byAlarmOutPortNum", c_ubyte),
        ("byDiskNum", c_ubyte),
        ("byDVRType", c_ubyte),
        ("byChanNum", c_ubyte),
        ("byStartChan", c_ubyte),
        ("byAudioChanNum", c_ubyte),
        ("byIPChanNum", c_ubyte),
    ]

def login_nvr(ip, port, username, password):
    """Login to Hikvision NVR"""
    try:
        HCNetSDK = ctypes.WinDLL(r"C:\Users\PC\Downloads\EN-HCNetSDKV6.1.9.48_build20230410_win64\EN-HCNetSDKV6.1.9.48_build20230410_win64\lib\HCNetSDK.dll")
        HCNetSDK.NET_DVR_Init()
        
        device_infor = NET_DVR_DEVICEINFO_V30()
        user_id = HCNetSDK.NET_DVR_Login_V30(
            ip.encode('utf-8'), 
            port, 
            username.encode('utf-8'), 
            password.encode('utf-8'), 
            byref(device_infor)
        )
        if user_id < 0:
            err = HCNetSDK.NET_DVR_GetLastError()
            raise Exception(f"Login NVR failed, error code: {err}")
        return user_id
    except Exception as e:
        print(f"[NVR LOGIN ERROR] {e}")
        return None
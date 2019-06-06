# coding:utf-8

from functools import wraps

from Crypto.Cipher import AES


class CustomException(Exception):
    def __init__(self, msg=None, code=None):
        super(BaseException, self).__init__()
        self.msg = msg
        self.code = code

    def __str__(self):
        return u"code:{0}, msg:{1}".format(self.msg, self.code)


class NeedCaptchaError(CustomException):
    def __init__(self, msg=None, code=None):
        super(NeedCaptchaError, self).__init__()
        self.msg = msg or u"需要图片验证码"
        self.code = code or 10001


class CaptchaError(CustomException):
    def __init__(self, msg=None, code=None):
        super(CaptchaError, self).__init__()
        self.msg = msg or u"图片验证码错误"
        self.code = code or 10002


def aes_decrypt(raw_str, key, iv, mode=None):
    try:
        if isinstance(raw_str, unicode):
            raw_str = raw_str.decode("hex")
        if isinstance(key, unicode):
            key = key.encode("utf-8")
        mode = mode or AES.MODE_CBC
        cipher = AES.new(key=key, IV=iv, mode=mode)
        msg = cipher.decrypt(raw_str)
        padding_len = 0 if len(msg) % len(key) == 0 else ord(msg[-1])
        ret = msg[:-padding_len].decode("utf-8")
        return ret
    except Exception as e:
        raise e


def catch_exception(func):
    @wraps(func)
    def _handle(self, response):
        logger = self.logger
        logger.debug("--->func:{0}, status:{1}, url:{2}".format(func.__name__, response.status, response.url))
        try:
            ret = func(self, response)
            return ret
        except Exception as e:
            logger.exception("--->func:{0}, error:{1}".format(func.__name__, str(e)))
            return

    return _handle

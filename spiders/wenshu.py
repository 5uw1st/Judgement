# coding:utf-8

import json
import os
import random
from base64 import b64decode
from re import compile as re_compile, findall as re_findall

import execjs
from scrapy.http import Request, FormRequest

from judgement import JS_PATH
from judgement.items import WenshuItem
from judgement.spiders.base import BaseSpider
from judgement.spiders.utils import aes_decrypt, catch_exception

CORE_JS_FILE = os.path.join(JS_PATH, "wenshu_core.js")
INFLATE_JS_FILE = os.path.join(JS_PATH, "wenshu_inflate.js")


def get_js_code(filename):
    with open(filename, "r") as f:
        js_str = f.read()
    return js_str


core_code = get_js_code(filename=CORE_JS_FILE)
core_ctx = execjs.compile(core_code)

inflate_code = get_js_code(filename=INFLATE_JS_FILE)
inflate_ctx = execjs.compile(inflate_code)


class WenshuSpider(BaseSpider):
    name = "wenshu"

    reg_target = re_compile(r"_\[_\]\[_\]\(([\s\S]+)\)\(\)")
    reg_key = re_compile(r'com\.str\._KEY="([^"]+)";')
    reg_case_info = re_compile(r'stringify\((\{[\s\S]+?\})\)')
    reg_relate_info = re_compile(r'RelateInfo: (\[[\s\S]+?\]),')
    reg_html = re_compile(r'jsonHtmlData = "(\{[\s\S]+?\})"')
    KEY_STR = "key_str"

    CASE_TYPE = {
        "1": u"刑事案件",
        "2": u"民事案件",
        "3": u"行政案件",
        "4": u"赔偿案件",
        "5": u"执行案件"
    }

    KEY_DICT = {
        u"审判程序": "caseTrialLevel",
        u"文书ID": "docId",
        u"案件名称": "caseName",
        u"案件类型": "caseType",
        u"案号": "caseNumber",
        u"法院名称": "courtName",
        u"裁判日期": "judgeDate",
        u"裁判要旨段原文": "judgeNote"
    }

    get_code_url = "http://wenshu.court.gov.cn/ValiCode/GetCode"
    get_vjkl5_url = "http://wenshu.court.gov.cn/list/list/?"
    get_list_url = "http://wenshu.court.gov.cn/List/ListContent"
    get_detail_url = "http://wenshu.court.gov.cn/CreateContentJS/CreateContentJS.aspx?DocID={doc_id}"
    get_case_url = "http://wenshu.court.gov.cn/content/content?DocID={doc_id}&KeyWord="
    get_captcha_url = "http://wenshu.court.gov.cn/User/ValidateCode"
    get_waf_captcha_url = "http://wenshu.court.gov.cn/waf_captcha/?{rnd}".format(rnd=random.random)

    def __init__(self):
        super(WenshuSpider, self).__init__()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:61.0) Gecko/20100101 Firefox/61.0",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
        }
        self._iv = "abcd134556abcedf"
        self.page_size = 10  # 目前网站每页最大值为5(2018-08-31)
        self.total_page = 5  # 单个条件最多返回5×5条数据

    @staticmethod
    def get_guid():
        """
        生成guid
        :return:
        """
        def __get_guid():
            return hex(int((1 + random.random()) * 0x10000) | 0)[3:]

        def _get_guid(num):
            return "".join([__get_guid() for _ in range(num)])

        return "-".join([_get_guid(n) for n in (2, 1, 2, 3)])

    def make_request(self, data):
        """
        生成初始请求
        :param data: dict --> task data
        :return:
        """
        return FormRequest(
            url=self.get_code_url,
            headers=self.headers,
            formdata={"guid": self.get_guid()},
            meta={"task": data, "params": {}},
            callback=self.parse_code
        )

    @catch_exception
    def parse_code(self, response):
        """
        解析获取code参数
        :param response:
        :return:
        """
        code = response.text
        meta = response.meta
        meta["params"]["code"] = code

        params = {
            "sorttype": 1,
            "number": "",
            "guid": self.get_guid()
        }
        req_url = self.get_vjkl5_url + "&".join(["{0}={1}".format(k, v) for k, v in params.items()])
        yield Request(
            url=req_url,
            headers=self.headers,
            meta=meta,
            callback=self.parse_vjkl5,
            dont_filter=True
        )

    @catch_exception
    def parse_vjkl5(self, response):
        """
        解析获取vjkl5参数
        :param response:
        :return:
        """
        vjkl5 = self._get_cookie(response, "vjkl5")
        meta = response.meta
        task = meta["task"]
        vl5x = self.get_vl5x(vk=vjkl5)
        self.logger.debug("===>vjkl5:{0}, vl5x:{1}".format(vjkl5, vl5x))
        meta["params"]["vl5x"] = vl5x
        form_data = {
            "Param": task.get("condition"),
            "Index": str(task.get("page")),
            "Page": str(task.get("size")),
            "Order": task.get("order"),
            "Direction": task.get("turn"),
            "vl5x": vl5x,
            "number": meta["params"]["code"],
            "guid": self.get_guid()
        }
        headers = self.headers.copy()
        headers.update({
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Host": "wenshu.court.gov.cn",
            "Origin": "http://wenshu.court.gov.cn",
        })
        meta["headers"] = headers

        yield FormRequest(
            url=self.get_list_url,
            formdata=form_data,
            headers=headers,
            meta=meta,
            callback=self.parse_list_data,
            dont_filter=True
        )

    @catch_exception
    def parse_list_data(self, response):
        """
        解析案件列表页数据
        :param response:
        :return:
        """
        meta = response.meta
        text = response.text
        if u"remind key" in text:
            self.logger.warning(">>>>This vl5x value is wrong or expire, need retry.")
            params = {
                "sorttype": 1,
                "number": "",
                "guid": self.get_guid()
            }
            req_url = self.get_vjkl5_url + "&".join(["{0}={1}".format(k, v) for k, v in params.items()])
            yield Request(
                url=req_url,
                headers=self.headers,
                meta=meta,
                callback=self.parse_vjkl5,
                dont_filter=True
            )
            return
        resp_data = json.loads(text[1:-1].replace('\\"', '"'))
        if len(resp_data) == 0:
            self.logger.warning(">>>There is no data, maybe this site something is wrong.")
            return
        eval_param = resp_data.pop(0)
        aes_key = self.get_aes_key(self.unzip(eval_param.get("RunEval", "")))
        case_count = eval_param.get("Count")
        meta["params"]["aes_key"] = aes_key

        total_pages = int(case_count) // min(meta["task"]["size"], len(resp_data)) + 1
        current_page = meta["task"]["page"]
        self.logger.debug(
            "===>key:{0}, count:{1}, page:{2}, total_page:{3}".format(aes_key, case_count, current_page, total_pages))
        meta["task"]["total_pages"] = total_pages
        for case in resp_data:
            case_data = self._turn_case_data(case, aes_key=aes_key)
            doc_id = case_data.get("docId")
            self.logger.debug(
                u"===>Start fetch case, docId: {0}, caseNo: {1}".format(doc_id, case_data.get("caseNumber")))
            meta["case_data"] = case_data
            yield Request(
                url=self.get_detail_url.format(doc_id=doc_id),
                headers=self.headers,
                meta=meta,
                callback=self.parse_detail_data,
                dont_filter=True
            )

        # 翻页
        task = meta["task"]
        if current_page < min(total_pages, self.total_page):
            page = current_page + 1
            meta["task"]["page"] = page
            form_data = {
                "Param": task.get("condition"),
                "Index": str(page),
                "Page": str(task.get("size")),
                "Order": task.get("order"),
                "Direction": task.get("turn"),
                "vl5x": meta["params"]["vl5x"],
                "number": meta["params"]["code"],
                "guid": self.get_guid()
            }
            yield FormRequest(
                url=self.get_list_url,
                formdata=form_data,
                headers=meta["headers"],
                meta=meta,
                callback=self.parse_list_data,
                dont_filter=True
            )

    @catch_exception
    def parse_detail_data(self, response):
        """
        解析案件详情数据
        :param response:
        :return:
        """
        text = response.text
        meta = response.meta
        case_detail_info = self.__parse_data(self.reg_case_info, text)
        case_relate_info_list = self.__parse_data(self.reg_relate_info, text, js_eval=True)
        case_relate_info = {i["key"]: i["value"] for i in case_relate_info_list}
        case_html_info = self.__parse_data(self.reg_html, text, rep=True)
        self.logger.debug("===>Case info:{0}, relate_info:{1}".format(case_detail_info, case_relate_info))
        item = WenshuItem()
        case_data = meta.get("case_data")
        item["caseUrl"] = self.get_case_url.format(doc_id=meta["case_data"]["docId"])
        item["appellor"] = case_relate_info.get("appellor")
        item["caseReason"] = case_relate_info.get("reason")
        item["pubDate"] = case_html_info.get("PubDate")
        item["judgeContent"] = self.get_text(case_html_info.get("Html"))
        item["searchKey"] = meta["task"]["condition"]
        item.update(case_data)
        yield item

    def __parse_data(self, reg, text, js_eval=False, rep=False):
        """
        解析正则数据
        :param reg: re compile object
        :param text: unicode
        :param js_eval: bool
        :param rep: bool
        :return: dict
        """
        try:
            data_str = reg.search(text).group(1)
            if js_eval:
                ret = execjs.eval(data_str)
            else:
                ret = json.loads(data_str.replace('\\"', '"') if rep else data_str)
            if ret is None:
                self.logger.warning(">>>>parse data warning: result is None")
            return ret
        except Exception as e:
            self.logger.exception(">>>parse data failed, reg:{0}, error:{1}".format(reg, str(e)))
            return

    def get_aes_key(self, str_data):
        """
        执行JS获取AES秘钥
        :param str_data:
        :return:
        """
        clean_str = str_data
        scripts = clean_str.split(";")
        scripts = [i for i in scripts if i]
        target_str = self.reg_target.search(scripts[-1]).group(1)
        scripts[-1] = "{1}={0}".format(target_str, self.KEY_STR)
        source = ";".join(scripts)
        ret = execjs.compile(source)
        key_str = ret.eval(self.KEY_STR)
        key = self.reg_key.search(key_str).group(1)
        return key

    def _turn_case_data(self, data, aes_key):
        """
        转换案件数据
        :param data:
        :param aes_key:
        :return:
        """
        case_data = {}
        for k, v in data.items():
            nk = self.KEY_DICT.get(k)
            if nk is None:
                continue
            if nk == "docId":
                raw_data = self.unzip(v)
                self.logger.debug("===>key:{1}, raw:{0}".format(raw_data, aes_key))
                v = self.decrypt(raw_data, key=aes_key)
            if nk == "caseType":
                v = self.CASE_TYPE.get(v)
            case_data[nk] = v
        return case_data

    @staticmethod
    def get_vl5x(vk):
        """
        通过执行JS生成key
        :param vk:
        :return:
        """
        res = core_ctx.call("getKey", vk)
        return res

    @staticmethod
    def unzip(b64_data):
        """
        通过JS解压数据
        :param b64_data:
        :return:
        """
        ziped_bytes = b64decode(b64_data)
        res = inflate_ctx.call("zip_inflate", ziped_bytes.decode("utf-8"))
        return res

    def unpack_task(self, task):
        """
        封装任务参数
        :param task:
        :return:
        """
        def_task = {
            "page": task.get("page", 1),
            "size": min(task.get("size", self.page_size), self.page_size),
            "order": task.get("order", u"法院层级"),
            "turn": task.get("turn", "asc"),
            "condition": task.get("condition", ""),
            "total_page": min(self.total_page, task.get("total_page"))
        }
        self.logger.debug("====> Task: {0}".format(def_task))
        return def_task

    @staticmethod
    def _get_cookie(resp, key):
        """
        获取response中指定的cookie
        :param resp:
        :param key: cookie key
        :return:
        """
        cookies = resp.headers.getlist("Set-Cookie")
        cookies_dict = {}
        for cookie in cookies:
            c = cookie.split(";", 1)[0].split("=")
            cookies_dict[c[0]] = c[1]
        return cookies_dict.get(key)

    def decrypt(self, data, key):
        """
        解密docId，需要解密两次
        :param data: data为hex数据，需要先decode
        :param key:
        :return:
        """
        try:
            new_str = aes_decrypt(data, key=key, iv=self._iv)
            msg = aes_decrypt(new_str, key=key, iv=self._iv)
            return msg
        except Exception as e:
            self.logger.exception("===>decrypt failed: {0}".format(str(e)))

    def get_text(self, text):
        """
        富文本转纯文本
        :param text:
        :return:
        """
        if not isinstance(text, basestring):
            self.logger.debug("===>This text is not basestring,text:{0}".format(text))
            return ""
        text_all = '>' + text + '<'
        pattern = '>([\s\S]*?)<'
        info = re_findall(pattern, text_all)
        infos = ''.join(info)
        return infos.strip()

    def handle_captcha(self, response):
        """
        处理图片验证码
        :param response:
        :return:
        """
        pass

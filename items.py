# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://doc.scrapy.org/en/latest/topics/items.html

import scrapy


class WenshuItem(scrapy.Item):
    """
    裁判文书网字段定义
    """
    uid = scrapy.Field()  # 唯一ID(用于去重, md5(caseNumber_courtName))
    docId = scrapy.Field()  # 文书ID
    caseName = scrapy.Field()  # 案件名称
    courtName = scrapy.Field()  # 法院名称
    caseType = scrapy.Field()  # 案件类型
    caseTrialLevel = scrapy.Field()  # 审判程序
    caseNumber = scrapy.Field()  # 案件号
    caseReason = scrapy.Field()  # 案件缘由
    judgeNote = scrapy.Field()  # 裁判要旨
    judgeDate = scrapy.Field()  # 裁判日期
    appellor = scrapy.Field()  # 当事人
    caseUrl = scrapy.Field()  # 案件url
    searchKey = scrapy.Field()  # 查询条件
    pubDate = scrapy.Field()  # 公布日期
    judgeContent = scrapy.Field()  # 裁判内容

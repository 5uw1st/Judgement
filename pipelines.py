# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://doc.scrapy.org/en/latest/topics/item-pipeline.html

from hashlib import md5

import pymongo
from scrapy.exceptions import DropItem


class MongoDBPipeline(object):
    def __init__(self, mongo_uri, mongo_db):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            mongo_uri=crawler.settings.get('MONGO_URI'),
            mongo_db=crawler.settings.get('MONGO_DATABASE', 'items')
        )

    def open_spider(self, spider):
        spider.client = pymongo.MongoClient(self.mongo_uri)
        spider.db = spider.client[self.mongo_db]

    def close_spider(self, spider):
        spider.client.close()

    def process_item(self, item, spider):
        collection_name = item.__class__.__name__
        try:
            spider.db[collection_name].insert(dict(item))
            return item
        except pymongo.errors.DuplicateKeyError:
            raise DropItem('DuplicateKeyError, ignore')


class DuplicatePipeline(object):
    def process_item(self, item, spider):
        collection_name = item.__class__.__name__
        distinct_id = "uid"
        fields = ("caseNumber", "courtName")
        uid_val = self._get_uid(item, fields)
        item[distinct_id] = uid_val
        spider.logger.info("This item uid:{0}".format(uid_val))
        if not getattr(self, collection_name, None):
            setattr(self, collection_name, set(spider.db[collection_name].distinct(distinct_id)))
        if uid_val in getattr(self, collection_name):
            raise DropItem('this {0} | {1} has been crawled!'.format(collection_name, [item.get(i) for i in fields]))
        getattr(self, collection_name).add(uid_val)
        return item

    @staticmethod
    def _get_uid(item, fields):
        val = "_".join([item.get(i, "None") for i in fields])
        return md5(val.encode("utf-8")).hexdigest()

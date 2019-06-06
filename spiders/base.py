# coding:utf-8

from json import loads as json_loads

from scrapy_redis.spiders import RedisSpider


class BaseSpider(RedisSpider):
    name = "base"
    version = 1

    def __init__(self):
        super(BaseSpider, self).__init__()
        pass

    def make_request_from_data(self, data):
        self.logger.debug("=====> Receive raw data from redis: {0}".format(data))
        if isinstance(data, bytes):
            data = data.decode(self.redis_encoding)
        elif isinstance(data, str):
            data = data.decode("utf-8")
        try:
            task = json_loads(data)
        except:
            self.logger.debug("This data is not dict!")
            task = data
        self.logger.info("=====> Receive a task: {0}".format(task))
        task_data = self.unpack_task(task)
        return self.make_request(task_data)

    def make_request(self, data):
        raise NotImplementedError

    def unpack_task(self, task):
        self.logger.debug("===> start unpack task ...")
        return task

    def __str__(self):
        return "<key: %s | class: %s name: %r, version: %d at 0x%0x>" % (self.redis_key, type(self).__name__, self.name,
                                                                         self.version, id(self))

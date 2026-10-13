"""Bounded renderer resources and reusable rounded-corner geometry."""
import math
from collections import OrderedDict
from functools import lru_cache

class TextureCache:
    def __init__(self,create,destroy,limit=128):
        if limit<1:raise ValueError('Cache limit must be positive')
        self.create=create;self.destroy=destroy;self.limit=limit
        self.items=OrderedDict()
    def get(self,key):
        if key in self.items:
            self.items.move_to_end(key)
            return self.items[key]
        item=self.create(key)
        if item is None:return None
        self.items[key]=item
        if len(self.items)>self.limit:
            _,old=self.items.popitem(last=False);self.destroy(old)
        return item
    def close(self):
        while self.items:
            _,item=self.items.popitem(last=False);self.destroy(item)

@lru_cache(maxsize=16)
def corner_insets(radius):
    return tuple(radius-math.sqrt(max(0,radius*radius-(radius-dy-.5)**2)) for dy in range(radius))

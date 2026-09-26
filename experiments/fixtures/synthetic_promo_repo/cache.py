from store import store
class Cache:
    def __init__(self, s):
        self.s = s
    def load(self, uid):
        return self.s.query(uid)
    def stale(self):
        return None

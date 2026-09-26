from store import store
class UserRepo:
    def __init__(self, s):
        self.s = s
    def fetch(self, uid):
        return self.s.query(uid)

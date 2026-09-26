from db import session
class UserRepo:
    def __init__(self, s):
        self.s = s
    def fetch(self, uid):
        return self.s.query(uid)
    def dead_method(self):
        return 42
def orphan_helper():
    return session.close()

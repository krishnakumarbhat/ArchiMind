from store import store
class AuditRepo:
    def __init__(self, s):
        self.s = s
    def scan(self, uid):
        return self.s.query(uid)

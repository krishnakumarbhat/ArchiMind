import routes
class UserRepo:
    def __init__(self, s): self.s = s
    def fetch(self, uid): return self.s.query(uid)
    def dead_method(self): return 42

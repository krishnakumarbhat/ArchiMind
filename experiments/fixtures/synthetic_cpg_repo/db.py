class Session:
    def query(self, uid):
        return {'uid': uid}
    def close(self):
        return None
session = Session()

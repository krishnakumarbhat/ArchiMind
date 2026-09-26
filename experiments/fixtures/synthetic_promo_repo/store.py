class Store:
    def query(self, uid):
        return {'uid': uid}
    def close(self):
        return None
    def commit(self):
        return None
store = Store()

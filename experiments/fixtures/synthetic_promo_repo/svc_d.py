from store import store
from cache import Cache
def get_cached(uid):
    c = Cache(store)
    c.load(uid)
    return store.commit()

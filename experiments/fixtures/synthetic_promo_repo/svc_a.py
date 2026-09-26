from store import store
from users import UserRepo
def get_user(uid):
    return UserRepo(store).fetch(uid)

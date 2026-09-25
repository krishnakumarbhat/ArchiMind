from repo import UserRepo
from db import session
def get_user(uid):
    return UserRepo(session).fetch(uid)

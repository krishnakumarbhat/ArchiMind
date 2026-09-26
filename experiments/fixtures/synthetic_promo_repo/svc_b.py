from store import store
from audit import AuditRepo
def get_audit(uid):
    return AuditRepo(store).scan(uid)

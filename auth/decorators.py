from functools import wraps
from flask_login import current_user
from flask import abort, session

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):

        # Administrador normal
        if current_user.is_authenticated and current_user.is_admin:
            return f(*args, **kwargs)

        # Administrador viendo como cliente
        if "admin_original" in session:
            return f(*args, **kwargs)

        abort(403)

    return decorated

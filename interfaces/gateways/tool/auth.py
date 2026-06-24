from interfaces.api.auth import require_role_setting

require_gateway_role = require_role_setting("rbac_role_gateway")

__all__ = ["require_gateway_role"]
